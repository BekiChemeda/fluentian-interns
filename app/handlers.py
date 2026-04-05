"""
handlers.py
Advanced Telegram handlers for interns and admin workflows.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.africa_data import (
    AFRICAN_COUNTRIES,
    GENDER_OPTIONS,
    LANGUAGE_LEVEL_OPTIONS,
    LANGUAGE_OPTIONS,
)
from app import config, db, utils

registration_state: Dict[int, Dict] = {}
REQUIRED_PROFILE_FIELDS = [
    "gender",
    "nationality",
    "current_country",
    "current_city",
    "country_language",
    "language_level",
]


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


def is_registration_open() -> bool:
    return bool(db.get_global_setting("registration_open", True))


def short_name(user: Dict) -> str:
    full = f"{user.get('first_name', '').strip()} {user.get('last_name', '').strip()}".strip()
    return full or user.get("email", "Unknown")


def profile_completion_percent(user: Dict) -> int:
    filled = 0
    for key in REQUIRED_PROFILE_FIELDS:
        if str(user.get(key, "")).strip():
            filled += 1
    return int((filled / len(REQUIRED_PROFILE_FIELDS)) * 100)


def is_profile_complete(user: Dict) -> bool:
    return all(str(user.get(k, "")).strip() for k in REQUIRED_PROFILE_FIELDS)


def missing_profile_fields(user: Dict) -> List[str]:
    labels = {
        "gender": "Gender",
        "nationality": "Nationality",
        "current_country": "Current Country",
        "current_city": "Current City",
        "country_language": "Language",
        "language_level": "Language Level",
    }
    return [
        labels[k] for k in REQUIRED_PROFILE_FIELDS if not str(user.get(k, "")).strip()
    ]


def paged_buttons(
    items: List[str], callback_prefix: str, page: int, per_page: int = 8
) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    start = page * per_page
    end = min(start + per_page, len(items))
    for idx in range(start, end):
        markup.add(
            InlineKeyboardButton(
                items[idx], callback_data=f"{callback_prefix}|{idx}|{page}"
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "Prev", callback_data=f"{callback_prefix}_page|{page - 1}"
            )
        )
    if end < len(items):
        nav.append(
            InlineKeyboardButton(
                "Next", callback_data=f"{callback_prefix}_page|{page + 1}"
            )
        )
    if nav:
        markup.row(*nav)
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="profile_edit_menu"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    return markup


def navigation_markup(
    back: Optional[str] = None, home: bool = True, cancel: bool = True
) -> InlineKeyboardMarkup:
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
    markup.add(
        InlineKeyboardButton("🔔 Notification Settings", callback_data="notif_settings")
    )
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
    markup.add(
        InlineKeyboardButton("📋 Tasks & Reviews", callback_data="admin_cat_tasks")
    )
    markup.add(
        InlineKeyboardButton("👥 Users & Roles", callback_data="admin_cat_users")
    )
    markup.add(
        InlineKeyboardButton(
            "📣 Communication & Settings", callback_data="admin_cat_settings"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "📊 Reports & Analytics", callback_data="admin_cat_reports"
        )
    )
    markup.add(
        InlineKeyboardButton("📈 Quick Stats", callback_data="admin_stats_overview")
    )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    return markup


def edit_or_send_message(
    bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    edit_message: Optional[Message] = None,
) -> None:
    if edit_message:
        try:
            bot.edit_message_text(
                text,
                edit_message.chat.id,
                edit_message.message_id,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=reply_markup)


def _contact_reply_markup(target_user_id: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("↩️ Reply", callback_data=f"contact_reply|{target_user_id}")
    )
    return markup


def _build_dashboard_text(user: Dict) -> str:
    score_visible = bool(db.get_global_setting("score_visibility", True))
    text = f"✅ Welcome, {short_name(user)}\nRole: {role_label(user.get('role', ''))}"
    if score_visible or user.get("role") == "admin":
        text += f"\nScore: {user.get('score', 0)}"
    return text


def _send_contact_message(
    bot, sender_id: int, target_id: int, payload: str, sender_is_admin: bool
) -> bool:
    sender = db.get_user(sender_id)
    sender_name = short_name(sender) if sender else str(sender_id)
    label = "Admin" if sender_is_admin else "User"
    text = (
        f"📩 {label} message\n"
        f"From: {sender_name}\n"
        f"Telegram ID: {sender_id}\n"
        f"Message: {payload}"
    )
    try:
        bot.send_message(target_id, text, reply_markup=_contact_reply_markup(sender_id))
        return True
    except Exception:
        return False


def clear_state(user_id: int) -> None:
    registration_state.pop(user_id, None)


def _parse_force_channel_input(
    raw: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    parts = [p.strip() for p in raw.split() if p.strip()]
    if not parts:
        return None, None, "Input is empty."

    channel_ref = parts[0]
    join_hint = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Accept public channel username or private/public chat id.
    if channel_ref.startswith("@"):
        return channel_ref, join_hint, None
    if channel_ref.startswith("-100") and channel_ref[1:].isdigit():
        return channel_ref, join_hint, None

    return (
        None,
        None,
        "Use @channel_username or private channel ID like -1001234567890.",
    )


def maybe_force_subscribed(bot, telegram_id: int) -> Tuple[bool, str]:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    enabled = bool(cfg.get("enabled"))
    channel = str(cfg.get("channel") or "").strip()
    join_hint = str(cfg.get("join_hint") or "").strip()
    join_target = join_hint or channel
    if not enabled or not channel:
        return True, ""
    try:
        member = bot.get_chat_member(channel, telegram_id)
        if member.status in {"member", "administrator", "creator", "restricted"}:
            return True, ""
    except Exception:
        return False, f"Please join {join_target} and try again."
    return False, f"Please join {join_target} and try again."


def show_dashboard(
    bot, telegram_id: int, chat_id: int, edit_message: Optional[Message] = None
) -> None:
    user = db.get_user(telegram_id)
    if not user:
        edit_or_send_message(
            bot,
            chat_id,
            "Please use /start to register first.",
            edit_message=edit_message,
        )
        return
    if user.get("is_banned"):
        edit_or_send_message(
            bot,
            chat_id,
            "Your account is restricted. Contact admin.",
            edit_message=edit_message,
        )
        return
    allowed, msg = maybe_force_subscribed(bot, telegram_id)
    if not allowed:
        edit_or_send_message(bot, chat_id, msg, edit_message=edit_message)
        return

    if not is_profile_complete(user):
        missing = "\n".join(f"- {m}" for m in missing_profile_fields(user))
        text = (
            "⚠️ Profile completion required before using the bot.\n"
            f"Progress: {profile_completion_percent(user)}%\n"
            "Please fill the missing fields:\n"
            f"{missing}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "✏️ Complete Profile", callback_data="profile_edit_menu"
            )
        )
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
        edit_or_send_message(
            bot, chat_id, text, reply_markup=markup, edit_message=edit_message
        )
        return

    edit_or_send_message(
        bot,
        chat_id,
        _build_dashboard_text(user),
        reply_markup=user_dashboard_markup(user),
        edit_message=edit_message,
    )


def require_profile_access_callback(bot, call: CallbackQuery) -> bool:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return False
    if is_profile_complete(user):
        return True
    show_dashboard(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)
    return False


def require_profile_access_source(bot, source) -> bool:
    telegram_id = source.from_user.id
    chat_id = (
        source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    )
    edit_message = source.message if isinstance(source, CallbackQuery) else None
    user = db.get_user(telegram_id)
    if not user:
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Not registered")
        else:
            bot.send_message(chat_id, "Not registered")
        return False
    if is_profile_complete(user):
        return True
    show_dashboard(bot, telegram_id, chat_id, edit_message=edit_message)
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)
    return False


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
    if is_registration_open():
        markup.add(InlineKeyboardButton("🟢 Register", callback_data="start_register"))
    markup.add(
        InlineKeyboardButton("📩 Contact Admin", callback_data="help_contact_admin")
    )
    status_line = (
        "Registration is currently open."
        if is_registration_open()
        else "Registration is currently closed by admin."
    )
    bot.send_message(
        message.chat.id,
        f"Welcome. Use /register (or button) to apply when registration is open.\n{status_line}",
        reply_markup=markup,
    )


def handle_register_start(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = (
        source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    )
    edit_message = source.message if isinstance(source, CallbackQuery) else None
    if not is_registration_open():
        edit_or_send_message(
            bot,
            chat_id,
            "Registration is currently closed by admin. Contact admin with /admin your message.",
            edit_message=edit_message,
        )
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id)
        return
    if db.get_user(user_id):
        edit_or_send_message(
            bot, chat_id, "You are already registered.", edit_message=edit_message
        )
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id)
        return
    registration_state[user_id] = {"step": "reg_first_name"}
    edit_or_send_message(
        bot,
        chat_id,
        "Enter first name (example: John):",
        reply_markup=navigation_markup(home=True, cancel=True),
        edit_message=edit_message,
    )
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
    bot.send_message(
        message.chat.id,
        "Enter last name (example: Michael):",
        reply_markup=navigation_markup(cancel=True),
    )


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
    bot.send_message(
        message.chat.id,
        "Enter email (example: john.michael@example.com):",
        reply_markup=navigation_markup(cancel=True),
    )


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
        markup.add(
            InlineKeyboardButton(role_label(role), callback_data=f"reg_role|{role}")
        )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        message.chat.id, "Select role from the buttons below:", reply_markup=markup
    )


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
        bot.send_message(
            call.message.chat.id, "Failed to submit application. Try again."
        )
        bot.answer_callback_query(call.id)
        return

    bot.send_message(
        call.message.chat.id, "✅ Application submitted. Wait for admin approval."
    )
    admins = db.get_users_by_role("admin")
    for admin in admins:
        try:
            m = InlineKeyboardMarkup()
            m.add(
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"reg_approve|{reg_id}"
                )
            )
            m.add(
                InlineKeyboardButton(
                    "❌ Decline", callback_data=f"reg_decline|{reg_id}"
                )
            )
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
    if reg and reg.get("status") != "PENDING":
        latest = db.pending_registrations.find_one(
            {"telegram_id": reg.get("telegram_id"), "status": "PENDING"},
            sort=[("created_at", -1)],
        )
        if latest:
            reg = latest
            reg_id = str(latest.get("_id"))
    if not reg or reg.get("status") != "PENDING":
        bot.answer_callback_query(call.id)
        return

    uid = reg["telegram_id"]
    if approve:
        user = {
            "telegram_id": uid,
            "email": reg.get("email", ""),
            "role": reg.get("requested_role", "frontend_developer"),
            "first_name": reg.get("first_name", ""),
            "last_name": reg.get("last_name", ""),
            "gender": "",
            "nationality": "",
            "current_city": "",
            "current_country": "",
            "country_language": "",
            "language_level": "",
            "state": config.USER_STATE_ACTIVE,
            "score": 0,
            "is_banned": False,
            "created_at": db.utcnow(),
        }
        created = db.add_user(user)
        db.update_pending_registration(
            reg_id, {"status": "APPROVED", "handled_by": call.from_user.id}
        )
        if created:
            notify_users(
                bot, [uid], "✅ Your registration was approved. You are now registered."
            )
            bot.edit_message_text(
                (
                    "✅ Registration approved\n"
                    f"Name: {reg.get('first_name', '')} {reg.get('last_name', '')}\n"
                    f"Email: {reg.get('email', '')}\n"
                    f"Role: {role_label(reg.get('requested_role', ''))}\n"
                    f"User ID: {uid}"
                ),
                call.message.chat.id,
                call.message.message_id,
            )
        else:
            bot.edit_message_text(
                "User is already registered.",
                call.message.chat.id,
                call.message.message_id,
            )
    else:
        db.update_pending_registration(
            reg_id, {"status": "DECLINED", "handled_by": call.from_user.id}
        )
        notify_users(
            bot,
            [uid],
            "❌ Your registration was declined. Contact admin with /admin your message.",
        )
        bot.edit_message_text(
            (
                "❌ Registration declined\n"
                f"Name: {reg.get('first_name', '')} {reg.get('last_name', '')}\n"
                f"Email: {reg.get('email', '')}\n"
                f"Role: {role_label(reg.get('requested_role', ''))}\n"
                f"User ID: {uid}"
            ),
            call.message.chat.id,
            call.message.message_id,
        )
    bot.answer_callback_query(call.id)


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
    bot.send_message(
        message.chat.id,
        f"✅ Email approved. Role: {role_label(role)}\nEnter first name:",
        reply_markup=navigation_markup(home=False),
    )


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
    bot.send_message(
        message.chat.id, "Enter last name:", reply_markup=navigation_markup(home=False)
    )


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
        "gender": "",
        "nationality": "",
        "current_city": "",
        "current_country": "",
        "country_language": "",
        "language_level": "",
        "state": config.USER_STATE_ACTIVE,
        "score": 0,
        "is_banned": False,
        "created_at": db.utcnow(),
    }
    if not db.add_user(user):
        bot.send_message(
            message.chat.id, "Registration failed. You may already be registered."
        )
        clear_state(message.from_user.id)
        return
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id, f"✅ Registration complete as {role_label(user['role'])}."
    )
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_cancel(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = (
        source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    )
    clear_state(user_id)
    if isinstance(source, CallbackQuery):
        show_dashboard(bot, user_id, chat_id, edit_message=source.message)
        bot.answer_callback_query(source.id)
    else:
        bot.send_message(chat_id, "Operation cancelled ✅")
        show_dashboard(bot, user_id, chat_id)


# User dashboard


def handle_dashboard_callback(bot, call: CallbackQuery) -> None:
    show_dashboard(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_profile(bot, call: CallbackQuery) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return
    score_visible = bool(db.get_global_setting("score_visibility", True))
    name_edit_enabled = bool(db.get_global_setting("allow_profile_name_edit", False))
    email_edit_enabled = bool(db.get_global_setting("allow_profile_email_edit", False))
    complete = is_profile_complete(user)
    text = (
        "👤 Profile\n"
        f"Name: {short_name(user)}\n"
        f"Email: {user.get('email', '')}\n"
        f"Role: {role_label(user.get('role', ''))}\n"
        f"Gender: {user.get('gender') or 'Not set'}\n"
        f"Nationality: {user.get('nationality') or 'Not set'}\n"
        f"Current Country: {user.get('current_country') or 'Not set'}\n"
        f"Current City: {user.get('current_city') or 'Not set'}\n"
        f"Language: {user.get('country_language') or 'Not set'}\n"
        f"Language Level: {user.get('language_level') or 'Not set'}\n"
        f"Profile Completion: {profile_completion_percent(user)}%"
    )
    if score_visible or user.get("role") == "admin":
        text += f"\nScore: {user.get('score', 0)}"
    if not complete:
        text += "\n\n⚠️ Complete missing profile details to access all features."
    if not name_edit_enabled:
        text += "\nName edit: Off"
    if not email_edit_enabled:
        text += "\nEmail edit: Off"

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✏️ Edit Profile", callback_data="profile_edit_menu")
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_profile_edit_menu(bot, call: CallbackQuery) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id)
        return
    name_edit_enabled = bool(db.get_global_setting("allow_profile_name_edit", False))
    email_edit_enabled = bool(db.get_global_setting("allow_profile_email_edit", False))
    text = (
        "✏️ Edit Profile\n"
        "Choose what to update.\n"
        f"Completion: {profile_completion_percent(user)}%"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Gender", callback_data="profile_pick_gender"))
    markup.add(
        InlineKeyboardButton("Nationality", callback_data="profile_pick_nationality|0")
    )
    markup.add(
        InlineKeyboardButton("Current Country", callback_data="profile_pick_country|0")
    )
    markup.add(
        InlineKeyboardButton("Current City (type)", callback_data="profile_pick_city")
    )
    markup.add(InlineKeyboardButton("Language", callback_data="profile_pick_language"))
    markup.add(
        InlineKeyboardButton(
            "Language Level", callback_data="profile_pick_language_level"
        )
    )
    if name_edit_enabled:
        markup.add(
            InlineKeyboardButton("First Name", callback_data="profile_edit_first_name")
        )
        markup.add(
            InlineKeyboardButton("Last Name", callback_data="profile_edit_last_name")
        )
    if email_edit_enabled:
        markup.add(InlineKeyboardButton("Email", callback_data="profile_edit_email"))
    markup.row(
        InlineKeyboardButton("✅ Done", callback_data="profile_finish"),
        InlineKeyboardButton("⬅️ Back", callback_data="profile"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_profile_pick_gender(bot, call: CallbackQuery) -> None:
    markup = InlineKeyboardMarkup()
    for g in GENDER_OPTIONS:
        markup.add(InlineKeyboardButton(g, callback_data=f"profile_set_gender|{g}"))
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="profile_edit_menu"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        "Select gender:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def _show_profile_country_picker(
    bot, call: CallbackQuery, field: str, page: int
) -> None:
    title = (
        "Select nationality:" if field == "nationality" else "Select current country:"
    )
    prefix = (
        "profile_set_nationality" if field == "nationality" else "profile_set_country"
    )
    markup = paged_buttons(AFRICAN_COUNTRIES, prefix, page)
    bot.edit_message_text(
        title, call.message.chat.id, call.message.message_id, reply_markup=markup
    )


def handle_profile_pick_nationality(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|", 1)
    page = int(parts[1]) if len(parts) == 2 else 0
    _show_profile_country_picker(bot, call, "nationality", max(0, page))
    bot.answer_callback_query(call.id)


def handle_profile_pick_nationality_page(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    _show_profile_country_picker(bot, call, "nationality", max(0, int(raw)))
    bot.answer_callback_query(call.id)


def handle_profile_pick_country(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|", 1)
    page = int(parts[1]) if len(parts) == 2 else 0
    _show_profile_country_picker(bot, call, "current_country", max(0, page))
    bot.answer_callback_query(call.id)


def handle_profile_pick_country_page(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    _show_profile_country_picker(bot, call, "current_country", max(0, int(raw)))
    bot.answer_callback_query(call.id)


def handle_profile_pick_city(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "profile_edit_current_city"}
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Type your current city:",
        reply_markup=navigation_markup(back="profile_edit_menu", cancel=True),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_profile_pick_city_page(bot, call: CallbackQuery) -> None:
    handle_profile_pick_city(bot, call)


def handle_profile_pick_language(bot, call: CallbackQuery) -> None:
    markup = InlineKeyboardMarkup()
    for i, lang in enumerate(LANGUAGE_OPTIONS):
        markup.add(
            InlineKeyboardButton(lang, callback_data=f"profile_set_language|{i}")
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="profile_edit_menu"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        "Select language:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_profile_pick_language_level(bot, call: CallbackQuery) -> None:
    markup = InlineKeyboardMarkup()
    for i, level in enumerate(LANGUAGE_LEVEL_OPTIONS):
        markup.add(
            InlineKeyboardButton(level, callback_data=f"profile_set_language_level|{i}")
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="profile_edit_menu"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        "Select language level:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_profile_set_gender(bot, call: CallbackQuery) -> None:
    _, value = call.data.split("|", 1)
    db.update_user(call.from_user.id, {"gender": value})
    handle_profile_edit_menu(bot, call)


def handle_profile_set_nationality(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|")
    if len(parts) < 2:
        bot.answer_callback_query(call.id)
        return
    idx = int(parts[1])
    if 0 <= idx < len(AFRICAN_COUNTRIES):
        db.update_user(call.from_user.id, {"nationality": AFRICAN_COUNTRIES[idx]})
    handle_profile_edit_menu(bot, call)


def handle_profile_set_country(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|")
    if len(parts) < 2:
        bot.answer_callback_query(call.id)
        return
    idx = int(parts[1])
    if 0 <= idx < len(AFRICAN_COUNTRIES):
        country = AFRICAN_COUNTRIES[idx]
        db.update_user(call.from_user.id, {"current_country": country})
    handle_profile_edit_menu(bot, call)


def handle_profile_set_city(bot, call: CallbackQuery) -> None:
    handle_profile_pick_city(bot, call)


def handle_profile_set_language(bot, call: CallbackQuery) -> None:
    _, raw_idx = call.data.split("|", 1)
    idx = int(raw_idx)
    if 0 <= idx < len(LANGUAGE_OPTIONS):
        db.update_user(
            call.from_user.id,
            {"country_language": LANGUAGE_OPTIONS[idx], "language_level": ""},
        )
    handle_profile_pick_language_level(bot, call)


def handle_profile_set_language_level(bot, call: CallbackQuery) -> None:
    _, raw_idx = call.data.split("|", 1)
    idx = int(raw_idx)
    if 0 <= idx < len(LANGUAGE_LEVEL_OPTIONS):
        db.update_user(
            call.from_user.id, {"language_level": LANGUAGE_LEVEL_OPTIONS[idx]}
        )
    handle_profile_edit_menu(bot, call)


def handle_profile_edit_city_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "profile_edit_current_city":
        return
    value = (message.text or "").strip()
    if len(value) < 2:
        bot.send_message(message.chat.id, "City name is too short.")
        return
    db.update_user(message.from_user.id, {"current_city": value})
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Current city updated.")
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_profile_finish(bot, call: CallbackQuery) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id)
        return
    if not is_profile_complete(user):
        missing = ", ".join(missing_profile_fields(user))
        bot.answer_callback_query(call.id, f"Missing: {missing}")
        return
    show_dashboard(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_profile_edit_name_or_email_start(
    bot, call: CallbackQuery, field: str
) -> None:
    if field in {"first_name", "last_name"} and not bool(
        db.get_global_setting("allow_profile_name_edit", False)
    ):
        bot.answer_callback_query(call.id, "Name editing is disabled by admin")
        return
    if field == "email" and not bool(
        db.get_global_setting("allow_profile_email_edit", False)
    ):
        bot.answer_callback_query(call.id, "Email editing is disabled by admin")
        return
    step_name = f"profile_edit_{field}"
    registration_state[call.from_user.id] = {"step": step_name}
    label = field.replace("_", " ").title()
    edit_or_send_message(
        bot,
        call.message.chat.id,
        f"Send new {label}:",
        reply_markup=navigation_markup(back="profile_edit_menu", cancel=True),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_profile_edit_name_or_email_input(bot, message: Message, field: str) -> None:
    state = registration_state.get(message.from_user.id)
    step_name = f"profile_edit_{field}"
    if not state or state.get("step") != step_name:
        return

    value = (message.text or "").strip()
    if not value:
        bot.send_message(message.chat.id, "Value cannot be empty.")
        return
    if field == "email" and not utils.is_valid_email(value.lower()):
        bot.send_message(message.chat.id, "Invalid email format.")
        return

    payload = {field: value.lower() if field == "email" else value}
    ok = db.update_user(message.from_user.id, payload)
    clear_state(message.from_user.id)
    if ok:
        bot.send_message(message.chat.id, "✅ Profile updated.")
    else:
        bot.send_message(message.chat.id, "No changes were applied.")
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_notif_settings(bot, call: CallbackQuery) -> None:
    pref = db.get_user_pref(call.from_user.id)
    enabled = pref.get("reminders_enabled", True)
    hours = pref.get("reminder_hours", [24, 2])
    text = f"🔔 Notifications\nEnabled: {'Yes' if enabled else 'No'}\nHours before deadline: {', '.join(str(h) for h in hours)}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Toggle On/Off", callback_data="notif_toggle"))
    markup.add(
        InlineKeyboardButton("Set reminder hours", callback_data="notif_set_hours")
    )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_notif_toggle(bot, call: CallbackQuery) -> None:
    pref = db.get_user_pref(call.from_user.id)
    new_val = not pref.get("reminders_enabled", True)
    db.set_user_pref(call.from_user.id, {"reminders_enabled": new_val})
    bot.answer_callback_query(
        call.id, f"Notifications {'enabled' if new_val else 'disabled'}"
    )
    handle_notif_settings(bot, call)


def handle_notif_set_hours(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "notif_hours"}
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Send reminder hours separated by commas. Example: 24,6,2",
        reply_markup=navigation_markup(back="notif_settings", cancel=True),
        edit_message=call.message,
    )
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
        bot.send_message(
            message.chat.id, "Please provide at least one hour value between 1 and 168."
        )
        return
    db.set_user_pref(message.from_user.id, {"reminder_hours": hours})
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Reminder preferences updated.")
    show_dashboard(bot, message.from_user.id, message.chat.id)


def handle_my_tasks(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
    bot.edit_message_text(
        "📌 My Tasks",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=tasks_menu_markup(),
    )
    bot.answer_callback_query(call.id)


def _task_status_for_user(task: Dict, user_id: int) -> str:
    submission = db.get_submission(str(task["_id"]), user_id)
    if submission and submission.get("status") == config.TASK_STATUS_DONE:
        return config.TASK_STATUS_COMPLETED
    return config.TASK_STATUS_ONGOING


def _task_list_for_user(user: Dict, requested_status: str) -> List[Dict]:
    result: List[Dict] = []
    for task in db.get_tasks_for_user(user):
        effective = (
            config.TASK_STATUS_COMPLETED
            if task.get("status") == config.TASK_STATUS_COMPLETED
            else _task_status_for_user(task, user["telegram_id"])
        )
        if effective == requested_status:
            result.append(task)
    return result


def handle_task_list(bot, call: CallbackQuery, status: str) -> None:
    if not require_profile_access_callback(bot, call):
        return
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return
    wanted = (
        config.TASK_STATUS_ONGOING
        if status == "ONGOING"
        else config.TASK_STATUS_COMPLETED
    )
    tasks = _task_list_for_user(user, wanted)
    if not tasks:
        bot.edit_message_text(
            f"No {wanted.lower()} tasks.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=navigation_markup(back="my_tasks"),
        )
        bot.answer_callback_query(call.id)
        return

    markup = InlineKeyboardMarkup()
    for t in tasks:
        markup.add(
            InlineKeyboardButton(
                f"📄 {t.get('title', 'Untitled')}", callback_data=f"task|{t['_id']}"
            )
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="my_tasks"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        f"{wanted.title()} Tasks",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_task_detail(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
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
        markup.add(
            InlineKeyboardButton("✅ Submit Task", callback_data=f"submit|{task_id}")
        )
    if task.get("attachments"):
        markup.add(
            InlineKeyboardButton(
                "📎 View task attachments", callback_data=f"taskatt|{task_id}"
            )
        )
    markup.add(
        InlineKeyboardButton(
            "💬 Task Discussion",
            callback_data=f"thread_open|{task_id}|{call.from_user.id}",
        )
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="tasks_ongoing"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
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
            bot.send_document(
                call.message.chat.id,
                item["file_id"],
                caption=item.get("file_name", "attachment"),
            )
        except Exception:
            continue


# Submission flow


def handle_submit_task(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    user = db.get_user(call.from_user.id)
    if not task or not user:
        bot.answer_callback_query(call.id, "Task not found")
        return
    registration_state[call.from_user.id] = {
        "step": "submit_work_url",
        "task_id": task_id,
        "submission": {"files": [], "custom_fields": []},
    }
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Send GitHub or Figma URL (example: https://github.com/user/repo):",
        reply_markup=navigation_markup(back=f"task|{task_id}"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_thread_open(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
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
    markup.add(
        InlineKeyboardButton(
            "✍️ Send Message", callback_data=f"thread_write|{task_id}|{user_id}"
        )
    )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "\n".join(lines),
        reply_markup=markup,
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_thread_write(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
    parts = call.data.split("|")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Invalid thread")
        return
    task_id = parts[1]
    user_id = int(parts[2])
    registration_state[call.from_user.id] = {
        "step": "thread_message",
        "task_id": task_id,
        "thread_user_id": user_id,
    }
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Send your thread message:",
        reply_markup=navigation_markup(cancel=True),
        edit_message=call.message,
    )
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
    db.add_thread_message(
        task_id, thread_user_id, message.from_user.id, sender.get("role", "user"), text
    )
    clear_state(message.from_user.id)
    task = db.get_task(task_id)
    task_title = task.get("title", "Task") if task else "Task"
    interns = db.get_user(thread_user_id)
    intern_name = short_name(interns) if interns else str(thread_user_id)
    recipients = {thread_user_id}
    admins = db.get_users_by_role("admin")
    for admin in admins:
        recipients.add(admin["telegram_id"])
    # Notify admins with a direct Open Thread button so they don't need task IDs.
    for admin in admins:
        try:
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(
                    "💬 Open Thread",
                    callback_data=f"thread_open|{task_id}|{thread_user_id}",
                )
            )
            bot.send_message(
                admin["telegram_id"],
                f"💬 New user message\nTask: {task_title}\nIntern: {intern_name}\nMessage: {text}",
                reply_markup=markup,
            )
        except Exception:
            continue
    notify_users(
        bot, [thread_user_id], f"💬 New thread message on '{task_title}': {text}"
    )
    bot.send_message(message.chat.id, "✅ Thread message sent.")


def handle_admin_threads_menu(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    # Show latest thread per task/user, including threads before submissions.
    threads = list(db.task_threads.find().sort("updated_at", -1).limit(30))
    if not threads:
        bot.edit_message_text(
            "No task threads yet.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=navigation_markup(back="admin_panel"),
        )
        bot.answer_callback_query(call.id)
        return
    markup = InlineKeyboardMarkup()
    for thread in threads:
        task_id = thread.get("task_id")
        user_id = thread.get("user_id")
        task = db.get_task(task_id)
        user = db.get_user(user_id)
        title = (task or {}).get("title", "Unknown Task")
        uname = short_name(user) if user else str(user_id)
        markup.add(
            InlineKeyboardButton(
                f"{title} - {uname}", callback_data=f"thread_open|{task_id}|{user_id}"
            )
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        "💬 Task Threads",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_submit_work_url(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_work_url":
        return
    url = message.text.strip()
    if not utils.is_valid_url(url):
        bot.send_message(
            message.chat.id, "Please send a valid URL (http:// or https://)."
        )
        return
    state["submission"]["work_url"] = url
    state["step"] = "submit_deployed"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Yes", callback_data="submit_deployed_yes"))
    markup.add(InlineKeyboardButton("❌ No", callback_data="submit_deployed_no"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        message.chat.id, "Is this task deployed/live?", reply_markup=markup
    )


def handle_submit_deployed_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_deployed":
        return
    has_demo = call.data.endswith("yes")
    state["submission"]["is_deployed"] = has_demo
    if has_demo:
        state["step"] = "submit_demo_url"
        bot.send_message(
            call.message.chat.id,
            "Send live demo URL (example: https://myapp.vercel.app):",
            reply_markup=navigation_markup(cancel=True),
        )
    else:
        state["submission"]["demo_url"] = None
        state["step"] = "submit_learned"
        bot.send_message(
            call.message.chat.id,
            "What did you learn from this task? (example: I learned API pagination and better state handling.)",
            reply_markup=navigation_markup(cancel=True),
        )
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
    bot.send_message(
        message.chat.id,
        "What did you learn from this task? (example: I learned API pagination and better state handling.)",
        reply_markup=navigation_markup(cancel=True),
    )


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
    bot.send_message(
        message.chat.id,
        "Rate task importance from 1 to 10 (example: 8):",
        reply_markup=navigation_markup(cancel=True),
    )


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
    markup.add(
        InlineKeyboardButton("➕ Add custom field", callback_data="submit_custom_yes")
    )
    markup.add(InlineKeyboardButton("➡️ Continue", callback_data="submit_custom_no"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        message.chat.id,
        "Do you want to add any extra field (name + data)?",
        reply_markup=markup,
    )


def handle_submit_custom_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_custom_field_ask":
        return
    if call.data == "submit_custom_yes":
        state["step"] = "submit_custom_name"
        bot.send_message(
            call.message.chat.id,
            "Enter custom field name (example: Figma Prototype):",
            reply_markup=navigation_markup(cancel=True),
        )
    else:
        state["step"] = "submit_assets_choice"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "✅ Yes, I have files", callback_data="submit_assets_yes"
            )
        )
        markup.add(
            InlineKeyboardButton("⏭️ No extra files", callback_data="submit_assets_no")
        )
        markup.row(
            InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
        )
        bot.send_message(
            call.message.chat.id,
            (
                "Do you want to include PDFs/images/other files?\n"
                "Please upload them to Google Drive, set permission to 'Anyone with the link', then share the folder/file link here."
            ),
            reply_markup=markup,
        )
    bot.answer_callback_query(call.id)


def handle_submit_assets_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_assets_choice":
        return
    if call.data == "submit_assets_yes":
        state["step"] = "submit_drive_link"
        bot.send_message(
            call.message.chat.id,
            "Send your Google Drive share link (example: https://drive.google.com/drive/folders/xxxxx, accessible to Anyone with the link):",
            reply_markup=navigation_markup(cancel=True),
        )
    else:
        state["submission"]["drive_assets_link"] = None
        _finalize_submission(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def handle_submit_drive_link(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_drive_link":
        return
    link = message.text.strip()
    if not utils.is_valid_url(link):
        bot.send_message(message.chat.id, "Please send a valid Google Drive URL.")
        return
    state["submission"]["drive_assets_link"] = link
    _finalize_submission(bot, message.from_user.id, message.chat.id)


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
    bot.send_message(
        message.chat.id,
        f"Enter value for '{name}' (example: https://figma.com/file/abc123):",
        reply_markup=navigation_markup(cancel=True),
    )


def handle_submit_custom_value(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_custom_value":
        return
    val = message.text.strip()
    if not val:
        bot.send_message(message.chat.id, "Value cannot be empty.")
        return
    state["submission"]["custom_fields"].append(
        {"name": state.pop("current_custom_name"), "value": val}
    )
    state["step"] = "submit_custom_field_ask"
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕ Add another field", callback_data="submit_custom_yes")
    )
    markup.add(InlineKeyboardButton("➡️ Continue", callback_data="submit_custom_no"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        message.chat.id, "Custom field added ✅. Add another?", reply_markup=markup
    )


def _prompt_submission_files(bot, chat_id: int) -> None:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Done uploading", callback_data="submit_files_done")
    )
    markup.add(InlineKeyboardButton("⏭️ Skip files", callback_data="submit_files_skip"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        chat_id,
        "Upload multiple files now (images, PDFs, docs). When finished click Done uploading.",
        reply_markup=markup,
    )


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
        bot.send_message(
            message.chat.id, "Unsupported file. Upload image/document/pdf/doc/docx."
        )
        return

    state["submission"]["files"].append(item)
    bot.send_message(
        message.chat.id, f"File added ✅ ({len(state['submission']['files'])} total)"
    )


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
        "drive_assets_link": sub.get("drive_assets_link"),
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
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Enter intern email:",
        reply_markup=navigation_markup(back="admin_panel"),
        edit_message=call.message,
    )
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
        markup.add(
            InlineKeyboardButton(
                role_label(role), callback_data=f"admin_add_role|{role}"
            )
        )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
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
        bot.edit_message_text(
            f"✅ Allowed intern added\nEmail: {email}\nRole: {role_label(role)}",
            call.message.chat.id,
            call.message.message_id,
        )
    else:
        bot.edit_message_text(
            "Failed to add intern.", call.message.chat.id, call.message.message_id
        )
    bot.answer_callback_query(call.id)


# Admin assign task with attachments


def handle_admin_assign_task(bot, source) -> None:
    if not require_profile_access_source(bot, source):
        return
    user_id = source.from_user.id
    chat_id = (
        source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    )
    edit_message = source.message if isinstance(source, CallbackQuery) else None
    if not is_admin(user_id):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return
    registration_state[user_id] = {
        "step": "admin_task_title",
        "task": {"assigned_user_ids": [], "assigned_roles": [], "attachments": []},
    }
    edit_or_send_message(
        bot,
        chat_id,
        "Enter task title (example: Build User Dashboard):",
        reply_markup=navigation_markup(back="admin_panel"),
        edit_message=edit_message,
    )
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
    bot.send_message(
        message.chat.id,
        "Enter task description (example: Implement responsive dashboard with charts and filters):",
        reply_markup=navigation_markup(cancel=True),
    )


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
    bot.send_message(
        message.chat.id,
        "Enter deadline in YYYY-MM-DD (example: 2026-04-10):",
        reply_markup=navigation_markup(cancel=True),
    )


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
    markup.add(
        InlineKeyboardButton(
            "📎 Add attachments", callback_data="admin_task_attach_yes"
        )
    )
    markup.add(InlineKeyboardButton("⏭️ Skip", callback_data="admin_task_attach_no"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.send_message(
        message.chat.id,
        "Attach task files (PDF/DOC/DOCX) if available?",
        reply_markup=markup,
    )


def handle_admin_task_attach_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_attach_ask":
        return
    if call.data == "admin_task_attach_yes":
        state["step"] = "admin_task_attach_files"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "✅ Done uploading", callback_data="admin_task_attach_done"
            )
        )
        markup.add(
            InlineKeyboardButton("⏭️ Skip", callback_data="admin_task_attach_skip")
        )
        markup.row(
            InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
        )
        edit_or_send_message(
            bot,
            call.message.chat.id,
            "Upload PDF/DOC/DOCX files now. Click Done when finished.",
            reply_markup=markup,
            edit_message=call.message,
        )
    else:
        state["step"] = "admin_task_assign_type"
        _send_assign_type_prompt(bot, call.message.chat.id, edit_message=call.message)
    bot.answer_callback_query(call.id)


def handle_admin_task_attachment_file(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_attach_files":
        return
    if not message.document:
        bot.send_message(
            message.chat.id, "Please upload a document file (PDF/DOC/DOCX)."
        )
        return
    doc = message.document
    fname = (doc.file_name or "").lower()
    allowed = (
        fname.endswith(".pdf") or fname.endswith(".doc") or fname.endswith(".docx")
    )
    if not allowed:
        bot.send_message(
            message.chat.id, "Only PDF/DOC/DOCX allowed for task attachments."
        )
        return
    state["task"]["attachments"].append(
        {
            "file_id": doc.file_id,
            "file_name": doc.file_name,
            "mime_type": doc.mime_type or "application/octet-stream",
        }
    )
    bot.send_message(
        message.chat.id,
        f"Attachment added ✅ ({len(state['task']['attachments'])} total)",
    )


def handle_admin_task_attachment_action(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_attach_files":
        return
    state["step"] = "admin_task_assign_type"
    _send_assign_type_prompt(bot, call.message.chat.id, edit_message=call.message)
    bot.answer_callback_query(call.id)


def _send_assign_type_prompt(
    bot, chat_id: int, edit_message: Optional[Message] = None
) -> None:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "🟦 Assign to Role", callback_data="admin_assign_type|role"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "✅ Assign to User(s)", callback_data="admin_assign_type|users"
        )
    )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot,
        chat_id,
        "How do you want to assign this task?",
        reply_markup=markup,
        edit_message=edit_message,
    )


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
            markup.add(
                InlineKeyboardButton(
                    role_label(role), callback_data=f"admin_task_role|{role}"
                )
            )
        markup.row(
            InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
        )
        edit_or_send_message(
            bot,
            call.message.chat.id,
            "Select role:",
            reply_markup=markup,
            edit_message=call.message,
        )
    else:
        state["step"] = "admin_task_select_users"
        state["user_page"] = 0
        _show_user_picker(bot, call.message.chat.id, state, edit_message=call.message)
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


def _show_user_picker(
    bot, chat_id: int, state: Dict, edit_message: Optional[Message] = None
) -> None:
    page = state.get("user_page", 0)
    per_page = 6
    users = db.get_users_paginated(skip=page * per_page, limit=per_page)
    selected = set(state["task"].get("assigned_user_ids", []))
    markup = InlineKeyboardMarkup()
    for u in users:
        uid = u["telegram_id"]
        mark = "✅" if uid in selected else "⬜"
        markup.add(
            InlineKeyboardButton(
                f"{mark} {short_name(u)} ({role_label(u.get('role', ''))})",
                callback_data=f"admin_pick_user|{uid}",
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton("Prev", callback_data=f"admin_user_page|{page - 1}")
        )
    if len(users) == per_page:
        nav.append(
            InlineKeyboardButton("Next", callback_data=f"admin_user_page|{page + 1}")
        )
    if nav:
        markup.row(*nav)
    markup.add(InlineKeyboardButton("✅ Done", callback_data="admin_users_done"))
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot,
        chat_id,
        "Select user(s). Tap to toggle:",
        reply_markup=markup,
        edit_message=edit_message,
    )


def handle_admin_user_page(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return
    _, p = call.data.split("|", 1)
    state["user_page"] = max(0, int(p))
    _show_user_picker(bot, call.message.chat.id, state, edit_message=call.message)
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

    notify_users(
        bot,
        list(targets),
        f"✅ New task: {task['title']}\nDeadline: {task['deadline']}",
    )
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
    if not require_profile_access_source(bot, source):
        return
    uid = source.from_user.id
    chat_id = (
        source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    )
    if not is_admin(uid):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return
    _show_admin_review_page(bot, chat_id, page=0, edit_message=None)
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def _show_admin_review_page(bot, chat_id: int, page: int, edit_message) -> None:
    items = [
        s
        for s in db.list_submissions()
        if s.get("status")
        in {config.TASK_STATUS_SUBMITTED, config.TASK_STATUS_ON_REVIEW}
    ]
    if not items:
        if edit_message:
            bot.edit_message_text(
                "No submissions waiting for review.",
                edit_message.chat.id,
                edit_message.message_id,
            )
        else:
            bot.send_message(chat_id, "No submissions waiting for review.")
        return
    per_page = 8
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]
    markup = InlineKeyboardMarkup()
    for s in page_items:
        user = db.get_user(s["user_id"])
        task = db.get_task(s["task_id"])
        if not user or not task:
            continue
        submitted_at = s.get("submitted_at") or s.get("updated_at")
        date_text = (
            submitted_at.strftime("%Y-%m-%d")
            if hasattr(submitted_at, "strftime")
            else "N/A"
        )
        label = f"📥 {date_text} | {short_name(user)} - {task.get('title', '')}"
        markup.add(
            InlineKeyboardButton(
                label, callback_data=f"admin_review_item|{s['task_id']}|{s['user_id']}"
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton("Prev", callback_data=f"admin_review_page|{page - 1}")
        )
    if end < len(items):
        nav.append(
            InlineKeyboardButton("Next", callback_data=f"admin_review_page|{page + 1}")
        )
    if nav:
        markup.row(*nav)
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    text = f"Select submission (page {page + 1}):"
    if edit_message:
        bot.edit_message_text(
            text, edit_message.chat.id, edit_message.message_id, reply_markup=markup
        )
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def handle_admin_review_page(bot, call: CallbackQuery) -> None:
    _, raw_page = call.data.split("|", 1)
    page = max(0, int(raw_page))
    _show_admin_review_page(
        bot, call.message.chat.id, page=page, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


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
    markup.add(
        InlineKeyboardButton(
            "🟦 Mark On Review", callback_data=f"admin_mark_review|{task_id}|{user_id}"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "✅ Mark Done + Score", callback_data=f"admin_mark_done|{task_id}|{user_id}"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "📎 Send files to admin",
            callback_data=f"admin_send_sub_files|{task_id}|{user_id}",
        )
    )
    markup.add(
        InlineKeyboardButton(
            "🗒️ Add note", callback_data=f"admin_add_sub_note|{task_id}|{user_id}"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "💬 Open thread", callback_data=f"thread_open|{task_id}|{user_id}"
        )
    )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
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
                bot.send_photo(
                    call.message.chat.id,
                    f["file_id"],
                    caption=f.get("file_name", "image"),
                )
            else:
                bot.send_document(
                    call.message.chat.id,
                    f["file_id"],
                    caption=f.get("file_name", "file"),
                )
        except Exception:
            continue


def handle_admin_mark_review(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    db.update_submission(task_id, user_id, {"status": config.TASK_STATUS_ON_REVIEW})
    bot.edit_message_text(
        "Submission moved to ON_REVIEW ✅",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=navigation_markup(back="admin_review_menu"),
    )
    bot.answer_callback_query(call.id)


def handle_admin_mark_done(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    registration_state[call.from_user.id] = {
        "step": "admin_score",
        "target_task_id": task_id,
        "target_user_id": user_id,
    }
    edit_or_send_message(
        bot,
        call.message.chat.id,
        f"Enter score (0-{config.MAX_SCORE}) (example: 85):",
        reply_markup=navigation_markup(cancel=True),
        edit_message=call.message,
    )
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
    bot.send_message(
        message.chat.id,
        "Add optional review note (or type '-') (example: Great structure, improve error handling):",
        reply_markup=navigation_markup(cancel=True),
    )


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
    db.update_submission(
        task_id,
        user_id,
        {
            "status": config.TASK_STATUS_DONE,
            "review_score": score,
            "review_note": note,
            "reviewed_by": message.from_user.id,
            "reviewed_at": db.utcnow(),
        },
    )
    db.increment_user_score(user_id, score)
    task = db.get_task(task_id)
    title = task.get("title", "task") if task else "task"
    score_visible = bool(db.get_global_setting("score_visibility", True))
    review_msg = f"✅ Your submission for '{title}' was reviewed."
    if score_visible:
        review_msg += f" Score: {score}"
    review_msg += f"\nNote: {note or 'No note'}"
    notify_users(bot, [user_id], review_msg)
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "Submission marked done ✅")


def handle_admin_add_submission_note_start(bot, call: CallbackQuery) -> None:
    parsed = _parse_triplet(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return
    task_id, user_id = parsed
    registration_state[call.from_user.id] = {
        "step": "admin_sub_note",
        "target_task_id": task_id,
        "target_user_id": user_id,
    }
    bot.send_message(
        call.message.chat.id,
        "Write note for this submission (example: Please add README screenshots):",
        reply_markup=navigation_markup(cancel=True),
    )
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
    notes.append(
        {"admin_id": message.from_user.id, "note": note, "created_at": db.utcnow()}
    )
    db.update_submission(task_id, user_id, {"admin_notes": notes})
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Note saved.")


# Admin advanced tools


def handle_admin_panel(bot, call: CallbackQuery) -> None:
    if not require_profile_access_callback(bot, call):
        return
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    bot.edit_message_text(
        "🛠️ Admin Panel",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=admin_panel_markup(),
    )
    bot.answer_callback_query(call.id)


def _admin_category_markup(category: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    if category == "tasks":
        markup.add(
            InlineKeyboardButton("📝 Assign Task", callback_data="admin_assign_task")
        )
        markup.add(
            InlineKeyboardButton(
                "📥 Review Submissions", callback_data="admin_review_menu"
            )
        )
        markup.add(
            InlineKeyboardButton("💬 Task Threads", callback_data="admin_threads_menu")
        )
    elif category == "users":
        markup.add(
            InlineKeyboardButton("✅ Add Intern", callback_data="admin_add_intern")
        )
        markup.add(
            InlineKeyboardButton("👥 Manage Users", callback_data="admin_manage_users")
        )
        markup.add(
            InlineKeyboardButton("🧩 Manage Roles", callback_data="admin_manage_roles")
        )
        markup.add(
            InlineKeyboardButton("♻️ Restore Users", callback_data="admin_restore_users")
        )
    elif category == "settings":
        markup.add(
            InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")
        )
        markup.add(
            InlineKeyboardButton(
                "📢 Force Subscribe", callback_data="admin_force_sub_menu"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "🛂 Profile Edit Controls", callback_data="admin_profile_edit_controls"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "📝 Registration Control", callback_data="admin_registration_control"
            )
        )
    elif category == "reports":
        markup.add(
            InlineKeyboardButton(
                "📈 Stats Overview", callback_data="admin_stats_overview"
            )
        )
        markup.add(
            InlineKeyboardButton("🏆 Leaderboard", callback_data="admin_leaderboard")
        )
        markup.add(
            InlineKeyboardButton("📤 Export CSV", callback_data="admin_export_menu")
        )
        markup.add(
            InlineKeyboardButton(
                "🎯 Score Visibility", callback_data="admin_score_visibility"
            )
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    return markup


def handle_admin_category(bot, call: CallbackQuery, category: str) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    titles = {
        "tasks": "📋 Tasks & Reviews",
        "users": "👥 Users & Roles",
        "settings": "📣 Communication & Settings",
        "reports": "📊 Reports & Analytics",
    }
    bot.edit_message_text(
        titles.get(category, "Admin"),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=_admin_category_markup(category),
    )
    bot.answer_callback_query(call.id)


def handle_admin_stats_overview(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    users = db.list_users(include_banned=True)
    if not users:
        bot.edit_message_text(
            "No users available for stats.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=navigation_markup(back="admin_panel"),
        )
        bot.answer_callback_query(call.id)
        return

    role_counts: Dict[str, int] = {}
    gender_counts: Dict[str, int] = {}
    complete = 0
    for u in users:
        role = u.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        gender = u.get("gender") or "Not set"
        gender_counts[gender] = gender_counts.get(gender, 0) + 1
        if is_profile_complete(u):
            complete += 1

    role_lines = [
        f"- {role_label(role)}: {count}"
        for role, count in sorted(role_counts.items(), key=lambda x: x[0])
    ]
    gender_lines = [
        f"- {g}: {c}" for g, c in sorted(gender_counts.items(), key=lambda x: x[0])
    ]
    completion_rate = int((complete / len(users)) * 100)
    text = (
        "📈 Admin Stats\n"
        f"Total users: {len(users)}\n"
        f"Profile completed: {complete}/{len(users)} ({completion_rate}%)\n\n"
        "By role:\n"
        f"{'\n'.join(role_lines)}\n\n"
        "By gender:\n"
        f"{'\n'.join(gender_lines)}"
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=navigation_markup(back="admin_cat_reports"),
    )
    bot.answer_callback_query(call.id)


def handle_admin_profile_edit_controls(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    allow_name = bool(db.get_global_setting("allow_profile_name_edit", False))
    allow_email = bool(db.get_global_setting("allow_profile_email_edit", False))
    text = (
        "🛂 Profile Edit Controls\n"
        f"Name editing: {'ON' if allow_name else 'OFF'}\n"
        f"Email editing: {'ON' if allow_email else 'OFF'}"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "Toggle Name Editing", callback_data="admin_toggle_name_edit"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Toggle Email Editing", callback_data="admin_toggle_email_edit"
        )
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_cat_settings"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_admin_toggle_profile_edit_control(
    bot, call: CallbackQuery, key: str
) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    current = bool(db.get_global_setting(key, False))
    db.set_global_setting(key, not current)
    handle_admin_profile_edit_controls(bot, call)


def handle_admin_broadcast_start(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id
    edit_message = source.message if isinstance(source, CallbackQuery) else None

    if not is_admin(user_id):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return

    registration_state[user_id] = {
        "step": "admin_broadcast_filter",
        "broadcast_filter": {
            "roles": [],
            "gender": "all",
            "profile": "all",
            "country_mode": "all",
            "country_value": "",
        },
    }
    _show_admin_broadcast_filter_menu(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        edit_message=edit_message,
    )
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def _normalize(v: str) -> str:
    return (v or "").strip().lower()


def _broadcast_matches_user(user: Dict, filters: Dict) -> bool:
    selected_roles = filters.get("roles", [])
    if selected_roles and user.get("role") not in selected_roles:
        return False

    gender_filter = filters.get("gender", "all")
    user_gender = _normalize(user.get("gender", ""))
    if gender_filter == "not_set" and user_gender:
        return False
    if gender_filter not in {"all", "not_set"} and user_gender != gender_filter:
        return False

    profile_filter = filters.get("profile", "all")
    complete = is_profile_complete(user)
    if profile_filter == "complete" and not complete:
        return False
    if profile_filter == "incomplete" and complete:
        return False

    country_mode = filters.get("country_mode", "all")
    user_country = _normalize(user.get("current_country", ""))
    if country_mode == "set" and not user_country:
        return False
    if country_mode == "unset" and user_country:
        return False
    if country_mode == "exact":
        target = _normalize(filters.get("country_value", ""))
        if not target or user_country != target:
            return False

    return True


def _broadcast_filter_summary(filters: Dict) -> str:
    roles = filters.get("roles", [])
    roles_label = "All" if not roles else ", ".join(role_label(r) for r in roles)

    gender_raw = filters.get("gender", "all")
    if gender_raw == "all":
        gender_label = "All"
    elif gender_raw == "not_set":
        gender_label = "Not set"
    else:
        gender_label = gender_raw.title()

    profile_raw = filters.get("profile", "all")
    profile_map = {
        "all": "All",
        "complete": "Completed profiles only",
        "incomplete": "Incomplete profiles only",
    }
    profile_label = profile_map.get(profile_raw, "All")

    country_mode = filters.get("country_mode", "all")
    if country_mode == "all":
        country_label = "All"
    elif country_mode == "set":
        country_label = "Country is set"
    elif country_mode == "unset":
        country_label = "Country is not set"
    else:
        country_label = (
            filters.get("country_value", "").strip() or "Exact country (not set)"
        )

    return (
        f"Roles: {roles_label}\n"
        f"Gender: {gender_label}\n"
        f"Profile: {profile_label}\n"
        f"Country: {country_label}"
    )


def _show_admin_broadcast_filter_menu(
    bot,
    user_id: int,
    chat_id: int,
    edit_message: Optional[Message] = None,
) -> None:
    state = registration_state.get(user_id)
    if not state:
        return
    filters = state.setdefault(
        "broadcast_filter",
        {
            "roles": [],
            "gender": "all",
            "profile": "all",
            "country_mode": "all",
            "country_value": "",
        },
    )

    users = db.list_users(include_banned=False)
    matched = sum(1 for u in users if _broadcast_matches_user(u, filters))

    text = (
        "📣 Broadcast Audience Filters\n"
        f"Matched users: {matched}\n\n"
        f"{_broadcast_filter_summary(filters)}\n\n"
        "Toggle options, then continue."
    )

    selected_roles = set(filters.get("roles", []))
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "Roles (multi-select)", callback_data="admin_broadcast_filter_menu"
        )
    )
    for role in get_active_roles(include_admin=False):
        mark = "✅" if role in selected_roles else "⬜"
        markup.add(
            InlineKeyboardButton(
                f"{mark} {role_label(role)}",
                callback_data=f"admin_broadcast_role_toggle|{role}",
            )
        )
    markup.add(
        InlineKeyboardButton("Clear Roles", callback_data="admin_broadcast_roles_clear")
    )

    markup.add(
        InlineKeyboardButton("Gender: All", callback_data="admin_broadcast_gender|all")
    )
    markup.add(
        InlineKeyboardButton(
            "Gender: Not set", callback_data="admin_broadcast_gender|not_set"
        )
    )
    for g in GENDER_OPTIONS:
        markup.add(
            InlineKeyboardButton(
                f"Gender: {g}", callback_data=f"admin_broadcast_gender|{_normalize(g)}"
            )
        )

    markup.add(
        InlineKeyboardButton(
            "Profile: All", callback_data="admin_broadcast_profile|all"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Profile: Completed", callback_data="admin_broadcast_profile|complete"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Profile: Incomplete", callback_data="admin_broadcast_profile|incomplete"
        )
    )

    markup.add(
        InlineKeyboardButton(
            "Country: All", callback_data="admin_broadcast_country_mode|all"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Country: Set", callback_data="admin_broadcast_country_mode|set"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Country: Not set", callback_data="admin_broadcast_country_mode|unset"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "Country: Exact (type)",
            callback_data="admin_broadcast_country_exact_prompt",
        )
    )

    markup.add(
        InlineKeyboardButton(
            "Continue To Message", callback_data="admin_broadcast_continue"
        )
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_cat_settings"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))

    edit_or_send_message(
        bot, chat_id, text, reply_markup=markup, edit_message=edit_message
    )


def handle_admin_broadcast_filter_menu(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") not in {
        "admin_broadcast_filter",
        "admin_broadcast_country_input",
    }:
        bot.answer_callback_query(call.id)
        return
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_role_toggle(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") not in {
        "admin_broadcast_filter",
        "admin_broadcast_country_input",
    }:
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id)
        return
    role = parts[1]
    if role not in get_active_roles(include_admin=False):
        bot.answer_callback_query(call.id, "Invalid role")
        return
    filters = state.setdefault("broadcast_filter", {})
    roles = set(filters.get("roles", []))
    if role in roles:
        roles.remove(role)
    else:
        roles.add(role)
    filters["roles"] = sorted(roles)
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_roles_clear(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    filters = state.setdefault("broadcast_filter", {})
    filters["roles"] = []
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id, "Roles cleared")


def handle_admin_broadcast_gender(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id)
        return
    filters = state.setdefault("broadcast_filter", {})
    filters["gender"] = parts[1]
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_profile(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id)
        return
    filters = state.setdefault("broadcast_filter", {})
    filters["profile"] = parts[1]
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_country_mode(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id)
        return
    mode = parts[1]
    if mode not in {"all", "set", "unset"}:
        bot.answer_callback_query(call.id)
        return
    filters = state.setdefault("broadcast_filter", {})
    filters["country_mode"] = mode
    if mode != "exact":
        filters["country_value"] = ""
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(
        bot, call.from_user.id, call.message.chat.id, edit_message=call.message
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_country_exact_prompt(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    state["step"] = "admin_broadcast_country_input"
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Type exact country name to filter by (example: Kenya).",
        reply_markup=navigation_markup(back="admin_broadcast_filter_menu"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_country_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_broadcast_country_input":
        return
    country = (message.text or "").strip()
    if not country:
        bot.send_message(message.chat.id, "Country cannot be empty.")
        return
    filters = state.setdefault("broadcast_filter", {})
    filters["country_mode"] = "exact"
    filters["country_value"] = country
    state["step"] = "admin_broadcast_filter"
    _show_admin_broadcast_filter_menu(bot, message.from_user.id, message.chat.id)


def handle_admin_broadcast_continue(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state:
        bot.answer_callback_query(call.id)
        return
    state["step"] = "admin_broadcast"
    filters = state.get("broadcast_filter", {})
    edit_or_send_message(
        bot,
        call.message.chat.id,
        (
            "Send broadcast message text (example: Daily standup starts in 30 minutes):\n\n"
            "Current audience filter:\n"
            f"{_broadcast_filter_summary(filters)}"
        ),
        reply_markup=navigation_markup(back="admin_broadcast_filter_menu"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_broadcast_message(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_broadcast":
        return
    text = message.text.strip()
    if not text:
        bot.send_message(message.chat.id, "Message cannot be empty.")
        return
    filters = state.get(
        "broadcast_filter",
        {
            "roles": [],
            "gender": "all",
            "profile": "all",
            "country_mode": "all",
            "country_value": "",
        },
    )
    users = db.list_users(include_banned=False)
    target_users = [u for u in users if _broadcast_matches_user(u, filters)]
    success = 0
    for u in target_users:
        try:
            bot.send_message(u["telegram_id"], f"📣 Broadcast\n\n{text}")
            success += 1
        except Exception:
            continue
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        (
            f"✅ Broadcast sent to {success} users.\n"
            f"Matched audience: {len(target_users)}\n"
            f"Filter used:\n{_broadcast_filter_summary(filters)}"
        ),
    )


def handle_admin_manage_users(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    _show_user_manage_page(bot, call.message.chat.id, 0, edit_message=call.message)
    bot.answer_callback_query(call.id)


def _show_user_manage_page(
    bot, chat_id: int, page: int, edit_message: Optional[Message] = None
) -> None:
    per = 8
    users = db.get_users_paginated(skip=page * per, limit=per)
    markup = InlineKeyboardMarkup()
    for u in users:
        badge = "⛔" if u.get("is_banned") else "✅"
        markup.add(
            InlineKeyboardButton(
                f"{badge} {short_name(u)} ({role_label(u.get('role', ''))})",
                callback_data=f"admin_user_view|{u['telegram_id']}",
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton("Prev", callback_data=f"admin_users_page|{page - 1}")
        )
    if len(users) == per:
        nav.append(
            InlineKeyboardButton("Next", callback_data=f"admin_users_page|{page + 1}")
        )
    if nav:
        markup.row(*nav)
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot, chat_id, "👥 Manage users:", reply_markup=markup, edit_message=edit_message
    )


def handle_admin_users_page(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    _show_user_manage_page(
        bot, call.message.chat.id, max(0, int(raw)), edit_message=call.message
    )
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
        markup.add(
            InlineKeyboardButton("✅ Unban", callback_data=f"admin_unban_user|{uid}")
        )
    else:
        markup.add(
            InlineKeyboardButton("⛔ Ban", callback_data=f"admin_ban_user|{uid}")
        )
    markup.add(
        InlineKeyboardButton("🟦 Change Role", callback_data=f"admin_change_role|{uid}")
    )
    markup.add(
        InlineKeyboardButton("❌ Remove User", callback_data=f"admin_remove_user|{uid}")
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_users"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    edit_or_send_message(
        bot, call.message.chat.id, text, reply_markup=markup, edit_message=call.message
    )
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
    text = "✅ User updated." if ok else "Failed to update user."
    edit_or_send_message(
        bot,
        call.message.chat.id,
        text,
        reply_markup=navigation_markup(back="admin_manage_users"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_remove_user(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    if uid == call.from_user.id:
        bot.answer_callback_query(call.id)
        edit_or_send_message(
            bot,
            call.message.chat.id,
            "You cannot remove yourself.",
            edit_message=call.message,
        )
        return
    ok = db.soft_delete_user(uid, deleted_by=call.from_user.id)
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "✅ User soft-deleted." if ok else "Failed to remove user.",
        reply_markup=navigation_markup(back="admin_manage_users"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


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
        markup.add(
            InlineKeyboardButton(
                f"♻️ Restore {short_name(u)}",
                callback_data=f"admin_restore_user|{u['telegram_id']}",
            )
        )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Deleted users:",
        reply_markup=markup,
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_restore_user(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    ok = db.restore_user(uid)
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "✅ User restored." if ok else "Failed to restore user.",
        reply_markup=navigation_markup(back="admin_restore_users"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_change_role(bot, call: CallbackQuery) -> None:
    _, raw = call.data.split("|", 1)
    uid = int(raw)
    markup = InlineKeyboardMarkup()
    for role in get_active_roles(include_admin=True):
        markup.add(
            InlineKeyboardButton(
                role_label(role), callback_data=f"admin_set_role|{uid}|{role}"
            )
        )
    markup.row(
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"),
    )
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Select new role:",
        reply_markup=markup,
        edit_message=call.message,
    )
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
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "✅ Role updated." if ok else "Failed to update role.",
        reply_markup=navigation_markup(back="admin_manage_users"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_force_sub_menu(bot, call: CallbackQuery) -> None:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    join_hint = cfg.get("join_hint") or "Not set"
    text = (
        "📢 Force Subscription\n"
        f"Enabled: {'Yes' if cfg.get('enabled') else 'No'}\n"
        f"Channel Ref: {cfg.get('channel') or 'Not set'}\n"
        f"Join Link/Hint: {join_hint}"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Set channel", callback_data="admin_force_set_channel")
    )
    markup.add(
        InlineKeyboardButton("Toggle On/Off", callback_data="admin_force_toggle")
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_admin_force_set_channel(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "admin_set_channel"}
    edit_or_send_message(
        bot,
        call.message.chat.id,
        (
            "Send channel reference for force-subscription.\n"
            "Formats:\n"
            "1) @public_channel\n"
            "2) -1001234567890 (private channel ID)\n"
            "Optional: add invite link after it, e.g.\n"
            "-1001234567890 https://t.me/+abcdef"
        ),
        reply_markup=navigation_markup(back="admin_force_sub_menu"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_set_channel_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_set_channel":
        return
    channel, join_hint, err = _parse_force_channel_input((message.text or "").strip())
    if err:
        bot.send_message(message.chat.id, err)
        return

    # Validate bot access to the channel reference before saving.
    try:
        bot.get_chat(channel)
    except Exception:
        bot.send_message(
            message.chat.id,
            "Bot cannot access that channel. Add the bot to the channel as admin and send a valid @username or -100... ID.",
        )
        return

    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    cfg["channel"] = channel
    cfg["join_hint"] = join_hint
    db.set_global_setting("force_subscription", cfg)
    clear_state(message.from_user.id)
    if join_hint:
        bot.send_message(
            message.chat.id,
            f"✅ Channel set to {channel}\nJoin hint set to: {join_hint}",
        )
    else:
        bot.send_message(message.chat.id, f"✅ Channel set to {channel}")


def handle_admin_force_toggle(bot, call: CallbackQuery) -> None:
    cfg = db.get_global_setting("force_subscription", {"enabled": False, "channel": ""})
    cfg["enabled"] = not bool(cfg.get("enabled"))
    db.set_global_setting("force_subscription", cfg)
    bot.answer_callback_query(call.id)
    handle_admin_force_sub_menu(bot, call)


def handle_admin_registration_menu(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    is_open = is_registration_open()
    text = f"📝 Registration Control\nStatus: {'OPEN' if is_open else 'CLOSED'}"
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "Toggle Open/Closed", callback_data="admin_registration_toggle"
        )
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_cat_settings"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_admin_registration_toggle(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    current = is_registration_open()
    db.set_global_setting("registration_open", not current)
    bot.answer_callback_query(
        call.id, f"Registration {'OPENED' if not current else 'CLOSED'}"
    )
    handle_admin_registration_menu(bot, call)


def handle_admin_reply_command(bot, message: Message) -> None:
    if not require_profile_access_source(bot, message):
        return
    txt = (message.text or "").strip()
    parts = txt.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: /admin your message")
        return
    payload = parts[1]

    if is_admin(message.from_user.id) and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if _send_contact_message(
            bot, message.from_user.id, target_id, payload, sender_is_admin=True
        ):
            bot.send_message(message.chat.id, "✅ Message sent.")
        else:
            bot.send_message(message.chat.id, "Failed to send message.")
        return

    admins = db.get_users_by_role("admin")
    if not admins:
        bot.send_message(message.chat.id, "No admin available now. Please try later.")
        return
    forwarded = 0
    for admin in admins:
        if _send_contact_message(
            bot,
            message.from_user.id,
            admin["telegram_id"],
            payload,
            sender_is_admin=False,
        ):
            forwarded += 1
    if forwarded:
        bot.send_message(message.chat.id, "✅ Message sent to admin.")
    else:
        bot.send_message(message.chat.id, "Failed to reach admin.")


def handle_contact_reply_start(bot, call: CallbackQuery) -> None:
    parts = call.data.split("|", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id)
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        bot.answer_callback_query(call.id)
        return

    if not is_admin(call.from_user.id) and not is_admin(target_id):
        bot.answer_callback_query(call.id)
        return

    registration_state[call.from_user.id] = {
        "step": "contact_reply",
        "target_user_id": target_id,
    }
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Type your reply message:",
        reply_markup=navigation_markup(cancel=True),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_contact_reply_input(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "contact_reply":
        return
    text = (message.text or "").strip()
    if not text:
        bot.send_message(message.chat.id, "Message cannot be empty.")
        return

    target_id = state.get("target_user_id")
    if not isinstance(target_id, int):
        clear_state(message.from_user.id)
        bot.send_message(message.chat.id, "Invalid reply target. Start again.")
        return

    sender_is_admin = is_admin(message.from_user.id)
    if not sender_is_admin and not is_admin(target_id):
        clear_state(message.from_user.id)
        bot.send_message(message.chat.id, "You can only reply to admins.")
        return

    ok = _send_contact_message(
        bot, message.from_user.id, target_id, text, sender_is_admin=sender_is_admin
    )
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id, "✅ Message sent." if ok else "Failed to send message."
    )


def handle_admin_manage_roles(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    roles = get_active_roles(include_admin=True)
    text = "🧩 Manage Roles\nCurrent roles:\n" + "\n".join(
        f"- {role_label(r)} ({r})" for r in roles
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕ Add role", callback_data="admin_role_add_start")
    )
    markup.add(
        InlineKeyboardButton("➖ Remove role", callback_data="admin_role_remove_menu")
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_admin_role_add_start(bot, call: CallbackQuery) -> None:
    registration_state[call.from_user.id] = {"step": "admin_role_add_name"}
    edit_or_send_message(
        bot,
        call.message.chat.id,
        "Send new role key (example: data_analyst). Use lowercase with underscore:",
        reply_markup=navigation_markup(back="admin_manage_roles"),
        edit_message=call.message,
    )
    bot.answer_callback_query(call.id)


def handle_admin_role_add_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_role_add_name":
        return
    role = message.text.strip().lower().replace(" ", "_")
    if not role or not role.replace("_", "").isalnum():
        bot.send_message(
            message.chat.id, "Invalid role key. Use letters/numbers/underscore."
        )
        return
    ok = db.add_role(role)
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Role added." if ok else "Failed to add role.")


def handle_admin_role_remove_menu(bot, call: CallbackQuery) -> None:
    roles = get_active_roles(include_admin=False)
    markup = InlineKeyboardMarkup()
    for role in roles:
        markup.add(
            InlineKeyboardButton(
                f"Remove {role_label(role)}", callback_data=f"admin_role_remove|{role}"
            )
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_roles"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        "Select role to remove:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_admin_role_remove(bot, call: CallbackQuery) -> None:
    _, role = call.data.split("|", 1)
    ok = db.remove_role(role)
    bot.answer_callback_query(
        call.id, "Role removed" if ok else "Failed (admin role cannot be removed)"
    )


def handle_admin_score_visibility_menu(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    enabled = bool(db.get_global_setting("score_visibility", True))
    text = f"🎯 Score visibility for interns: {'ON' if enabled else 'OFF'}"
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Toggle", callback_data="admin_score_visibility_toggle")
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
    bot.answer_callback_query(call.id)


def handle_admin_score_visibility_toggle(bot, call: CallbackQuery) -> None:
    current = bool(db.get_global_setting("score_visibility", True))
    db.set_global_setting("score_visibility", not current)
    bot.answer_callback_query(
        call.id, f"Score visibility {'ON' if not current else 'OFF'}"
    )
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
    markup.add(
        InlineKeyboardButton(
            "Submissions CSV", callback_data="admin_export_submissions"
        )
    )
    markup.add(
        InlineKeyboardButton("Reminders CSV", callback_data="admin_export_reminders")
    )
    markup.add(
        InlineKeyboardButton(
            "Leaderboard CSV", callback_data="admin_export_leaderboard"
        )
    )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        "📤 Select CSV export:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_admin_export_submissions(bot, call: CallbackQuery) -> None:
    rows = [
        [
            "task_id",
            "user_id",
            "status",
            "work_url",
            "demo_url",
            "importance",
            "files_count",
            "notes_count",
        ]
    ]
    for s in db.list_submissions():
        rows.append(
            [
                str(s.get("task_id", "")),
                str(s.get("user_id", "")),
                str(s.get("status", "")),
                str(s.get("work_url", "")),
                str(s.get("demo_url", "")),
                str(s.get("importance_rating", "")),
                str(len(s.get("files", []))),
                str(len(s.get("admin_notes", []))),
            ]
        )
    _send_csv(bot, call.message.chat.id, "submissions.csv", rows)
    bot.answer_callback_query(call.id)


def handle_admin_export_reminders(bot, call: CallbackQuery) -> None:
    rows = [["telegram_id", "name", "reminders_enabled", "reminder_hours"]]
    for user in db.list_users(include_banned=True):
        pref = db.get_user_pref(user["telegram_id"])
        rows.append(
            [
                str(user.get("telegram_id", "")),
                short_name(user),
                str(pref.get("reminders_enabled", True)),
                ";".join(str(h) for h in pref.get("reminder_hours", [24, 2])),
            ]
        )
    _send_csv(bot, call.message.chat.id, "reminders.csv", rows)
    bot.answer_callback_query(call.id)


def handle_admin_export_leaderboard(bot, call: CallbackQuery) -> None:
    rows = [["rank", "telegram_id", "name", "role", "score"]]
    rank = 1
    for user in db.get_leaderboard(limit=1000):
        rows.append(
            [
                str(rank),
                str(user.get("telegram_id", "")),
                short_name(user),
                role_label(user.get("role", "")),
                str(user.get("score", 0)),
            ]
        )
        rank += 1
    _send_csv(bot, call.message.chat.id, "leaderboard.csv", rows)
    bot.answer_callback_query(call.id)


# Leaderboard


def handle_admin_leaderboard(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("All roles", callback_data="admin_leaderboard_role|all")
    )
    for role in get_active_roles(include_admin=False):
        markup.add(
            InlineKeyboardButton(
                role_label(role), callback_data=f"admin_leaderboard_role|{role}"
            )
        )
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_cat_reports"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        "🏆 Leaderboard\nChoose a role filter:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)


def handle_admin_leaderboard_filter(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    parts = call.data.split("|", 1)
    role = None
    if len(parts) == 2 and parts[1] != "all":
        role = parts[1]

    board = db.get_leaderboard(role=role, limit=20)
    if not board:
        label = role_label(role) if role else "All roles"
        bot.edit_message_text(
            f"Leaderboard is empty for {label}.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=navigation_markup(back="admin_leaderboard"),
        )
        bot.answer_callback_query(call.id)
        return

    label = role_label(role) if role else "All roles"
    lines = [f"🏆 Leaderboard ({label})"]
    i = 1
    for u in board:
        lines.append(
            f"{i}. {short_name(u)} ({role_label(u.get('role', ''))}) - {u.get('score', 0)}"
        )
        i += 1

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Change Filter", callback_data="admin_leaderboard"))
    markup.row(
        InlineKeyboardButton("⬅️ Back", callback_data="admin_cat_reports"),
        InlineKeyboardButton("🏠 Home", callback_data="go_dashboard"),
    )
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow"))
    bot.edit_message_text(
        "\n".join(lines),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )
    bot.answer_callback_query(call.id)
