# Fluentian Telegram Bot

A production-ready Telegram bot for intern management, built with Python, Telebot (pyTelegramBotAPI), and MongoDB (PyMongo).

## Features
- Email whitelist onboarding (intern must be in allowed list)
- Time-limited `/register` application flow (until April 3, 2026)
- Registration request approval/decline by admin
- Declined users can contact admin via `/admin your message`
- Role-based registration and dashboard
- Inline navigation for:
	- My tasks (ongoing and completed)
	- Task details with deadline
	- Task submission flow
- Submission flow collects:
	- GitHub/Figma URL
	- Optional live demo URL (if deployed)
	- What intern learned from the task
	- Importance rating from 1 to 10
	- Optional custom fields (name + value)
	- Multiple files (images, PDF, docs)
- Admin panel for:
	- Adding interns to allowed list (email + role)
	- Assigning tasks to specific users or by role
	- Attaching task files (PDF/DOC/DOCX)
	- Reviewing and scoring submissions
	- Per-submission notes from admin
	- Per-task discussion thread between intern and admin
	- Viewing submission files
	- Reply communication to users with `/admin` (reply-to)
	- Broadcast to all users
	- Managing users (ban/unban/soft-delete/change role)
	- Restore soft-deleted users
	- Toggle score visibility for interns
	- Manage available roles (add/remove roles)
	- CSV export: submissions, reminders, leaderboard
	- Force-subscription settings (set channel and toggle on/off)
	- Leaderboard by score
- Notifications:
	- Intern notified when a task is assigned
	- Admin notified when a submission is sent
	- Intern notified when review is completed
	- Deadline reminders based on each user's reminder preference

## Setup Instructions

### 1. Clone the repository
```
git clone <repo-url>
cd fluentian-interns
```

### 2. Install dependencies
```
pip install -r requirements.txt
```
Or, if using uv:
```
uv pip install -r requirements.txt
```

### 3. Set up MongoDB
- Ensure MongoDB is running (local or cloud)
- Create a database (default: `fluentian_bot`)
- Add invited users to the `invited_users` collection:
	```json
	{ "email": "user@example.com", "role": "frontend_developer", "roles": ["frontend_developer"] }
	```

### 4. Configure environment variables
Create a `.env` file in the root directory:
```
TELEGRAM_TOKEN=your-telegram-bot-token
MONGO_DB_URI=mongodb://localhost:27017/
MONGO_DB=fluentian_bot
```

### 5. Run the bot
```
python -m app.bot
```

## File Structure
- `app/bot.py` — Main bot entry and dispatcher
- `app/handlers.py` — All bot handlers
- `app/db.py` — MongoDB helpers
- `app/utils.py` — Validation and utility functions
- `app/config.py` — Configuration and constants

## Notes
- All interactive multi-step flows use in-memory state (restart clears active in-progress steps).
- Admin features require the registered role `admin`.

## Useful Commands
- `/start` - Register and open dashboard
- `/register` - Submit registration request (first name, last name, email, role)
- `/dashboard` - Open dashboard again
- `/cancel` - Cancel current operation
- `/addintern` - Admin: add allowed intern email + role
- `/assigntask` - Admin: assign task to users or role
- `/review` - Admin: open submission review menu
- `/broadcast` - Admin: broadcast message to users
- `/admin` - Admin: reply to a user's message with admin response

## Registration Approval Flow
- User runs `/register` before the deadline.
- User fills first name, last name, email, and selects role.
- Admin receives approve/decline inline actions.
- On approval, user is registered automatically.
- On decline, user is informed and can contact admin using `/admin your message`.

## /admin Command Behavior
- For admins:
	- Reply mode: reply to a user message with `/admin your text` to send direct response.
- For all users (including unregistered):
	- Send `/admin your text` to contact admins.

## Exported CSV Files
- `submissions.csv` includes task/user status, links, importance, file count, note count
- `reminders.csv` includes user reminder preferences
- `leaderboard.csv` includes rank, user, role, and score

---
MIT License