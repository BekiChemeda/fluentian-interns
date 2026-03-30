from db import users, allowed_lists
from bson import ObjectId
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot

# Let's check if the email is in the users list who have passed the first cleaning step and are allowed to proceed with the bot interactions. 
async def allowed_email(email):
    allowed_list = await allowed_lists.find_one({"email": email})
    if allowed_list:
        return True
    return False



#  This function is admin only and it adds the email to the allowed list collection in the database. 
async def add_allowed_email(telegram_id: str, email: str):
    user = await users.find_one({"telegram_id": telegram_id, "is_admin": True})
    if not user:
        return False
    try:
        for e in email:
            await allowed_lists.insert_one({"email": e})
        return True
    except Exception as e:
        print(f"Error adding allowed email: {e}")
        return False


# This function is used to notify the admin about any important events or updates related to the bot. It sends a message to all admins in the database.
async def notify_admin(bot: AsyncTeleBot, message: str):
    admins = await users.find({"is_admin": True}).to_list(length=None)
    for admin in admins:
        try:
            await bot.send_message(admin["telegram_id"], message)
        except Exception as e:
            print(f"Error notifying admin {admin['first_name']}: {e}")


# This function is used to fetch a user from the database based on their Telegram ID. It returns the user document if found, or None if there was an error or the user does not exist.
async def get_user_by_telegram_id(telegram_id):
    try:
        user = await users.find_one({"telegram_id": telegram_id})
        return user
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

async def add_user(telegram_id, first_name, last_name, email, is_admin=False, intern_role=None):
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        user = {
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "is_admin": is_admin,
            "intern_role": intern_role
        }
        await users.insert_one(user)
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        return False