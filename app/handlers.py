"""
handlers.py
All Telegram bot handlers for registration, dashboard, and admin features.
"""
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app import db, utils, config
from app.db import log_event
from typing import Dict

# In-memory registration state: {telegram_id: {step, email, ...}}
registration_state: Dict[int, Dict] = {}

# --- Registration Handlers ---
def handle_start(bot, message: Message):
    """Handle /start command and begin registration if user not registered."""
    user = db.get_user(message.from_user.id)
    if user:
        bot.send_message(message.chat.id, "You are already registered.")
        show_dashboard(bot, message.from_user.id, message.chat.id)
        return
    registration_state[message.from_user.id] = {"step": "email"}
    bot.send_message(message.chat.id, "Welcome! Please enter your email to register:")
    log_event("start_registration", {"telegram_id": message.from_user.id})

def handle_email(bot, message: Message):
    """Handle email input during registration."""
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "email":
        return
    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format. Try again:")
        return
    invited = db.get_invited_user(email)
    tg_username = message.from_user.username or ""
    # Allow admin registration even if not invited
    if not invited and tg_username.lower() != "bek_i":
        bot.send_message(message.chat.id, "Email not found in allowed list. Contact admin.")
        registration_state.pop(message.from_user.id, None)
        log_event("registration_failed", {"telegram_id": message.from_user.id, "email": email})
        return
    # If admin, allow all roles
    if tg_username.lower() == "bek_i":
        state["email"] = email
        state["roles"] = ["admin"]
        state["assigned_role"] = "admin"
    else:
        state["email"] = email
        state["roles"] = invited.get("roles", config.ALLOWED_ROLES)
        state["assigned_role"] = state["roles"][0] if state["roles"] else ""
    state["step"] = "first_name"
    bot.send_message(message.chat.id, "Enter your first name:")
    log_event("email_verified", {"telegram_id": message.from_user.id, "email": email})

def handle_role_selection(bot, call: CallbackQuery):
    """Handle role selection during registration."""
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "role":
        return
    role = call.data.replace("role_", "")
    if role not in state["roles"]:
        bot.answer_callback_query(call.id, "Invalid role.")
        return
    state["assigned_role"] = role
    state["step"] = "first_name"
    bot.edit_message_text("Enter your first name:", call.message.chat.id, call.message.message_id)

# --- Registration: First Name ---
def handle_first_name(bot, message: Message):
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "first_name":
        return
    first_name = message.text.strip()
    if not first_name:
        bot.send_message(message.chat.id, "Please enter a valid first name:")
        return
    state["first_name"] = first_name
    state["step"] = "last_name"
    bot.send_message(message.chat.id, "Enter your last name:")

# --- Registration: Last Name ---
def handle_last_name(bot, message: Message):
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "last_name":
        return
    last_name = message.text.strip()
    if not last_name:
        bot.send_message(message.chat.id, "Please enter a valid last name:")
        return
    state["last_name"] = last_name
    state["step"] = "confirm_role"
    # Show assigned role and ask for confirmation
    assigned_role = state.get("assigned_role") or (state["roles"][0] if state.get("roles") else "")
    role_display = config.ROLE_DISPLAY.get(assigned_role, assigned_role.title())
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Yes, confirm", callback_data="confirm_role_yes"))
    markup.add(InlineKeyboardButton("No, cancel", callback_data="confirm_role_no"))
    bot.send_message(message.chat.id, f"Your assigned role is: {role_display}. Do you agree?", reply_markup=markup)

# --- Registration: Confirm Role ---
def handle_confirm_role(bot, call: CallbackQuery):
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "confirm_role":
        return
    if call.data == "confirm_role_yes":
        # Complete registration
        user = {
            "telegram_id": call.from_user.id,
            "email": state["email"],
            "role": state.get("assigned_role") or (state["roles"][0] if state.get("roles") else ""),
            "first_name": state["first_name"],
            "last_name": state["last_name"],
            "state": config.USER_STATE_ACTIVE,
            "score": 0
        }
        if db.add_user(user):
            bot.edit_message_text(f"Registration complete! Welcome, {user['first_name']} {user['last_name']} as {config.ROLE_DISPLAY.get(user['role'], user['role'].title())}.", call.message.chat.id, call.message.message_id)
            registration_state.pop(call.from_user.id, None)
            log_event("registration_success", user)
            show_dashboard(bot, call.from_user.id, call.message.chat.id)
        else:
            bot.edit_message_text("Registration failed or duplicate.", call.message.chat.id, call.message.message_id)
            registration_state.pop(call.from_user.id, None)
            log_event("registration_failed", user)
    else:
        bot.edit_message_text("Registration cancelled.", call.message.chat.id, call.message.message_id)
        registration_state.pop(call.from_user.id, None)

# --- Dashboard & Task Handlers ---
def show_dashboard(bot, telegram_id: int, chat_id: int):
    """Show user dashboard with task options."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Ongoing Tasks", callback_data="tasks_ongoing"))
    markup.add(InlineKeyboardButton("Completed Tasks", callback_data="tasks_completed"))
    bot.send_message(chat_id, "Dashboard:", reply_markup=markup)

def handle_task_list(bot, call: CallbackQuery, status: str):
    """Show tasks for user by status."""
    user = db.get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Not registered.")
        return
    tasks = db.get_tasks_for_user(call.from_user.id, status)
    tasks += db.get_tasks_for_role(user["role"], status)
    if not tasks:
        bot.edit_message_text(f"No {status.lower()} tasks.", call.message.chat.id, call.message.message_id)
        return
    text = f"{status.title()} Tasks:\n"
    for t in tasks:
        text += f"\n- {t['title']}: {t.get('description', '')}"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

# --- Admin Handlers ---
def is_admin(telegram_id: int) -> bool:
    user = db.get_user(telegram_id)
    return user and user.get("role") == "admin"

def handle_assign_task(bot, message: Message):
    """Admin: Start task assignment flow."""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only.")
        return
    # For brevity, ask for title, description, then assign to user or role
    bot.send_message(message.chat.id, "Enter task title:")
    registration_state[message.from_user.id] = {"step": "task_title"}

def handle_task_title(bot, message: Message):
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "task_title":
        return
    state["title"] = message.text.strip()
    state["step"] = "task_desc"
    bot.send_message(message.chat.id, "Enter task description:")

def handle_task_desc(bot, message: Message):
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "task_desc":
        return
    state["description"] = message.text.strip()
    state["step"] = "task_assign"
    # Show assign options
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Assign to User", callback_data="assign_user"))
    markup.add(InlineKeyboardButton("Assign to Role", callback_data="assign_role"))
    bot.send_message(message.chat.id, "Assign to:", reply_markup=markup)

def handle_assign_choice(bot, call: CallbackQuery):
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "task_assign":
        return
    if call.data == "assign_user":
        # List users
        user_list = db.users.find()
        markup = InlineKeyboardMarkup()
        for u in user_list:
            markup.add(InlineKeyboardButton(f"{u['email']} ({u['role']})", callback_data=f"assign_uid_{u['telegram_id']}"))
        bot.edit_message_text("Select user:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "assign_role":
        markup = InlineKeyboardMarkup()
        for role in config.ALLOWED_ROLES:
            markup.add(InlineKeyboardButton(role.title(), callback_data=f"assign_role_{role}"))
        bot.edit_message_text("Select role:", call.message.chat.id, call.message.message_id, reply_markup=markup)

def handle_assign_user(bot, call: CallbackQuery):
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "task_assign":
        return
    if call.data.startswith("assign_uid_"):
        uid = int(call.data.replace("assign_uid_", ""))
        state["assigned_to"] = [uid]
        state["assigned_role"] = None
        save_task_from_state(bot, call)
    elif call.data.startswith("assign_role_"):
        role = call.data.replace("assign_role_", "")
        state["assigned_to"] = []
        state["assigned_role"] = role
        save_task_from_state(bot, call)

def save_task_from_state(bot, call: CallbackQuery):
    state = registration_state.get(call.from_user.id)
    if not state:
        return
    from datetime import datetime
    task = {
        "title": state["title"],
        "description": state["description"],
        "assigned_to": state.get("assigned_to", []),
        "assigned_role": state.get("assigned_role"),
        "status": config.TASK_STATUS_ONGOING,
        "created_at": datetime.utcnow()
    }
    if db.add_task(task):
        bot.edit_message_text("Task assigned!", call.message.chat.id, call.message.message_id)
        log_event("task_assigned", {"admin": call.from_user.id, **task})
    else:
        bot.edit_message_text("Failed to assign task.", call.message.chat.id, call.message.message_id)
    registration_state.pop(call.from_user.id, None)

# --- Task Status Update (Admin) ---
def handle_update_task(bot, message: Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only.")
        return
    # For brevity, not fully implemented: would list tasks and allow update
    bot.send_message(message.chat.id, "Feature coming soon.")

# --- Admin Add Allowed Email ---
def handle_admin_add_allowed(bot, call: CallbackQuery):
    """Admin: Start flow to add allowed email."""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only.")
        return
    registration_state[call.from_user.id] = {"step": "admin_add_email"}
    bot.send_message(call.message.chat.id, "Enter email to allow:")

def handle_admin_add_email(bot, message: Message):
    state = registration_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_add_email":
        return
    email = message.text.strip().lower()
    if not utils.is_valid_email(email):
        bot.send_message(message.chat.id, "Invalid email format. Try again:")
        return
    state["email"] = email
    state["step"] = "admin_add_role"
    # Show role selection
    markup = InlineKeyboardMarkup()
    for role in config.ALLOWED_ROLES:
        markup.add(InlineKeyboardButton(role.title(), callback_data=f"admin_role_{role}"))
    bot.send_message(message.chat.id, "Select role for allowed email:", reply_markup=markup)

def handle_admin_add_role(bot, call: CallbackQuery):
    state = registration_state.get(call.from_user.id)
    if not state or state.get("step") != "admin_add_role":
        return
    role = call.data.replace("admin_role_", "")
    email = state.get("email")
    if not email or role not in config.ALLOWED_ROLES:
        bot.answer_callback_query(call.id, "Invalid role or email.")
        return
    # Add to invited_users
    try:
        db.invited_users.update_one({"email": email}, {"$set": {"email": email, "roles": [role]}}, upsert=True)
        bot.edit_message_text(f"Added {email} as allowed with role {role}.", call.message.chat.id, call.message.message_id)
        log_event("admin_added_allowed", {"admin": call.from_user.id, "email": email, "role": role})
    except Exception as e:
        bot.edit_message_text(f"Failed to add allowed email: {e}", call.message.chat.id, call.message.message_id)
    registration_state.pop(call.from_user.id, None)

# --- Admin: Assign Task Flow ---
def handle_admin_assign_task(bot, message: Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only.")
        return
    registration_state[message.from_user.id] = {"step": "admin_task_title"}
    bot.send_message(message.chat.id, "Enter task title:")

def handle_admin_task_title(bot, message: Message):
    state = registration_state.get(message.from.user.id)
    if not state or state.get("step") != "admin_task_title":
        return
    state["title"] = message.text.strip()
    state["step"] = "admin_task_desc"
    bot.send_message(message.chat.id, "Enter task description:")

def handle_admin_task_desc(bot, message: Message):
    state = registration_state.get(message.from.user.id)
    if not state or state.get("step") != "admin_task_desc":
        return
    state["description"] = message.text.strip()
    state["step"] = "admin_task_assign_type"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Assign to Role", callback_data="admin_assign_role"))
    markup.add(InlineKeyboardButton("Assign to User(s)", callback_data="admin_assign_users"))
    bot.send_message(message.chat.id, "Assign this task to:", reply_markup=markup)

def handle_admin_assign_type(bot, call: CallbackQuery):
    state = registration_state.get(call.from.user.id)
    if not state or state.get("step") != "admin_task_assign_type":
        return
    if call.data == "admin_assign_role":
        markup = InlineKeyboardMarkup()
        for role in config.ALLOWED_ROLES:
            if role == "admin": continue
            markup.add(InlineKeyboardButton(config.ROLE_DISPLAY[role], callback_data=f"admin_task_role_{role}"))
        bot.edit_message_text("Select role:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        state["step"] = "admin_task_role"
    elif call.data == "admin_assign_users":
        # Start paginated user selection
        state["step"] = "admin_task_user_page"
        state["user_page"] = 0
        show_admin_user_page(bot, call.message, 0)

def handle_admin_task_role(bot, call: CallbackQuery):
    state = registration_state.get(call.from.user.id)
    if not state or state.get("step") != "admin_task_role":
        return
    role = call.data.replace("admin_task_role_", "")
    state["assigned_role"] = role
    state["assigned_to"] = []
    state["step"] = "admin_task_deadline"
    bot.edit_message_text("Enter deadline for this task (YYYY-MM-DD):", call.message.chat.id, call.message.message_id)

def show_admin_user_page(bot, message, page):
    users = db.get_users_paginated(skip=page*5, limit=5)
    if not users:
        bot.send_message(message.chat.id, "No users found.")
        return
    markup = InlineKeyboardMarkup()
    for u in users:
        markup.add(InlineKeyboardButton(f"{u.get('first_name','')} {u.get('last_name','')} ({u.get('email','')})", callback_data=f"admin_task_user_{u['telegram_id']}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"admin_task_userpage_{page-1}"))
    nav.append(InlineKeyboardButton("Next", callback_data=f"admin_task_userpage_{page+1}"))
    markup.row(*nav)
    bot.send_message(message.chat.id, "Select user(s) to assign:", reply_markup=markup)

def handle_admin_task_user_page(bot, call: CallbackQuery):
    page = int(call.data.replace("admin_task_userpage_", ""))
    show_admin_user_page(bot, call.message, page)
    state = registration_state.get(call.from.user.id)
    if state:
        state["user_page"] = page

def handle_admin_task_user_select(bot, call: CallbackQuery):
    state = registration_state.get(call.from.user.id)
    if not state or not state.get("step","").startswith("admin_task_user"):
        return
    uid = int(call.data.replace("admin_task_user_", ""))
    assigned = state.setdefault("assigned_to", [])
    if uid not in assigned:
        assigned.append(uid)
    # Stay on user selection, or add a 'Done' button
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Done selecting", callback_data="admin_task_user_done"))
    bot.edit_message_text(f"Selected users: {len(assigned)}. Click Done when finished.", call.message.chat.id, call.message.message_id, reply_markup=markup)
    state["step"] = "admin_task_user_done"

def handle_admin_task_user_done(bot, call: CallbackQuery):
    state = registration_state.get(call.from.user.id)
    if not state or state.get("step") != "admin_task_user_done":
        return
    state["assigned_role"] = None
    state["step"] = "admin_task_deadline"
    bot.edit_message_text("Enter deadline for this task (YYYY-MM-DD):", call.message.chat.id, call.message.message_id)

def handle_admin_task_deadline(bot, message: Message):
    state = registration_state.get(message.from.user.id)
    if not state or state.get("step") != "admin_task_deadline":
        return
    deadline = message.text.strip()
    from datetime import datetime
    try:
        datetime.strptime(deadline, "%Y-%m-%d")
    except Exception:
        bot.send_message(message.chat.id, "Invalid date format. Use YYYY-MM-DD:")
        return
    state["deadline"] = deadline
    # Save task
    task = {
        "title": state["title"],
        "description": state["description"],
        "assigned_to": state.get("assigned_to", []),
        "assigned_role": state.get("assigned_role"),
        "status": config.TASK_STATUS_ONGOING,
        "created_at": datetime.utcnow(),
        "deadline": deadline
    }
    if db.add_task(task):
        bot.send_message(message.chat.id, "Task assigned!")
        log_event("task_assigned", {"admin": message.from.user.id, **task})
        # Notify users
        notify_users = state.get("assigned_to", [])
        if state.get("assigned_role"):
            notify_users += [u["telegram_id"] for u in db.get_users_by_role(state["assigned_role"])]
        for uid in set(notify_users):
            try:
                bot.send_message(uid, f"New task assigned: {task['title']} (Deadline: {deadline})")
            except Exception:
                pass
    else:
        bot.send_message(message.chat.id, "Failed to assign task.")
    registration_state.pop(message.from.user.id, None)
