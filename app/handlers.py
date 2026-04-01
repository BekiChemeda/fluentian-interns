"""
handlers.py
Telegram handlers for onboarding, intern task workflow, and admin management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import config, db, utils

# In-memory state store
registration_state: Dict[int, Dict] = {}


def is_admin(telegram_id: int) -> bool:
    user = db.get_user(telegram_id)
    return bool(user and user.get("role") == "admin")


def role_label(role: str) -> str:
    return config.ROLE_DISPLAY.get(role, role.replace("_", " ").title())


def short_name(user: Dict) -> str:
    return f"{user.get('first_name', '').strip()} {user.get('last_name', '').strip()}".strip() or user.get("email", "Unknown")


def user_dashboard_markup(user: Dict) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("My Tasks", callback_data="my_tasks"))
    markup.add(InlineKeyboardButton("My Profile", callback_data="profile"))
    if user.get("role") == "admin":
        markup.add(InlineKeyboardButton("Admin Panel", callback_data="admin_panel"))
    return markup


def tasks_menu_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Ongoing", callback_data="tasks_ongoing"))
    markup.add(InlineKeyboardButton("Completed", callback_data="tasks_completed"))
    markup.add(InlineKeyboardButton("Back", callback_data="go_dashboard"))
    return markup


def admin_panel_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Add Intern", callback_data="admin_add_intern"))
    markup.add(InlineKeyboardButton("Assign Task", callback_data="admin_assign_task"))
    markup.add(InlineKeyboardButton("Review Submissions", callback_data="admin_review_menu"))
    markup.add(InlineKeyboardButton("Leaderboard", callback_data="admin_leaderboard"))
    markup.add(InlineKeyboardButton("Back", callback_data="go_dashboard"))
    return markup


def show_dashboard(bot, telegram_id: int, chat_id: int) -> None:
    user = db.get_user(telegram_id)
    if not user:
        bot.send_message(chat_id, "Please use /start to register first.")
        return
    text = f"Welcome, {short_name(user)}\nRole: {role_label(user.get('role', ''))}"
    bot.send_message(chat_id, text, reply_markup=user_dashboard_markup(user))


def notify_users(bot, user_ids: List[int], text: str) -> None:
    for uid in sorted(set(user_ids)):
        try:
            bot.send_message(uid, text)
        except Exception:
            # Notification should not break main flow
            continue


# Registration flow

def handle_start(bot, message: Message) -> None:
    existing = db.get_user(message.from_user.id)
    if existing:
        show_dashboard(bot, message.from_user.id, message.chat.id)
        return

    registration_state[message.from_user.id] = {"step": "email"}
    bot.send_message(message.chat.id, "Welcome. Please enter your email to continue registration:")


def handle_email(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "email":
        return

    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format. Please send a valid email:")
        return

    invited = db.get_invited_user(email)
    if not invited:
        bot.send_message(message.chat.id, "Your email is not in the allowed list. Contact your admin.")
        registration_state.pop(message.from_user.id, None)
        db.log_event("registration_denied", {"telegram_id": message.from_user.id, "email": email})
        return

    role = invited.get("role")
    if not role:
        roles = invited.get("roles", [])
        role = roles[0] if roles else "intern"

    state["email"] = email
    state["role"] = role
    state["step"] = "first_name"

    bot.send_message(
        message.chat.id,
        f"Email approved. Your role is {role_label(role)}.\nPlease enter your first name:",
    )


def handle_first_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "first_name":
        return

    first_name = message.text.strip()
    if not first_name:
        bot.send_message(message.chat.id, "First name cannot be empty. Please enter your first name:")
        return

    state["first_name"] = first_name
    state["step"] = "last_name"
    bot.send_message(message.chat.id, "Please enter your last name:")


def handle_last_name(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "last_name":
        return

    last_name = message.text.strip()
    if not last_name:
        bot.send_message(message.chat.id, "Last name cannot be empty. Please enter your last name:")
        return

    user = {
        "telegram_id": message.from_user.id,
        "email": state["email"],
        "role": state["role"],
        "first_name": state["first_name"],
        "last_name": last_name,
        "state": config.USER_STATE_ACTIVE,
        "score": 0,
        "created_at": db.utcnow(),
    }

    if not db.add_user(user):
        bot.send_message(message.chat.id, "Registration failed. You may already be registered.")
        registration_state.pop(message.from_user.id, None)
        return

    registration_state.pop(message.from_user.id, None)
    db.log_event("registration_success", {"telegram_id": message.from_user.id, "email": user["email"]})

    bot.send_message(
        message.chat.id,
        f"Registration complete. Role: {role_label(user['role'])}",
    )
    show_dashboard(bot, message.from_user.id, message.chat.id)


# User dashboard and tasks

def handle_dashboard_callback(bot, call: CallbackQuery) -> None:
    show_dashboard(bot, call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id)


def handle_profile(bot, call: CallbackQuery) -> None:
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered")
        return

    text = (
        "Profile\n"
        f"Name: {short_name(user)}\n"
        f"Email: {user.get('email', '')}\n"
        f"Role: {role_label(user.get('role', ''))}\n"
        f"Score: {user.get('score', 0)}"
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=tasks_menu_markup())
    bot.answer_callback_query(call.id)


def handle_my_tasks(bot, call: CallbackQuery) -> None:
    bot.edit_message_text("My Tasks", call.message.chat.id, call.message.message_id, reply_markup=tasks_menu_markup())
    bot.answer_callback_query(call.id)


def _task_status_for_user(task: Dict, user_id: int) -> str:
    submission = db.get_submission(str(task["_id"]), user_id)
    if submission and submission.get("status") == config.TASK_STATUS_DONE:
        return config.TASK_STATUS_COMPLETED
    return config.TASK_STATUS_ONGOING


def _task_list_for_user(user: Dict, requested_status: str) -> List[Dict]:
    all_tasks = db.get_tasks_for_user(user)
    result = []
    for task in all_tasks:
        if task.get("status") == config.TASK_STATUS_COMPLETED:
            effective = config.TASK_STATUS_COMPLETED
        else:
            effective = _task_status_for_user(task, user["telegram_id"])
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
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Back", callback_data="my_tasks"))
        bot.edit_message_text(f"No {wanted.lower()} tasks.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
        return

    markup = InlineKeyboardMarkup()
    for task in tasks:
        markup.add(InlineKeyboardButton(task.get("title", "Untitled Task"), callback_data=f"task|{task['_id']}"))
    markup.add(InlineKeyboardButton("Back", callback_data="my_tasks"))

    bot.edit_message_text(f"{wanted.title()} Tasks", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_task_detail(bot, call: CallbackQuery) -> None:
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    user = db.get_user(call.from_user.id)
    if not task or not user:
        bot.answer_callback_query(call.id, "Task not found")
        return

    submission = db.get_submission(task_id, call.from_user.id)
    sub_status = submission.get("status") if submission else "not submitted"

    text = (
        f"Task: {task.get('title', '')}\n"
        f"Description: {task.get('description', '')}\n"
        f"Deadline: {task.get('deadline', 'N/A')}\n"
        f"Task Status: {task.get('status', 'ONGOING')}\n"
        f"Your Submission: {sub_status}"
    )

    markup = InlineKeyboardMarkup()
    if _task_status_for_user(task, user["telegram_id"]) == config.TASK_STATUS_ONGOING:
        markup.add(InlineKeyboardButton("Submit Task", callback_data=f"submit|{task_id}"))
    markup.add(InlineKeyboardButton("Back", callback_data="tasks_ongoing"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


# Submission flow: work url -> deployed? -> live demo url (optional) -> learned -> importance rating

def handle_submit_task(bot, call: CallbackQuery) -> None:
    _, task_id = call.data.split("|", 1)
    task = db.get_task(task_id)
    user = db.get_user(call.from_user.id)
    if not task or not user:
        bot.answer_callback_query(call.id, "Task not found")
        return

    if _task_status_for_user(task, user["telegram_id"]) != config.TASK_STATUS_ONGOING:
        bot.answer_callback_query(call.id, "Task already completed")
        return

    registration_state[call.from_user.id] = {
        "step": "submit_work_url",
        "task_id": task_id,
        "submission": {},
    }
    bot.send_message(call.message.chat.id, "Send your GitHub or Figma URL:")
    bot.answer_callback_query(call.id)


def handle_submit_work_url(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_work_url":
        return

    url = message.text.strip()
    if not utils.is_valid_url(url):
        bot.send_message(message.chat.id, "Please send a valid URL (must start with http:// or https://):")
        return

    state["submission"]["work_url"] = url
    state["step"] = "submit_deployed"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Yes", callback_data="submit_deployed_yes"))
    markup.add(InlineKeyboardButton("No", callback_data="submit_deployed_no"))
    bot.send_message(message.chat.id, "Is this task deployed/live?", reply_markup=markup)


def handle_submit_deployed_choice(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "submit_deployed":
        return

    has_demo = call.data.endswith("yes")
    state["submission"]["is_deployed"] = has_demo

    if has_demo:
        state["step"] = "submit_demo_url"
        bot.send_message(call.message.chat.id, "Send the live demo URL:")
    else:
        state["submission"]["demo_url"] = None
        state["step"] = "submit_learned"
        bot.send_message(call.message.chat.id, "What did you learn from this task?")

    bot.answer_callback_query(call.id)


def handle_submit_demo_url(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_demo_url":
        return

    url = message.text.strip()
    if not utils.is_valid_url(url):
        bot.send_message(message.chat.id, "Please send a valid demo URL (http:// or https://):")
        return

    state["submission"]["demo_url"] = url
    state["step"] = "submit_learned"
    bot.send_message(message.chat.id, "What did you learn from this task?")


def handle_submit_learned(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_learned":
        return

    learned = message.text.strip()
    if len(learned) < 5:
        bot.send_message(message.chat.id, "Please provide a bit more detail about what you learned:")
        return

    state["submission"]["learned"] = learned
    state["step"] = "submit_importance"
    bot.send_message(message.chat.id, "Rate this task importance from 1 to 10:")


def handle_submit_importance(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "submit_importance":
        return

    try:
        importance = int(message.text.strip())
        if importance < 1 or importance > 10:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a number between 1 and 10:")
        return

    task_id = state["task_id"]
    payload = {
        "task_id": task_id,
        "user_id": message.from_user.id,
        "work_url": state["submission"].get("work_url"),
        "is_deployed": state["submission"].get("is_deployed", False),
        "demo_url": state["submission"].get("demo_url"),
        "learned": state["submission"].get("learned"),
        "importance_rating": importance,
        "submitted_at": db.utcnow(),
        "status": config.TASK_STATUS_SUBMITTED,
    }

    ok = db.upsert_submission(task_id, message.from_user.id, payload)
    if not ok:
        bot.send_message(message.chat.id, "Failed to save submission. Please try again.")
        registration_state.pop(message.from_user.id, None)
        return

    db.log_event("task_submitted", {"task_id": task_id, "user_id": message.from_user.id})
    registration_state.pop(message.from_user.id, None)

    bot.send_message(message.chat.id, "Submission saved and sent for review.")
    notify_admins_of_submission(bot, message.from_user.id, task_id)


def notify_admins_of_submission(bot, user_id: int, task_id: str) -> None:
    user = db.get_user(user_id)
    task = db.get_task(task_id)
    if not user or not task:
        return

    admins = db.get_users_by_role("admin")
    text = f"New submission from {short_name(user)} for task: {task.get('title', '')}"
    notify_users(bot, [admin["telegram_id"] for admin in admins], text)


# Admin panel and intern management

def handle_admin_panel(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return
    bot.edit_message_text("Admin Panel", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_markup())
    bot.answer_callback_query(call.id)


def handle_admin_add_intern(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return

    registration_state[call.from_user.id] = {"step": "admin_add_email"}
    bot.send_message(call.message.chat.id, "Enter intern email to allow:")
    bot.answer_callback_query(call.id)


def handle_admin_add_email(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_add_email":
        return

    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format. Enter a valid email:")
        return

    state["email"] = email
    state["step"] = "admin_add_role"

    markup = InlineKeyboardMarkup()
    for role in config.ALLOWED_ROLES:
        if role == "admin":
            continue
        markup.add(InlineKeyboardButton(role_label(role), callback_data=f"admin_add_role|{role}"))

    bot.send_message(message.chat.id, "Select role for this intern:", reply_markup=markup)


def handle_admin_add_role(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_add_role":
        return

    _, role = call.data.split("|", 1)
    email = state.get("email")
    if not email or role not in config.ALLOWED_ROLES:
        bot.answer_callback_query(call.id, "Invalid input")
        return

    ok = db.upsert_invited_user(email, role, added_by=call.from_user.id)
    registration_state.pop(call.from_user.id, None)

    if ok:
        bot.edit_message_text(
            f"Intern added to allowed list\nEmail: {email}\nRole: {role_label(role)}",
            call.message.chat.id,
            call.message.message_id,
        )
        db.log_event("admin_added_intern", {"admin": call.from_user.id, "email": email, "role": role})
    else:
        bot.edit_message_text("Failed to add intern.", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)


# Admin task assignment: title -> description -> deadline -> assign type -> role/users

def handle_admin_assign_task(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id

    if not is_admin(user_id):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return

    registration_state[user_id] = {
        "step": "admin_task_title",
        "task": {"assigned_user_ids": [], "assigned_roles": []},
    }
    bot.send_message(chat_id, "Enter task title:")
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def handle_admin_task_title(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_title":
        return

    title = message.text.strip()
    if not title:
        bot.send_message(message.chat.id, "Title cannot be empty. Enter task title:")
        return

    state["task"]["title"] = title
    state["step"] = "admin_task_description"
    bot.send_message(message.chat.id, "Enter task description:")


def handle_admin_task_description(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_description":
        return

    description = message.text.strip()
    if not description:
        bot.send_message(message.chat.id, "Description cannot be empty. Enter task description:")
        return

    state["task"]["description"] = description
    state["step"] = "admin_task_deadline"
    bot.send_message(message.chat.id, "Enter deadline in YYYY-MM-DD format:")


def handle_admin_task_deadline(bot, message: Message) -> None:
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_task_deadline":
        return

    deadline = message.text.strip()
    try:
        datetime.strptime(deadline, "%Y-%m-%d")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid date format. Please use YYYY-MM-DD:")
        return

    state["task"]["deadline"] = deadline
    state["step"] = "admin_task_assign_type"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Assign to Role", callback_data="admin_assign_type|role"))
    markup.add(InlineKeyboardButton("Assign to User(s)", callback_data="admin_assign_type|users"))
    bot.send_message(message.chat.id, "How do you want to assign this task?", reply_markup=markup)


def handle_admin_assign_type(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_assign_type":
        return

    _, assign_type = call.data.split("|", 1)

    if assign_type == "role":
        state["step"] = "admin_task_select_role"
        markup = InlineKeyboardMarkup()
        for role in config.ALLOWED_ROLES:
            if role == "admin":
                continue
            markup.add(InlineKeyboardButton(role_label(role), callback_data=f"admin_task_role|{role}"))
        bot.edit_message_text("Select role:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        state["step"] = "admin_task_select_users"
        state["user_page"] = 0
        state["task"]["assigned_user_ids"] = []
        _show_user_picker(bot, call.message.chat.id, call.message.message_id, state)

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


def _show_user_picker(bot, chat_id: int, message_id: int, state: Dict) -> None:
    page = state.get("user_page", 0)
    per_page = 6
    candidates = db.get_users_paginated(skip=page * per_page, limit=per_page)

    markup = InlineKeyboardMarkup()
    selected = set(state["task"].get("assigned_user_ids", []))

    for user in candidates:
        uid = user["telegram_id"]
        check = "[x]" if uid in selected else "[ ]"
        label = f"{check} {short_name(user)} ({role_label(user.get('role', ''))})"
        markup.add(InlineKeyboardButton(label, callback_data=f"admin_pick_user|{uid}"))

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("Prev", callback_data=f"admin_user_page|{page - 1}"))
    if len(candidates) == per_page:
        nav_row.append(InlineKeyboardButton("Next", callback_data=f"admin_user_page|{page + 1}"))
    if nav_row:
        markup.row(*nav_row)

    markup.add(InlineKeyboardButton("Done", callback_data="admin_users_done"))

    bot.edit_message_text(
        "Select user(s). Tap again to unselect.",
        chat_id,
        message_id,
        reply_markup=markup,
    )


def handle_admin_user_page(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return

    _, page = call.data.split("|", 1)
    state["user_page"] = max(0, int(page))
    _show_user_picker(bot, call.message.chat.id, call.message.message_id, state)
    bot.answer_callback_query(call.id)


def handle_admin_pick_user(bot, call: CallbackQuery) -> None:
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_task_select_users":
        return

    _, raw_uid = call.data.split("|", 1)
    uid = int(raw_uid)
    selected = state["task"].setdefault("assigned_user_ids", [])

    if uid in selected:
        selected.remove(uid)
    else:
        selected.append(uid)

    _show_user_picker(bot, call.message.chat.id, call.message.message_id, state)
    bot.answer_callback_query(call.id)


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
        "status": config.TASK_STATUS_ONGOING,
        "created_by": admin_id,
        "created_at": db.utcnow(),
    }

    task_id = db.create_task(task)
    if not task_id:
        bot.send_message(chat_id, "Failed to assign task.")
        registration_state.pop(admin_id, None)
        return

    registration_state.pop(admin_id, None)

    # Resolve audience from explicit users and roles
    targets = set(task["assigned_user_ids"])
    for role in task["assigned_roles"]:
        for user in db.get_users_by_role(role):
            targets.add(user["telegram_id"])

    notify_users(
        bot,
        list(targets),
        f"New task assigned: {task['title']}\nDeadline: {task['deadline']}",
    )

    db.log_event("task_assigned", {"task_id": str(task_id), "admin": admin_id, "targets": list(targets)})
    bot.send_message(chat_id, "Task assigned successfully.")


# Admin review and scoring

def _parse_review_callback(data: str) -> Optional[Tuple[str, int]]:
    # Format: action|task_id|user_id
    parts = data.split("|")
    if len(parts) != 3:
        return None
    _, task_id, raw_uid = parts
    try:
        return task_id, int(raw_uid)
    except ValueError:
        return None


def handle_admin_review_menu(bot, source) -> None:
    user_id = source.from_user.id
    chat_id = source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id

    if not is_admin(user_id):
        if isinstance(source, CallbackQuery):
            bot.answer_callback_query(source.id, "Admin only")
        else:
            bot.send_message(chat_id, "Admin only")
        return

    reviewables = [s for s in db.list_submissions() if s.get("status") in {config.TASK_STATUS_SUBMITTED, config.TASK_STATUS_ON_REVIEW}]
    if not reviewables:
        bot.send_message(chat_id, "No submissions waiting for review.")
        return

    markup = InlineKeyboardMarkup()
    for sub in reviewables:
        task = db.get_task(sub["task_id"])
        user = db.get_user(sub["user_id"])
        if not task or not user:
            continue
        label = f"{short_name(user)} - {task.get('title', '')}"
        markup.add(InlineKeyboardButton(label, callback_data=f"admin_review_item|{sub['task_id']}|{sub['user_id']}"))

    bot.send_message(chat_id, "Select submission to review:", reply_markup=markup)
    if isinstance(source, CallbackQuery):
        bot.answer_callback_query(source.id)


def handle_admin_review_item(bot, call: CallbackQuery) -> None:
    parsed = _parse_review_callback(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid review item")
        return

    task_id, user_id = parsed
    submission = db.get_submission(task_id, user_id)
    task = db.get_task(task_id)
    user = db.get_user(user_id)
    if not submission or not task or not user:
        bot.answer_callback_query(call.id, "Submission not found")
        return

    text = (
        f"Submission Review\n"
        f"Intern: {short_name(user)}\n"
        f"Task: {task.get('title', '')}\n"
        f"Work URL: {submission.get('work_url', 'N/A')}\n"
        f"Live Demo: {submission.get('demo_url') or 'N/A'}\n"
        f"Learned: {submission.get('learned', '')}\n"
        f"Importance (/10): {submission.get('importance_rating', 'N/A')}\n"
        f"Current Status: {submission.get('status', '')}"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Mark On Review", callback_data=f"admin_mark_review|{task_id}|{user_id}"))
    markup.add(InlineKeyboardButton("Mark Done + Score", callback_data=f"admin_mark_done|{task_id}|{user_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


def handle_admin_mark_review(bot, call: CallbackQuery) -> None:
    parsed = _parse_review_callback(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return

    task_id, user_id = parsed
    db.update_submission(task_id, user_id, {"status": config.TASK_STATUS_ON_REVIEW})
    bot.edit_message_text("Submission moved to On Review.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


def handle_admin_mark_done(bot, call: CallbackQuery) -> None:
    parsed = _parse_review_callback(call.data)
    if not parsed:
        bot.answer_callback_query(call.id, "Invalid request")
        return

    task_id, user_id = parsed
    registration_state[call.from_user.id] = {
        "step": "admin_score",
        "target_task_id": task_id,
        "target_user_id": user_id,
    }
    bot.send_message(call.message.chat.id, f"Enter score (0-{config.MAX_SCORE}) for this submission:")
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
        bot.send_message(message.chat.id, f"Invalid score. Enter a number between 0 and {config.MAX_SCORE}:")
        return

    state["score"] = score
    state["step"] = "admin_note"
    bot.send_message(message.chat.id, "Add an optional review note (or type '-' to skip):")


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
    title = task.get("title", "your task") if task else "your task"
    notify_users(
        bot,
        [user_id],
        f"Your submission for '{title}' is marked DONE. Score: {score}.\nNote: {note or 'No note'}",
    )

    bot.send_message(message.chat.id, "Submission marked done and intern notified.")
    registration_state.pop(message.from_user.id, None)


# Leaderboard

def handle_admin_leaderboard(bot, call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only")
        return

    leaderboard = db.get_leaderboard(limit=20)
    if not leaderboard:
        bot.edit_message_text("Leaderboard is empty.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    lines = ["Leaderboard"]
    rank = 1
    for user in leaderboard:
        lines.append(f"{rank}. {short_name(user)} ({role_label(user.get('role', ''))}) - {user.get('score', 0)}")
        rank += 1

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Back", callback_data="admin_panel"))
    bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)
