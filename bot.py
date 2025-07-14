import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler, # Import MessageHandler for handling text input
    filters # Import filters for message handling
)
import requests

# Initialize Flask app for health check
app = Flask(__name__)

# Flask route for health check
@app.route('/')
def health_check():
    return "EarnBot is running!"

def run_flask_server():
    """Runs the Flask health check server."""
    PORT = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting Flask health check server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(MONGO_URI)
db = client.get_database('earnbot')
users = db.users

# --- Admin ID ---
ADMIN_ID = 7315805581 # Your specified Admin ID
# --- Admin ID ---

# Bot constants
MIN_WITHDRAWAL = 70
EARN_PER_LINK = 0.15
REFERRAL_BONUS = 0.50
LINK_COOLDOWN = 1  # minutes

# Shortlink API configuration
API_TOKEN = '4ca8f20ebd8b02f6fe1f55eb1e49136f69e2f5a0'
SHORTS_API_BASE_URL = "https://dashboard.smallshorts.com/api"

# Database setup
def init_db():
    users.create_index("user_id", unique=True)
    users.create_index("referral_code", unique=True, sparse=True)
    init_user_state_db() # Initialize user state collection
init_db()

# Admin State for multi-step commands
# This helps track what the admin is currently trying to do (e.g., enter user ID for balance check)
user_states = db.user_states # A new collection for temporary user states

def init_user_state_db():
    user_states.create_index("user_id", unique=True)

def get_user_state(user_id):
    state = user_states.find_one({"user_id": user_id})
    return state.get("state") if state else None

def set_user_state(user_id, state_name):
    user_states.update_one({"user_id": user_id}, {"$set": {"state": state_name}}, upsert=True)

def clear_user_state(user_id):
    user_states.delete_one({"user_id": user_id})

# Helper functions
def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "balance": 0.0,
            "referral_code": f"ref_{user_id}",
            "referrals": 0,
            "referral_earnings": 0.0,
            "total_earned": 0.0,
            "withdrawn": 0.0,
            "last_click": None,
            "created_at": datetime.utcnow(),
            "referred_by": None # To track who referred them
        }
        users.insert_one(user)
    return user

def update_user(user_id, update_data):
    users.update_one({"user_id": user_id}, {"$set": update_data})

# Function to generate short link
def generate_short_link(long_url):
    try:
        params = {
            'api': API_TOKEN,
            'url': long_url
        }
        response = requests.get(SHORTS_API_BASE_URL, params=params)
        response.raise_for_status()
        result = response.json()

        if result.get('status') == 'error':
            logger.error(f"SmallShorts API Error: {result.get('message')}")
            return None
        elif result.get('shortenedUrl'):
            return result['shortenedUrl']
        else:
            logger.error(f"Unexpected SmallShorts API response: {result}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to SmallShorts API: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing SmallShorts API response (not JSON): {e}")
        return None

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    bot_username = (await context.bot.get_me()).username

    # Clear any previous admin state
    clear_user_state(user_id)

    if context.args:
        arg = context.args[0]
        if arg.startswith('ref_'):
            referrer_id = int(arg.split('_')[1])
            referrer = get_user(referrer_id)
            # Ensure referrer exists, is not the same user, and user hasn't been referred before
            if referrer and referrer['user_id'] != user_id and user['referred_by'] is None:
                update_user(referrer_id, {
                    "$inc": { # Use $inc to atomically increment values
                        "referrals": 1,
                        "referral_earnings": REFERRAL_BONUS,
                        "balance": REFERRAL_BONUS,
                        "total_earned": REFERRAL_BONUS
                    }
                })
                # Mark the user as referred
                update_user(user_id, {"referred_by": referrer_id})
                await update.message.reply_text(
                    f"🎉 Welcome! You were referred by {referrer_id}! A bonus of ₹{REFERRAL_BONUS:.2f} has been added to their account."
                )
            elif referrer and referrer['user_id'] == user_id:
                await update.message.reply_text("You cannot refer yourself.")
            elif user['referred_by'] is not None:
                 await update.message.reply_text("You have already been referred.")
            else:
                await update.message.reply_text("Invalid referrer.")

        elif arg.startswith('solve_'):
            solved_user_id = int(arg.split('_')[1])
            if solved_user_id == user_id:
                if user['last_click'] and (datetime.utcnow() - user['last_click']) < timedelta(minutes=LINK_COOLDOWN):
                    remaining = (user['last_click'] + timedelta(minutes=LINK_COOLDOWN)) - datetime.utcnow()
                    remaining_seconds = int(remaining.total_seconds())
                    await update.message.reply_text(
                        f"⏳ You've recently completed a link. Please wait {remaining_seconds} seconds before earning again."
                    )
                else:
                    new_balance = user['balance'] + EARN_PER_LINK
                    update_user(user_id, {
                        "balance": new_balance,
                        "total_earned": user['total_earned'] + EARN_PER_LINK,
                        "last_click": datetime.utcnow()
                    })
                    await update.message.reply_text(
                        f"✅ Link solved successfully!\n"
                        f"💰 You earned ₹{EARN_PER_LINK:.2f}. Your new balance: ₹{new_balance:.2f}"
                    )
            else:
                await update.message.reply_text("This link was not generated for you.")

    keyboard = [
        [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')],
        [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')],
        [InlineKeyboardButton("👥 Refer Friends", callback_data='referral')]
    ]

    await update.message.reply_text(
        "🎉 Welcome to Earn Bot!\n"
        "Solve links and earn ₹0.15 per link!\n"
        "Minimum withdrawal: ₹70",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)
    bot_username = (await context.bot.get_me()).username

    # Clear any previous admin state
    clear_user_state(user_id)

    if query.data == 'generate_link':
        if user['last_click'] and (datetime.utcnow() - user['last_click']) < timedelta(minutes=LINK_COOLDOWN):
            remaining = (user['last_click'] + timedelta(minutes=LINK_COOLDOWN)) - datetime.utcnow()
            remaining_seconds = int(remaining.total_seconds())
            await query.edit_message_text(f"⏳ Please wait {remaining_seconds} seconds before generating another link.")
            return

        destination_link = f"https://t.me/{bot_username}?start=solve_{user_id}"
        short_link = generate_short_link(destination_link)

        if not short_link:
            await query.edit_message_text(
                "❌ Link generate करने में समस्या हुई। कृपया बाद में पुनः प्रयास करें।"
            )
            return

        keyboard_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Click to Solve Link", url=short_link)],
            [InlineKeyboardButton("❓ How to Solve Link", url="https://t.me/Asbhai_bsr/289")],
            [InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]
        ])

        await query.edit_message_text(
            f"✅ Your link is ready! Please click the button below to solve it.\n\n"
            f"Once you complete the steps on the website, you'll be redirected back to me, and your balance will be updated automatically.\n"
            f"⏳ Next link available in {LINK_COOLDOWN} minute(s) after successful completion.",
            reply_markup=keyboard_markup
        )

    elif query.data == 'wallet':
        await query.edit_message_text(
            f"💰 Your Wallet\n\n"
            f"🪙 Balance: ₹{user['balance']:.2f}\n"
            f"📊 Total Earned: ₹{user['total_earned']:.2f}\n"
            f"💸 Withdrawn: ₹{user['withdrawn']:.2f}\n"
            f"👥 Referrals: {user['referrals']} (₹{user['referral_earnings']:.2f})\n\n"
            f"💵 Minimum withdrawal: ₹{MIN_WITHDRAWAL}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💵 Withdraw", callback_data='withdraw')],
                [InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]
            ])
        )

    elif query.data == 'referral':
        await query.edit_message_text(
            f"👥 Referral Program\n\n"
            f"🔗 Your referral link:\n"
            f"https://t.me/{bot_username}?start={user['referral_code']}\n\n"
            f"💰 Earn ₹{REFERRAL_BONUS} for each friend who joins using your link!\n"
            f"👥 Total referrals: {user['referrals']}\n"
            f"💸 Earned from referrals: ₹{user['referral_earnings']:.2f}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
        )

    elif query.data == 'back_to_main':
        keyboard = [
            [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')],
            [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')],
            [InlineKeyboardButton("👥 Refer Friends", callback_data='referral')]
        ]
        await query.edit_message_text(
            "🎉 Welcome to Earn Bot!\n"
            "Solve links and earn ₹0.15 per link!\n"
            "Minimum withdrawal: ₹70",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == 'withdraw':
        await query.edit_message_text(
            "⚠️ Withdrawal is not yet implemented. Please check back later!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
        )

    # --- Admin Callbacks ---
    elif query.data == 'admin_get_balance':
        set_user_state(user_id, 'GET_BALANCE_USER_ID')
        await query.edit_message_text("Please send the User ID of the user whose balance you want to check.")
    elif query.data == 'admin_add_balance':
        set_user_state(user_id, 'ADD_BALANCE_USER_ID')
        await query.edit_message_text("Please send the User ID of the user to whom you want to add balance.")
    elif query.data == 'admin_main_menu':
        await admin_menu(update, context) # Re-show admin menu
    # --- End Admin Callbacks ---


# --- Admin Handlers ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    await admin_menu(update, context)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Get User Balance", callback_data='admin_get_balance')],
        [InlineKeyboardButton("➕ Add Balance to User", callback_data='admin_add_balance')],
        [InlineKeyboardButton("💸 Withdrawal Requests (Soon)", callback_data='admin_withdrawals_placeholder')],
        [InlineKeyboardButton("↩️ Back to Main Menu", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "⚙️ Admin Panel Options:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚙️ Admin Panel Options:",
            reply_markup=reply_markup
        )

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return # Ignore non-admin messages in this handler

    current_state = get_user_state(user_id)
    text_input = update.message.text

    if current_state == 'GET_BALANCE_USER_ID':
        try:
            target_user_id = int(text_input)
            target_user = users.find_one({"user_id": target_user_id})
            if target_user:
                await update.message.reply_text(
                    f"User ID: `{target_user_id}`\n"
                    f"Balance: ₹{target_user['balance']:.2f}\n"
                    f"Total Earned: ₹{target_user['total_earned']:.2f}\n"
                    f"Referrals: {target_user['referrals']}\n"
                    f"Referred By: {target_user['referred_by'] if target_user.get('referred_by') else 'N/A'}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("User not found.")
        except ValueError:
            await update.message.reply_text("Invalid User ID. Please send a numeric User ID.")
        finally:
            clear_user_state(user_id) # Clear state after processing

    elif current_state == 'ADD_BALANCE_USER_ID':
        try:
            target_user_id = int(text_input)
            context.user_data['target_user_id_for_add'] = target_user_id # Store temporarily
            set_user_state(user_id, 'ADD_BALANCE_AMOUNT')
            await update.message.reply_text(f"User ID: `{target_user_id}`. Now, please send the amount to add.", parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text("Invalid User ID. Please send a numeric User ID.")
            clear_user_state(user_id)

    elif current_state == 'ADD_BALANCE_AMOUNT':
        target_user_id = context.user_data.get('target_user_id_for_add')
        if not target_user_id:
            await update.message.reply_text("Error: User ID not set for balance addition. Please start again from 'Add Balance to User'.")
            clear_user_state(user_id)
            return

        try:
            amount_to_add = float(text_input)
            if amount_to_add <= 0:
                await update.message.reply_text("Amount must be positive.")
                return

            target_user = users.find_one({"user_id": target_user_id})
            if target_user:
                users.update_one(
                    {"user_id": target_user_id},
                    {"$inc": {"balance": amount_to_add}}
                )
                await update.message.reply_text(
                    f"Successfully added ₹{amount_to_add:.2f} to user `{target_user_id}`'s balance.\n"
                    f"New balance: ₹{target_user['balance'] + amount_to_add:.2f}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("User not found.")
        except ValueError:
            await update.message.reply_text("Invalid amount. Please send a numeric value.")
        finally:
            clear_user_state(user_id) # Clear state after processing
            if 'target_user_id_for_add' in context.user_data:
                del context.user_data['target_user_id_for_add']

# --- End Admin Handlers ---

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)
    if update.callback_query:
        await update.callback_query.message.reply_text('⚠️ An error occurred. Please try again.')
    elif update.message:
        await update.message.reply_text('⚠️ An error occurred. Please try again.')

def run_bot():
    """Runs the Telegram bot using polling."""
    try:
        application = Application.builder().token(TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('admin', admin_command, filters=filters.User(ADMIN_ID))) # Admin command handler
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_input)) # Admin text input handler

        application.add_error_handler(error_handler)

        logger.info("Starting Telegram bot with polling...")
        application.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    # Start Flask health check server in a separate thread first
    flask_thread = Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()

    # Then start the Telegram bot
    run_bot()
