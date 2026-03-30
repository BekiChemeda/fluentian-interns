# Fluentian Telegram Bot

A production-ready Telegram bot for intern management, built with Python, Telebot (pyTelegramBotAPI), and MongoDB (PyMongo).

## Features
- Email whitelist registration with role selection
- User dashboard with ongoing/completed tasks
- Admin task assignment and management
- Modular, robust code with error handling

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
	{ "email": "user@example.com", "roles": ["intern"] }
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
- All registration state is kept in memory (not persisted).
- All user interactions use inline keyboards.
- Admin features require the user to have the `admin` role.

---
MIT License