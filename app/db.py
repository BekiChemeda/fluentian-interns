
"""
db.py
MongoDB connection and database helper functions for the Telegram bot.
"""
import os
from pymongo import MongoClient, errors
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_DB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB", "fluentian_bot")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


# Collections
invited_users = db["invited_users"]
users = db["users"]
tasks = db["tasks"]
submissions = db["submissions"]
logs = db["logs"]

def log_event(event: str, data: Optional[Dict[str, Any]] = None):
	"""Log an event to the logs collection."""
	try:
		logs.insert_one({"event": event, "data": data or {}, "timestamp": db.command('serverStatus')['localTime']})
	except Exception as e:
		print(f"[DB LOG ERROR] {e}")

def get_invited_user(email: str) -> Optional[Dict[str, Any]]:
	"""Return invited user by email if exists."""
	try:
		return invited_users.find_one({"email": email})
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return None


def add_user(user: Dict[str, Any]) -> bool:
	"""Add a new user to the users collection. User should include first_name, last_name, role, email, telegram_id, state."""
	try:
		users.insert_one(user)
		return True
	except errors.DuplicateKeyError:
		return False
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def update_user(telegram_id: int, update_fields: Dict[str, Any]) -> bool:
	"""Update user fields by telegram_id."""
	try:
		result = users.update_one({"telegram_id": telegram_id}, {"$set": update_fields})
		return result.modified_count > 0
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
	"""Get a user by Telegram ID."""
	try:
		return users.find_one({"telegram_id": telegram_id})
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return None

def get_users_by_role(role: str):
	"""Get all users with a specific role."""
	try:
		return list(users.find({"role": role}))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []


def add_task(task: Dict[str, Any]) -> bool:
	"""Add a new task to the tasks collection. Task should include title, description, assigned_to, assigned_role, status, created_at, deadline."""
	try:
		tasks.insert_one(task)
		return True
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def add_submission(submission: Dict[str, Any]) -> bool:
	"""Add a new task submission. Should include user_id, task_id, link, files, submitted_at."""
	try:
		submissions.insert_one(submission)
		return True
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def get_submissions_for_task(task_id):
	try:
		return list(submissions.find({"task_id": task_id}))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []

def get_submission(user_id, task_id):
	try:
		return submissions.find_one({"user_id": user_id, "task_id": task_id})
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return None

def update_submission(user_id, task_id, update_fields: Dict[str, Any]) -> bool:
	try:
		result = submissions.update_one({"user_id": user_id, "task_id": task_id}, {"$set": update_fields})
		return result.modified_count > 0
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def get_leaderboard(role: str = None, limit: int = 20):
	"""Return users sorted by total score, optionally filtered by role."""
	query = {"role": role} if role else {}
	try:
		return list(users.find(query).sort("score", -1).limit(limit))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []

def increment_user_score(telegram_id: int, score: int) -> bool:
	try:
		result = users.update_one({"telegram_id": telegram_id}, {"$inc": {"score": score}})
		return result.modified_count > 0
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False

def get_users_paginated(skip: int = 0, limit: int = 10, role: str = None):
	query = {"role": role} if role else {}
	try:
		return list(users.find(query).skip(skip).limit(limit))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []

def get_tasks_for_user(telegram_id: int, status: Optional[str] = None):
	"""Get tasks assigned to a user."""
	query = {"assigned_to": telegram_id}
	if status:
		query["status"] = status
	try:
		return list(tasks.find(query))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []

def get_tasks_for_role(role: str, status: Optional[str] = None):
	"""Get tasks assigned to a role."""
	query = {"assigned_role": role}
	if status:
		query["status"] = status
	try:
		return list(tasks.find(query))
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return []

def update_task(task_id, update_fields: Dict[str, Any]) -> bool:
	"""Update a task by its _id."""
	from bson import ObjectId
	try:
		result = tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_fields})
		return result.modified_count > 0
	except Exception as e:
		log_event("db_error", {"error": str(e)})
		return False