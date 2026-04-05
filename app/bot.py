"""
bot.py
Telegram bot entrypoint and route wiring.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import telebot
from telebot.types import CallbackQuery, Message

from app import config, db
from app.handlers import (
    handle_admin_add_email,
    handle_admin_add_intern,
    handle_admin_add_role,
    handle_admin_assign_task,
    handle_admin_assign_type,
    handle_admin_ban_toggle,
    handle_admin_broadcast_message,
    handle_admin_broadcast_start,
    handle_admin_change_role,
    handle_admin_force_set_channel,
    handle_admin_force_sub_menu,
    handle_admin_force_toggle,
    handle_admin_registration_menu,
    handle_admin_registration_toggle,
    handle_admin_leaderboard,
    handle_admin_leaderboard_filter,
    handle_admin_manage_users,
    handle_admin_mark_done,
    handle_admin_mark_review,
    handle_admin_add_submission_note_input,
    handle_admin_add_submission_note_start,
    handle_admin_category,
    handle_admin_note,
    handle_admin_panel,
    handle_admin_profile_edit_controls,
    handle_admin_pick_user,
    handle_admin_remove_user,
    handle_admin_reply_command,
    handle_contact_reply_input,
    handle_contact_reply_start,
    handle_admin_role_add_name,
    handle_admin_role_add_start,
    handle_admin_role_remove,
    handle_admin_role_remove_menu,
    handle_admin_manage_roles,
    handle_admin_review_item,
    handle_admin_review_menu,
    handle_admin_review_page,
    handle_admin_score,
    handle_admin_send_submission_files,
    handle_admin_set_channel_input,
    handle_admin_set_role,
    handle_admin_threads_menu,
    handle_admin_export_leaderboard,
    handle_admin_export_menu,
    handle_admin_export_reminders,
    handle_admin_export_submissions,
    handle_admin_restore_user,
    handle_admin_restore_users,
    handle_admin_score_visibility_menu,
    handle_admin_score_visibility_toggle,
    handle_admin_stats_overview,
    handle_admin_toggle_profile_edit_control,
    handle_admin_task_attach_choice,
    handle_admin_task_attachment_action,
    handle_admin_task_attachment_file,
    handle_admin_task_deadline,
    handle_admin_task_description,
    handle_admin_task_role,
    handle_admin_task_title,
    handle_admin_user_view,
    handle_admin_users_page,
    handle_admin_user_page,
    handle_admin_users_done,
    handle_cancel,
    handle_dashboard_callback,
    handle_email,
    handle_first_name,
    handle_last_name,
    handle_register_start,
    handle_register_first_name,
    handle_register_last_name,
    handle_register_email,
    handle_register_role,
    handle_registration_approval,
    handle_my_tasks,
    handle_notif_hours_input,
    handle_notif_set_hours,
    handle_notif_settings,
    handle_notif_toggle,
    handle_profile,
    handle_profile_edit_menu,
    handle_profile_edit_name_or_email_input,
    handle_profile_edit_name_or_email_start,
    handle_profile_edit_city_input,
    handle_profile_finish,
    handle_profile_pick_city,
    handle_profile_pick_city_page,
    handle_profile_pick_country,
    handle_profile_pick_country_page,
    handle_profile_pick_gender,
    handle_profile_pick_language,
    handle_profile_pick_language_level,
    handle_profile_pick_nationality,
    handle_profile_pick_nationality_page,
    handle_profile_set_city,
    handle_profile_set_country,
    handle_profile_set_gender,
    handle_profile_set_language,
    handle_profile_set_language_level,
    handle_profile_set_nationality,
    handle_start,
    handle_submit_custom_choice,
    handle_submit_custom_name,
    handle_submit_custom_value,
    handle_submit_demo_url,
    handle_submit_deployed_choice,
    handle_submit_file_message,
    handle_submit_files_action,
    handle_submit_importance,
    handle_submit_learned,
    handle_submit_task,
    handle_submit_assets_choice,
    handle_submit_drive_link,
    handle_submit_work_url,
    handle_task_attachments,
    handle_task_detail,
    handle_task_list,
    handle_thread_message_input,
    handle_thread_open,
    handle_thread_write,
    is_admin,
    registration_state,
    show_dashboard,
)

bot = telebot.TeleBot(config.TELEGRAM_TOKEN)
db.ensure_indexes()


def _should_send_reminder(task: dict, user_id: int, hours: int) -> bool:
    sent = task.get("reminder_log", {})
    key = f"{user_id}:{hours}"
    return key not in sent


def _mark_reminder_sent(task_id, user_id: int, hours: int) -> None:
    key = f"reminder_log.{user_id}:{hours}"
    db.update_task(task_id, {key: db.utcnow()})


def reminder_loop() -> None:
    while True:
        try:
            tasks = db.list_tasks_for_reminders()
            now = datetime.now(timezone.utc)
            for task in tasks:
                deadline_raw = task.get("deadline")
                if not deadline_raw:
                    continue
                try:
                    deadline = datetime.strptime(deadline_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                delta_hours = (deadline - now).total_seconds() / 3600.0
                if delta_hours <= 0:
                    continue

                targets = set(task.get("assigned_user_ids", []))
                for role in task.get("assigned_roles", []):
                    for user in db.get_users_by_role(role):
                        targets.add(user["telegram_id"])

                for uid in targets:
                    user = db.get_user(uid)
                    if not user or user.get("is_banned"):
                        continue
                    pref = db.get_user_pref(uid)
                    if not pref.get("reminders_enabled", True):
                        continue
                    for h in pref.get("reminder_hours", [24, 2]):
                        if abs(delta_hours - h) <= 0.5 and _should_send_reminder(task, uid, h):
                            bot.send_message(uid, f"⏰ Reminder: '{task.get('title', 'Task')}' is due in about {h} hour(s).")
                            _mark_reminder_sent(task["_id"], uid, h)
        except Exception:
            pass

        time.sleep(300)


@bot.message_handler(commands=["start"])
def start_cmd(message: Message):
    handle_start(bot, message)


@bot.message_handler(commands=["register"])
def register_cmd(message: Message):
    handle_register_start(bot, message)


@bot.message_handler(commands=["dashboard"])
def dashboard_cmd(message: Message):
    show_dashboard(bot, message.from_user.id, message.chat.id)


@bot.message_handler(commands=["cancel"])
def cancel_cmd(message: Message):
    handle_cancel(bot, message)


@bot.message_handler(commands=["admin"])
def admin_reply_cmd(message: Message):
    handle_admin_reply_command(bot, message)


@bot.message_handler(commands=["assigntask"])
def assigntask_cmd(message: Message):
    handle_admin_assign_task(bot, message)


@bot.message_handler(commands=["addintern"])
def addintern_cmd(message: Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only")
        return
    registration_state[message.from_user.id] = {"step": "admin_add_email"}
    bot.send_message(message.chat.id, "Enter intern email:")


@bot.message_handler(commands=["review"])
def review_cmd(message: Message):
    handle_admin_review_menu(bot, message)


@bot.message_handler(commands=["broadcast"])
def broadcast_cmd(message: Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin only")
        return
    registration_state[message.from_user.id] = {"step": "admin_broadcast"}
    bot.send_message(message.chat.id, "Send broadcast message:")


# state messages
@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "email")
def email_step(message: Message):
    handle_email(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "reg_first_name")
def reg_first_name_step(message: Message):
    handle_register_first_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "reg_last_name")
def reg_last_name_step(message: Message):
    handle_register_last_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "reg_email")
def reg_email_step(message: Message):
    handle_register_email(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "first_name")
def first_name_step(message: Message):
    handle_first_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "last_name")
def last_name_step(message: Message):
    handle_last_name(bot, message)


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


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_drive_link")
def submit_drive_link_step(message: Message):
    handle_submit_drive_link(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_custom_name")
def submit_custom_name_step(message: Message):
    handle_submit_custom_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "submit_custom_value")
def submit_custom_value_step(message: Message):
    handle_submit_custom_value(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_add_email")
def admin_add_email_step(message: Message):
    handle_admin_add_email(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_title")
def admin_task_title_step(message: Message):
    handle_admin_task_title(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_description")
def admin_task_description_step(message: Message):
    handle_admin_task_description(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_task_deadline")
def admin_task_deadline_step(message: Message):
    handle_admin_task_deadline(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_score")
def admin_score_step(message: Message):
    handle_admin_score(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_note")
def admin_note_step(message: Message):
    handle_admin_note(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_sub_note")
def admin_sub_note_step(message: Message):
    handle_admin_add_submission_note_input(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_broadcast")
def admin_broadcast_step(message: Message):
    handle_admin_broadcast_message(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "notif_hours")
def notif_hours_step(message: Message):
    handle_notif_hours_input(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_set_channel")
def admin_set_channel_step(message: Message):
    handle_admin_set_channel_input(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "admin_role_add_name")
def admin_role_add_name_step(message: Message):
    handle_admin_role_add_name(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "thread_message")
def thread_message_step(message: Message):
    handle_thread_message_input(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "contact_reply")
def contact_reply_step(message: Message):
    handle_contact_reply_input(bot, message)


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "profile_edit_first_name")
def profile_edit_first_name_step(message: Message):
    handle_profile_edit_name_or_email_input(bot, message, "first_name")


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "profile_edit_last_name")
def profile_edit_last_name_step(message: Message):
    handle_profile_edit_name_or_email_input(bot, message, "last_name")


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "profile_edit_email")
def profile_edit_email_step(message: Message):
    handle_profile_edit_name_or_email_input(bot, message, "email")


@bot.message_handler(func=lambda m: registration_state.get(m.from_user.id, {}).get("step") == "profile_edit_current_city")
def profile_edit_current_city_step(message: Message):
    handle_profile_edit_city_input(bot, message)


@bot.message_handler(content_types=["document", "photo"])
def any_file_step(message: Message):
    state = registration_state.get(message.from_user.id, {}).get("step")
    if state == "submit_files":
        handle_submit_file_message(bot, message)
    elif state == "admin_task_attach_files":
        handle_admin_task_attachment_file(bot, message)


# callbacks
@bot.callback_query_handler(func=lambda call: call.data == "go_dashboard")
def go_dashboard_callback(call: CallbackQuery):
    handle_dashboard_callback(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_flow")
def cancel_flow_callback(call: CallbackQuery):
    handle_cancel(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "start_register")
def start_register_callback(call: CallbackQuery):
    handle_register_start(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "help_contact_admin")
def help_contact_admin_callback(call: CallbackQuery):
    try:
        bot.edit_message_text(
            "Use /admin your message to contact admin.",
            call.message.chat.id,
            call.message.message_id,
        )
    except Exception:
        bot.send_message(call.message.chat.id, "Use /admin your message to contact admin.")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("contact_reply|"))
def contact_reply_callback(call: CallbackQuery):
    handle_contact_reply_start(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_callback(call: CallbackQuery):
    handle_profile(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_edit_menu")
def profile_edit_menu_callback(call: CallbackQuery):
    handle_profile_edit_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_pick_gender")
def profile_pick_gender_callback(call: CallbackQuery):
    handle_profile_pick_gender(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_pick_nationality|"))
def profile_pick_nationality_callback(call: CallbackQuery):
    handle_profile_pick_nationality(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_nationality_page|"))
def profile_pick_nationality_page_callback(call: CallbackQuery):
    handle_profile_pick_nationality_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_pick_country|"))
def profile_pick_country_callback(call: CallbackQuery):
    handle_profile_pick_country(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_country_page|"))
def profile_pick_country_page_callback(call: CallbackQuery):
    handle_profile_pick_country_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_pick_city")
def profile_pick_city_callback(call: CallbackQuery):
    handle_profile_pick_city(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_city_page|"))
def profile_pick_city_page_callback(call: CallbackQuery):
    handle_profile_pick_city_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_pick_language")
def profile_pick_language_callback(call: CallbackQuery):
    handle_profile_pick_language(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_pick_language_level")
def profile_pick_language_level_callback(call: CallbackQuery):
    handle_profile_pick_language_level(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_gender|"))
def profile_set_gender_callback(call: CallbackQuery):
    handle_profile_set_gender(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_nationality|"))
def profile_set_nationality_callback(call: CallbackQuery):
    handle_profile_set_nationality(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_country|"))
def profile_set_country_callback(call: CallbackQuery):
    handle_profile_set_country(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_city|"))
def profile_set_city_callback(call: CallbackQuery):
    handle_profile_set_city(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_language|"))
def profile_set_language_callback(call: CallbackQuery):
    handle_profile_set_language(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_set_language_level|"))
def profile_set_language_level_callback(call: CallbackQuery):
    handle_profile_set_language_level(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_finish")
def profile_finish_callback(call: CallbackQuery):
    handle_profile_finish(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "profile_edit_first_name")
def profile_edit_first_name_callback(call: CallbackQuery):
    handle_profile_edit_name_or_email_start(bot, call, "first_name")


@bot.callback_query_handler(func=lambda call: call.data == "profile_edit_last_name")
def profile_edit_last_name_callback(call: CallbackQuery):
    handle_profile_edit_name_or_email_start(bot, call, "last_name")


@bot.callback_query_handler(func=lambda call: call.data == "profile_edit_email")
def profile_edit_email_callback(call: CallbackQuery):
    handle_profile_edit_name_or_email_start(bot, call, "email")


@bot.callback_query_handler(func=lambda call: call.data == "notif_settings")
def notif_settings_callback(call: CallbackQuery):
    handle_notif_settings(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "notif_toggle")
def notif_toggle_callback(call: CallbackQuery):
    handle_notif_toggle(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "notif_set_hours")
def notif_set_hours_callback(call: CallbackQuery):
    handle_notif_set_hours(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "my_tasks")
def my_tasks_callback(call: CallbackQuery):
    handle_my_tasks(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "tasks_ongoing")
def ongoing_callback(call: CallbackQuery):
    handle_task_list(bot, call, "ONGOING")


@bot.callback_query_handler(func=lambda call: call.data == "tasks_completed")
def completed_callback(call: CallbackQuery):
    handle_task_list(bot, call, "COMPLETED")


@bot.callback_query_handler(func=lambda call: call.data.startswith("task|"))
def task_detail_callback(call: CallbackQuery):
    handle_task_detail(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("taskatt|"))
def task_attachments_callback(call: CallbackQuery):
    handle_task_attachments(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("thread_open|"))
def thread_open_callback(call: CallbackQuery):
    handle_thread_open(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("thread_write|"))
def thread_write_callback(call: CallbackQuery):
    handle_thread_write(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("submit|"))
def submit_callback(call: CallbackQuery):
    handle_submit_task(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_role|"))
def reg_role_callback(call: CallbackQuery):
    handle_register_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_approve|"))
def reg_approve_callback(call: CallbackQuery):
    handle_registration_approval(bot, call, True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_decline|"))
def reg_decline_callback(call: CallbackQuery):
    handle_registration_approval(bot, call, False)


@bot.callback_query_handler(func=lambda call: call.data in {"submit_deployed_yes", "submit_deployed_no"})
def submit_deployed_callback(call: CallbackQuery):
    handle_submit_deployed_choice(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"submit_custom_yes", "submit_custom_no"})
def submit_custom_callback(call: CallbackQuery):
    handle_submit_custom_choice(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"submit_assets_yes", "submit_assets_no"})
def submit_assets_callback(call: CallbackQuery):
    handle_submit_assets_choice(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"submit_files_done", "submit_files_skip"})
def submit_files_callback(call: CallbackQuery):
    handle_submit_files_action(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call: CallbackQuery):
    handle_admin_panel(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_cat_tasks")
def admin_cat_tasks_callback(call: CallbackQuery):
    handle_admin_category(bot, call, "tasks")


@bot.callback_query_handler(func=lambda call: call.data == "admin_cat_users")
def admin_cat_users_callback(call: CallbackQuery):
    handle_admin_category(bot, call, "users")


@bot.callback_query_handler(func=lambda call: call.data == "admin_cat_settings")
def admin_cat_settings_callback(call: CallbackQuery):
    handle_admin_category(bot, call, "settings")


@bot.callback_query_handler(func=lambda call: call.data == "admin_cat_reports")
def admin_cat_reports_callback(call: CallbackQuery):
    handle_admin_category(bot, call, "reports")


@bot.callback_query_handler(func=lambda call: call.data == "admin_stats_overview")
def admin_stats_overview_callback(call: CallbackQuery):
    handle_admin_stats_overview(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_profile_edit_controls")
def admin_profile_edit_controls_callback(call: CallbackQuery):
    handle_admin_profile_edit_controls(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_name_edit")
def admin_toggle_name_edit_callback(call: CallbackQuery):
    handle_admin_toggle_profile_edit_control(bot, call, "allow_profile_name_edit")


@bot.callback_query_handler(func=lambda call: call.data == "admin_toggle_email_edit")
def admin_toggle_email_edit_callback(call: CallbackQuery):
    handle_admin_toggle_profile_edit_control(bot, call, "allow_profile_email_edit")


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_intern")
def admin_add_intern_callback(call: CallbackQuery):
    handle_admin_add_intern(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_role|"))
def admin_add_role_callback(call: CallbackQuery):
    handle_admin_add_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_assign_task")
def admin_assign_task_callback(call: CallbackQuery):
    handle_admin_assign_task(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"admin_task_attach_yes", "admin_task_attach_no"})
def admin_task_attach_choice_callback(call: CallbackQuery):
    handle_admin_task_attach_choice(bot, call)


@bot.callback_query_handler(func=lambda call: call.data in {"admin_task_attach_done", "admin_task_attach_skip"})
def admin_task_attach_action_callback(call: CallbackQuery):
    handle_admin_task_attachment_action(bot, call)


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


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_review_page|"))
def admin_review_page_callback(call: CallbackQuery):
    handle_admin_review_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_review_item|"))
def admin_review_item_callback(call: CallbackQuery):
    handle_admin_review_item(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_send_sub_files|"))
def admin_send_sub_files_callback(call: CallbackQuery):
    handle_admin_send_submission_files(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_review|"))
def admin_mark_review_callback(call: CallbackQuery):
    handle_admin_mark_review(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_mark_done|"))
def admin_mark_done_callback(call: CallbackQuery):
    handle_admin_mark_done(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_sub_note|"))
def admin_add_sub_note_callback(call: CallbackQuery):
    handle_admin_add_submission_note_start(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_callback(call: CallbackQuery):
    handle_admin_broadcast_start(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_threads_menu")
def admin_threads_menu_callback(call: CallbackQuery):
    handle_admin_threads_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_users")
def admin_manage_users_callback(call: CallbackQuery):
    handle_admin_manage_users(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_roles")
def admin_manage_roles_callback(call: CallbackQuery):
    handle_admin_manage_roles(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_role_add_start")
def admin_role_add_start_callback(call: CallbackQuery):
    handle_admin_role_add_start(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_role_remove_menu")
def admin_role_remove_menu_callback(call: CallbackQuery):
    handle_admin_role_remove_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_role_remove|"))
def admin_role_remove_callback(call: CallbackQuery):
    handle_admin_role_remove(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_users_page|"))
def admin_users_page_callback(call: CallbackQuery):
    handle_admin_users_page(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_user_view|"))
def admin_user_view_callback(call: CallbackQuery):
    handle_admin_user_view(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_ban_user|"))
def admin_ban_user_callback(call: CallbackQuery):
    handle_admin_ban_toggle(bot, call, True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_unban_user|"))
def admin_unban_user_callback(call: CallbackQuery):
    handle_admin_ban_toggle(bot, call, False)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_remove_user|"))
def admin_remove_user_callback(call: CallbackQuery):
    handle_admin_remove_user(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_restore_users")
def admin_restore_users_callback(call: CallbackQuery):
    handle_admin_restore_users(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_restore_user|"))
def admin_restore_user_callback(call: CallbackQuery):
    handle_admin_restore_user(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_change_role|"))
def admin_change_role_callback(call: CallbackQuery):
    handle_admin_change_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_set_role|"))
def admin_set_role_callback(call: CallbackQuery):
    handle_admin_set_role(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_force_sub_menu")
def admin_force_sub_menu_callback(call: CallbackQuery):
    handle_admin_force_sub_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_force_set_channel")
def admin_force_set_channel_callback(call: CallbackQuery):
    handle_admin_force_set_channel(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_force_toggle")
def admin_force_toggle_callback(call: CallbackQuery):
    handle_admin_force_toggle(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_registration_control")
def admin_registration_control_callback(call: CallbackQuery):
    handle_admin_registration_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_registration_toggle")
def admin_registration_toggle_callback(call: CallbackQuery):
    handle_admin_registration_toggle(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_leaderboard")
def admin_leaderboard_callback(call: CallbackQuery):
    handle_admin_leaderboard(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_leaderboard_role|"))
def admin_leaderboard_role_callback(call: CallbackQuery):
    handle_admin_leaderboard_filter(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_export_menu")
def admin_export_menu_callback(call: CallbackQuery):
    handle_admin_export_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_export_submissions")
def admin_export_submissions_callback(call: CallbackQuery):
    handle_admin_export_submissions(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_export_reminders")
def admin_export_reminders_callback(call: CallbackQuery):
    handle_admin_export_reminders(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_export_leaderboard")
def admin_export_leaderboard_callback(call: CallbackQuery):
    handle_admin_export_leaderboard(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_score_visibility")
def admin_score_visibility_callback(call: CallbackQuery):
    handle_admin_score_visibility_menu(bot, call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_score_visibility_toggle")
def admin_score_visibility_toggle_callback(call: CallbackQuery):
    handle_admin_score_visibility_toggle(bot, call)


if __name__ == "__main__":
    t = threading.Thread(target=reminder_loop, daemon=True)
    t.start()
    print("Bot is running...")
    bot.infinity_polling()
