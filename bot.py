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
    MessageHandler,
    filters
)
import requests
from telegram.error import TelegramError # Import TelegramError for robust error handling
from bson.objectid import ObjectId # Import ObjectId for MongoDB _id lookup

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
user_states = db.user_states # A new collection for temporary user states
withdrawal_requests = db.withdrawal_requests # New collection for withdrawal requests

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
    init_withdrawal_requests_db() # Initialize withdrawal requests collection
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
            "referred_by": None # To track who referred them
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

    # Clear any previous user state (important for consistent flow)
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

    # Clear user state if a non-admin clicks any button
    if user_id != ADMIN_ID:
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
        set_user_state(user_id, 'WITHDRAW_ENTER_UPI')
        await query.edit_message_text(
            "Please send your **UPI ID** (e.g., `yourname@bank` or `phonenumber@upi`).",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
        )
    elif query.data == 'withdraw_bank':
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
        set_user_state(user_id, 'WITHDRAW_UPLOAD_QR')
        await query.edit_message_text(
            "Please upload your **UPI QR Code screenshot**. Make sure the QR code is clear and visible.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
        )


    # --- Admin Callbacks ---
    elif query.data == 'admin_get_balance':
        if user_id == ADMIN_ID:
            set_user_state(user_id, 'GET_BALANCE_USER_ID')
            await query.edit_message_text("Please send the User ID of the user whose balance you want to check.")
    elif query.data == 'admin_add_balance':
        if user_id == ADMIN_ID:
            set_user_state(user_id, 'ADD_BALANCE_USER_ID')
            await query.edit_message_text("Please send the User ID of the user to whom you want to add balance.")
    elif query.data == 'admin_main_menu':
        if user_id == ADMIN_ID:
            await admin_menu(update, context) # Re-show admin menu
    elif query.data == 'admin_show_pending_withdrawals': # UPDATED CALLBACK
        if user_id == ADMIN_ID:
            await admin_show_withdrawals(update, context) # Call the new function
    elif query.data.startswith('approve_payment_'): # NEW CALLBACK
        if user_id == ADMIN_ID:
            request_id = query.data.split('_')[2] # Extract the MongoDB _id
            await admin_approve_payment(update, context, request_id)
    # --- End Admin Callbacks ---


# --- Admin Handlers ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    # Clear any existing admin state when starting /admin
    clear_user_state(user_id)
    await admin_menu(update, context)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Get User Balance", callback_data='admin_get_balance')],
        [InlineKeyboardButton("➕ Add Balance to User", callback_data='admin_add_balance')],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data='admin_show_pending_withdrawals')], # Updated button
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

# Admin function to show pending withdrawals
async def admin_show_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_requests = list(withdrawal_requests.find({"status": "pending"}))

    if not pending_requests:
        await update.callback_query.edit_message_text(
            "✅ No pending withdrawal requests at the moment.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
        )
        return

    for req in pending_requests:
        user_obj = get_user(req['user_id']) # Get full user data
        username = user_obj.get('username', f"User_{req['user_id']}") # Get username if available
        
        details_str = ""
        if req['withdrawal_details']['method'] == "UPI ID":
            details_str = f"UPI ID: `{req['withdrawal_details']['id']}`"
        elif req['withdrawal_details']['method'] == "Bank Account":
            details_str = f"Bank Details:\n```\n{req['withdrawal_details']['details']}\n```"
        elif req['withdrawal_details']['method'] == "QR Code":
            details_str = f"QR Code File ID: `{req['withdrawal_details']['file_id']}`"
            # If QR code, try to send the photo again for admin convenience
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
    
    await update.callback_query.edit_message_text(
        "👆 Above are all pending withdrawal requests. Click 'Mark as Paid' to process them.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
    )

# Admin function to approve payment
async def admin_approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: str):
    query = update.callback_query
    await query.answer("Processing payment approval...")

    try:
        request = withdrawal_requests.find_one_and_update(
            {"_id": ObjectId(request_id), "status": "pending"},
            {"$set": {"status": "completed", "completed_at": datetime.utcnow()}},
            return_document=True # Return the updated document
        )

        if request:
            user_id = request['user_id']
            amount = request['amount']
            withdrawal_method = request['withdrawal_details']['method']

            # --- RESET USER DATA AFTER SUCCESSFUL PAYMENT ---
            # Set desired fields back to their initial state (except user_id and withdrawn)
            users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "balance": 0.0,
                    "referrals": 0,
                    "referral_earnings": 0.0,
                    "total_earned": 0.0,
                    "last_click": None,
                    "referred_by": None # Assuming referral chain also resets for this user's earnings
                }}
            )
            logger.info(f"User {user_id}'s earning data reset after successful withdrawal.")
            # --- END RESET USER DATA ---

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
                    f"User's earning data has been reset.", # Add this line
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Pending List", callback_data='admin_show_pending_withdrawals')]])
                )
            except TelegramError as e:
                logger.error(f"Failed to notify user {user_id} about successful payment: {e}")
                await query.edit_message_text(
                    f"✅ Payment for User `{user_id}` (Request ID: `{request_id}`) marked as Paid, but failed to notify user.\n"
                    f"User's earning data has been reset.", # Add this line
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
        # Add more stats here if needed, e.g., total earned, total withdrawn
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
            clear_user_state(user_id) # Clear state after processing

    elif current_state == 'ADD_BALANCE_USER_ID':
        try:
            target_user_id = int(text_input)
            context.user_data['target_user_id_for_add'] = target_user_id # Store temporarily
            set_user_state(user_id, 'ADD_BALANCE_AMOUNT')
            await update.message.reply_text(f"User ID: `{target_user_id}`. Now, please send the amount to add.", parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text(
                "Invalid User ID. Please send a numeric User ID.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Admin Menu", callback_data='admin_main_menu')]])
            )
            clear_user_state(user_id) # Clear state if invalid User ID

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
                clear_user_state(user_id) # Clear state if invalid amount
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
            clear_user_state(user_id) # Clear state after processing
            if 'target_user_id_for_add' in context.user_data:
                del context.user_data['target_user_id_for_add']
    
    elif current_state == 'BROADCAST_MESSAGE':
        message_to_broadcast = text_input
        sent_count = 0
        failed_count = 0
        all_users = users.find({}, {"user_id": 1}) # Fetch only user_id

        for user_doc in all_users:
            try:
                await context.bot.send_message(chat_id=user_doc['user_id'], text=message_to_broadcast)
                sent_count += 1
            except TelegramError as e:
                # Handle specific Telegram errors like user blocking the bot
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
    # This wrapper function checks the state and then calls the appropriate handler
    user_id = update.effective_user.id
    current_state = get_user_state(user_id)
    user = get_user(user_id) 

    # If not in a withdrawal state, or if balance is insufficient, ignore/reset
    if not current_state or not current_state.startswith('WITHDRAW_') or user['balance'] < MIN_WITHDRAWAL:
        if user['balance'] < MIN_WITHDRAWAL:
            await update.message.reply_text(
                f"❌ Your balance (₹{user['balance']:.2f}) is below the minimum withdrawal amount of ₹{MIN_WITHDRAWAL:.2f}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_to_main')]])
            )
        # Clear any potentially stuck withdrawal state if conditions aren't met
        clear_user_state(user_id) 
        return # Exit if not in a valid withdrawal state or not eligible

    # Proceed based on specific withdrawal state
    if current_state == 'WITHDRAW_ENTER_UPI':
        upi_id = update.message.text.strip()
        withdrawal_details = {"method": "UPI ID", "id": upi_id}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_ENTER_BANK':
        bank_details_raw = update.message.text.strip()
        # Basic validation/parsing for bank details (can be improved)
        if len(bank_details_raw) < 50: # Arbitrary length check for minimum details
            await update.message.reply_text(
                "Please provide complete bank account details in the specified format.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
            )
            return # Don't clear state yet, await correct input
        
        withdrawal_details = {"method": "Bank Account", "details": bank_details_raw}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_UPLOAD_QR':
        if update.message.photo:
            # Get the largest photo (last element in the list)
            file_id = update.message.photo[-1].file_id
            withdrawal_details = {"method": "QR Code", "file_id": file_id}
            await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)
        else:
            await update.message.reply_text(
                "Please upload a **photo** of your QR Code. Text messages are not accepted for QR code withdrawals.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Cancel", callback_data='back_to_main')]])
            )
            return # Don't clear state yet, await correct input
    
    # After successful processing, or if wrong input type for QR, clear state is done in process_withdrawal_request
    # or the specific handler allows retry. This part is mostly for debugging or future expansion.
    # If control reaches here for an unhandled state, it might mean an unexpected input.
    else: # Fallback for unexpected states
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
        "withdrawal_details": details, # Store the dictionary with method and specific details
        "timestamp": datetime.utcnow(),
        "status": "pending"
    }
    # This inserts the _id which we will use for approval
    inserted_result = withdrawal_requests.insert_one(request_data) 
    request_obj_id = inserted_result.inserted_id

    # Deduct balance and update withdrawn amount
    # IMPORTANT: We are only setting balance to 0.0 here. Other stats are reset on admin approval.
    users.update_one(
        {"user_id": user_id},
        {"$set": {"balance": 0.0}, "$inc": {"withdrawn": amount}}
    )

    await update.message.reply_text(
        f"🎉 Withdrawal request submitted!\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Method: {details['method']}\n"
        f"Your balance has been reset to ₹0.00. Your request will be processed soon.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_to_main')]])
    )

    # Notify admin
    admin_message = (
        f"🚨 **New Withdrawal Request!** 🚨\n"
        f"User ID: [`{user_id}`](tg://user?id={user_id})\n" # Link to user's profile
        f"Amount: ₹{amount:.2f}\n"
        f"Method: {details['method']}\n"
    )

    if details['method'] == "UPI ID":
        admin_message += f"UPI ID: `{details['id']}`"
    elif details['method'] == "Bank Account":
        admin_message += f"Bank Details:\n```\n{details['details']}\n```"
    elif details['method'] == "QR Code":
        admin_message += f"QR Code File ID: `{details['file_id']}`\n(QR image sent separately below)"
    
    admin_keyboard = [[InlineKeyboardButton("✅ Mark as Paid", callback_data=f"approve_payment_{request_obj_id}")]]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        if details['method'] == "QR Code" and update.message.photo:
            # Also forward the QR code photo to the admin for convenience
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
        clear_user_state(user_id) # Clear state after successful submission


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)
    
    # Check if update is not None before accessing its attributes
    if update:
        # Check if update.callback_query is not None
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text('⚠️ An error occurred. Please try again.')
            except Exception as e:
                logger.error(f"Failed to send error message to callback_query user: {e}")
        # Check if update.message is not None
        elif update.message:
            try:
                await update.message.reply_text('⚠️ An error occurred. Please try again.')
            except Exception as e:
                logger.error(f"Failed to send error message to message user: {e}")
        else:
            # If neither callback_query nor message, log the update object
            logger.warning(f"Error occurred with unhandled update type: {update}")
    else:
        logger.warning("Error handler called with None update object.")

# --- NEW: MongoDB Cleanup Function ---
# This function will run periodically
def cleanup_old_data(application_instance):
    """
    Cleans up old user data if MongoDB storage approaches its limit.
    This is a conceptual function as exact MongoDB storage monitoring
    depends on your hosting (e.g., MongoDB Atlas metrics, local `db.stats()`).
    For demonstration, we'll use a placeholder for "check_db_usage".
    """
    logger.info("Attempting MongoDB data cleanup...")
    
    # --- IMPORTANT: Replace this with actual MongoDB usage check ---
    # How to get actual usage depends on your MongoDB setup:
    # - For MongoDB Atlas: Use their API or monitoring tools.
    # - For a local MongoDB: You can run `db.command("dbstats")` and parse 'dataSize' or 'storageSize'.
    #   However, this can be complex to integrate directly into a Python bot without
    #   proper authentication/permissions setup for 'db.command'.
    # For now, we'll simulate a high usage condition.
    
    # Placeholder: Assume we are at 95% usage for testing.
    # In a real scenario, you'd fetch actual usage and calculate percentage.
    # For example:
    # db_stats = db.command("dbstats")
    # current_size_mb = db_stats['dataSize'] / (1024*1024)
    # total_storage_mb = YOUR_MONGO_DB_CAP_MB # You need to define this if applicable
    # db_usage_percentage = (current_size_mb / total_storage_mb) * 100 if total_storage_mb > 0 else 0
    
    db_usage_percentage = 95 # Simulating high usage for demonstration

    if db_usage_percentage >= 90: # Trigger cleanup if 90% or more full
        logger.warning(f"MongoDB usage is at {db_usage_percentage:.2f}%. Initiating cleanup of old data.")
        
        # Find oldest users who have successfully withdrawn (less likely to be active)
        # Or, simply oldest users who haven't interacted in a long time.
        # For simplicity and your request: "20% puran data jispe kuxh kam nhi ho rah ho"
        # We'll consider users who haven't had recent clicks or activity, ordered by creation date.
        
        # Option 1: Oldest users, regardless of activity (simplest, but might delete active users)
        # all_users = list(users.find({}).sort("created_at", 1)) # Sort by creation date ascending
        
        # Option 2: Users who haven't clicked a link recently (better for "inactive")
        # You might need to define what "inactive" means (e.g., no last_click in X days)
        # For this example, let's just get the oldest users based on creation date
        # and prioritize those with 0 balance (already withdrawn or never earned much)
        
        # Get total number of users
        total_users_count = users.count_documents({})
        if total_users_count == 0:
            logger.info("No users to clean up.")
            return

        # Calculate 20% of users to delete
        num_to_delete = max(1, int(total_users_count * 0.20)) # Ensure at least 1 user is deleted if applicable

        logger.info(f"Attempting to delete {num_to_delete} oldest inactive users.")

        # Find the oldest users to delete.
        # A simple approach: find users sorted by 'created_at' in ascending order.
        # You could also consider users with 'balance': 0, meaning they've withdrawn or never earned.
        # For a truly "inactive" user, you might need a `last_activity` field.
        
        # Let's target users with 0 balance (already withdrawn or minimal activity) AND are oldest.
        users_to_delete = list(users.find({"balance": 0.0}) # Users with zero balance
                                  .sort("created_at", 1) # Oldest first
                                  .limit(num_to_delete))

        if not users_to_delete:
            logger.info("Could not find suitable users to clean up (e.g., no users with 0 balance).")
            # Fallback: if no 0-balance users, just delete the very oldest ones
            users_to_delete = list(users.find({})
                                      .sort("created_at", 1)
                                      .limit(num_to_delete))
            if not users_to_delete:
                 logger.info("No users found to delete even with fallback.")
                 return

        deleted_count = 0
        deleted_user_ids = []
        for user_doc in users_to_delete:
            try:
                users.delete_one({"_id": user_doc['_id']})
                user_states.delete_one({"user_id": user_doc['user_id']}) # Also clear their states
                # You might also want to delete their withdrawal requests if they are 'completed'
                # For simplicity, we'll keep withdrawal requests for historical tracking,
                # but you could delete old 'completed' ones too.
                deleted_count += 1
                deleted_user_ids.append(user_doc['user_id'])
            except Exception as e:
                logger.error(f"Error deleting user {user_doc['user_id']} during cleanup: {e}")
        
        logger.info(f"MongoDB cleanup complete. Deleted {deleted_count} users. User IDs: {deleted_user_ids}")
        # Notify admin about cleanup
        try:
            admin_msg = f"🧹 **MongoDB Cleanup Alert!** 🧹\n" \
                        f"Database usage was high ({db_usage_percentage:.2f}%).\n" \
                        f"{deleted_count} oldest inactive users have been deleted to free up space.\n" \
                        f"Deleted User IDs: {', '.join(map(str, deleted_user_ids)) if deleted_user_ids else 'None'}"
            # Send as a separate thread to not block the main loop if many users
            Thread(target=lambda: application_instance.bot.send_message(
                chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown'
            )).start()
        except Exception as e:
            logger.error(f"Failed to send cleanup notification to admin: {e}")
    else:
        logger.info(f"MongoDB usage is at {db_usage_percentage:.2f}%, no cleanup needed yet.")


def run_bot():
    """Runs the Telegram bot using polling."""
    try:
        application = Application.builder().token(TOKEN).build()

        # Delete any lingering webhooks to prevent conflicts, especially in polling mode
        try:
            logger.info("Deleting any existing webhooks...")
            webhook_deleted = application.bot.delete_webhook()
            if webhook_deleted:
                logger.info("Existing webhook successfully deleted.")
            else:
                logger.warning("No webhook to delete or deletion failed silently.")
        except TelegramError as e:
            logger.warning(f"Could not delete webhook (may not exist or permission issue): {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during webhook deletion: {e}")


        # Add handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('admin', admin_command, filters=filters.User(ADMIN_ID)))
        application.add_handler(CommandHandler('broadcast', broadcast_command, filters=filters.User(ADMIN_ID)))
        application.add_handler(CommandHandler('stats', stats_command, filters=filters.User(ADMIN_ID)))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Handler for admin text inputs based on state
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_input))
        
        # Handler for ALL user inputs when in a withdrawal state (text or photo)
        application.add_handler(MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND & ~filters.User(ADMIN_ID),
            handle_withdrawal_input_wrapper # Use a wrapper to check state before calling the main handler
        ))


        application.add_error_handler(error_handler)

        logger.info("Starting Telegram bot with polling...")
        # Add job queue for periodic cleanup
        job_queue = application.job_queue
        # Schedule cleanup to run every 12 hours (adjust as needed)
        # job_queue.run_repeating(cleanup_old_data, interval=timedelta(hours=12), first=0, data={"application_instance": application})
        # For testing, you might use a shorter interval like 1 minute:
        job_queue.run_repeating(cleanup_old_data, interval=timedelta(minutes=1), first=0, data={"application_instance": application})


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

