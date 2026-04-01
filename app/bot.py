"""
bot.py
Telegram bot entrypoint and route wiring.
"""

import telebot
from telebot.types import CallbackQuery, Message

from app import config, db
from app.handlers import (
    handle_admin_add_email,
    handle_admin_add_intern,
    handle_admin_add_role,
    handle_admin_assign_task,
    handle_admin_assign_type,
    handle_admin_leaderboard,
    handle_admin_mark_done,
    handle_admin_mark_review,
    handle_admin_note,
    handle_admin_panel,
    handle_admin_pick_user,
    handle_admin_review_item,
    handle_admin_review_menu,
    handle_admin_score,
    handle_admin_task_deadline,
    handle_admin_task_description,
    handle_admin_task_role,
    handle_admin_task_title,
    handle_admin_user_page,
    handle_admin_users_done,
    handle_dashboard_callback,
    handle_email,
    handle_first_name,
    handle_last_name,
    handle_my_tasks,
    handle_profile,
    is_admin,
    handle_start,
    handle_submit_demo_url,
    handle_submit_deployed_choice,
    handle_submit_importance,
    handle_submit_learned,
    handle_submit_task,
    handle_submit_work_url,
    handle_task_detail,
    handle_task_list,
    registration_state,
    show_dashboard,
)

bot = telebot.TeleBot(config.TELEGRAM_TOKEN)
db.ensure_indexes()


@bot.message_handler(commands=["start"])
def start_cmd(message: Message):
    handle_start(bot, message)


@bot.message_handler(commands=["dashboard"])
def dashboard_cmd(message: Message):
    show_dashboard(bot, message.from_user.id, message.chat.id)


@bot.message_handler(commands=["assigntask"])
def assigntask_cmd(message: Message):
    handle_admin_assign_task(bot, message)


@bot.message_handler(commands=["addintern"])
def addintern_cmd(message: Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only")
        return
    registration_state[message.from_user.id] = {"step": "admin_add_email"}
    bot.send_message(message.chat.id, "Enter intern email to allow:")


@bot.message_handler(commands=["review"])
def review_cmd(message: Message):
    handle_admin_review_menu(bot, message)


# Registration steps
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "email")
def registration_email_step(message: Message):
    handle_email(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "first_name")
def registration_first_name_step(message: Message):
    handle_first_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "last_name")
def registration_last_name_step(message: Message):
    handle_last_name(bot, message)


# Submission steps
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_work_url")
def submit_work_url_step(message: Message):
    handle_submit_work_url(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_demo_url")
def submit_demo_url_step(message: Message):
    handle_submit_demo_url(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_learned")
def submit_learned_step(message: Message):
    handle_submit_learned(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_importance")
def submit_importance_step(message: Message):
    handle_submit_importance(bot, message)


# Admin add intern step
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_add_email")
def admin_add_email_step(message: Message):
    handle_admin_add_email(bot, message)


# Admin assign task steps
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_title")
def admin_task_title_step(message: Message):
    handle_admin_task_title(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_description")
def admin_task_description_step(message: Message):
    handle_admin_task_description(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_deadline")
def admin_task_deadline_step(message: Message):
    handle_admin_task_deadline(bot, message)


# Admin review scoring steps
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_score")
def admin_score_step(message: Message):
    handle_admin_score(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_note")
def admin_note_step(message: Message):
    handle_admin_note(bot, message)


# Dashboard callbacks
@bot.callback_query_handler(func=lambda call: call.data == "go_dashboard")
def dashboard_callback(call: CallbackQuery):
    handle_dashboard_callback(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_callback(call: CallbackQuery):
    handle_profile(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "my_tasks")
def my_tasks_callback(call: CallbackQuery):
    handle_my_tasks(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "tasks_ongoing")
def tasks_ongoing_callback(call: CallbackQuery):
    handle_task_list(bot, call, "ONGOING")


@bot.callback_query_handler(func=lambda call: call.data == "tasks_completed")
def tasks_completed_callback(call: CallbackQuery):
    handle_task_list(bot, call, "COMPLETED")


@bot.callback_query_handler(func=lambda call: call.data.startswith("task|"))
def task_detail_callback(call: CallbackQuery):
    handle_task_detail(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("submit|"))
def submit_task_callback(call: CallbackQuery):
    handle_submit_task(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"submit_deployed_yes", "submit_deployed_no"})
def submit_deployed_callback(call: CallbackQuery):
    handle_submit_deployed_choice(bot, call)


# Admin panel callbacks
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call: CallbackQuery):
    handle_admin_panel(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_intern")
def admin_add_intern_callback(call: CallbackQuery):
    handle_admin_add_intern(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_role|"))
def admin_add_role_callback(call: CallbackQuery):
    handle_admin_add_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_assign_task")
def admin_assign_task_callback(call: CallbackQuery):
    handle_admin_assign_task(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_assign_type|"))
def admin_assign_type_callback(call: CallbackQuery):
    handle_admin_assign_type(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_task_role|"))
def admin_task_role_callback(call: CallbackQuery):
    handle_admin_task_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_user_page|"))
def admin_user_page_callback(call: CallbackQuery):
    handle_admin_user_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_pick_user|"))
def admin_pick_user_callback(call: CallbackQuery):
    handle_admin_pick_user(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_users_done")
def admin_users_done_callback(call: CallbackQuery):
    handle_admin_users_done(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_review_menu")
def admin_review_menu_callback(call: CallbackQuery):
    handle_admin_review_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_review_item|"))
def admin_review_item_callback(call: CallbackQuery):
    handle_admin_review_item(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_review|"))
def admin_mark_review_callback(call: CallbackQuery):
    handle_admin_mark_review(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_done|"))
def admin_mark_done_callback(call: CallbackQuery):
    handle_admin_mark_done(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_leaderboard")
def admin_leaderboard_callback(call: CallbackQuery):
    handle_admin_leaderboard(bot, call)


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
