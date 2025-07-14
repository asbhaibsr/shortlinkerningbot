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

# Configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(MONGO_URI)
db = client.get_database('earnbot')
users = db.users

# Bot constants
WAITING_FOR_UPI = 1
MIN_WITHDRAWAL = 70
EARN_PER_LINK = 0.15
REFERRAL_BONUS = 0.50
LINK_COOLDOWN = 5  # minutes

# Database setup
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

# [Rest of your handler functions...]

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)
    if update.callback_query:
        await update.callback_query.message.reply_text('⚠️ An error occurred. Please try again.')
    elif update.message:
        await update.message.reply_text('⚠️ An error occurred. Please try again.')

def main() -> None:
    try:
        application = Application.builder().token(TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler('start', start))
        # [Add other handlers...]

        application.add_error_handler(error_handler)

        PORT = int(os.environ.get('PORT', 8443))
        HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
        
        if HEROKU_APP_NAME:
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=f"https://{HEROKU_APP_NAME}.herokuapp.com/{TOKEN}"
            )
        else:
            application.run_polling()
            
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
