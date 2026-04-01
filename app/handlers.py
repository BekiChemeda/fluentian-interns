"""
handlers.py
Advanced Telegram handlers for interns and admin workflows.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import config, db, utils

registration_state: Dict[int, Dict] = {}
REGISTER_DEADLINE = datetime(2026, 4, 3, 23, 59, 59, tzinfo=timezone.utc)


def get_active_roles(include_admin: bool = True) -> List[str]:
    roles = db.get_roles()
    if include_admin:
        return roles
    return [r for r in roles if r != "admin"]


def is_admin(telegram_id: int) -> bool:
    user = db.get_user(telegram_id)
    return bool(user and user.get("role") == "admin")


def role_label(role: str) -> str:
    return config.ROLE_DISPLAY.get(role, role.replace("_", " ").title())


def short_name(user: Dict) -> str:
    full = f"{user.get('first_name', '').strip()} {user.get('last_name', '').strip()}".strip()
    return full or user.get("email", "Unknown")


def navigation_markup(back: Optional[str] = None, home: bool = True, cancel: bool = True) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    row = []
    if back:
        row.append(InlineKeyboardButton("⬅️ Back", callback_data=back))
    if home:
        row.append(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    if row:
        markup.row(*row)
    if cancel:
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    return markup


def user_dashboard_markup(user: Dict) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📌 My Tasks", callback_data="my_tasks"))
    markup.add(InlineKeyboardButton("👤 My Profile", callback_data="profile"))
    markup.add(InlineKeyboardButton("🔔 Notification Settings", callback_data="notif_settings"))
    if user.get("role") == "admin":
        markup.add(InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel"))
    return markup


def tasks_menu_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🟦 Ongoing", callback_data="tasks_ongoing"))
    markup.add(InlineKeyboardButton("✅ Completed", callback_data="tasks_completed"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    return markup


def admin_panel_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Add Intern", callback_data="admin_add_intern"))
    markup.add(InlineKeyboardButton("📝 Assign Task", callback_data="admin_assign_task"))
    markup.add(InlineKeyboardButton("📥 Review Submissions", callback_data="admin_review_menu"))
    markup.add(InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast"))
    markup.add(InlineKeyboardButton("👥 Manage Users", callback_data="admin_manage_users"))
    markup.add(InlineKeyboardButton("🧩 Manage Roles", callback_data="admin_manage_roles"))
    markup.add(InlineKeyboardButton("♻️ Restore Users", callback_data="admin_restore_users"))
    markup.add(InlineKeyboardButton("📤 Export CSV", callback_data="admin_export_menu"))
    markup.add(InlineKeyboardButton("🎯 Score Visibility", callback_data="admin_score_visibility"))
    markup.add(InlineKeyboardButton("📢 Channel & Force Subscribe", callback_data="admin_force_sub_menu"))
    markup.add(InlineKeyboardButton("🏆 Leaderboard", callback_data="admin_leaderboard"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    return markup


def clear_state(user_id: int) -> None:
    registration_state.pop(user_id, None)


def maybe_force_subscribed(bot, telegram_id: int) -> Tuple[bool, str]:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    enabled = bool(cfg.get("enabled"))
    channel = (cfg.get("channel") or "").strip()
    if not enabled or not channel:
        return True, ""
    try:
        member = bot.get_chat_member(channel, telegram_id)
        if member.status in {"member", "administrator", "creator"}:
            return True, ""
    except Exception:
        return False, f"Please join {channel} and try again."
    return False, f"Please join {channel} and try again."


def show_dashboard(bot, telegram_id: int, chat_id: int) -> None:
    user = db.get_user(telegram_id)
    if not user:
        bot.send_message(chat_id, "Please use /start to register first.")
        return
    if user.get("is_banned"):
        bot.send_message(chat_id, "Your account is restricted. Contact admin.")
        return
    allowed, msg = maybe_force_subscribed(bot, telegram_id)
    if not allowed:
        bot.send_message(chat_id, msg)
        return

    score_visible = bool(db.get_global_setting("score_visibility", True))
    text = f"✅ Welcome, {short_name(user)}\nRole: {role_label(user.get('role', ''))}"
    if score_visible or user.get("role") == "admin":
        text += f"\nScore: {user.get('score', 0)}"
    bot.send_message(chat_id, text, reply_markup=user_dashboard_markup(user))


def notify_users(bot, user_ids: List[int], text: str) -> None:
    for uid in sorted(set(user_ids)):
        try:
            bot.send_message(uid, text)
        except Exception:
            continue


def notify_admins_of_submission(bot, user_id: int, task_id: str) -> None:
    user = db.get_user(user_id)
    task = db.get_task(task_id)
    if not user or not task:
        return
    admins = db.get_users_by_role("admin")
    text = f"📥 New submission from {short_name(user)} for '{task.get('title', '')}'."
    notify_users(bot, [u["telegram_id"] for u in admins], text)


# Registration

def handle_start(bot, message: Message) -> None:
    existing = db.get_user(message.from_user.id)
    if existing:
        show_dashboard(bot, message.from_user.id, message.chat.id)
        return
    markup = InlineKeyboardMarkup()
    if db.utcnow() <= REGISTER_DEADLINE:
        markup.add(InlineKeyboardButton("🟢 Register", callback_data="start_register"))
    markup.add(InlineKeyboardButton("📩 Contact Admin", callback_data="help_contact_admin"))
    bot.send_message(
        message.chat.id,
        "Welcome. Use /register (or button) to apply. Registration closes on April 3, 2026.",
        reply_markup=markup,
    )


def handle_register_start(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    if db.utcnow() > REGISTER_DEADLINE:
        bot.send_message(chat_id, "Registration is closed. Contact admin with /admin your message.")
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id)
        return
    if db.get_user(user_id):
        bot.send_message(chat_id, "You are already registered.")
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id)
        return
    registration_state[user_id] = {"step": "reg_first_name"}
    bot.send_message(chat_id, "Enter first name:", reply_markup=navigation_markup(home=True, cancel=True))
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def handle_register_first_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "reg_first_name":
        return
    first_name = message.text.strip()
    if not first_name:
        bot.send_message(message.chat.id, "First name cannot be empty.")
        return
    state["first_name"] = first_name
    state["step"] = "reg_last_name"
    bot.send_message(message.chat.id, "Enter last name:", reply_markup=navigation_markup(cancel=True))


def handle_register_last_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "reg_last_name":
        return
    last_name = message.text.strip()
    if not last_name:
        bot.send_message(message.chat.id, "Last name cannot be empty.")
        return
    state["last_name"] = last_name
    state["step"] = "reg_email"
    bot.send_message(message.chat.id, "Enter email:", reply_markup=navigation_markup(cancel=True))


def handle_register_email(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "reg_email":
        return
    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format.")
        return
    state["email"] = email
    state["step"] = "reg_role"
    markup = InlineKeyboardMarkup()
    for role in get_active_roles(include_admin=False):
        markup.add(InlineKeyboardButton(role_label(role), callback_data=f"reg_role|{role}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Select role:", reply_markup=markup)


def handle_register_role(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "reg_role":
        return
    _, role = call.data.split("|", 1)
    if role not in get_active_roles(include_admin=False):
        bot.answer_callback_query(call.id, "Role not available")
        return
    payload = {
        "telegram_id": call.from_user.id,
        "first_name": state.get("first_name"),
        "last_name": state.get("last_name"),
        "email": state.get("email"),
        "requested_role": role,
        "status": "PENDING",
    }
    reg_id = db.create_pending_registration(payload)
    clear_state(call.from_user.id)
    if not reg_id:
        bot.send_message(call.message.chat.id, "Failed to submit application. Try again.")
        bot.answer_callback_query(call.id)
        return

    bot.send_message(call.message.chat.id, "✅ Application submitted. Wait for admin approval.")
    admins = db.get_users_by_role("admin")
    for admin in admins:
        try:
            m = InlineKeyboardMarkup()
            m.add(InlineKeyboardButton("✅ Approve", callback_data=f"reg_approve|{reg_id}"))
            m.add(InlineKeyboardButton("❌ Decline", callback_data=f"reg_decline|{reg_id}"))
            bot.send_message(
                admin["telegram_id"],
                (
                    "New registration request\n"
                    f"Name: {payload['first_name']} {payload['last_name']}\n"
                    f"Email: {payload['email']}\n"
                    f"Role: {role_label(role)}\n"
                    f"User ID: {payload['telegram_id']}"
                ),
                reply_markup=m,
            )
        except Exception:
            continue
    bot.answer_callback_query(call.id)


def handle_registration_approval(bot, call: CallbackQuery, approve: bool) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    reg_id = parts[1]
    reg = db.get_pending_registration(reg_id)
    if not reg or reg.get("status") != "PENDING":
        bot.answer_callback_query(call.id, "Request already handled")
        return

    uid = reg["telegram_id"]
    if approve:
        user = {
            "telegram_id": uid,
            "email": reg.get("email", ""),
            "role": reg.get("requested_role", "frontend_developer"),
            "first_name": reg.get("first_name", ""),
            "last_name": reg.get("last_name", ""),
            "state": config.USER_STATE_ACTIVE,
            "score": 0,
            "is_banned": False,
            "created_at": db.utcnow(),
        }
        created = db.add_user(user)
        db.update_pending_registration(reg_id, {"status": "APPROVED", "handled_by": call.from_user.id})
        if created:
            notify_users(bot, [uid], "✅ Your registration was approved. You are now registered.")
            bot.answer_callback_query(call.id, "Approved")
        else:
            bot.answer_callback_query(call.id, "Already registered")
    else:
        db.update_pending_registration(reg_id, {"status": "DECLINED", "handled_by": call.from_user.id})
        notify_users(bot, [uid], "❌ Your registration was declined. Contact admin with /admin your message.")
        bot.answer_callback_query(call.id, "Declined")


def handle_email(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "email":
        return
    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email. Send a valid email address.")
        return
    invited = db.get_invited_user(email)
    if not invited:
        bot.send_message(message.chat.id, "Email not in allowed list. Contact admin.")
        clear_state(message.from_user.id)
        return
    role = invited.get("role") or (invited.get("roles", [""])[0])
    state.update({"email": email, "role": role, "step": "first_name"})
    bot.send_message(message.chat.id, f"✅ Email approved. Role: {role_label(role)}\nEnter first name:", reply_markup=navigation_markup(home=False))


def handle_first_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "first_name":
        return
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "First name cannot be empty.")
        return
    state["first_name"] = name
    state["step"] = "last_name"
    bot.send_message(message.chat.id, "Enter last name:", reply_markup=navigation_markup(home=False))


def handle_last_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "last_name":
        return
    lname = message.text.strip()
    if not lname:
        bot.send_message(message.chat.id, "Last name cannot be empty.")
        return
    user = {
        "telegram_id": message.from_user.id,
        "email": state["email"],
        "role": state["role"],
        "first_name": state["first_name"],
        "last_name": lname,
        "state": config.USER_STATE_ACTIVE,
        "score": 0,
        "is_banned": False,
        "created_at": db.utcnow(),
    }
    if not db.add_user(user):
        bot.send_message(message.chat.id, "Registration failed. You may already be registered.")
        clear_state(message.from_user.id)
        return
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, f"✅ Registration complete as {role_label(user['role'])}.")
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_cancel(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    clear_state(user_id)
    bot.send_message(chat_id, "Operation cancelled ✅")
    show_dashboard(bot, user_id, chat_id)
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


# User dashboard

def handle_dashboard_callback(bot, call: CallbackQuery) -> None:
    show_dashboard(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def handle_profile(bot, call: CallbackQuery) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return
    score_visible = bool(db.get_global_setting("score_visibility", True))
    text = (
        "👤 Profile\n"
        f"Name: {short_name(user)}\n"
        f"Email: {user.get('email', '')}\n"
        f"Role: {role_label(user.get('role', ''))}"
    )
    if score_visible or user.get("role") == "admin":
        text += f"\nScore: {user.get('score', 0)}"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=navigation_markup(back="go_dashboard", cancel=True))
    bot.answer_callback_query(call.id)


def handle_notif_settings(bot, call: CallbackQuery) -> None:
    pref = db.get_user_pref(call.from_user.id)
    enabled = pref.get("reminders_enabled", True)
    hours = pref.get("reminder_hours", [24, 2])
    text = f"🔔 Notifications\nEnabled: {'Yes' if enabled else 'No'}\nHours before deadline: {', '.join(str(h) for h in hours)}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Toggle On/Off", callback_data="notif_toggle"))
    markup.add(InlineKeyboardButton("Set reminder hours", callback_data="notif_set_hours"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_notif_toggle(bot, call: CallbackQuery) -> None:
    pref = db.get_user_pref(call.from_user.id)
    new_val = not pref.get("reminders_enabled", True)
    db.set_user_pref(call.from_user.id, {"reminders_enabled": new_val})
    bot.answer_callback_query(call.id, f"Notifications {'enabled' if new_val else 'disabled'}")
    handle_notif_settings(bot, call)


def handle_notif_set_hours(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "notif_hours"}
    bot.send_message(call.message.chat.id, "Send reminder hours separated by commas. Example: 24,6,2", reply_markup=navigation_markup(back="notif_settings", cancel=True))
    bot.answer_callback_query(call.id)


def handle_notif_hours_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "notif_hours":
        return
    raw = message.text.strip()
    try:
        hours = [int(x.strip()) for x in raw.split(",") if x.strip()]
        hours = sorted(set(h for h in hours if 1 <= h <= 168), reverse=True)
    except ValueError:
        bot.send_message(message.chat.id, "Invalid format. Example: 24,6,2")
        return
    if not hours:
        bot.send_message(message.chat.id, "Please provide at least one hour value between 1 and 168.")
        return
    db.set_user_pref(message.from_user.id, {"reminder_hours": hours})
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Reminder preferences updated.")
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_my_tasks(bot, call: CallbackQuery) -> None:
    bot.edit_message_text("📌 My Tasks", call.message.chat.id, call.message.message_id, reply_markup=tasks_menu_markup())
    bot.answer_callback_query(call.id)


def _task_status_for_user(task: Dict, user_id: int) -> str:
    submission = db.get_submission(str(task["_id"]), user_id)
    if submission and submission.get("status") == config.TASK_STATUS_DONE:
        return config.TASK_STATUS_COMPLETED
    return config.TASK_STATUS_ONGOING


def _task_list_for_user(user: Dict, requested_status: str) -> List[Dict]:
    result: List[Dict] = []
    for task in db.get_tasks_for_user(user):
        effective = config.TASK_STATUS_COMPLETED if task.get("status") == config.TASK_STATUS_COMPLETED else _task_status_for_user(task, user["telegram_id"])
        if effective == requested_status:
            result.append(task)
    return result


def handle_task_list(bot, call: CallbackQuery, status: str) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return
    wanted = config.TASK_STATUS_ONGOING if status == "ONGOING" else config.TASK_STATUS_COMPLETED
    tasks = _task_list_for_user(user, wanted)
    if not tasks:
        bot.edit_message_text(f"No {wanted.lower()} tasks.", call.message.chat.id, call.message.message_id, reply_markup=navigation_markup(back="my_tasks"))
        bot.answer_callback_query(call.id)
        return

    markup = InlineKeyboardMarkup()
    for t in tasks:
        markup.add(InlineKeyboardButton(f"📄 {t.get('title', 'Untitled')}", callback_data=f"task|{t['_id']}"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="my_tasks"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(f"{wanted.title()} Tasks", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_task_detail(bot, call: CallbackQuery) -> None:
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    user = db.get_user(call.from_user.id)
    if not task or not user:
        bot.answer_callback_query(call.id, "Task not found")
        return
    sub = db.get_submission(task_id, call.from_user.id)
    files_count = len((sub or {}).get("files", []))
    text = (
        f"📄 Task: {task.get('title', '')}\n"
        f"Description: {task.get('description', '')}\n"
        f"Deadline: {task.get('deadline', 'N/A')}\n"
        f"Status: {_task_status_for_user(task, call.from_user.id)}\n"
        f"Submission files: {files_count}"
    )
    if task.get("attachments"):
        text += f"\nTask attachments: {len(task.get('attachments', []))}"
    markup = InlineKeyboardMarkup()
    if _task_status_for_user(task, call.from_user.id) == config.TASK_STATUS_ONGOING:
        markup.add(InlineKeyboardButton("✅ Submit Task", callback_data=f"submit|{task_id}"))
    if task.get("attachments"):
        markup.add(InlineKeyboardButton("📎 View task attachments", callback_data=f"taskatt|{task_id}"))
    markup.add(InlineKeyboardButton("💬 Task Discussion", callback_data=f"thread_open|{task_id}|{call.from_user.id}"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="tasks_ongoing"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_task_attachments(bot, call: CallbackQuery) -> None:
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    if not task:
        bot.answer_callback_query(call.id, "Task not found")
        return
    attachments = task.get("attachments", [])
    if not attachments:
        bot.answer_callback_query(call.id, "No attachments")
        return
    bot.answer_callback_query(call.id, "Sending attachments...")
    for item in attachments:
        try:
            bot.send_document(call.message.chat.id, item["file_id"], caption=item.get("file_name", "attachment"))
        except Exception:
            continue


# Submission flow

def handle_submit_task(bot, call: CallbackQuery) -> None:
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    user = db.get_user(call.from_user.id)
    if not task or not user:
        bot.answer_callback_query(call.id, "Task not found")
        return
    registration_state[call.from_user.id] = {"step": "submit_work_url", "task_id": task_id, "submission": {"files": [], "custom_fields": []}}
    bot.send_message(call.message.chat.id, "Send GitHub or Figma URL:", reply_markup=navigation_markup(back=f"task|{task_id}"))
    bot.answer_callback_query(call.id)


def handle_thread_open(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Invalid thread")
        return
    task_id = parts[1]
    user_id = int(parts[2])
    task = db.get_task(task_id)
    if not task:
        bot.answer_callback_query(call.id, "Task not found")
        return
    caller = db.get_user(call.from_user.id)
    if not caller:
        bot.answer_callback_query(call.id, "Not registered")
        return

    if caller.get("role") != "admin" and call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "Not allowed")
        return

    thread = db.get_thread(task_id, user_id) or {"messages": []}
    messages = thread.get("messages", [])[-8:]
    lines = [f"💬 Thread for: {task.get('title', '')}"]
    if not messages:
        lines.append("No messages yet.")
    for msg in messages:
        role = msg.get("sender_role", "user")
        lines.append(f"[{role}] {msg.get('text', '')}")

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✍️ Send Message", callback_data=f"thread_write|{task_id}|{user_id}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(call.message.chat.id, "\n".join(lines), reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_thread_write(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Invalid thread")
        return
    task_id = parts[1]
    user_id = int(parts[2])
    registration_state[call.from_user.id] = {"step": "thread_message", "task_id": task_id, "thread_user_id": user_id}
    bot.send_message(call.message.chat.id, "Send your thread message:", reply_markup=navigation_markup(cancel=True))
    bot.answer_callback_query(call.id)


def handle_thread_message_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "thread_message":
        return
    text = message.text.strip()
    if not text:
        bot.send_message(message.chat.id, "Message cannot be empty.")
        return
    sender = db.get_user(message.from_user.id)
    if not sender:
        bot.send_message(message.chat.id, "Not registered.")
        clear_state(message.from_user.id)
        return
    task_id = state["task_id"]
    thread_user_id = state["thread_user_id"]
    db.add_thread_message(task_id, thread_user_id, message.from_user.id, sender.get("role", "user"), text)
    clear_state(message.from_user.id)
    recipients = {thread_user_id}
    admins = db.get_users_by_role("admin")
    for admin in admins:
        recipients.add(admin["telegram_id"])
    notify_users(bot, list(recipients), f"💬 New thread message on task {task_id}: {text}")
    bot.send_message(message.chat.id, "✅ Thread message sent.")


def handle_submit_work_url(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_work_url":
        return
    url = message.text.strip()
    if not utils.is_valid_url(url):
        bot.send_message(message.chat.id, "Please send a valid URL (http:// or https://).")
        return
    state["submission"]["work_url"] = url
    state["step"] = "submit_deployed"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Yes", callback_data="submit_deployed_yes"))
    markup.add(InlineKeyboardButton("❌ No", callback_data="submit_deployed_no"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Is this task deployed/live?", reply_markup=markup)


def handle_submit_deployed_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_deployed":
        return
    has_demo = call.data.endswith("yes")
    state["submission"]["is_deployed"] = has_demo
    if has_demo:
        state["step"] = "submit_demo_url"
        bot.send_message(call.message.chat.id, "Send live demo URL:", reply_markup=navigation_markup(cancel=True))
    else:
        state["submission"]["demo_url"] = None
        state["step"] = "submit_learned"
        bot.send_message(call.message.chat.id, "What did you learn from this task?", reply_markup=navigation_markup(cancel=True))
    bot.answer_callback_query(call.id)


def handle_submit_demo_url(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_demo_url":
        return
    url = message.text.strip()
    if not utils.is_valid_url(url):
        bot.send_message(message.chat.id, "Please send a valid demo URL.")
        return
    state["submission"]["demo_url"] = url
    state["step"] = "submit_learned"
    bot.send_message(message.chat.id, "What did you learn from this task?", reply_markup=navigation_markup(cancel=True))


def handle_submit_learned(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_learned":
        return
    learned = message.text.strip()
    if len(learned) < 5:
        bot.send_message(message.chat.id, "Please provide more detail.")
        return
    state["submission"]["learned"] = learned
    state["step"] = "submit_importance"
    bot.send_message(message.chat.id, "Rate task importance from 1 to 10:", reply_markup=navigation_markup(cancel=True))


def handle_submit_importance(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_importance":
        return
    try:
        val = int(message.text.strip())
        if val < 1 or val > 10:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "Enter a number between 1 and 10.")
        return
    state["submission"]["importance_rating"] = val
    state["step"] = "submit_custom_field_ask"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Add custom field", callback_data="submit_custom_yes"))
    markup.add(InlineKeyboardButton("➡️ Continue", callback_data="submit_custom_no"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Do you want to add any extra field (name + data)?", reply_markup=markup)


def handle_submit_custom_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_custom_field_ask":
        return
    if call.data == "submit_custom_yes":
        state["step"] = "submit_custom_name"
        bot.send_message(call.message.chat.id, "Enter custom field name:", reply_markup=navigation_markup(cancel=True))
    else:
        state["step"] = "submit_files"
        _prompt_submission_files(bot, call.message.chat.id)
    bot.answer_callback_query(call.id)


def handle_submit_custom_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_custom_name":
        return
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Field name cannot be empty.")
        return
    state["current_custom_name"] = name
    state["step"] = "submit_custom_value"
    bot.send_message(message.chat.id, f"Enter value for '{name}':", reply_markup=navigation_markup(cancel=True))


def handle_submit_custom_value(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_custom_value":
        return
    val = message.text.strip()
    if not val:
        bot.send_message(message.chat.id, "Value cannot be empty.")
        return
    state["submission"]["custom_fields"].append({"name": state.pop("current_custom_name"), "value": val})
    state["step"] = "submit_custom_field_ask"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Add another field", callback_data="submit_custom_yes"))
    markup.add(InlineKeyboardButton("➡️ Continue", callback_data="submit_custom_no"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Custom field added ✅. Add another?", reply_markup=markup)


def _prompt_submission_files(bot, chat_id: int) -> None:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Done uploading", callback_data="submit_files_done"))
    markup.add(InlineKeyboardButton("⏭️ Skip files", callback_data="submit_files_skip"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(chat_id, "Upload multiple files now (images, PDFs, docs). When finished click Done uploading.", reply_markup=markup)


def handle_submit_file_message(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_files":
        return

    item = None
    if message.document:
        item = {
            "file_id": message.document.file_id,
            "file_name": message.document.file_name or "document",
            "mime_type": message.document.mime_type or "application/octet-stream",
        }
    elif message.photo:
        item = {
            "file_id": message.photo[-1].file_id,
            "file_name": "photo.jpg",
            "mime_type": "image/jpeg",
        }

    if not item:
        bot.send_message(message.chat.id, "Unsupported file. Upload image/document/pdf/doc/docx.")
        return

    state["submission"]["files"].append(item)
    bot.send_message(message.chat.id, f"File added ✅ ({len(state['submission']['files'])} total)")


def handle_submit_files_action(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_files":
        return
    if call.data == "submit_files_skip":
        state["submission"]["files"] = []
    _finalize_submission(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def _finalize_submission(bot, user_id: int, chat_id: int) -> None:
    state = registration_state.get(user_id)
    if not state:
        return
    task_id = state["task_id"]
    sub = state["submission"]
    payload = {
        "task_id": task_id,
        "user_id": user_id,
        "work_url": sub.get("work_url"),
        "is_deployed": sub.get("is_deployed", False),
        "demo_url": sub.get("demo_url"),
        "learned": sub.get("learned"),
        "importance_rating": sub.get("importance_rating"),
        "custom_fields": sub.get("custom_fields", []),
        "files": sub.get("files", []),
        "submitted_at": db.utcnow(),
        "status": config.TASK_STATUS_SUBMITTED,
    }
    ok = db.upsert_submission(task_id, user_id, payload)
    clear_state(user_id)
    if not ok:
        bot.send_message(chat_id, "Failed to save submission. Please retry.")
        return
    bot.send_message(chat_id, "✅ Submission saved and sent for review.")
    notify_admins_of_submission(bot, user_id, task_id)


# Admin: add intern

def handle_admin_add_intern(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    registration_state[call.from_user.id] = {"step": "admin_add_email"}
    bot.send_message(call.message.chat.id, "Enter intern email:", reply_markup=navigation_markup(back="admin_panel"))
    bot.answer_callback_query(call.id)


def handle_admin_add_email(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_add_email":
        return
    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format.")
        return
    state["email"] = email
    state["step"] = "admin_add_role"
    markup = InlineKeyboardMarkup()
    for role in get_active_roles(include_admin=False):
        if role == "admin":
            continue
        markup.add(InlineKeyboardButton(role_label(role), callback_data=f"admin_add_role|{role}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Select role:", reply_markup=markup)


def handle_admin_add_role(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_add_role":
        return
    _, role = call.data.split("|", 1)
    email = state.get("email")
    if not email:
        bot.answer_callback_query(call.id, "Invalid state")
        return
    ok = db.upsert_invited_user(email, role, added_by=call.from_user.id)
    clear_state(call.from_user.id)
    if ok:
        bot.edit_message_text(f"✅ Allowed intern added\nEmail: {email}\nRole: {role_label(role)}", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("Failed to add intern.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


# Admin assign task with attachments

def handle_admin_assign_task(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    if not is_admin(user_id):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return
    registration_state[user_id] = {"step": "admin_task_title", "task": {"assigned_user_ids": [], "assigned_roles": [], "attachments": []}}
    bot.send_message(chat_id, "Enter task title:", reply_markup=navigation_markup(back="admin_panel"))
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def handle_admin_task_title(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_title":
        return
    title = message.text.strip()
    if not title:
        bot.send_message(message.chat.id, "Title cannot be empty.")
        return
    state["task"]["title"] = title
    state["step"] = "admin_task_description"
    bot.send_message(message.chat.id, "Enter task description:", reply_markup=navigation_markup(cancel=True))


def handle_admin_task_description(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_description":
        return
    desc = message.text.strip()
    if not desc:
        bot.send_message(message.chat.id, "Description cannot be empty.")
        return
    state["task"]["description"] = desc
    state["step"] = "admin_task_deadline"
    bot.send_message(message.chat.id, "Enter deadline in YYYY-MM-DD:", reply_markup=navigation_markup(cancel=True))


def handle_admin_task_deadline(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_deadline":
        return
    deadline = message.text.strip()
    try:
        datetime.strptime(deadline, "%Y-%m-%d")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid date format. Use YYYY-MM-DD.")
        return
    state["task"]["deadline"] = deadline
    state["step"] = "admin_task_attach_ask"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📎 Add attachments", callback_data="admin_task_attach_yes"))
    markup.add(InlineKeyboardButton("⏭️ Skip", callback_data="admin_task_attach_no"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(message.chat.id, "Attach task files (PDF/DOC/DOCX) if available?", reply_markup=markup)


def handle_admin_task_attach_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_attach_ask":
        return
    if call.data == "admin_task_attach_yes":
        state["step"] = "admin_task_attach_files"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Done uploading", callback_data="admin_task_attach_done"))
        markup.add(InlineKeyboardButton("⏭️ Skip", callback_data="admin_task_attach_skip"))
        markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
        bot.send_message(call.message.chat.id, "Upload PDF/DOC/DOCX files now. Click Done when finished.", reply_markup=markup)
    else:
        state["step"] = "admin_task_assign_type"
        _send_assign_type_prompt(bot, call.message.chat.id)
    bot.answer_callback_query(call.id)


def handle_admin_task_attachment_file(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_attach_files":
        return
    if not message.document:
        bot.send_message(message.chat.id, "Please upload a document file (PDF/DOC/DOCX).")
        return
    doc = message.document
    fname = (doc.file_name or "").lower()
    allowed = fname.endswith(".pdf") or fname.endswith(".doc") or fname.endswith(".docx")
    if not allowed:
        bot.send_message(message.chat.id, "Only PDF/DOC/DOCX allowed for task attachments.")
        return
    state["task"]["attachments"].append({"file_id": doc.file_id, "file_name": doc.file_name, "mime_type": doc.mime_type or "application/octet-stream"})
    bot.send_message(message.chat.id, f"Attachment added ✅ ({len(state['task']['attachments'])} total)")


def handle_admin_task_attachment_action(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_attach_files":
        return
    state["step"] = "admin_task_assign_type"
    _send_assign_type_prompt(bot, call.message.chat.id)
    bot.answer_callback_query(call.id)


def _send_assign_type_prompt(bot, chat_id: int) -> None:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🟦 Assign to Role", callback_data="admin_assign_type|role"))
    markup.add(InlineKeyboardButton("✅ Assign to User(s)", callback_data="admin_assign_type|users"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(chat_id, "How do you want to assign this task?", reply_markup=markup)


def handle_admin_assign_type(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_assign_type":
        return
    _, typ = call.data.split("|", 1)
    if typ == "role":
        state["step"] = "admin_task_select_role"
        markup = InlineKeyboardMarkup()
        for role in get_active_roles(include_admin=False):
            if role == "admin":
                continue
            markup.add(InlineKeyboardButton(role_label(role), callback_data=f"admin_task_role|{role}"))
        markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
        bot.send_message(call.message.chat.id, "Select role:", reply_markup=markup)
    else:
        state["step"] = "admin_task_select_users"
        state["user_page"] = 0
        _show_user_picker(bot, call.message.chat.id, state)
    bot.answer_callback_query(call.id)


def handle_admin_task_role(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_role":
        return
    _, role = call.data.split("|", 1)
    state["task"]["assigned_roles"] = [role]
    state["task"]["assigned_user_ids"] = []
    _finalize_task_creation(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def _show_user_picker(bot, chat_id: int, state: Dict) -> None:
    page = state.get("user_page", 0)
    per_page = 6
    users = db.get_users_paginated(skip=page * per_page, limit=per_page)
    selected = set(state["task"].get("assigned_user_ids", []))
    markup = InlineKeyboardMarkup()
    for u in users:
        uid = u["telegram_id"]
        mark = "✅" if uid in selected else "⬜"
        markup.add(InlineKeyboardButton(f"{mark} {short_name(u)} ({role_label(u.get('role', ''))})", callback_data=f"admin_pick_user|{uid}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"admin_user_page|{page - 1}"))
    if len(users) == per_page:
        nav.append(InlineKeyboardButton("Next", callback_data=f"admin_user_page|{page + 1}"))
    if nav:
        markup.row(*nav)
    markup.add(InlineKeyboardButton("✅ Done", callback_data="admin_users_done"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(chat_id, "Select user(s). Tap to toggle:", reply_markup=markup)


def handle_admin_user_page(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return
    _, p = call.data.split("|", 1)
    state["user_page"] = max(0, int(p))
    _show_user_picker(bot, call.message.chat.id, state)
    bot.answer_callback_query(call.id)


def handle_admin_pick_user(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    selected = state["task"].setdefault("assigned_user_ids", [])
    if uid in selected:
        selected.remove(uid)
    else:
        selected.append(uid)
    bot.answer_callback_query(call.id, f"Selected: {len(selected)}")


def handle_admin_users_done(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return
    if not state["task"].get("assigned_user_ids"):
        bot.answer_callback_query(call.id, "Select at least one user")
        return
    state["task"]["assigned_roles"] = []
    _finalize_task_creation(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def _finalize_task_creation(bot, admin_id: int, chat_id: int) -> None:
    state = registration_state.get(admin_id)
    if not state:
        return
    task = {
        "title": state["task"]["title"],
        "description": state["task"]["description"],
        "deadline": state["task"]["deadline"],
        "assigned_user_ids": state["task"].get("assigned_user_ids", []),
        "assigned_roles": state["task"].get("assigned_roles", []),
        "attachments": state["task"].get("attachments", []),
        "status": config.TASK_STATUS_ONGOING,
        "created_by": admin_id,
        "created_at": db.utcnow(),
    }
    task_id = db.create_task(task)
    clear_state(admin_id)
    if not task_id:
        bot.send_message(chat_id, "Failed to create task.")
        return

    targets = set(task["assigned_user_ids"])
    for role in task["assigned_roles"]:
        for user in db.get_users_by_role(role):
            targets.add(user["telegram_id"])

    notify_users(bot, list(targets), f"✅ New task: {task['title']}\nDeadline: {task['deadline']}")
    bot.send_message(chat_id, "✅ Task assigned successfully.")


# Admin review and score

def _parse_triplet(data: str) -> Optional[Tuple[str, int]]:
    parts = data.split("|")
    if len(parts) != 3:
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def handle_admin_review_menu(bot, source) -> None:
    uid = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    if not is_admin(uid):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return
    items = [s for s in db.list_submissions() if s.get("status") in {config.TASK_STATUS_SUBMITTED, config.TASK_STATUS_ON_REVIEW}]
    if not items:
        bot.send_message(chat_id, "No submissions waiting for review.")
        return
    markup = InlineKeyboardMarkup()
    for s in items:
        user = db.get_user(s["user_id"])
        task = db.get_task(s["task_id"])
        if user and task:
            markup.add(InlineKeyboardButton(f"📥 {short_name(user)} - {task.get('title', '')}", callback_data=f"admin_review_item|{s['task_id']}|{s['user_id']}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(chat_id, "Select submission:", reply_markup=markup)
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def handle_admin_review_item(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid item")
        return
    task_id, user_id = parsed
    sub = db.get_submission(task_id, user_id)
    task = db.get_task(task_id)
    user = db.get_user(user_id)
    if not sub or not task or not user:
        bot.answer_callback_query(call.id, "Not found")
        return
    text = (
        f"Intern: {short_name(user)}\n"
        f"Task: {task.get('title', '')}\n"
        f"Work URL: {sub.get('work_url', 'N/A')}\n"
        f"Demo URL: {sub.get('demo_url') or 'N/A'}\n"
        f"Learned: {sub.get('learned', '')}\n"
        f"Importance: {sub.get('importance_rating', 'N/A')}/10\n"
        f"Custom fields: {len(sub.get('custom_fields', []))}\n"
        f"Files: {len(sub.get('files', []))}\n"
        f"Status: {sub.get('status', '')}"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🟦 Mark On Review", callback_data=f"admin_mark_review|{task_id}|{user_id}"))
    markup.add(InlineKeyboardButton("✅ Mark Done + Score", callback_data=f"admin_mark_done|{task_id}|{user_id}"))
    markup.add(InlineKeyboardButton("📎 Send files to admin", callback_data=f"admin_send_sub_files|{task_id}|{user_id}"))
    markup.add(InlineKeyboardButton("🗒️ Add note", callback_data=f"admin_add_sub_note|{task_id}|{user_id}"))
    markup.add(InlineKeyboardButton("💬 Open thread", callback_data=f"thread_open|{task_id}|{user_id}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_send_submission_files(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid item")
        return
    task_id, user_id = parsed
    sub = db.get_submission(task_id, user_id)
    if not sub or not sub.get("files"):
        bot.answer_callback_query(call.id, "No files attached")
        return
    bot.answer_callback_query(call.id, "Sending files...")
    for f in sub.get("files", []):
        mime = f.get("mime_type", "")
        try:
            if mime.startswith("image/"):
                bot.send_photo(call.message.chat.id, f["file_id"], caption=f.get("file_name", "image"))
            else:
                bot.send_document(call.message.chat.id, f["file_id"], caption=f.get("file_name", "file"))
        except Exception:
            continue


def handle_admin_mark_review(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    db.update_submission(task_id, user_id, {"status": config.TASK_STATUS_ON_REVIEW})
    bot.edit_message_text("Submission moved to ON_REVIEW ✅", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


def handle_admin_mark_done(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    registration_state[call.from_user.id] = {"step": "admin_score", "target_task_id": task_id, "target_user_id": user_id}
    bot.send_message(call.message.chat.id, f"Enter score (0-{config.MAX_SCORE}):", reply_markup=navigation_markup(cancel=True))
    bot.answer_callback_query(call.id)


def handle_admin_score(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_score":
        return
    try:
        score = int(message.text.strip())
        if score < 0 or score > config.MAX_SCORE:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, f"Invalid score. Enter 0-{config.MAX_SCORE}.")
        return
    state["score"] = score
    state["step"] = "admin_note"
    bot.send_message(message.chat.id, "Add optional review note (or type '-'): ", reply_markup=navigation_markup(cancel=True))


def handle_admin_note(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_note":
        return
    note = message.text.strip()
    if note == "-":
        note = ""
    task_id = state["target_task_id"]
    user_id = state["target_user_id"]
    score = state["score"]
    db.update_submission(task_id, user_id, {"status": config.TASK_STATUS_DONE, "review_score": score, "review_note": note, "reviewed_by": message.from_user.id, "reviewed_at": db.utcnow()})
    db.increment_user_score(user_id, score)
    task = db.get_task(task_id)
    title = task.get("title", "task") if task else "task"
    notify_users(bot, [user_id], f"✅ Your submission for '{title}' was reviewed. Score: {score}\nNote: {note or 'No note'}")
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "Submission marked done ✅")


def handle_admin_add_submission_note_start(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    registration_state[call.from_user.id] = {"step": "admin_sub_note", "target_task_id": task_id, "target_user_id": user_id}
    bot.send_message(call.message.chat.id, "Write note for this submission:", reply_markup=navigation_markup(cancel=True))
    bot.answer_callback_query(call.id)


def handle_admin_add_submission_note_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_sub_note":
        return
    note = message.text.strip()
    if not note:
        bot.send_message(message.chat.id, "Note cannot be empty.")
        return
    task_id = state["target_task_id"]
    user_id = state["target_user_id"]
    sub = db.get_submission(task_id, user_id) or {}
    notes = sub.get("admin_notes", [])
    notes.append({"admin_id": message.from_user.id, "note": note, "created_at": db.utcnow()})
    db.update_submission(task_id, user_id, {"admin_notes": notes})
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Note saved.")


# Admin advanced tools

def handle_admin_panel(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    bot.edit_message_text("🛠️ Admin Panel", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_markup())
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_start(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    registration_state[call.from_user.id] = {"step": "admin_broadcast"}
    bot.send_message(call.message.chat.id, "Send broadcast message text:", reply_markup=navigation_markup(back="admin_panel"))
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_message(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_broadcast":
        return
    text = message.text.strip()
    if not text:
        bot.send_message(message.chat.id, "Message cannot be empty.")
        return
    users = db.list_users(include_banned=False)
    success = 0
    for u in users:
        try:
            bot.send_message(u["telegram_id"], f"📣 Broadcast\n\n{text}")
            success += 1
        except Exception:
            continue
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, f"✅ Broadcast sent to {success} users.")


def handle_admin_manage_users(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    _show_user_manage_page(bot, call.message.chat.id, 0)
    bot.answer_callback_query(call.id)


def _show_user_manage_page(bot, chat_id: int, page: int) -> None:
    per = 8
    users = db.get_users_paginated(skip=page * per, limit=per)
    markup = InlineKeyboardMarkup()
    for u in users:
        badge = "⛔" if u.get("is_banned") else "✅"
        markup.add(InlineKeyboardButton(f"{badge} {short_name(u)} ({role_label(u.get('role', ''))})", callback_data=f"admin_user_view|{u['telegram_id']}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"admin_users_page|{page - 1}"))
    if len(users) == per:
        nav.append(InlineKeyboardButton("Next", callback_data=f"admin_users_page|{page + 1}"))
    if nav:
        markup.row(*nav)
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(chat_id, "👥 Manage users:", reply_markup=markup)


def handle_admin_users_page(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    _show_user_manage_page(bot, call.message.chat.id, max(0, int(raw)))
    bot.answer_callback_query(call.id)


def handle_admin_user_view(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    user = db.get_user(uid)
    if not user:
        bot.answer_callback_query(call.id, "User not found")
        return
    text = (
        f"👤 {short_name(user)}\n"
        f"Email: {user.get('email', '')}\n"
        f"Role: {role_label(user.get('role', ''))}\n"
        f"Banned: {'Yes' if user.get('is_banned') else 'No'}"
    )
    markup = InlineKeyboardMarkup()
    if user.get("is_banned"):
        markup.add(InlineKeyboardButton("✅ Unban", callback_data=f"admin_unban_user|{uid}"))
    else:
        markup.add(InlineKeyboardButton("⛔ Ban", callback_data=f"admin_ban_user|{uid}"))
    markup.add(InlineKeyboardButton("🟦 Change Role", callback_data=f"admin_change_role|{uid}"))
    markup.add(InlineKeyboardButton("❌ Remove User", callback_data=f"admin_remove_user|{uid}"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_users"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    bot.send_message(call.message.chat.id, text, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_ban_toggle(bot, call: CallbackQuery, ban: bool) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    ok = db.set_user_ban(uid, ban, reason="Set by admin")
    if ok:
        if ban:
            notify_users(bot, [uid], "⛔ Your account was restricted by admin.")
        else:
            notify_users(bot, [uid], "✅ Your account access was restored by admin.")
    bot.answer_callback_query(call.id, "Updated" if ok else "Failed")


def handle_admin_remove_user(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    if uid == call.from_user.id:
        bot.answer_callback_query(call.id, "You cannot remove yourself")
        return
    ok = db.soft_delete_user(uid, deleted_by=call.from_user.id)
    bot.answer_callback_query(call.id, "Soft-deleted" if ok else "Failed")


def handle_admin_restore_users(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    deleted = db.list_deleted_users(limit=50)
    if not deleted:
        bot.answer_callback_query(call.id, "No deleted users")
        return
    markup = InlineKeyboardMarkup()
    for u in deleted:
        markup.add(InlineKeyboardButton(f"♻️ Restore {short_name(u)}", callback_data=f"admin_restore_user|{u['telegram_id']}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(call.message.chat.id, "Deleted users:", reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_restore_user(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    ok = db.restore_user(uid)
    bot.answer_callback_query(call.id, "Restored" if ok else "Failed")


def handle_admin_change_role(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    markup = InlineKeyboardMarkup()
    for role in get_active_roles(include_admin=True):
        markup.add(InlineKeyboardButton(role_label(role), callback_data=f"admin_set_role|{uid}|{role}"))
    markup.row(InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.send_message(call.message.chat.id, "Select new role:", reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_set_role(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    uid = int(parts[1])
    role = parts[2]
    ok = db.set_user_role(uid, role)
    if ok:
        notify_users(bot, [uid], f"✅ Your role was updated to {role_label(role)}")
    bot.answer_callback_query(call.id, "Role updated" if ok else "Failed")


def handle_admin_force_sub_menu(bot, call: CallbackQuery) -> None:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    text = f"📢 Force Subscription\nEnabled: {'Yes' if cfg.get('enabled') else 'No'}\nChannel: {cfg.get('channel') or 'Not set'}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Set channel", callback_data="admin_force_set_channel"))
    markup.add(InlineKeyboardButton("Toggle On/Off", callback_data="admin_force_toggle"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_force_set_channel(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "admin_set_channel"}
    bot.send_message(call.message.chat.id, "Send channel username like @mychannel", reply_markup=navigation_markup(back="admin_force_sub_menu"))
    bot.answer_callback_query(call.id)


def handle_admin_set_channel_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_set_channel":
        return
    channel = message.text.strip()
    if not channel.startswith("@"):
        bot.send_message(message.chat.id, "Channel should start with @")
        return
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    cfg["channel"] = channel
    db.set_global_setting("force_subscription", cfg)
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, f"✅ Channel set to {channel}")


def handle_admin_force_toggle(bot, call: CallbackQuery) -> None:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    cfg["enabled"] = not bool(cfg.get("enabled"))
    db.set_global_setting("force_subscription", cfg)
    bot.answer_callback_query(call.id, f"Force subscription {'ON' if cfg['enabled'] else 'OFF'}")
    handle_admin_force_sub_menu(bot, call)


def handle_admin_reply_command(bot, message: Message) -> None:
    txt = (message.text or "").strip()
    parts = txt.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: /admin your message")
        return
    payload = parts[1]
    user = db.get_user(message.from_user.id)
    sender_name = short_name(user) if user else (message.from_user.full_name or str(message.from_user.id))

    if is_admin(message.from_user.id) and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        try:
            bot.send_message(target_id, f"📩 Admin message:\n{payload}")
            bot.send_message(message.chat.id, "✅ Message sent.")
        except Exception:
            bot.send_message(message.chat.id, "Failed to send message.")
        return

    admins = db.get_users_by_role("admin")
    if not admins:
        bot.send_message(message.chat.id, "No admin available now. Please try later.")
        return
    forwarded = 0
    for admin in admins:
        try:
            bot.send_message(
                admin["telegram_id"],
                (
                    "📩 User to admin\n"
                    f"From: {sender_name}\n"
                    f"Telegram ID: {message.from_user.id}\n"
                    f"Message: {payload}"
                ),
            )
            forwarded += 1
        except Exception:
            continue
    if forwarded:
        bot.send_message(message.chat.id, "✅ Message sent to admin.")
    else:
        bot.send_message(message.chat.id, "Failed to reach admin.")


def handle_admin_manage_roles(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    roles = get_active_roles(include_admin=True)
    text = "🧩 Manage Roles\nCurrent roles:\n" + "\n".join(f"- {role_label(r)} ({r})" for r in roles)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Add role", callback_data="admin_role_add_start"))
    markup.add(InlineKeyboardButton("➖ Remove role", callback_data="admin_role_remove_menu"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_role_add_start(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "admin_role_add_name"}
    bot.send_message(call.message.chat.id, "Send new role key (example: data_analyst):", reply_markup=navigation_markup(back="admin_manage_roles"))
    bot.answer_callback_query(call.id)


def handle_admin_role_add_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_role_add_name":
        return
    role = message.text.strip().lower().replace(" ", "_")
    if not role or not role.replace("_", "").isalnum():
        bot.send_message(message.chat.id, "Invalid role key. Use letters/numbers/underscore.")
        return
    ok = db.add_role(role)
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Role added." if ok else "Failed to add role.")


def handle_admin_role_remove_menu(bot, call: CallbackQuery) -> None:
    roles = get_active_roles(include_admin=False)
    markup = InlineKeyboardMarkup()
    for role in roles:
        markup.add(InlineKeyboardButton(f"Remove {role_label(role)}", callback_data=f"admin_role_remove|{role}"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_roles"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text("Select role to remove:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_role_remove(bot, call: CallbackQuery) -> None:
    _, role = call.data.split("|", 1)
    ok = db.remove_role(role)
    bot.answer_callback_query(call.id, "Role removed" if ok else "Failed (admin role cannot be removed)")


def handle_admin_score_visibility_menu(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    enabled = bool(db.get_global_setting("score_visibility", True))
    text = f"🎯 Score visibility for interns: {'ON' if enabled else 'OFF'}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Toggle", callback_data="admin_score_visibility_toggle"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_score_visibility_toggle(bot, call: CallbackQuery) -> None:
    current = bool(db.get_global_setting("score_visibility", True))
    db.set_global_setting("score_visibility", not current)
    bot.answer_callback_query(call.id, f"Score visibility {'ON' if not current else 'OFF'}")
    handle_admin_score_visibility_menu(bot, call)


def _send_csv(bot, chat_id: int, filename: str, rows: List[List[str]]) -> None:
    sio = io.StringIO()
    writer = csv.writer(sio)
    for row in rows:
        writer.writerow(row)
    bio = io.BytesIO(sio.getvalue().encode("utf-8"))
    bio.name = filename
    bot.send_document(chat_id, bio, caption=f"✅ Exported {filename}")


def handle_admin_export_menu(bot, call: CallbackQuery) -> None:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Submissions CSV", callback_data="admin_export_submissions"))
    markup.add(InlineKeyboardButton("Reminders CSV", callback_data="admin_export_reminders"))
    markup.add(InlineKeyboardButton("Leaderboard CSV", callback_data="admin_export_leaderboard"))
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"), InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text("📤 Select CSV export:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_export_submissions(bot, call: CallbackQuery) -> None:
    rows = [["task_id", "user_id", "status", "work_url", "demo_url", "importance", "files_count", "notes_count"]]
    for s in db.list_submissions():
        rows.append([
            str(s.get("task_id", "")),
            str(s.get("user_id", "")),
            str(s.get("status", "")),
            str(s.get("work_url", "")),
            str(s.get("demo_url", "")),
            str(s.get("importance_rating", "")),
            str(len(s.get("files", []))),
            str(len(s.get("admin_notes", []))),
        ])
    _send_csv(bot, call.message.chat.id, "submissions.csv", rows)
    bot.answer_callback_query(call.id)


def handle_admin_export_reminders(bot, call: CallbackQuery) -> None:
    rows = [["telegram_id", "name", "reminders_enabled", "reminder_hours"]]
    for user in db.list_users(include_banned=True):
        pref = db.get_user_pref(user["telegram_id"])
        rows.append([
            str(user.get("telegram_id", "")),
            short_name(user),
            str(pref.get("reminders_enabled", True)),
            ";".join(str(h) for h in pref.get("reminder_hours", [24, 2])),
        ])
    _send_csv(bot, call.message.chat.id, "reminders.csv", rows)
    bot.answer_callback_query(call.id)


def handle_admin_export_leaderboard(bot, call: CallbackQuery) -> None:
    rows = [["rank", "telegram_id", "name", "role", "score"]]
    rank = 1
    for user in db.get_leaderboard(limit=1000):
        rows.append([
            str(rank),
            str(user.get("telegram_id", "")),
            short_name(user),
            role_label(user.get("role", "")),
            str(user.get("score", 0)),
        ])
        rank += 1
    _send_csv(bot, call.message.chat.id, "leaderboard.csv", rows)
    bot.answer_callback_query(call.id)


# Leaderboard

def handle_admin_leaderboard(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    board = db.get_leaderboard(limit=20)
    if not board:
        bot.edit_message_text("Leaderboard is empty.", call.message.chat.id, call.message.message_id, reply_markup=navigation_markup(back="admin_panel"))
        bot.answer_callback_query(call.id)
        return
    lines = ["🏆 Leaderboard"]
    i = 1
    show_scores = bool(db.get_global_setting("score_visibility", True))
    for u in board:
        suffix = f" - {u.get('score', 0)}" if show_scores else ""
        lines.append(f"{i}. {short_name(u)} ({role_label(u.get('role', ''))}){suffix}")
        i += 1
    bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=navigation_markup(back="admin_panel"))
    bot.answer_callback_query(call.id)
