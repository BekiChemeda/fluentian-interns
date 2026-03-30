"""
bot.py
Main entry point for the Telegram bot. Sets up Telebot, handlers, and polling.
"""
import telebot
from telebot.types import Message, CallbackQuery
from app import config

from app.handlers import (
    handle_start, handle_email, handle_role_selection,
    show_dashboard, handle_task_list,
    handle_assign_task, handle_task_title, handle_task_desc,
    handle_assign_choice, handle_assign_user, handle_update_task,
    handle_admin_add_allowed, handle_admin_add_email, handle_admin_add_role,
    handle_first_name, handle_last_name, handle_confirm_role,
    handle_admin_dashboard, handle_admin_leaderboard,
    handle_admin_assign_task, handle_admin_task_title, handle_admin_task_desc,
    handle_admin_assign_type, handle_admin_task_role, handle_admin_task_deadline,
    handle_admin_task_user_page, handle_admin_task_user_select, handle_admin_task_user_done,
    registration_state
)
# --- Admin assign task ---
@bot.message_handler(commands=['assigntask'])
def admin_assign_task_cmd(message: Message):
    handle_admin_assign_task(bot, message)

@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'admin_task_title')
def admin_task_title_step(message: Message):
    handle_admin_task_title(bot, message)

@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'admin_task_desc')
def admin_task_desc_step(message: Message):
    handle_admin_task_desc(bot, message)

@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'admin_task_deadline')
def admin_task_deadline_step(message: Message):
    handle_admin_task_deadline(bot, message)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_assign_role' or call.data == 'admin_assign_users')
def admin_assign_type_callback(call: CallbackQuery):
    handle_admin_assign_type(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_task_role_'))
def admin_task_role_callback(call: CallbackQuery):
    handle_admin_task_role(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_task_userpage_'))
def admin_task_user_page_callback(call: CallbackQuery):
    handle_admin_task_user_page(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_task_user_'))
def admin_task_user_select_callback(call: CallbackQuery):
    handle_admin_task_user_select(bot, call)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_task_user_done')
def admin_task_user_done_callback(call: CallbackQuery):
    handle_admin_task_user_done(bot, call)
# --- Admin dashboard ---
@bot.message_handler(commands=['dashboard'])
def admin_dashboard_cmd(message: Message):
    handle_admin_dashboard(bot, message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_leaderboard_'))
def admin_leaderboard_callback(call: CallbackQuery):
    handle_admin_leaderboard(bot, call)

bot = telebot.TeleBot(config.TELEGRAM_TOKEN)

# --- Registration ---
@bot.message_handler(commands=['start'])
def start_cmd(message: Message):
    handle_start(bot, message)


# Registration email step

# Registration email step
# Registration email step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'email')
def email_step(message: Message):
    handle_email(bot, message)

# Registration first name step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'first_name')
def first_name_step(message: Message):
    handle_first_name(bot, message)

# Registration last name step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'last_name')
def last_name_step(message: Message):
    handle_last_name(bot, message)

# Admin add allowed email step

# Admin add allowed email step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'admin_add_email')
def admin_add_email_step(message: Message):
    handle_admin_add_email(bot, message)


# Task title step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'task_title')
def task_title_step(message: Message):
    handle_task_title(bot, message)


# Task description step
@bot.message_handler(func=lambda m: m.from_user.id in registration_state and registration_state[m.from_user.id].get('step') == 'task_desc')
def task_desc_step(message: Message):
    handle_task_desc(bot, message)

# --- Admin assign task ---
@bot.message_handler(commands=['assign'])
def assign_cmd(message: Message):
    handle_assign_task(bot, message)

@bot.message_handler(commands=['update'])
def update_cmd(message: Message):
    handle_update_task(bot, message)


# Registration confirm role step
@bot.callback_query_handler(func=lambda call: call.data in ['confirm_role_yes', 'confirm_role_no'])
def confirm_role_callback(call: CallbackQuery):
    handle_confirm_role(bot, call)

# --- Callback queries ---

# Registration role selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('role_'))
def role_callback(call: CallbackQuery):
    handle_role_selection(bot, call)

# Admin add allowed button
@bot.callback_query_handler(func=lambda call: call.data == 'admin_add_allowed')
def admin_add_allowed_callback(call: CallbackQuery):
    handle_admin_add_allowed(bot, call)

# Admin add allowed role selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_role_'))
def admin_add_role_callback(call: CallbackQuery):
    handle_admin_add_role(bot, call)

@bot.callback_query_handler(func=lambda call: call.data in ['tasks_ongoing', 'tasks_completed'])
def dashboard_tasks_callback(call: CallbackQuery):
    status = 'ONGOING' if call.data == 'tasks_ongoing' else 'COMPLETED'
    handle_task_list(bot, call, status)

@bot.callback_query_handler(func=lambda call: call.data in ['assign_user', 'assign_role'])
def assign_choice_callback(call: CallbackQuery):
    handle_assign_choice(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('assign_uid_') or call.data.startswith('assign_role_'))
def assign_user_role_callback(call: CallbackQuery):
    handle_assign_user(bot, call)

# --- Main ---
if __name__ == '__main__':
    print('Bot is running...')
    bot.infinity_polling()