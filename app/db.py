"""
db.py
MongoDB connection and helper functions for users, invited interns, tasks, and submissions.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient, errors

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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_indexes() -> None:
    """Create indexes used by the bot. Safe to call multiple times."""
    users.create_index([("telegram_id", ASCENDING)], unique=True)
    users.create_index([("email", ASCENDING)], unique=True)
    users.create_index([("role", ASCENDING)])

    invited_users.create_index([("email", ASCENDING)], unique=True)

    tasks.create_index([("status", ASCENDING)])
    tasks.create_index([("assigned_user_ids", ASCENDING)])
    tasks.create_index([("assigned_roles", ASCENDING)])

    submissions.create_index([("task_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    submissions.create_index([("status", ASCENDING)])


def log_event(event: str, data: Optional[Dict[str, Any]] = None) -> None:
    try:
        logs.insert_one({"event": event, "data": data or {}, "timestamp": utcnow()})
    except Exception as exc:
        print(f"[db log error] {exc}")


# Invited interns

def get_invited_user(email: str) -> Optional[Dict[str, Any]]:
    try:
        return invited_users.find_one({"email": email.lower().strip()})
    except Exception as exc:
        log_event("db_error", {"op": "get_invited_user", "error": str(exc)})
        return None


def upsert_invited_user(email: str, role: str, added_by: Optional[int] = None) -> bool:
    clean_email = email.lower().strip()
    try:
        invited_users.update_one(
            {"email": clean_email},
            {
                "$set": {
                    "email": clean_email,
                    "role": role,
                    "roles": [role],
                    "updated_at": utcnow(),
                    "added_by": added_by,
                },
                "$setOnInsert": {"created_at": utcnow()},
            },
            upsert=True,
        )
        return True
    except Exception as exc:
        log_event("db_error", {"op": "upsert_invited_user", "error": str(exc)})
        return False


# Users

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    try:
        return users.find_one({"telegram_id": telegram_id})
    except Exception as exc:
        log_event("db_error", {"op": "get_user", "error": str(exc)})
        return None


def add_user(user: Dict[str, Any]) -> bool:
    payload = dict(user)
    payload.setdefault("created_at", utcnow())
    payload.setdefault("updated_at", utcnow())
    payload.setdefault("score", 0)
    try:
        users.insert_one(payload)
        return True
    except errors.DuplicateKeyError:
        return False
    except Exception as exc:
        log_event("db_error", {"op": "add_user", "error": str(exc)})
        return False


def update_user(telegram_id: int, update_fields: Dict[str, Any]) -> bool:
    payload = dict(update_fields)
    payload["updated_at"] = utcnow()
    try:
        result = users.update_one({"telegram_id": telegram_id}, {"$set": payload})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "update_user", "error": str(exc)})
        return False


def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    try:
        return list(users.find({"role": role}).sort("first_name", ASCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "get_users_by_role", "error": str(exc)})
        return []


def get_users_paginated(skip: int = 0, limit: int = 10, role: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"role": role} if role else {}
    try:
        return list(users.find(query).sort("first_name", ASCENDING).skip(skip).limit(limit))
    except Exception as exc:
        log_event("db_error", {"op": "get_users_paginated", "error": str(exc)})
        return []


def increment_user_score(telegram_id: int, score: int) -> bool:
    try:
        result = users.update_one({"telegram_id": telegram_id}, {"$inc": {"score": score}, "$set": {"updated_at": utcnow()}})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "increment_user_score", "error": str(exc)})
        return False


def get_leaderboard(role: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    query = {"role": role} if role else {}
    try:
        return list(users.find(query).sort("score", DESCENDING).limit(limit))
    except Exception as exc:
        log_event("db_error", {"op": "get_leaderboard", "error": str(exc)})
        return []


# Tasks

def create_task(task: Dict[str, Any]) -> Optional[ObjectId]:
    payload = dict(task)
    now = utcnow()
    payload.setdefault("status", "ONGOING")
    payload.setdefault("assigned_user_ids", [])
    payload.setdefault("assigned_roles", [])
    payload.setdefault("created_at", now)
    payload.setdefault("updated_at", now)
    try:
        result = tasks.insert_one(payload)
        return result.inserted_id
    except Exception as exc:
        log_event("db_error", {"op": "create_task", "error": str(exc)})
        return None


def get_task(task_id: str | ObjectId) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(task_id) if isinstance(task_id, str) else task_id
        return tasks.find_one({"_id": oid})
    except Exception as exc:
        log_event("db_error", {"op": "get_task", "error": str(exc), "task_id": str(task_id)})
        return None


def update_task(task_id: str | ObjectId, update_fields: Dict[str, Any]) -> bool:
    payload = dict(update_fields)
    payload["updated_at"] = utcnow()
    try:
        oid = ObjectId(task_id) if isinstance(task_id, str) else task_id
        result = tasks.update_one({"_id": oid}, {"$set": payload})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "update_task", "error": str(exc), "task_id": str(task_id)})
        return False


def get_tasks_for_user(user: Dict[str, Any], status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {
        "$or": [
            {"assigned_user_ids": user["telegram_id"]},
            {"assigned_roles": user.get("role")},
        ]
    }
    if status:
        query["status"] = status
    try:
        return list(tasks.find(query).sort("deadline", ASCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "get_tasks_for_user", "error": str(exc)})
        return []


def get_tasks_by_status(status: str) -> List[Dict[str, Any]]:
    try:
        return list(tasks.find({"status": status}).sort("updated_at", DESCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "get_tasks_by_status", "error": str(exc)})
        return []


# Submissions

def upsert_submission(task_id: str, user_id: int, payload: Dict[str, Any]) -> bool:
    data = dict(payload)
    data["updated_at"] = utcnow()
    data.setdefault("status", "SUBMITTED")
    try:
        submissions.update_one(
            {"task_id": task_id, "user_id": user_id},
            {"$set": data, "$setOnInsert": {"created_at": utcnow()}},
            upsert=True,
        )
        return True
    except Exception as exc:
        log_event("db_error", {"op": "upsert_submission", "error": str(exc)})
        return False


def get_submission(task_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        return submissions.find_one({"task_id": task_id, "user_id": user_id})
    except Exception as exc:
        log_event("db_error", {"op": "get_submission", "error": str(exc)})
        return None


def list_submissions(status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"status": status} if status else {}
    try:
        return list(submissions.find(query).sort("updated_at", DESCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "list_submissions", "error": str(exc)})
        return []


def update_submission(task_id: str, user_id: int, update_fields: Dict[str, Any]) -> bool:
    payload = dict(update_fields)
    payload["updated_at"] = utcnow()
    try:
        result = submissions.update_one({"task_id": task_id, "user_id": user_id}, {"$set": payload})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "update_submission", "error": str(exc)})
        return False
