"""
config.py
Configuration and constants for the Telegram bot.
"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "fluentian_bot")


# Define allowed roles (updated)
ALLOWED_ROLES = [
    "uiux_engineer",
    "frontend_developer",
    "backend_developer",
    "ml_engineer",
    "mobile_app_developer",
    "admin"
]

# Role display names
ROLE_DISPLAY = {
    "uiux_engineer": "UI/UX Engineer",
    "frontend_developer": "Frontend Developer",
    "backend_developer": "Backend Developer",
    "ml_engineer": "ML Engineer",
    "mobile_app_developer": "Mobile App Developer",
    "admin": "Admin"
}

# User states
USER_STATE_ACTIVE = "ACTIVE"
USER_STATE_REGISTERING = "REGISTERING"


# Task statuses
TASK_STATUS_ONGOING = "ONGOING"
TASK_STATUS_COMPLETED = "COMPLETED"
TASK_STATUS_SUBMITTED = "SUBMITTED"
TASK_STATUS_ON_REVIEW = "ON_REVIEW"
TASK_STATUS_DONE = "DONE"

# Scoring
MAX_SCORE = 100
