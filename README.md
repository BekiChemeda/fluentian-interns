# Fluentian Telegram Bot

A production-ready Telegram bot for intern management, built with Python, Telebot (pyTelegramBotAPI), and MongoDB (PyMongo).

## Features
- Email whitelist onboarding (intern must be in allowed list)
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
- Admin panel for:
	- Adding interns to allowed list (email + role)
	- Assigning tasks to specific users or by role
	- Reviewing and scoring submissions
	- Leaderboard by score
- Notifications:
	- Intern notified when a task is assigned
	- Admin notified when a submission is sent
	- Intern notified when review is completed

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
- `/dashboard` - Open dashboard again
- `/addintern` - Admin: add allowed intern email + role
- `/assigntask` - Admin: assign task to users or role
- `/review` - Admin: open submission review menu

---
MIT License