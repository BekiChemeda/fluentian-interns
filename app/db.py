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
settings = db["settings"]
user_prefs = db["user_prefs"]
task_threads = db["task_threads"]
pending_registrations = db["pending_registrations"]


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

    settings.create_index([("key", ASCENDING)], unique=True)
    user_prefs.create_index([("telegram_id", ASCENDING)], unique=True)
    task_threads.create_index([("task_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    pending_registrations.create_index([("telegram_id", ASCENDING), ("status", ASCENDING)])
    pending_registrations.create_index([("email", ASCENDING), ("status", ASCENDING)])


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
        return users.find_one({"telegram_id": telegram_id, "is_deleted": {"$ne": True}})
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
        return list(users.find({"role": role, "is_deleted": {"$ne": True}}).sort("first_name", ASCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "get_users_by_role", "error": str(exc)})
        return []


def get_users_paginated(skip: int = 0, limit: int = 10, role: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"role": role} if role else {}
    query["is_deleted"] = {"$ne": True}
    try:
        return list(users.find(query).sort("first_name", ASCENDING).skip(skip).limit(limit))
    except Exception as exc:
        log_event("db_error", {"op": "get_users_paginated", "error": str(exc)})
        return []


def list_users(include_banned: bool = True) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if not include_banned:
        query["is_banned"] = {"$ne": True}
    query["is_deleted"] = {"$ne": True}
    try:
        return list(users.find(query).sort("created_at", DESCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "list_users", "error": str(exc)})
        return []


def set_user_ban(telegram_id: int, is_banned: bool, reason: str = "") -> bool:
    try:
        result = users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"is_banned": is_banned, "ban_reason": reason, "updated_at": utcnow()}},
        )
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "set_user_ban", "error": str(exc)})
        return False


def delete_user(telegram_id: int) -> bool:
    return soft_delete_user(telegram_id)


def soft_delete_user(telegram_id: int, deleted_by: Optional[int] = None) -> bool:
    try:
        result = users.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": utcnow(),
                    "deleted_by": deleted_by,
                    "updated_at": utcnow(),
                }
            },
        )
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "soft_delete_user", "error": str(exc)})
        return False


def list_deleted_users(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        return list(users.find({"is_deleted": True}).sort("deleted_at", DESCENDING).limit(limit))
    except Exception as exc:
        log_event("db_error", {"op": "list_deleted_users", "error": str(exc)})
        return []


def restore_user(telegram_id: int) -> bool:
    try:
        result = users.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {"is_deleted": False, "updated_at": utcnow()},
                "$unset": {"deleted_at": "", "deleted_by": ""},
            },
        )
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "restore_user", "error": str(exc)})
        return False


def set_user_role(telegram_id: int, role: str) -> bool:
    try:
        result = users.update_one({"telegram_id": telegram_id}, {"$set": {"role": role, "updated_at": utcnow()}})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "set_user_role", "error": str(exc)})
        return False


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


def list_tasks_for_reminders() -> List[Dict[str, Any]]:
    try:
        return list(tasks.find({"status": {"$in": ["ONGOING", "SUBMITTED", "ON_REVIEW"]}}))
    except Exception as exc:
        log_event("db_error", {"op": "list_tasks_for_reminders", "error": str(exc)})
        return []


def get_tasks_by_status(status: str) -> List[Dict[str, Any]]:
    try:
        return list(tasks.find({"status": status}).sort("updated_at", DESCENDING))
    except Exception as exc:
        log_event("db_error", {"op": "get_tasks_by_status", "error": str(exc)})
        return []


def add_thread_message(task_id: str, user_id: int, sender_id: int, sender_role: str, text: str) -> bool:
    try:
        task_threads.update_one(
            {"task_id": task_id, "user_id": user_id},
            {
                "$setOnInsert": {"task_id": task_id, "user_id": user_id, "created_at": utcnow()},
                "$set": {"updated_at": utcnow()},
                "$push": {
                    "messages": {
                        "sender_id": sender_id,
                        "sender_role": sender_role,
                        "text": text,
                        "created_at": utcnow(),
                    }
                },
            },
            upsert=True,
        )
        return True
    except Exception as exc:
        log_event("db_error", {"op": "add_thread_message", "error": str(exc)})
        return False


def get_thread(task_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        return task_threads.find_one({"task_id": task_id, "user_id": user_id})
    except Exception as exc:
        log_event("db_error", {"op": "get_thread", "error": str(exc)})
        return None


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


def get_global_setting(key: str, default: Any = None) -> Any:
    try:
        item = settings.find_one({"key": key})
        return default if not item else item.get("value", default)
    except Exception as exc:
        log_event("db_error", {"op": "get_global_setting", "error": str(exc)})
        return default


def set_global_setting(key: str, value: Any) -> bool:
    try:
        settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": utcnow()}, "$setOnInsert": {"created_at": utcnow()}},
            upsert=True,
        )
        return True
    except Exception as exc:
        log_event("db_error", {"op": "set_global_setting", "error": str(exc)})
        return False


def get_roles() -> List[str]:
    roles = get_global_setting("roles", None)
    if not roles:
        return [
            "uiux_engineer",
            "frontend_developer",
            "backend_developer",
            "ml_engineer",
            "mobile_app_developer",
            "admin",
        ]
    return list(roles)


def set_roles(roles: List[str]) -> bool:
    clean = sorted(set(r.strip() for r in roles if r and r.strip()))
    if "admin" not in clean:
        clean.append("admin")
    return set_global_setting("roles", clean)


def add_role(role: str) -> bool:
    roles = get_roles()
    if role in roles:
        return True
    roles.append(role)
    return set_roles(roles)


def remove_role(role: str) -> bool:
    if role == "admin":
        return False
    roles = [r for r in get_roles() if r != role]
    return set_roles(roles)


def create_pending_registration(payload: Dict[str, Any]) -> Optional[ObjectId]:
    data = dict(payload)
    data.setdefault("status", "PENDING")
    data.setdefault("created_at", utcnow())
    try:
        pending_registrations.update_one(
            {"telegram_id": data["telegram_id"], "status": "PENDING"},
            {"$set": data},
            upsert=True,
        )
        saved = pending_registrations.find_one({"telegram_id": data["telegram_id"], "status": "PENDING"}, sort=[("created_at", -1)])
        return saved["_id"] if saved else None
    except Exception as exc:
        log_event("db_error", {"op": "create_pending_registration", "error": str(exc)})
        return None


def get_pending_registration(reg_id: str | ObjectId) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
        return pending_registrations.find_one({"_id": oid})
    except Exception as exc:
        log_event("db_error", {"op": "get_pending_registration", "error": str(exc)})
        return None


def update_pending_registration(reg_id: str | ObjectId, update_fields: Dict[str, Any]) -> bool:
    payload = dict(update_fields)
    payload["updated_at"] = utcnow()
    try:
        oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
        result = pending_registrations.update_one({"_id": oid}, {"$set": payload})
        return result.modified_count > 0
    except Exception as exc:
        log_event("db_error", {"op": "update_pending_registration", "error": str(exc)})
        return False


def get_user_pref(telegram_id: int) -> Dict[str, Any]:
    default = {"telegram_id": telegram_id, "reminders_enabled": True, "reminder_hours": [24, 2]}
    try:
        pref = user_prefs.find_one({"telegram_id": telegram_id})
        return pref or default
    except Exception as exc:
        log_event("db_error", {"op": "get_user_pref", "error": str(exc)})
        return default


def set_user_pref(telegram_id: int, update_fields: Dict[str, Any]) -> bool:
    payload = dict(update_fields)
    payload["updated_at"] = utcnow()
    try:
        user_prefs.update_one(
            {"telegram_id": telegram_id},
            {"$set": payload, "$setOnInsert": {"telegram_id": telegram_id, "created_at": utcnow()}},
            upsert=True,
        )
        return True
    except Exception as exc:
        log_event("db_error", {"op": "set_user_pref", "error": str(exc)})
        return False
