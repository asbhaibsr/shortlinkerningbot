import os
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(MONGO_URI)
db = client.get_database('earnbot')
users = db.users

# Bot states
WAITING_FOR_UPI = 1

# Bot configuration
MIN_WITHDRAWAL = 70
EARN_PER_LINK = 0.15
REFERRAL_BONUS = 0.50
LINK_COOLDOWN = 5  # minutes

# Initialize database indexes
def init_db():
    users.create_index("user_id", unique=True)
    users.create_index("referral_code", unique=True, sparse=True)

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
        }
        users.insert_one(user)
    return user

def update_user(user_id, update_data):
    users.update_one({"user_id": user_id}, {"$set": update_data})

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Check if this is a referral
    if context.args and context.args[0].startswith('ref_'):
        referrer_id = int(context.args[0].split('_')[1])
        referrer = get_user(referrer_id)
        if referrer and referrer['user_id'] != user_id:
            update_user(referrer_id, {
                "referrals": referrer['referrals'] + 1,
                "referral_earnings": referrer['referral_earnings'] + REFERRAL_BONUS,
                "balance": referrer['balance'] + REFERRAL_BONUS,
                "total_earned": referrer['total_earned'] + REFERRAL_BONUS
            })
    
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

async def generate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Check cooldown
    if user['last_click'] and (datetime.utcnow() - user['last_click']) < timedelta(minutes=LINK_COOLDOWN):
        remaining = (user['last_click'] + timedelta(minutes=LINK_COOLDOWN) - datetime.utcnow()).seconds // 60
        await query.edit_message_text(
            f"⏳ Please wait {remaining} minutes before generating another link!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 My Wallet", callback_data='wallet')]
            ])
        )
        return
    
    # In production, replace this with your actual shortlink API call
    SHORTS_API_KEY = os.getenv('SHORTS_API_KEY', 'your_api_key')
    redirect_url = f"https://t.me/{context.bot.username}?start=verify_{user_id}"
    shortlink = f"https://smallshorts.example.com/mock-link-for-{user_id}"
    
    await query.edit_message_text(
        f"🔗 Solve this link to earn ₹{EARN_PER_LINK}:\n{shortlink}\n\n"
        "After solving, return here and click 'I completed'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ I Completed", callback_data=f'verify_{user_id}')]
        ])
    )

async def verify_completion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # In production, verify with your shortlink service API here
    is_verified = True  # Replace with actual verification
    
    if not is_verified:
        await query.edit_message_text(
            "❌ Link not completed yet! Please solve the link first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Get Link Again", callback_data='generate_link')]
            ])
        )
        return
    
    new_balance = user['balance'] + EARN_PER_LINK
    update_user(user_id, {
        "balance": new_balance,
        "total_earned": user['total_earned'] + EARN_PER_LINK,
        "last_click": datetime.utcnow()
    })
    
    await query.edit_message_text(
        f"✅ ₹{EARN_PER_LINK} Credited! New balance: ₹{new_balance:.2f}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Next Link", callback_data='generate_link')],
            [InlineKeyboardButton("💳 My Wallet", callback_data='wallet')]
        ])
    )

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    keyboard = []
    if user['balance'] >= MIN_WITHDRAWAL:
        keyboard.append([InlineKeyboardButton("💰 Withdraw", callback_data='withdraw')])
    
    await query.edit_message_text(
        f"💼 Your Wallet\n\n"
        f"Balance: ₹{user['balance']:.2f}\n"
        f"Total Earned: ₹{user['total_earned']:.2f}\n"
        f"Withdrawn: ₹{user['withdrawn']:.2f}\n"
        f"Referrals: {user['referrals']} (₹{user['referral_earnings']:.2f})\n\n"
        f"Minimum withdrawal: ₹{MIN_WITHDRAWAL}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user['balance'] < MIN_WITHDRAWAL:
        await query.edit_message_text(
            f"❌ You need at least ₹{MIN_WITHDRAWAL} to withdraw. Current balance: ₹{user['balance']:.2f}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Generate Link", callback_data='generate_link')]
            ])
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        "📤 Please send your UPI ID for withdrawal (e.g., 1234567890@ybl):\n\n"
        "Type /cancel to cancel withdrawal"
    )
    return WAITING_FOR_UPI

async def process_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    upi_id = update.message.text
    user = get_user(user_id)
    
    # Simple UPI ID validation
    if '@' not in upi_id or len(upi_id) < 5:
        await update.message.reply_text("❌ Invalid UPI ID. Please send a valid UPI ID (e.g., 1234567890@ybl)")
        return WAITING_FOR_UPI
    
    # Process withdrawal
    amount = user['balance']
    update_user(user_id, {
        "balance": 0.0,
        "withdrawn": user['withdrawn'] + amount
    })
    
    await update.message.reply_text(
        f"✅ Withdrawal request for ₹{amount:.2f} to {upi_id} submitted!\n"
        "Processing may take 24-48 hours.\n\n"
        "Use /start to return to main menu"
    )
    
    return ConversationHandler.END

async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Withdrawal cancelled.")
    return ConversationHandler.END

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    ref_link = f"https://t.me/{context.bot.username}?start={user['referral_code']}"
    
    await query.edit_message_text(
        f"👥 Referral Program\n\n"
        f"Invite friends and earn ₹{REFERRAL_BONUS} per referral!\n\n"
        f"Your referral link:\n{ref_link}\n\n"
        "When someone joins using your link and earns ₹5, you get ₹0.50 bonus!"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if update.callback_query:
        await update.callback_query.message.reply_text('⚠️ An error occurred. Please try again.')
    else:
        await update.message.reply_text('⚠️ An error occurred. Please try again.')

def main() -> None:
    # Create the Application and pass it your bot's token.
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN environment variable set")
    
    application = Application.builder().token(TOKEN).build()

    # Add conversation handler for withdrawals
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw, pattern='^withdraw$')],
        states={
            WAITING_FOR_UPI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_upi),
                CommandHandler('cancel', cancel_withdrawal)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_withdrawal)],
    )

    # Register handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(generate_link, pattern='^generate_link$'))
    application.add_handler(CallbackQueryHandler(verify_completion, pattern='^verify_'))
    application.add_handler(CallbackQueryHandler(show_wallet, pattern='^wallet$'))
    application.add_handler(CallbackQueryHandler(show_referral, pattern='^referral$'))
    application.add_handler(conv_handler)
    
    # Error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    PORT = int(os.environ.get('PORT', 8443))
    HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
    
    if HEROKU_APP_NAME:  # Running on production
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{HEROKU_APP_NAME}.herokuapp.com/{TOKEN}"
        )
    else:  # Running locally
        application.run_polling()

if __name__ == '__main__':
    main()
