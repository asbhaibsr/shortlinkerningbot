# bot.py

import random
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove # ReplyKeyboardRemove जोड़ा
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from datetime import datetime
from bson.objectid import ObjectId
import json
import asyncio
import os
from pymongo.errors import WriteError

# Flask को इम्पोर्ट करें
from flask import Flask, request

# आपकी कस्टम इम्पोर्ट्स (सुनिश्चित करें कि config.py में सभी आवश्यक वेरिएबल्स हैं)
from config import (
    BOT_TOKEN, ADMIN_WITHDRAWAL_CHANNEL_ID, SHORTLINK_API_URL, SHORTLINK_API_KEY,
    POINTS_PER_SHORTLINK, REFERRAL_POINTS_PER_REFERRAL, POINTS_PER_CHANNEL_JOIN,
    MIN_WITHDRAWAL_POINTS, UPI_QR_BANK_POINTS_TO_RUPEES_RATE, REDEEM_CODE_POINTS_TO_RUPEES_RATE,
    FORCE_SUBSCRIBE_CHANNEL_ID, FORCE_SUBSCRIBE_CHANNEL_USERNAME, JOIN_TO_EARN_CHANNELS,
    WEBHOOK_URL # वेबहुक सेट करने के लिए
)
from languages import LANGUAGES, DEFAULT_LANGUAGE, get_text
from database_utils import (
    init_db, get_user_data, update_user_data, record_withdrawal_request,
    set_user_language, withdrawal_requests_collection, users_collection,
    get_user_language, update_withdrawal_request_status
)

# Logging कॉन्फ़िगरेशन
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# डेटाबेस कनेक्शन को इनिशियलाइज़ करें
init_db()

# Telegram.ext.Application इंस्टेंस को ग्लोबल बनाएं
application = Application.builder().token(BOT_TOKEN).build()

# --- सहायक कार्य: चैनल सदस्यता की जांच करें ---
async def is_user_subscribed(user_id: str, bot) -> bool:
    if not FORCE_SUBSCRIBE_CHANNEL_ID:
        return True # यदि कोई अनिवार्य चैनल नहीं है, तो हमेशा True लौटाएं

    try:
        member = await bot.get_chat_member(FORCE_SUBSCRIBE_CHANNEL_ID, user_id)
        # सदस्य या व्यवस्थापक होने पर True लौटाएं
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel subscription for user {user_id}: {e}", exc_info=True)
        return False # त्रुटि होने पर False लौटाएं

# --- कमांड हैंडलर: /start कमांड ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name
    user_lang = get_user_language(user_id) # उपयोगकर्ता की मौजूदा भाषा प्राप्त करें

    # *** यहाँ ReplyKeyboardRemove जोड़ा गया है ***
    # यह सुनिश्चित करता है कि कोई भी पुराना ReplyKeyboard हटा दिया जाए।
    # आप इसे हर /start पर भेज सकते हैं, या केवल एक बार यदि आप चाहें।
    await update.message.reply_text(get_text("welcome_message_initial", user_lang), reply_markup=ReplyKeyboardRemove())
    # Note: "welcome_message_initial" के लिए अपनी languages.py में एक टेक्स्ट जोड़ें, 
    # या आप इसे खाली स्ट्रिंग "" भी रख सकते हैं।

    # 1. चैनल सदस्यता की जांच करें
    if not await is_user_subscribed(user_id, context.bot):
        if FORCE_SUBSCRIBE_CHANNEL_USERNAME:
            channel_link = f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_USERNAME}"
            text = get_text("force_subscribe_message", user_lang).format(channel_link=channel_link)
            keyboard = [[
                InlineKeyboardButton(get_text("force_subscribe_button", user_lang), url=channel_link),
                InlineKeyboardButton(get_text("force_subscribe_check_button", user_lang), callback_data="check_subscription")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # यहाँ reply_text का उपयोग किया गया है
            await update.message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        else:
            await update.message.reply_text(get_text("force_subscribe_error_no_username", user_lang))
        return # यहां रुकें, आगे न बढ़ें

    # 2. भाषा चयन की जांच करें (यदि उपयोगकर्ता ने पहले से कोई भाषा नहीं चुनी है)
    user_data = get_user_data(user_id)
    if not user_data or not user_data.get("language_set"):
        text = get_text("choose_language", user_lang)
        keyboard = []
        for lang_code, lang_name in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_name.get("name_in_english"), callback_data=f"set_lang_{lang_code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        return # यहां रुकें, आगे न बढ़ें

    # यदि चैनल में शामिल हो गए हैं और भाषा चुन ली गई है, तो मुख्य मेनू दिखाएं
    await show_main_menu(update, context)

# --- कॉलबैक हैंडलर: सदस्यता जांच के लिए ---
async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # कॉलैक क्वेरी का जवाब दें

    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)

    if await is_user_subscribed(user_id, context.bot):
        user_data = get_user_data(user_id)
        if not user_data or not user_data.get("language_set"):
            text = get_text("choose_language", user_lang)
            keyboard = []
            for lang_code, lang_name in LANGUAGES.items():
                keyboard.append([InlineKeyboardButton(lang_name.get("name_in_english"), callback_data=f"set_lang_{lang_code}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await show_main_menu_from_query(query, context) # मुख्य मेनू दिखाएं
    else:
        text = get_text("force_subscribe_not_joined", user_lang)
        keyboard = [[
            InlineKeyboardButton(get_text("force_subscribe_button", user_lang), url=f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_USERNAME}"),
            InlineKeyboardButton(get_text("force_subscribe_check_button", user_lang), callback_data="check_subscription")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, disable_web_page_preview=True)

# --- कॉलबैक हैंडलर: भाषा बदलने के लिए ---
async def change_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # कॉलैक क्वेरी का जवाब दें

    user_id = str(query.from_user.id)
    
    lang_code = query.data.replace("set_lang_", "")
    
    if lang_code in LANGUAGES:
        try:
            set_user_language(user_id, lang_code)
            update_user_data(user_id, set_data={"language_set": True})
            
            user_lang = get_user_language(user_id) # नई भाषा में पाठ प्राप्त करें
            await query.edit_message_text(get_text("language_set_success", user_lang).format(lang_name=LANGUAGES[lang_code]['name_in_english']))
            await show_main_menu_from_query(query, context) # भाषा सेट करने के बाद मुख्य मेनू दिखाएं
        except WriteError as e:
            logger.error(f"MongoDB WriteError in change_language_callback for user {user_id}: {e}", exc_info=True)
            user_lang = get_user_language(user_id)
            await query.edit_message_text(get_text("error_language_change", user_lang))
        except Exception as e:
            logger.error(f"Unexpected error in change_language_callback for user {user_id}: {e}", exc_info=True)
            user_lang = get_user_language(user_id)
            await query.edit_message_text(get_text("error_general", user_lang))
    else:
        user_lang = get_user_language(user_id)
        await query.edit_message_text(get_text("invalid_language_selection", user_lang))

# --- मुख्य मेनू दिखाने के लिए सहायक फ़ंक्शन (नया मैसेज) ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_lang = get_user_language(user_id)
    text = get_text("main_menu_message", user_lang)
    keyboard = [[
        InlineKeyboardButton(get_text("start_button_earn", user_lang), callback_data="earn_points"),
        InlineKeyboardButton(get_text("start_button_refer", user_lang), callback_data="refer_friend"),
    ], [
        InlineKeyboardButton(get_text("start_button_balance", user_lang), callback_data="check_balance"),
        InlineKeyboardButton(get_text("start_button_withdraw", user_lang), callback_data="withdraw_points"),
    ], [
        InlineKeyboardButton(get_text("start_button_language", user_lang), callback_data="change_language_option"),
        InlineKeyboardButton(get_text("start_button_help", user_lang), callback_data="help_info"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

# कॉलबैक क्वेरी से मुख्य मेनू दिखाने के लिए (मौजूदा मैसेज को एडिट)
async def show_main_menu_from_query(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    text = get_text("main_menu_message", user_lang)
    keyboard = [[
        InlineKeyboardButton(get_text("start_button_earn", user_lang), callback_data="earn_points"),
        InlineKeyboardButton(get_text("start_button_refer", user_lang), callback_data="refer_friend"),
    ], [
        InlineKeyboardButton(get_text("start_button_balance", user_lang), callback_data="check_balance"),
        InlineKeyboardButton(get_text("start_button_withdraw", user_lang), callback_data="withdraw_points"),
    ], [
        InlineKeyboardButton(get_text("start_button_language", user_lang), callback_data="change_language_option"),
        InlineKeyboardButton(get_text("start_button_help", user_lang), callback_data="help_info"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)


# --- कॉलबैक हैंडलर: भाषा बदलने के लिए बटन पर क्लिक करने पर ---
async def change_language_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    
    text = get_text("choose_language", user_lang)
    keyboard = []
    for lang_code, lang_name in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(lang_name.get("name_in_english"), callback_data=f"set_lang_{lang_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

# --- कमांड हैंडलर: /help कमांड (यह पहले से आपके पास हो सकता है) ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_lang = get_user_language(user_id)
    text = get_text("help_message", user_lang)
    await update.message.reply_text(text)


# --- कॉलबैक हैंडलर: अर्निंग पॉइंट्स के लिए ---
async def earn_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)

    # Shortlink API से URL जनरेट करें
    try:
        target_url = "https://example.com/thank-you-for-visiting-our-site" 
        
        shortlink_api_params = {
            "api": SHORTLINK_API_KEY,
            "url": target_url,
            "data": user_id 
        }
        
        response = requests.get(SHORTLINK_API_URL, params=shortlink_api_params)
        response.raise_for_status() 

        shortlink_data = response.json()
        
        if shortlink_data and shortlink_data.get("status") == "success" and shortlink_data.get("shortenedUrl"):
            generated_shortlink = shortlink_data["shortenedUrl"]
            
            text_message = get_text("earn_points_instructions", user_lang).format(shortlink_url=generated_shortlink)
            
            keyboard = [[
                InlineKeyboardButton(get_text("button_visit_shortlink", user_lang), url=generated_shortlink), # यहाँ URL जोड़ा है
                InlineKeyboardButton(get_text("button_check_completion_status", user_lang), callback_data=f"check_shortlink_{user_id}") # एक नया बटन जोड़ा है
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text_message, reply_markup=reply_markup, disable_web_page_preview=True)

        else:
            await query.edit_message_text(get_text("error_generating_shortlink", user_lang), parse_mode='HTML')
            logger.error(f"Failed to generate shortlink for user {user_id}: {shortlink_data}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling shortlink API for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_api_call", user_lang), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Unexpected error in earn_points_callback for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_general", user_lang), parse_mode='HTML')


# --- कॉलबैक हैंडलर: शॉर्टलिंक पूरा होने की जांच करें ---
async def check_shortlink_completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)

    try:
        check_api_params = {
            "api": SHORTLINK_API_KEY,
            "sub_id": user_id, 
        }
        
        response = requests.get(f"{SHORTLINK_API_URL}/status", params=check_api_params) 
        response.raise_for_status()

        status_data = response.json()
        
        if status_data and status_data.get("status") == "completed" and status_data.get("sub_id") == user_id:
            current_user_data = get_user_data(user_id)
            if not current_user_data:
                await query.edit_message_text(get_text("user_not_found", user_lang))
                return

            if not isinstance(current_user_data.get("points"), (int, float)):
                update_user_data(user_id, set_data={"points": 0})
                logger.warning(f"User {user_id}'s points field was non-numeric/missing. Reset to 0 before increment.")

            update_user_data(user_id, inc_data={"points": POINTS_PER_SHORTLINK})
            
            updated_user_data = get_user_data(user_id)
            new_balance = updated_user_data.get("points", 0)
            
            await query.edit_message_text(get_text("shortlink_completed_success", user_lang).format(points=POINTS_PER_SHORTLINK, balance=new_balance))
            logger.info(f"User {user_id} completed shortlink and received {POINTS_PER_SHORTLINK} points.")
        else:
            await query.edit_message_text(get_text("shortlink_not_completed", user_lang))
            logger.info(f"User {user_id} shortlink not yet completed or status not confirmed.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking shortlink API status for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_api_check", user_lang), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Unexpected error in check_shortlink_completion_callback for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_general", user_lang), parse_mode='HTML')


async def refer_friend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    referral_link = f"https://t.me/{context.bot.username}?start=refer_{user_id}"
    await query.edit_message_text(get_text("refer_message", user_lang).format(referral_link=referral_link))

async def check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    user_data = get_user_data(user_id)
    points = user_data.get("points", 0)
    await query.edit_message_text(get_text("balance_message", user_lang).format(points=points))

async def withdraw_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    await query.edit_message_text(get_text("withdraw_message", user_lang))


# --- Flask एप्लिकेशन सेटअप ---

app = Flask(__name__)

application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))

application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
application.add_handler(CallbackQueryHandler(change_language_callback, pattern="^set_lang_"))
application.add_handler(CallbackQueryHandler(change_language_option_callback, pattern="^change_language_option$"))

application.add_handler(CallbackQueryHandler(earn_points_callback, pattern="^earn_points$"))
application.add_handler(CallbackQueryHandler(check_shortlink_completion_callback, pattern="^check_shortlink_"))

application.add_handler(CallbackQueryHandler(refer_friend_callback, pattern="^refer_friend$"))
application.add_handler(CallbackQueryHandler(check_balance_callback, pattern="^check_balance$"))
application.add_handler(CallbackQueryHandler(withdraw_points_callback, pattern="^withdraw_points$"))

try:
    async def initialize_and_set_webhook():
        await application.initialize()
        full_webhook_url = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
        try:
            current_webhook_info = await application.bot.get_webhook_info()
            if current_webhook_info.url != full_webhook_url:
                await application.bot.set_webhook(url=full_webhook_url)
                logger.info(f"Telegram webhook set to: {full_webhook_url}")
            else:
                logger.info(f"Telegram webhook already set to: {full_webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set Telegram webhook: {e}", exc_info=True)
        
        await application.start()
        logger.info("Telegram Application initialized and started (webhook mode).")

    asyncio.run(initialize_and_set_webhook())

except Exception as e:
    logger.critical(f"FATAL ERROR during initial Telegram Application setup: {e}", exc_info=True)
    raise e

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, application.bot)
        asyncio.create_task(application.process_update(update))
        return "ok"
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)
        return "error", 500

if __name__ == "__main__":
    logger.info("Running Flask app in development mode.")
    app.run(host="0.0.0.0", port=8000, debug=True)
