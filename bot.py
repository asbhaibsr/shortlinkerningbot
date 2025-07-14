import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, abort
from threading import Thread
import asyncio
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
import requests
from telegram.error import TelegramError
from bson.objectid import ObjectId

# Initialize Flask app for health check
app = Flask(__name__)

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
user_states = db.user_states
withdrawal_requests = db.withdrawal_requests

# --- Admin ID ---
ADMIN_ID = 7315805581  # Replace with your actual Telegram User ID
# --- Admin ID ---

# Bot constants - UPDATED VALUES
MIN_WITHDRAWAL = 10  # Changed from 70 to 10
EARN_PER_LINK = 0.15
REFERRAL_BONUS = 0.50  # Changed from 0.05 to 0.50
LINK_COOLDOWN = 1  # minutes

# Shortlink API configuration
API_TOKEN = '4ca8f20ebd8b02f6fe1f55eb1e49136f69e2f5a0'  # Replace with your SmallShorts API Token
SHORTS_API_BASE_URL = "https://dashboard.smallshorts.com/api"

# Database setup functions
def init_user_state_db():
    """Initializes the user_states collection."""
    user_states.create_index("user_id", unique=True)

def init_withdrawal_requests_db():
    """Initializes the withdrawal_requests collection."""
    withdrawal_requests.create_index("user_id")
    withdrawal_requests.create_index("status")
    withdrawal_requests.create_index("timestamp")

def init_db():
    """Initializes all necessary database collections and indexes."""
    users.create_index("user_id", unique=True)
    users.create_index("referral_code", unique=True, sparse=True)
    init_user_state_db()
    init_withdrawal_requests_db()
init_db()

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
            "referred_by": None
        }
        users.insert_one(user)
    return user

def update_user(user_id, update_data):
    users.update_one({"user_id": user_id}, {"$set": update_data})

def get_user_state(user_id):
    state = user_states.find_one({"user_id": user_id})
    return state.get("state") if state else None

def set_user_state(user_id, state_name):
    user_states.update_one({"user_id": user_id}, {"$set": {"state": state_name}}, upsert=True)

def clear_user_state(user_id):
    user_states.delete_one({"user_id": user_id})

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

    clear_user_state(user_id)

    if context.args:
        arg = context.args[0]
        if arg.startswith('ref_'):
            referrer_id = int(arg.split('_')[1])
            referrer = get_user(referrer_id)
            if referrer and referrer['user_id'] != user_id and user['referred_by'] is None:
                users.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {
                        "referrals": 1,
                        "referral_earnings": REFERRAL_BONUS,
                        "balance": REFERRAL_BONUS,
                        "total_earned": REFERRAL_BONUS
                    }}
                )
                users.update_one({"user_id": user_id}, {"$set": {"referred_by": referrer_id}})
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
                    users.update_one(
                        {"user_id": user_id},
                        {"$set": {
                            "balance": new_balance,
                            "total_earned": user['total_earned'] + EARN_PER_LINK,
                            "last_click": datetime.utcnow()
                        }}
                    )
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
        f"Solve links and earn ₹{EARN_PER_LINK:.2f} per link!\n"
        f"Minimum withdrawal: ₹{MIN_WITHDRAWAL}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)
    bot_username = (await context.bot.get_me()).username

    # Ensure state is cleared for non-admin interactions unless specifically handled
    # This line might have been clearing state prematurely, moved state clearing logic to specific handlers
    # if user_id != ADMIN_ID:
    #     clear_user_state(user_id)

    if query.data == 'generate_link':
        clear_user_state(user_id) # Clear state when starting new non-stateful flow
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
        clear_user_state(user_id) # Clear state when starting new non-stateful flow
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
        clear_user_state(user_id) # Clear state when starting new non-stateful flow
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
        clear_user_state(user_id) # Always clear state when going back to main menu
        keyboard = [
            [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')],
            [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')],
            [InlineKeyboardButton("👥 Refer Friends", callback_data='referral')]
        ]
        await query.edit_message_text(
            "🎉 Welcome to Earn Bot!\n"
            f"Solve links and earn ₹{EARN_PER_LINK:.2f} per link!\n"
            f"Minimum withdrawal: ₹{MIN_WITHDRAWAL}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == 'withdraw':
        clear_user_state(user_id) # Clear state before starting withdrawal process
        if user['balance'] >= MIN_WITHDRAWAL:
            # Offer withdrawal options
            keyboard = [
                [InlineKeyboardButton("💳 UPI ID", callback_data='withdraw_upi')],
                [InlineKeyboardButton("🏦 Bank Account", callback_data='withdraw_bank')],
                [InlineKeyboardButton("🤳 QR Code (Screenshot)", callback_data='withdraw_qr')],
                [InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]
            ]
            await query.edit_message_text(
                f"✅ Your balance is ₹{user['balance']:.2f}. Please select your preferred withdrawal method:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
            )

    # New withdrawal method callbacks
    elif query.data == 'withdraw_upi':
        if user['balance'] < MIN_WITHDRAWAL: # Re-check balance
            await query.edit_message_text(
                f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_ENTER_UPI')
        await query.edit_message_text(
            "Please send your **UPI ID** (e.g., `yourname@bank` or `phonenumber@upi`).",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
        )
    elif query.data == 'withdraw_bank':
        if user['balance'] < MIN_WITHDRAWAL: # Re-check balance
            await query.edit_message_text(
                f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_ENTER_BANK')
        await query.edit_message_text(
            "Please send your **Bank Account Details** in the following format:\n\n"
            "```\n"
            "Account Holder Name: [Your Name]\n"
            "Account Number: [Your Account Number]\n"
            "IFSC Code: [Your IFSC Code]\n"
            "Bank Name: [Your Bank Name]\n"
            "```\n"
            "Example:\n"
            "```\n"
            "Account Holder Name: John Doe\n"
            "Account Number: 123456789012\n"
            "IFSC Code: SBIN0000001\n"
            "Bank Name: State Bank of India\n"
            "```",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
        )
    elif query.data == 'withdraw_qr':
        if user['balance'] < MIN_WITHDRAWAL: # Re-check balance
            await query.edit_message_text(
                f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_UPLOAD_QR')
        await query.edit_message_text(
            "Please upload your **UPI QR Code screenshot**. Make sure the QR code is clear and visible.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
        )

    # --- Admin Callbacks ---
    elif query.data == 'admin_get_balance':
        if user_id == ADMIN_ID:
            clear_user_state(user_id) # Clear admin state before setting new one
            set_user_state(user_id, 'GET_BALANCE_USER_ID')
            await query.edit_message_text("Please send the User ID of the user whose balance you want to check.")
    elif query.data == 'admin_add_balance':
        if user_id == ADMIN_ID:
            clear_user_state(user_id) # Clear admin state before setting new one
            set_user_state(user_id, 'ADD_BALANCE_USER_ID')
            await query.edit_message_text("Please send the User ID of the user to whom you want to add balance.")
    elif query.data == 'admin_main_menu':
        if user_id == ADMIN_ID:
            clear_user_state(user_id) # Clear admin state when going to main admin menu
            await admin_menu(update, context)
    elif query.data == 'admin_show_pending_withdrawals':
        if user_id == ADMIN_ID:
            clear_user_state(user_id) # Clear admin state before showing withdrawals
            await admin_show_withdrawals(update, context)
    elif query.data.startswith('approve_payment_'):
        if user_id == ADMIN_ID:
            request_id = query.data.split('_')[2]
            await admin_approve_payment(update, context, request_id)


# --- Admin Handlers ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    clear_user_state(user_id)
    await admin_menu(update, context)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Get User Balance", callback_data='admin_get_balance')],
        [InlineKeyboardButton("➕ Add Balance to User", callback_data='admin_add_balance')],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data='admin_show_pending_withdrawals')],
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

async def admin_show_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_requests = list(withdrawal_requests.find({"status": "pending"}))

    if not pending_requests:
        await update.callback_query.edit_message_text(
            "✅ No pending withdrawal requests at the moment.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
        )
        return

    # To avoid "Message is not modified" error, send a new message for each request
    # and then edit the original query message to indicate completion.
    await update.callback_query.edit_message_text("Fetching pending withdrawal requests...") # Initial message update

    for req in pending_requests:
        user_obj = get_user(req['user_id'])
        username = user_obj.get('username', f"User_{req['user_id']}")

        details_str = ""
        if req['withdrawal_details']['method'] == "UPI ID":
            details_str = f"UPI ID: `{req['withdrawal_details']['id']}`"
        elif req['withdrawal_details']['method'] == "Bank Account":
            details_str = f"Bank Details:\n```\n{req['withdrawal_details']['details']}\n```"
        elif req['withdrawal_details']['method'] == "QR Code":
            details_str = f"QR Code File ID: `{req['withdrawal_details']['file_id']}`"
            try:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=req['withdrawal_details']['file_id'],
                    caption=f"QR for User `{req['user_id']}` (Amount: ₹{req['amount']:.2f})"
                )
            except Exception as e:
                logger.error(f"Failed to resend QR photo to admin for request {req['_id']}: {e}")
                details_str += "\n_ (Could not resend QR photo) _"

        message_text = (
            f"💸 **Pending Withdrawal Request** 💸\n"
            f"User: [{username}](tg://user?id={req['user_id']})\n"
            f"User ID: `{req['user_id']}`\n"
            f"Amount: ₹{req['amount']:.2f}\n"
            f"Method: {req['withdrawal_details']['method']}\n"
            f"{details_str}\n"
            f"Requested On: {req['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        keyboard = [[InlineKeyboardButton("✅ Mark as Paid", callback_data=f"approve_payment_{req['_id']}")]]

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text="👆 Above are all pending withdrawal requests. Click 'Mark as Paid' to process them.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
    )

async def admin_approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: str):
    query = update.callback_query
    await query.answer("Processing payment approval...")

    try:
        request = withdrawal_requests.find_one_and_update(
            {"_id": ObjectId(request_id), "status": "pending"},
            {"$set": {"status": "completed", "completed_at": datetime.utcnow()}},
            return_document=True
        )

        if request:
            user_id = request['user_id']
            amount = request['amount']
            withdrawal_method = request['withdrawal_details']['method']

            # --- RESET USER'S EARNING DATA AFTER SUCCESSFUL PAYMENT ---
            # IMPORTANT: Set balance to 0, and increment 'withdrawn' by the amount
            users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "balance": 0.0, # Reset balance to 0 after withdrawal
                    "referrals": 0, # Reset referrals count
                    "referral_earnings": 0.0, # Reset referral earnings
                    "last_click": None,
                    "referred_by": None # Reset referred by, or keep if you prefer users always retain their referrer
                },
                    "$inc": {
                        "withdrawn": amount # Increment total withdrawn amount
                    }
                }
            )
            logger.info(f"User {user_id}'s earning data reset after successful withdrawal of {amount}.")

            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **Payment Successful!** 🎉\n\n"
                         f"Your withdrawal request of ₹{amount:.2f} via {withdrawal_method} has been successfully processed.\n"
                         f"Your earning balance has been reset to start fresh. Thank you for using Earn Bot!",
                    parse_mode='Markdown'
                )
                await query.edit_message_text(
                    f"✅ Payment for User `{user_id}` (Request ID: `{request_id}`) marked as Paid and user notified.\n"
                    f"User's earning data has been reset.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Pending List", callback_data='admin_show_pending_withdrawals')]])
                )
            except TelegramError as e:
                logger.error(f"Failed to notify user {user_id} about successful payment: {e}")
                await query.edit_message_text(
                    f"✅ Payment for User `{user_id}` (Request ID: `{request_id}`) marked as Paid, but failed to notify user.\n"
                    f"User's earning data has been reset.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Pending List", callback_data='admin_show_pending_withdrawals')]])
                )

        else:
            await query.edit_message_text(
                "❌ This withdrawal request was already processed or could not be found.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Pending List", callback_data='admin_show_pending_withdrawals')]])
            )

    except Exception as e:
        logger.error(f"Error processing payment approval for request {request_id}: {e}")
        await query.edit_message_text(
            f"❌ An error occurred while approving this payment: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Pending List", callback_data='admin_show_pending_withdrawals')]])
        )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return
    set_user_state(user_id, 'BROADCAST_MESSAGE')
    await update.message.reply_text(
        "📝 Please send the message you want to broadcast to all users.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel Broadcast", callback_data='admin_main_menu')]])
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    total_users = users.count_documents({})

    await update.message.reply_text(
        f"📊 Bot Statistics:\n"
        f"Total Users: {total_users}\n"
    )

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

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
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
                )
            else:
                await update.message.reply_text(
                    "User not found.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
                )
        except ValueError:
            await update.message.reply_text(
                "Invalid User ID. Please send a numeric User ID.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
            )
        finally:
            clear_user_state(user_id)

    elif current_state == 'ADD_BALANCE_USER_ID':
        try:
            target_user_id = int(text_input)
            context.user_data['target_user_id_for_add'] = target_user_id
            set_user_state(user_id, 'ADD_BALANCE_AMOUNT')
            await update.message.reply_text(f"User ID: `{target_user_id}`. Now, please send the amount to add.", parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text(
                "Invalid User ID. Please send a numeric User ID.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
            )
            clear_user_state(user_id)

    elif current_state == 'ADD_BALANCE_AMOUNT':
        target_user_id = context.user_data.get('target_user_id_for_add')
        if not target_user_id:
            await update.message.reply_text(
                "Error: User ID not set for balance addition. Please start again from 'Add Balance to User'.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
            )
            clear_user_state(user_id)
            return

        try:
            amount_to_add = float(text_input)
            if amount_to_add <= 0:
                await update.message.reply_text(
                    "Amount must be positive.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
                )
                clear_user_state(user_id)
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
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
                )
            else:
                await update.message.reply_text(
                    "User not found.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
                )
        except ValueError:
            await update.message.reply_text(
                "Invalid amount. Please send a numeric value.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
            )
        finally:
            clear_user_state(user_id)
            if 'target_user_id_for_add' in context.user_data:
                del context.user_data['target_user_id_for_add']

    elif current_state == 'BROADCAST_MESSAGE':
        message_to_broadcast = text_input
        sent_count = 0
        failed_count = 0
        all_users = users.find({}, {"user_id": 1})

        for user_doc in all_users:
            try:
                await context.bot.send_message(chat_id=user_doc['user_id'], text=message_to_broadcast)
                sent_count += 1
            except TelegramError as e:
                if "blocked by the user" in str(e) or "user is deactivated" in str(e):
                    logger.info(f"User {user_doc['user_id']} blocked the bot or is deactivated. Skipping.")
                else:
                    logger.warning(f"Failed to send broadcast to user {user_doc['user_id']}: {e}")
                failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"An unexpected error occurred sending broadcast to user {user_doc['user_id']}: {e}")

        await update.message.reply_text(
            f"✅ Broadcast complete!\n"
            f"Sent to: {sent_count} users.\n"
            f"Failed for: {failed_count} users.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
        )
        clear_user_state(user_id)


# --- User Withdrawal Input Handler ---
async def handle_withdrawal_input_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_state = get_user_state(user_id)
    user = get_user(user_id)

    # If user is not in a withdrawal state, or if balance is insufficient for a *new* request,
    # then treat this as a regular message or an invalid input for withdrawal.
    # Only proceed with processing if they are in a withdrawal state AND meet min balance.
    if not current_state or not current_state.startswith('WITHDRAW_'):
        # If user sent a message when not in a state, just ignore or send a generic reply
        # logger.warning(f"User {user_id} sent message '{update.message.text}' when not in a specific state.")
        # await update.message.reply_text("Please use the menu buttons to interact with the bot.")
        return # Do not process further if not in a withdrawal state

    if user['balance'] < MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_to_main')]])
        )
        clear_user_state(user_id) # Clear state if balance is insufficient
        return

    # Proceed based on specific withdrawal state
    if current_state == 'WITHDRAW_ENTER_UPI':
        upi_id = update.message.text.strip()
        if not upi_id:
            await update.message.reply_text("UPI ID cannot be empty. Please send your UPI ID.")
            return
        withdrawal_details = {"method": "UPI ID", "id": upi_id}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_ENTER_BANK':
        bank_details_raw = update.message.text.strip()
        if len(bank_details_raw) < 50:  # Simple check for minimum length
            await update.message.reply_text(
                "Please provide complete bank account details in the specified format.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
            )
            return
        withdrawal_details = {"method": "Bank Account", "details": bank_details_raw}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_UPLOAD_QR':
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            withdrawal_details = {"method": "QR Code", "file_id": file_id}
            await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)
        else:
            await update.message.reply_text(
                "Please upload a **photo** of your QR Code. Text messages are not accepted for QR code withdrawals.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
            )
            return
    else:
        # This else block should theoretically not be hit if checks above are correct,
        # but it's good for debugging unexpected states.
        logger.warning(f"User {user_id} sent message while in unexpected state: {current_state}")
        await update.message.reply_text(
            "It looks like you're in an unexpected state. Please try again from the main menu or click 'Cancel'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_to_main')]])
        )
        clear_user_state(user_id)


async def process_withdrawal_request(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: float, details: dict):
    """Handles the common logic for creating and notifying about a withdrawal request."""
    # Record the withdrawal request
    request_data = {
        "user_id": user_id,
        "amount": amount,
        "withdrawal_details": details,
        "timestamp": datetime.utcnow(),
        "status": "pending"
    }
    inserted_result = withdrawal_requests.insert_one(request_data)
    request_obj_id = inserted_result.inserted_id

    await update.message.reply_text(
        f"🎉 Withdrawal request submitted!\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Method: {details['method']}\n"
        f"Your request has been sent to admin and will be processed soon. Your balance will be updated after admin approval.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_to_main')]])
    )

    # Notify admin
    admin_message = (
        f"🚨 **New Withdrawal Request!** 🚨\n"
        f"User ID: [`{user_id}`](tg://user?id={user_id})\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Method: {details['method']}\n"
    )

    if details['method'] == "UPI ID":
        admin_message += f"UPI ID: `{details['id']}`"
    elif details['method'] == "Bank Account":
        admin_message += f"Bank Details:\n```\n{details['details']}\n```"
    elif details['method'] == "QR Code":
        admin_message += f"QR Code File ID: `{details['file_id']}`\n(QR image will be forwarded below)"

    admin_keyboard = [[InlineKeyboardButton("✅ Mark as Paid", callback_data=f"approve_payment_{request_obj_id}")]]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        if details['method'] == "QR Code" and update.message.photo:
            # Forward the original photo message to admin
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⬆️ Above QR code is for User ID `{user_id}` withdrawal (Request ID: `{request_obj_id}`).",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open User Chat", url=f"tg://user?id={user_id}")]])
            )

    except TelegramError as e:
        logger.error(f"Failed to notify admin {ADMIN_ID} about withdrawal request: {e}")
    finally:
        clear_user_state(user_id)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)

    if update:
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text('⚠️ An error occurred. Please try again.')
            except Exception as e:
                logger.error(f"Failed to send error message to callback_query user: {e}")
        elif update.message:
            try:
                await update.message.reply_text('⚠️ An error occurred. Please try again.')
            except Exception as e:
                logger.error(f"Failed to send error message to message user: {e}")
        else:
            logger.warning(f"Error occurred with unhandled update type: {update}")
    else:
        logger.warning("Error handler called with None update object.")

async def cleanup_old_data(context: ContextTypes.DEFAULT_TYPE):
    application_instance = context.job.data["application_instance"]
    logger.info("Attempting MongoDB data cleanup...")

    # For demonstration, assume 95% usage for cleanup to run
    # In a real scenario, you'd check actual MongoDB storage statistics.
    # Example (requires admin privileges to DB for 'dbStats'):
    # try:
    #     stats = db.command("dbStats")
    #     db_size_mb = stats.get('dataSize', 0) / (1024 * 1024)
    #     storage_size_mb = stats.get('storageSize', 0) / (1024 * 1024)
    #     db_usage_percentage = (db_size_mb / storage_size_mb) * 100 if storage_size_mb else 0
    # except Exception as e:
    #     logger.warning(f"Could not get MongoDB stats: {e}. Assuming high usage for cleanup.")
    db_usage_percentage = 95 # Placeholder for now

    if db_usage_percentage >= 90:
        logger.warning(f"MongoDB usage is at {db_usage_percentage:.2f}%. Initiating cleanup of old data.")

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Find users with 0 balance, not admin, and inactive for 30 days
        users_to_delete_cursor = users.find({
            "balance": 0.0,
            "user_id": {"$ne": ADMIN_ID}, # Exclude admin
            "$or": [
                {"created_at": {"$lt": thirty_days_ago}}, # Created before 30 days and inactive
                {"last_click": {"$lt": thirty_days_ago}} # Last click before 30 days
            ]
        }).sort("created_at", 1) # Sort by creation date to delete oldest first

        users_to_delete = list(users_to_delete_cursor)

        if not users_to_delete:
            logger.info("No suitable non-admin users with 0 balance and inactivity found for cleanup.")
            return

        # Delete up to 20% of inactive users to free up space
        num_to_delete = max(1, int(len(users_to_delete) * 0.20))
        users_to_delete = users_to_delete[:num_to_delete]

        deleted_count = 0
        deleted_user_ids = []
        for user_doc in users_to_delete:
            if user_doc['user_id'] == ADMIN_ID or user_doc['balance'] > 0.0:
                logger.warning(f"Attempted to delete user {user_doc['user_id']} with non-zero balance or ADMIN_ID during cleanup. Skipping.")
                continue

            try:
                users.delete_one({"_id": user_doc['_id']})
                user_states.delete_one({"user_id": user_doc['user_id']}) # Also clear their state if any
                # Optionally delete their withdrawal requests if any, depending on your policy
                # withdrawal_requests.delete_many({"user_id": user_doc['user_id']})
                deleted_count += 1
                deleted_user_ids.append(user_doc['user_id'])
            except Exception as e:
                logger.error(f"Error deleting user {user_doc['user_id']} during cleanup: {e}")

        logger.info(f"MongoDB cleanup complete. Deleted {deleted_count} users. User IDs: {deleted_user_ids}")

        admin_msg = f"🧹 **MongoDB Cleanup Alert!** 🧹\n" \
                    f"Database usage was high ({db_usage_percentage:.2f}%).\n" \
                    f"{deleted_count} oldest *inactive users with 0 balance* have been deleted to free up space.\n" \
                    f"Deleted User IDs: {', '.join(map(str, deleted_user_ids)) if deleted_user_ids else 'None'}"
        try:
            await application_instance.bot.send_message(
                chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send cleanup notification to admin: {e}")
    else:
        logger.info(f"MongoDB usage is at {db_usage_percentage:.2f}%, no cleanup needed yet.")


# Initialize the Application globally
application = Application.builder().token(TOKEN).build()

# Add handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('admin', admin_command, filters=filters.User(ADMIN_ID)))
application.add_handler(CommandHandler('broadcast', broadcast_command, filters=filters.User(ADMIN_ID)))
application.add_handler(CommandHandler('stats', stats_command, filters=filters.User(ADMIN_ID)))
application.add_handler(CallbackQueryHandler(button_handler))

# Admin input handling (text messages when in specific admin states)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_input))

# User withdrawal input handling (text/photo messages when in specific withdrawal states)
# This handler should only activate for users NOT ADMIN and when they are in a withdrawal state.
# The filters are crucial here.
application.add_handler(MessageHandler(
    (filters.TEXT | filters.PHOTO) & ~filters.COMMAND & ~filters.User(ADMIN_ID),
    handle_withdrawal_input_wrapper
))

application.add_error_handler(error_handler)

# Setup job queue for cleanup
job_queue = application.job_queue
if job_queue is not None:
    job_queue.run_repeating(cleanup_old_data, interval=timedelta(days=1), first=datetime.now() + timedelta(minutes=5), # Run 5 minutes after start
                            data={"application_instance": application})
else:
    logger.error("JobQueue is not initialized. Ensure python-telegram-bot[job-queue] is installed.")


# Flask routes for health check ONLY
@app.route('/')
def health_check():
    return "EarnBot is running!"

def run_flask_server():
    """Runs the Flask health check server."""
    PORT = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == '__main__':
    flask_server_thread = Thread(target=run_flask_server)
    flask_server_thread.daemon = True
    flask_server_thread.start()

    logger.info("Starting Telegram bot in polling mode.")
    try:
        application.run_polling(poll_interval=1, timeout=30)
    except KeyboardInterrupt:
        logger.info("Bot process interrupted. Shutting down.")
        application.stop()
        client.close()
    except Exception as e:
        logger.critical(f"An unhandled error occurred in the polling loop: {e}", exc_info=True)
        application.stop()
        client.close()

