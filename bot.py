import os
import logging
from datetime import datetime, timedelta, date # Import date (though we'll primarily use datetime)
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
import uuid # For generating unique IDs
import random # For random selection of shortlink API

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
MIN_WITHDRAWAL = 10
# EARN_PER_LINK is now dynamic based on links_completed_today
REFERRAL_BONUS = 0.50
LINK_COOLDOWN = 1  # minutes
REQUIRED_LINKS_FOR_REFERRAL_BONUS = 5 # Number of links a referred user must complete
DAILY_LINK_LIMIT = 30 # NEW: Maximum links a user can complete in a day

# Shortlink API configurations
SHORTLINK_APIS = [
    {"name": "Arlinks", "base_url": "https://arlinks.in/api", "token": "5bcaa11eddf0429bf55ee2b84230fb3dc9cee28a"},
    {"name": "Just2Earn", "base_url": "https://just2earn.com/api", "token": "3e26a55a7dd8ba61786bb707ac451f783c0f4ab8"},
    {"name": "GPLinks", "base_url": "https://api.gplinks.com/api", "token": "7c9045b10559ffa7d8358a3e83984dc63a61c72e"},
    {"name": "Seturl", "base_url": "https://seturl.in/api", "token": "c7f2f4eb705e0aa27a46fb3aa3fc3d41220c6cfb"},
    {"name": "Short2Url", "base_url": "https://short2url.in/api", "token": "36a440ba814cf37f362ea8be07af667b5d53c2d7"},
    {"name": "Adrinolinks", "base_url": "https://adrinolinks.in/api", "token": "4f374dca406de7d0fe955ee2c1f731b250175895"},
    {"name": "Linkpays", "base_url": "https://linkpays.in/api", "token": "35aced15e021e8efcf1870f5208e4fba97a55d92"},
    {"name": "ShrinkForEarn", "base_url": "https://shrinkforearn.in/api", "token": "42e84174eceb9661f177065846b130e37b6e368b"},
    {"name": "Arolinks", "base_url": "https://arolinks.com/api", "token": "e59d9a7076acc80820345129b5634aec2f6c54c6"}
]

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
            "username": None, # Will be set on /start
            "balance": 0.0,
            "referral_code": f"ref_{user_id}",
            "referrals": 0,
            "referral_earnings": 0.0,
            "total_earned": 0.0,
            "withdrawn": 0.0,
            "last_click": None,
            "created_at": datetime.utcnow(),
            "referred_by": None,
            "links_completed": 0, # Total links ever completed by this user
            "links_completed_today": 0, # NEW: Links completed today for daily limit
            "last_earning_day": datetime.utcnow() # CHANGED: Store full datetime, for daily reset
        }
        users.insert_one(user)
    
    # Ensure new fields are present for existing users and fix datetime.date issue
    # This migration logic should ideally run once on startup or as a separate script
    if "links_completed_today" not in user:
        users.update_one({"user_id": user_id}, {"$set": {"links_completed_today": 0}})
        user["links_completed_today"] = 0
    
    # Fix for datetime.date if it was previously stored
    if "last_earning_day" not in user or isinstance(user["last_earning_day"], date) and not isinstance(user["last_earning_day"], datetime):
        # If it's a date object, convert it to a datetime at the start of that day UTC
        if isinstance(user.get("last_earning_day"), date):
            converted_datetime = datetime(user["last_earning_day"].year, user["last_earning_day"].month, user["last_earning_day"].day, 0, 0, 0)
            users.update_one({"user_id": user_id}, {"$set": {"last_earning_day": converted_datetime}})
            user["last_earning_day"] = converted_datetime
        else: # If not present or some other unexpected type, set to current UTC datetime
            users.update_one({"user_id": user_id}, {"$set": {"last_earning_day": datetime.utcnow()}})
            user["last_earning_day"] = datetime.utcnow()

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
    selected_api = random.choice(SHORTLINK_APIS)
    api_name = selected_api["name"]
    base_url = selected_api["base_url"]
    api_token = selected_api["token"]

    try:
        params = {
            'api': api_token,
            'url': long_url
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        result = response.json()

        if result.get('status') == 'error':
            logger.error(f"{api_name} API Error: {result.get('message')}")
            return None
        elif result.get('shortenedUrl'):
            return result['shortenedUrl']
        elif result.get('short'):
             return result['short']
        else:
            logger.error(f"Unexpected {api_name} API response: {result}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to {api_name} API: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing {api_name} API response (not JSON): {e}")
        return None

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    user = get_user(user_id) # Ensure user object is fetched with potential date fix
    bot_username = (await context.bot.get_me()).username

    # Update user's username in DB
    if user.get('username') != username:
        update_user(user_id, {"username": username})

    clear_user_state(user_id)

    # --- Daily Link Count Reset Logic ---
    current_utc_date = datetime.utcnow().date()
    # Compare only the date part of 'last_earning_day'
    if user['last_earning_day'].date() != current_utc_date:
        users.update_one(
            {"user_id": user_id},
            {"$set": {
                "links_completed_today": 0,
                "last_earning_day": datetime.utcnow() # Store full datetime when resetting
            }}
        )
        user['links_completed_today'] = 0 # Update in current user object as well for immediate use
        user['last_earning_day'] = datetime.utcnow() # Update in current user object
    # --- End Daily Link Count Reset Logic ---

    if context.args:
        arg = context.args[0]
        if arg.startswith('ref_'):
            referrer_id = int(arg.split('_')[1])
            referrer = get_user(referrer_id)
            if referrer and referrer['user_id'] != user_id and user['referred_by'] is None:
                # Store referrer ID, but don't give bonus yet
                users.update_one({"user_id": user_id}, {"$set": {"referred_by": referrer_id}})
                await update.message.reply_text(
                    f"🎉 Welcome! You were referred by {referrer_id}! "
                    f"The referrer will receive a bonus once you complete {REQUIRED_LINKS_FOR_REFERRAL_BONUS} links."
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
                    # Re-send main menu buttons
                    keyboard = [
                        [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')],
                        [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')],
                        [InlineKeyboardButton("👥 Refer Friends", callback_data='referral')]
                    ]
                    await update.message.reply_text(
                        "Please choose an option:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return

                # --- Tiered Earning Logic ---
                earning_rate = 0.0
                notification_message = ""
                
                # Re-fetch user to ensure latest links_completed_today count
                updated_user_for_earning = get_user(user_id) 

                if updated_user_for_earning['links_completed_today'] < 10:
                    earning_rate = 0.15
                    if updated_user_for_earning['links_completed_today'] == 9: # After completing 10th link, for 11th
                        notification_message = "\n---\n**सूचना:** आपने आज अपनी पहली 10 लिंक पूरी कर ली हैं। अब से, आपको प्रति लिंक ₹0.10 मिलेंगे।"
                elif updated_user_for_earning['links_completed_today'] < 20:
                    earning_rate = 0.10
                    if updated_user_for_earning['links_completed_today'] == 19: # After completing 20th link, for 21st
                        notification_message = "\n---\n**सूचना:** आपने आज अपनी 20 लिंक पूरी कर ली हैं। अब से, आपको प्रति लिंक ₹0.05 मिलेंगे। यह आपकी दैनिक कमाई की अंतिम दर है।"
                elif updated_user_for_earning['links_completed_today'] < DAILY_LINK_LIMIT: # Limit at 30
                    earning_rate = 0.05
                else:
                    # Daily limit reached
                    await update.message.reply_text(
                        "आप आज के लिए इतनी ही लिंक जनरेट कर सकते हैं। कृपया अगले दिन प्रयास करें।\n"
                        "--- \nअधिक पैसा कमाने के लिए अपने दोस्तों को रेफर करें!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 दोस्तों को रेफर करें", callback_data='referral')]])
                    )
                    return # Exit without earning

                # Update user's balance and link counts
                new_balance = updated_user_for_earning['balance'] + earning_rate
                
                users.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "balance": new_balance,
                        "total_earned": updated_user_for_earning['total_earned'] + earning_rate,
                        "last_click": datetime.utcnow(),
                        "last_earning_day": datetime.utcnow() # Store full datetime
                    },
                     "$inc": {
                         "links_completed": 1, # Total links ever completed
                         "links_completed_today": 1 # Links completed today
                     }
                    }
                )
                
                # Re-fetch user after update to get the very latest count for referral bonus check
                updated_user_after_earning = get_user(user_id) 
                
                # Check for referral bonus
                if updated_user_after_earning['referred_by'] is not None and updated_user_after_earning['links_completed_today'] == REQUIRED_LINKS_FOR_REFERRAL_BONUS:
                    referrer_id = updated_user_after_earning['referred_by']
                    referrer = get_user(referrer_id)
                    if referrer:
                        users.update_one(
                            {"user_id": referrer_id},
                            {"$inc": {
                                "referrals": 1,
                                "referral_earnings": REFERRAL_BONUS,
                                "balance": REFERRAL_BONUS,
                                "total_earned": REFERRAL_BONUS
                            }}
                        )
                        # Remove referred_by after bonus is given to prevent double counting
                        users.update_one({"user_id": user_id}, {"$unset": {"referred_by": ""}})
                        
                        await update.message.reply_text(
                            f"🎉 Congratulations! आपने आज {REQUIRED_LINKS_FOR_REFERRAL_BONUS} लिंक पूरी कर ली हैं। "
                            f"आपके रेफ़रर ({referrer_id}) के खाते में ₹{REFERRAL_BONUS:.2f} का बोनस जोड़ दिया गया है।"
                        )
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 **Referral Bonus!** 🎉\n\n"
                                     f"User [{updated_user_after_earning.get('username', f'User_{user_id}')}](tg://user?id={user_id}) "
                                     f"has completed {REQUIRED_LINKS_FOR_REFERRAL_BONUS} links. "
                                     f"You earned ₹{REFERRAL_BONUS:.2f}!\n"
                                     f"Your new balance: ₹{referrer['balance'] + REFERRAL_BONUS:.2f}",
                                parse_mode='Markdown'
                            )
                        except TelegramError as e:
                            logger.warning(f"Failed to notify referrer {referrer_id} about bonus: {e}")

                await update.message.reply_text(
                    f"✅ Link solved successfully!\n"
                    f"💰 आपने ₹{earning_rate:.2f} कमाए हैं। आपका नया बैलेंस: ₹{new_balance:.2f}"
                    f"{notification_message}"
                )
            else:
                await update.message.reply_text("यह लिंक आपके लिए जनरेट नहीं की गई थी।")

    keyboard = [
        [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')],
        [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')],
        [InlineKeyboardButton("👥 Refer Friends", callback_data='referral')]
    ]

    await update.message.reply_text(
        "🎉 Earn Bot में आपका स्वागत है!\n"
        f"लिंक सॉल्व करें और प्रति लिंक ₹0.15 तक कमाएं!\n" # Initial earning rate in message
        f"न्यूनतम निकासी: ₹{MIN_WITHDRAWAL}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id) # Ensure user object is fetched with potential date fix
    bot_username = (await context.bot.get_me()).username

    # --- Daily Link Count Reset Logic for Callback Queries ---
    current_utc_date = datetime.utcnow().date()
    # Compare only the date part of 'last_earning_day'
    if user['last_earning_day'].date() != current_utc_date:
        users.update_one(
            {"user_id": user_id},
            {"$set": {
                "links_completed_today": 0,
                "last_earning_day": datetime.utcnow() # Store full datetime when resetting
            }}
        )
        user = get_user(user_id) # Re-fetch user object to get updated counts
    # --- End Daily Link Count Reset Logic ---

    if query.data == 'generate_link':
        clear_user_state(user_id)

        # Check daily limit BEFORE cooldown
        if user['links_completed_today'] >= DAILY_LINK_LIMIT:
            await query.edit_message_text(
                "आप आज के लिए इतनी ही लिंक जनरेट कर सकते हैं। कृपया अगले दिन प्रयास करें।\n"
                "--- \nअधिक पैसा कमाने के लिए अपने दोस्तों को रेफर करें!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 दोस्तों को रेफर करें", callback_data='referral')],
                                                   [InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]]) # Added back button here
            )
            return

        if user['last_click'] and (datetime.utcnow() - user['last_click']) < timedelta(minutes=LINK_COOLDOWN):
            remaining = (user['last_click'] + timedelta(minutes=LINK_COOLDOWN)) - datetime.utcnow()
            remaining_seconds = int(remaining.total_seconds())
            await query.edit_message_text(f"⏳ कृपया एक और लिंक जनरेट करने से पहले {remaining_seconds} सेकंड इंतजार करें।")
            return

        # Generate a unique long URL by adding a UUID
        unique_param = uuid.uuid4().hex
        destination_link = f"https://t.me/{bot_username}?start=solve_{user_id}_{unique_param}"
        short_link = generate_short_link(destination_link)

        if not short_link:
            await query.edit_message_text(
                "❌ लिंक जनरेट करने में समस्या हुई। कृपया बाद में पुनः प्रयास करें।"
            )
            return

        keyboard_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 लिंक हल करने के लिए क्लिक करें", url=short_link)],
            [InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]
        ])

        await query.edit_message_text(
            f"✅ आपकी लिंक तैयार है! इसे हल करने के लिए नीचे दिए गए बटन पर क्लिक करें।\n\n"
            f"एक बार जब आप वेबसाइट पर चरणों को पूरा कर लेंगे, तो आपको मेरे पास वापस भेज दिया जाएगा, और आपका बैलेंस स्वचालित रूप से अपडेट हो जाएगा।\n"
            f"⏳ सफल समापन के बाद {LINK_COOLDOWN} मिनट के बाद अगली लिंक उपलब्ध होगी।",
            reply_markup=keyboard_markup
        )

    elif query.data == 'wallet':
        clear_user_state(user_id)
        await query.edit_message_text(
            f"💰 आपका वॉलेट\n\n"
            f"🪙 बैलेंस: ₹{user['balance']:.2f}\n"
            f"📊 कुल कमाई: ₹{user['total_earned']:.2f}\n"
            f"💸 निकाली गई राशि: ₹{user['withdrawn']:.2f}\n"
            f"👥 रेफरल: {user['referrals']} (₹{user['referral_earnings']:.2f})\n"
            f"🔗 आज पूरे किए गए लिंक: {user.get('links_completed_today', 0)} / {DAILY_LINK_LIMIT}\n\n" # Display daily count
            f"💵 न्यूनतम निकासी: ₹{MIN_WITHDRAWAL}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💵 निकालें", callback_data='withdraw')],
                [InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]
            ])
        )

    elif query.data == 'referral':
        clear_user_state(user_id)
        referral_message = (
            f"👥 रेफरल प्रोग्राम\n\n"
            f"🔗 आपकी रेफरल लिंक:\n"
            f"https://t.me/{bot_username}?start={user['referral_code']}\n\n"
            f"💰 अपने दोस्तों को अपनी लिंक का उपयोग करके जुड़ने और {REQUIRED_LINKS_FOR_REFERRAL_BONUS} लिंक पूरे करने पर प्रति मित्र ₹{REFERRAL_BONUS:.2f} कमाएं!\n"
            f"👥 कुल रेफरल: {user['referrals']}\n"
            f"💸 रेफरल से कमाई: ₹{user['referral_earnings']:.2f}"
        )
        await query.edit_message_text(
            referral_message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]])
        )

    elif query.data == 'back_to_main':
        clear_user_state(user_id)
        keyboard = [
            [InlineKeyboardButton("💰 लिंक जनरेट करें", callback_data='generate_link')],
            [InlineKeyboardButton("📊 मेरा वॉलेट", callback_data='wallet')],
            [InlineKeyboardButton("👥 दोस्तों को रेफर करें", callback_data='referral')]
        ]
        await query.edit_message_text(
            "🎉 Earn Bot में आपका स्वागत है!\n"
            f"लिंक हल करें और प्रति लिंक ₹0.15 तक कमाएं!\n"
            f"न्यूनतम निकासी: ₹{MIN_WITHDRAWAL}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == 'withdraw':
        clear_user_state(user_id)
        if user['balance'] >= MIN_WITHDRAWAL:
            keyboard = [
                [InlineKeyboardButton("💳 UPI ID", callback_data='withdraw_upi')],
                [InlineKeyboardButton("🏦 बैंक खाता", callback_data='withdraw_bank')],
                [InlineKeyboardButton("🤳 QR कोड (स्क्रीनशॉट)", callback_data='withdraw_qr')],
                [InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]
            ]
            await query.edit_message_text(
                f"✅ आपका बैलेंस ₹{user['balance']:.2f} है। कृपया अपनी पसंदीदा निकासी विधि चुनें:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                f"❌ आपका बैलेंस (₹{user['balance']:.2f}) न्यूनतम निकासी राशि ₹{MIN_WITHDRAWAL:.2f} से कम है।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]])
            )

    # New withdrawal method callbacks
    elif query.data == 'withdraw_upi':
        if user['balance'] < MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ आपका बैलेंस (₹{user['balance']:.2f}) न्यूनतम निकासी राशि ₹{MIN_WITHDRAWAL:.2f} से कम है।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_ENTER_UPI')
        await query.edit_message_text(
            "कृपया अपनी **UPI ID** भेजें (जैसे, `आपकानाम@बैंक` या `फ़ोननंबर@upi`)।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]])
        )
    elif query.data == 'withdraw_bank':
        if user['balance'] < MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ आपका बैलेंस (₹{user['balance']:.2f}) न्यूनतम निकासी राशि ₹{MIN_WITHDRAWAL:.2f} से कम है।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_ENTER_BANK')
        await query.edit_message_text(
            "कृपया अपने **बैंक खाते का विवरण** निम्नलिखित प्रारूप में भेजें:\n\n"
            "```\n"
            "खाता धारक का नाम: [आपका नाम]\n"
            "खाता संख्या: [आपका खाता संख्या]\n"
            "IFSC कोड: [आपका IFSC कोड]\n"
            "बैंक का नाम: [आपके बैंक का नाम]\n"
            "```\n"
            "उदाहरण:\n"
            "```\n"
            "खाता धारक का नाम: जॉन डो\n"
            "खाता संख्या: 123456789012\n"
            "IFSC कोड: SBIN0000001\n"
            "बैंक का नाम: स्टेट बैंक ऑफ़ इंडिया\n"
            "```",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]])
        )
    elif query.data == 'withdraw_qr':
        if user['balance'] < MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ आपका बैलेंस (₹{user['balance']:.2f}) न्यूनतम निकासी राशि ₹{MIN_WITHDRAWAL:.2f} से कम है।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data='back_to_main')]])
            )
            return
        set_user_state(user_id, 'WITHDRAW_UPLOAD_QR')
        await query.edit_message_text(
            "कृपया अपने **UPI QR कोड का स्क्रीनशॉट** अपलोड करें। सुनिश्चित करें कि QR कोड स्पष्ट और दिखाई दे रहा हो।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]])
        )

    # --- Admin Callbacks ---
    elif query.data == 'admin_get_balance':
        if user_id == ADMIN_ID:
            clear_user_state(user_id)
            set_user_state(user_id, 'GET_BALANCE_USER_ID')
            await query.edit_message_text("कृपया उस यूजर आईडी भेजें जिसका बैलेंस आप देखना चाहते हैं।")
    elif query.data == 'admin_add_balance':
        if user_id == ADMIN_ID:
            clear_user_state(user_id)
            set_user_state(user_id, 'ADD_BALANCE_USER_ID')
            await query.edit_message_text("कृपया उस यूजर आईडी भेजें जिसे आप बैलेंस जोड़ना चाहते हैं।")
    elif query.data == 'admin_main_menu':
        if user_id == ADMIN_ID:
            clear_user_state(user_id)
            await admin_menu(update, context)
    elif query.data == 'admin_show_pending_withdrawals':
        if user_id == ADMIN_ID:
            clear_user_state(user_id)
            await admin_show_withdrawals(update, context)
    elif query.data.startswith('approve_payment_'):
        if user_id == ADMIN_ID:
            request_id = query.data.split('_')[2]
            await admin_approve_payment(update, context, request_id)


# --- Admin Handlers ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 आपको इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return

    clear_user_state(user_id)
    await admin_menu(update, context)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 यूजर बैलेंस प्राप्त करें", callback_data='admin_get_balance')],
        [InlineKeyboardButton("➕ यूजर को बैलेंस जोड़ें", callback_data='admin_add_balance')],
        [InlineKeyboardButton("💸 लंबित निकासी", callback_data='admin_show_pending_withdrawals')],
        [InlineKeyboardButton("↩️ मुख्य मेनू पर वापस", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "⚙️ एडमिन पैनल विकल्प:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚙️ एडमिन पैनल विकल्प:",
            reply_markup=reply_markup
        )

async def admin_show_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_requests = list(withdrawal_requests.find({"status": "pending"}))

    if not pending_requests:
        await update.callback_query.edit_message_text(
            "✅ इस समय कोई लंबित निकासी अनुरोध नहीं हैं।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
        )
        return

    await update.callback_query.edit_message_text("लंबित निकासी अनुरोध प्राप्त हो रहे हैं...")

    for req in pending_requests:
        user_obj = get_user(req['user_id'])
        username = user_obj.get('username', f"User_{req['user_id']}") # Use stored username

        details_str = ""
        if req['withdrawal_details']['method'] == "UPI ID":
            details_str = f"UPI ID: `{req['withdrawal_details']['id']}`"
        elif req['withdrawal_details']['method'] == "Bank Account":
            details_str = f"बैंक विवरण:\n```\n{req['withdrawal_details']['details']}\n```"
        elif req['withdrawal_details']['method'] == "QR Code":
            details_str = f"QR कोड फ़ाइल आईडी: `{req['withdrawal_details']['file_id']}`"
            try:
                # Send the QR photo separately for better visibility
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=req['withdrawal_details']['file_id'],
                    caption=f"यूजर `{req['user_id']}` के लिए QR (राशि: ₹{req['amount']:.2f})",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"रिक्वेस्ट {req['_id']} के लिए एडमिन को QR फोटो दोबारा भेजने में विफल: {e}")
                details_str += "\n_ (QR फोटो दोबारा नहीं भेजी जा सकी) _"

        message_text = (
            f"💸 **लंबित निकासी अनुरोध** 💸\n"
            f"यूजर: [{username}](tg://user?id={req['user_id']})\n"
            f"यूजर आईडी: `{req['user_id']}`\n"
            f"राशि: ₹{req['amount']:.2f}\n"
            f"विधि: {req['withdrawal_details']['method']}\n"
            f"{details_str}\n"
            f"अनुरोध किया गया: {req['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        keyboard = [[InlineKeyboardButton("✅ भुगतान किया गया चिह्नित करें", callback_data=f"approve_payment_{req['_id']}")]]

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text="👆 ऊपर सभी लंबित निकासी अनुरोध हैं। उन्हें प्रोसेस करने के लिए 'भुगतान किया गया चिह्नित करें' पर क्लिक करें।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
    )

async def admin_approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: str):
    query = update.callback_query
    await query.answer("भुगतान अनुमोदन प्रोसेस किया जा रहा है...")

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

            # Reset balance to 0, and increment 'withdrawn' by the amount
            users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "balance": 0.0, # Reset balance to 0 after withdrawal
                    "last_click": None, # Reset last_click so they can generate new links immediately
                    "links_completed_today": 0, # Reset daily count on withdrawal approval for fresh start
                    "last_earning_day": datetime.utcnow() # Ensure day is reset to current datetime
                },
                    "$inc": {
                        "withdrawn": amount # Increment total withdrawn amount
                    }
                }
            )
            logger.info(f"यूजर {user_id} का बैलेंस रीसेट हो गया है और सफलतापूर्वक {amount} की निकासी के बाद निकाली गई राशि अपडेट हो गई है।")

            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **भुगतान सफल!** 🎉\n\n"
                         f"₹{amount:.2f} की आपकी निकासी अनुरोध ({withdrawal_method} के माध्यम से) सफलतापूर्वक प्रोसेस हो गई है।\n"
                         f"आपका कमाई बैलेंस नए सिरे से शुरू करने के लिए रीसेट कर दिया गया है। अर्न बॉट का उपयोग करने के लिए धन्यवाद!",
                    parse_mode='Markdown'
                )
                await query.edit_message_text(
                    f"✅ यूजर `{user_id}` (अनुरोध आईडी: `{request_id}`) के लिए भुगतान भुगतान किया गया चिह्नित किया गया और यूजर को सूचित किया गया।\n"
                    f"यूजर का कमाई बैलेंस रीसेट कर दिया गया है।",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ लंबित सूची पर वापस", callback_data='admin_show_pending_withdrawals')]])
                )
            except TelegramError as e:
                logger.error(f"यूजर {user_id} को सफल भुगतान के बारे में सूचित करने में विफल: {e}")
                await query.edit_message_text(
                    f"✅ यूजर `{user_id}` (अनुरोध आईडी: `{request_id}`) के लिए भुगतान भुगतान किया गया चिह्नित किया गया, लेकिन यूजर को सूचित करने में विफल।\n"
                    f"यूजर का कमाई बैलेंस रीसेट कर दिया गया है।",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ लंबित सूची पर वापस", callback_data='admin_show_pending_withdrawals')]])
                )

        else:
            await query.edit_message_text(
                "❌ यह निकासी अनुरोध पहले ही प्रोसेस हो चुका था या नहीं मिला।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ लंबित सूची पर वापस", callback_data='admin_show_pending_withdrawals')]])
            )

    except Exception as e:
        logger.error(f"अनुरोध {request_id} के लिए भुगतान अनुमोदन प्रोसेस करने में त्रुटि: {e}")
        await query.edit_message_text(
            f"❌ इस भुगतान को अप्रूव करते समय एक त्रुटि हुई: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ लंबित सूची पर वापस", callback_data='admin_show_pending_withdrawals')]])
        )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 आपको इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return
    set_user_state(user_id, 'BROADCAST_MESSAGE')
    await update.message.reply_text(
        "📝 कृपया वह मैसेज भेजें जिसे आप सभी यूजर्स को ब्रॉडकास्ट करना चाहते हैं।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ ब्रॉडकास्ट रद्द करें", callback_data='admin_main_menu')]])
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 आपको इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return

    total_users = users.count_documents({})

    await update.message.reply_text(
        f"📊 बॉट सांख्यिकी:\n"
        f"कुल यूजर्स: {total_users}\n"
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
                    f"यूजर आईडी: `{target_user_id}`\n"
                    f"यूजरनेम: @{target_user['username'] if target_user.get('username') else 'N/A'}\n"
                    f"बैलेंस: ₹{target_user['balance']:.2f}\n"
                    f"कुल कमाई: ₹{target_user['total_earned']:.2f}\n"
                    f"रेफरल: {target_user['referrals']}\n"
                    f"रेफर किया गया: {target_user['referred_by'] if target_user.get('referred_by') else 'N/A'}\n"
                    f"कुल लिंक पूरे किए: {target_user.get('links_completed', 0)}\n"
                    f"आज पूरे किए गए लिंक: {target_user.get('links_completed_today', 0)} / {DAILY_LINK_LIMIT}", # Display daily count
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
                )
            else:
                await update.message.reply_text(
                    "यूजर नहीं मिला।",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
                )
        except ValueError:
            await update.message.reply_text(
                "अवैध यूजर आईडी। कृपया एक संख्यात्मक यूजर आईडी भेजें।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
            )
        finally:
            clear_user_state(user_id)

    elif current_state == 'ADD_BALANCE_USER_ID':
        try:
            target_user_id = int(text_input)
            context.user_data['target_user_id_for_add'] = target_user_id
            set_user_state(user_id, 'ADD_BALANCE_AMOUNT')
            await update.message.reply_text(f"यूजर आईडी: `{target_user_id}`। अब, कृपया जोड़ने के लिए राशि भेजें।", parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text(
                "अवैध यूजर आईडी। कृपया एक संख्यात्मक यूजर आईडी भेजें।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
            )
            clear_user_state(user_id)

    elif current_state == 'ADD_BALANCE_AMOUNT':
        target_user_id = context.user_data.get('target_user_id_for_add')
        if not target_user_id:
            await update.message.reply_text(
                "त्रुटि: बैलेंस जोड़ने के लिए यूजर आईडी सेट नहीं है। कृपया 'यूजर को बैलेंस जोड़ें' से फिर से शुरू करें।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
            )
            clear_user_state(user_id)
            return

        try:
            amount_to_add = float(text_input)
            if amount_to_add <= 0:
                await update.message.reply_text(
                    "राशि सकारात्मक होनी चाहिए।",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
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
                    f"यूजर `{target_user_id}` के बैलेंस में सफलतापूर्वक ₹{amount_to_add:.2f} जोड़ दिए गए हैं।\n"
                    f"नया बैलेंस: ₹{target_user['balance'] + amount_to_add:.2f}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
                )
                # Notify the user that balance was added (optional)
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"💰 आपका बैलेंस अपडेट हो गया है! आपके खाते में ₹{amount_to_add:.2f} जोड़ दिए गए हैं।\n"
                             f"आपका नया बैलेंस ₹{target_user['balance'] + amount_to_add:.2f} है।",
                        parse_mode='Markdown'
                    )
                except TelegramError as e:
                    logger.warning(f"यूजर {target_user_id} को बैलेंस जोड़ने के बारे में सूचित नहीं कर सका: {e}")
            else:
                await update.message.reply_text(
                    "यूजर नहीं मिला।",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
                )
        except ValueError:
            await update.message.reply_text(
                "अवैध राशि। कृपया एक संख्यात्मक मान भेजें।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
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
                    logger.info(f"यूजर {user_doc['user_id']} ने बॉट को ब्लॉक कर दिया या निष्क्रिय है। छोड़ रहा है।")
                else:
                    logger.warning(f"यूजर {user_doc['user_id']} को ब्रॉडकास्ट भेजने में विफल: {e}")
                failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"यूजर {user_doc['user_id']} को ब्रॉडकास्ट भेजते समय एक अप्रत्याशित त्रुटि हुई: {e}")

        await update.message.reply_text(
            f"✅ ब्रॉडकास्ट पूरा हुआ!\n"
            f"भेजा गया: {sent_count} यूजर्स को।\n"
            f"विफल: {failed_count} यूजर्स के लिए।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ एडमिन मेनू पर वापस", callback_data='admin_main_menu')]])
        )
        clear_user_state(user_id)


# --- User Withdrawal Input Handler ---
async def handle_withdrawal_input_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_state = get_user_state(user_id)
    user = get_user(user_id)

    # Only process if user is in a withdrawal state
    if not current_state or not current_state.startswith('WITHDRAW_'):
        logger.debug(f"यूजर {user_id} ने निकासी की स्थिति में न होने पर मैसेज भेजा। स्थिति: {current_state}")
        return

    # Check balance again (important for race conditions or if balance changed after callback)
    if user['balance'] < MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ आपका बैलेंस (₹{user['balance']:.2f}) न्यूनतम निकासी राशि ₹{MIN_WITHDRAWAL:.2f} से कम है।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 मुख्य मेनू पर वापस", callback_data='back_to_main')]])
        )
        clear_user_state(user_id)
        return

    if current_state == 'WITHDRAW_ENTER_UPI':
        upi_id = update.message.text.strip()
        if not upi_id:
            await update.message.reply_text("UPI ID खाली नहीं हो सकती। कृपया अपनी UPI ID भेजें।")
            return
        withdrawal_details = {"method": "UPI ID", "id": upi_id}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_ENTER_BANK':
        bank_details_raw = update.message.text.strip()
        if len(bank_details_raw) < 50: # Simple validation, can be improved
            await update.message.reply_text(
                "कृपया निर्दिष्ट प्रारूप में पूर्ण बैंक खाता विवरण प्रदान करें।",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]])
            )
            return
        withdrawal_details = {"method": "Bank Account", "details": bank_details_raw}
        await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)

    elif current_state == 'WITHDRAW_UPLOAD_QR':
        if update.message.photo:
            file_id = update.message.photo[-1].file_id # Get the largest photo size
            withdrawal_details = {"method": "QR Code", "file_id": file_id}
            await process_withdrawal_request(update, context, user_id, user['balance'], withdrawal_details)
        else:
            await update.message.reply_text(
                "कृपया अपने QR कोड का **फोटो** अपलोड करें। QR कोड निकासी के लिए टेक्स्ट मैसेज स्वीकार नहीं किए जाते हैं।",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ रद्द करें", callback_data='back_to_main')]])
            )
            return
    else:
        logger.warning(f"यूजर {user_id} ने अप्रत्याशित निकासी स्थिति में मैसेज भेजा: {current_state}")
        await update.message.reply_text(
            "आप एक अप्रत्याशित स्थिति में हैं। कृपया मुख्य मेनू से फिर से प्रयास करें या 'रद्द करें' पर क्लिक करें।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 मुख्य मेनू पर वापस", callback_data='back_to_main')]])
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
        f"🎉 निकासी अनुरोध सबमिट किया गया!\n"
        f"राशि: ₹{amount:.2f}\n"
        f"विधि: {details['method']}\n"
        f"आपका अनुरोध एडमिन को भेज दिया गया है और जल्द ही प्रोसेस किया जाएगा। एडमिन की मंजूरी के बाद आपका बैलेंस अपडेट किया जाएगा।",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 मुख्य मेनू पर वापस", callback_data='back_to_main')]])
    )

    # Notify admin
    admin_message = (
        f"🚨 **नया निकासी अनुरोध!** 🚨\n"
        f"यूजर आईडी: [`{user_id}`](tg://user?id={user_id})\n"
        f"राशि: ₹{amount:.2f}\n"
        f"विधि: {details['method']}\n"
    )

    if details['method'] == "UPI ID":
        admin_message += f"UPI ID: `{details['id']}`"
    elif details['method'] == "Bank Account":
        admin_message += f"बैंक विवरण:\n```\n{details['details']}\n```"
    elif details['method'] == "QR Code":
        admin_message += f"QR कोड फ़ाइल आईडी: `{details['file_id']}`\n(QR इमेज नीचे फॉरवर्ड की जाएगी)"

    admin_keyboard = [[InlineKeyboardButton("✅ भुगतान किया गया चिह्नित करें", callback_data=f"approve_payment_{request_obj_id}")]]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        # Forward the original photo message to admin if it's a QR code withdrawal
        if details['method'] == "QR Code" and update.message.photo:
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⬆️ ऊपर QR कोड यूजर आईडी `{user_id}` निकासी (अनुरोध आईडी: `{request_obj_id}`) के लिए है।",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("यूजर चैट खोलें", url=f"tg://user?id={user_id}")]])
            )

    except TelegramError as e:
        logger.error(f"एडमिन {ADMIN_ID} को निकासी अनुरोध के बारे में सूचित करने में विफल: {e}")
    finally:
        clear_user_state(user_id)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("अपडेट को हैंडल करते समय अपवाद:", exc_info=context.error)

    if update:
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text('⚠️ एक त्रुटि हुई। कृपया फिर से प्रयास करें।')
            except Exception as e:
                logger.error(f"callback_query यूजर को त्रुटि संदेश भेजने में विफल: {e}")
        elif update.message:
            try:
                await update.message.reply_text('⚠️ एक त्रुटि हुई। कृपया फिर से प्रयास करें।')
            except Exception as e:
                logger.error(f"मैसेज यूजर को त्रुटि संदेश भेजने में विफल: {e}")
        else:
            logger.warning(f"अप्रबंधित अपडेट प्रकार के साथ त्रुटि हुई: {update}")
    else:
        logger.warning("त्रुटि हैंडलर को कोई अपडेट ऑब्जेक्ट नहीं मिला।")

async def cleanup_old_data(context: ContextTypes.DEFAULT_TYPE):
    application_instance = context.job.data["application_instance"]
    logger.info("MongoDB डेटा क्लीनअप का प्रयास किया जा रहा है...")

    total_users_count = users.count_documents({})
    cleanup_threshold_users = 1000 # Example: if you have more than 1000 users, consider cleaning up

    if total_users_count > cleanup_threshold_users:
        logger.warning(f"कुल यूजर्स ({total_users_count}) क्लीनअप थ्रेशोल्ड ({cleanup_threshold_users}) से अधिक हैं। पुराने डेटा का क्लीनअप शुरू कर रहा है।")

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Find users with 0 balance, not admin, and inactive for 30 days
        users_to_delete_cursor = users.find({
            "balance": 0.0,
            "user_id": {"$ne": ADMIN_ID}, # Exclude admin
            "$or": [
                {"created_at": {"$lt": thirty_days_ago}}, # Created before 30 days and inactive
                # Ensure last_click is a datetime object for comparison. Handle cases where it might be missing or date.
                {"last_click": {"$lt": thirty_days_ago}, "last_click": {"$ne": None}}, 
                {"last_earning_day": {"$lt": thirty_days_ago}, "last_earning_day": {"$ne": None}}
            ]
        }).sort("created_at", 1) # Sort by creation date to delete oldest first

        users_to_delete = list(users_to_delete_cursor)

        if not users_to_delete:
            logger.info("क्लीनअप के लिए 0 बैलेंस और निष्क्रियता वाले कोई उपयुक्त गैर-एडमिन यूजर नहीं मिले।")
            return

        # Delete up to 20% of inactive users to free up space
        num_to_delete = max(1, int(len(users_to_delete) * 0.20))
        users_to_delete = users_to_delete[:num_to_delete]

        deleted_count = 0
        deleted_user_ids = []
        for user_doc in users_to_delete:
            # Re-check conditions before deleting to prevent race conditions or unexpected deletions
            current_user_status = users.find_one({"_id": user_doc['_id']})
            if current_user_status and current_user_status['balance'] == 0.0 and current_user_status['user_id'] != ADMIN_ID:
                try:
                    users.delete_one({"_id": user_doc['_id']})
                    user_states.delete_one({"user_id": user_doc['user_id']}) # Also clear their state if any
                    deleted_count += 1
                    deleted_user_ids.append(user_doc['user_id'])
                except Exception as e:
                    logger.error(f"क्लीनअप के दौरान यूजर {user_doc['user_id']} को हटाने में त्रुटि: {e}")
            else:
                logger.warning(f"यूजर {user_doc['user_id']} अब क्लीनअप मानदंड (बैलेंस > 0 या एडमिन है) को पूरा नहीं करता है। छोड़ रहा है।")


        logger.info(f"MongoDB क्लीनअप पूरा हुआ। {deleted_count} यूजर्स हटाए गए। यूजर आईडी: {deleted_user_ids}")

        admin_msg = f"🧹 **MongoDB क्लीनअप अलर्ट!** 🧹\n" \
                    f"कुल यूजर्स थ्रेशोल्ड ({cleanup_threshold_users}) से अधिक हो गए हैं।\n" \
                    f"डेटा प्रबंधित करने के लिए {deleted_count} सबसे पुराने *0 बैलेंस वाले निष्क्रिय यूजर्स* हटा दिए गए हैं।\n" \
                    f"हटाए गए यूजर आईडी: {', '.join(map(str, deleted_user_ids)) if deleted_user_ids else 'कोई नहीं'}"
        try:
            await application_instance.bot.send_message(
                chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"एडमिन को क्लीनअप नोटिफिकेशन भेजने में विफल: {e}")
    else:
        logger.info(f"कुल यूजर्स ({total_users_count}) क्लीनअप थ्रेशोल्ड ({cleanup_threshold_users}) से कम हैं। अभी कोई क्लीनअप की आवश्यकता नहीं है।")


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
application.add_handler(MessageHandler(
    (filters.TEXT | filters.PHOTO) & ~filters.COMMAND & ~filters.User(ADMIN_ID),
    handle_withdrawal_input_wrapper
))

application.add_error_handler(error_handler)

# Setup job queue for cleanup
job_queue = application.job_queue
if job_queue is not None:
    # Run cleanup daily at a fixed time (e.g., 03:00 AM UTC)
    job_queue.run_repeating(cleanup_old_data, interval=timedelta(days=1), first=datetime.now() + timedelta(minutes=5),
                            data={"application_instance": application})
else:
    logger.error("JobQueue प्रारंभ नहीं किया गया है। सुनिश्चित करें कि python-telegram-bot[job-queue] इंस्टॉल है।")


# Flask routes for health check ONLY
@app.route('/')
def health_check():
    return "EarnBot चल रहा है!"

def run_flask_server():
    """Runs the Flask health check server."""
    PORT = int(os.environ.get('PORT', 8000))
    logger.info(f"Flask सर्वर पोर्ट {PORT} पर शुरू हो रहा है")
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == '__main__':
    flask_server_thread = Thread(target=run_flask_server)
    flask_server_thread.daemon = True
    flask_server_thread.start()

    logger.info("टेलीग्राम बॉट पोलिंग मोड में शुरू हो रहा है।")
    try:
        application.run_polling(poll_interval=1, timeout=30)
    except KeyboardInterrupt:
        logger.info("बॉट प्रक्रिया बाधित। बंद हो रहा है।")
        application.stop()
        client.close()
    except Exception as e:
        logger.critical(f"पोलिंग लूप में एक अप्रबंधित त्रुटि हुई: {e}", exc_info=True)
        application.stop()
        client.close()

