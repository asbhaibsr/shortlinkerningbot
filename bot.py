# bot.py

import random
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from datetime import datetime
from bson.objectid import ObjectId
import json
import asyncio
import os

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
# यहां से WITHDRAWAL_STATUS_UPDATE_MESSAGES को हटाया गया है
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
            await update.message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        else:
            await update.message.reply_text(get_text("force_subscribe_error_no_username", user_lang))
        return # यहां रुकें, आगे न बढ़ें

    # 2. भाषा चयन की जांच करें (यदि उपयोगकर्ता ने पहले से कोई भाषा नहीं चुनी है)
    user_data = get_user_data(user_id)
    if user_lang == DEFAULT_LANGUAGE and not user_data.get("language_set"): # एक ध्वज जोड़ें ताकि यह केवल एक बार दिखाई दे
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
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)

    if await is_user_subscribed(user_id, context.bot):
        # यदि सदस्यता की पुष्टि हो गई है, तो भाषा चयन पर आगे बढ़ें
        user_data = get_user_data(user_id)
        if get_user_language(user_id) == DEFAULT_LANGUAGE and not user_data.get("language_set"):
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
    await query.answer()
    user_id = str(query.from_user.id)
    
    # यदि callback_data "set_lang_xx" है
    lang_code = query.data.replace("set_lang_", "")
    
    if lang_code in LANGUAGES:
        set_user_language(user_id, lang_code)
        # डेटाबेस में language_set फ्लैग को True पर सेट करें
        update_user_data(user_id, {"language_set": True})
        
        user_lang = get_user_language(user_id) # नई भाषा में पाठ प्राप्त करें
        await query.edit_message_text(get_text("language_set_success", user_lang).format(lang_name=LANGUAGES[lang_code]['name_in_english']))
        await show_main_menu_from_query(query, context) # भाषा सेट करने के बाद मुख्य मेनू दिखाएं
    else:
        await query.edit_message_text("Invalid language selection.")

# --- मुख्य मेनू दिखाने के लिए सहायक फ़ंक्शन (नया मैसेज) ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_lang = get_user_language(user_id)
    text = get_text("main_menu_message", user_lang) # एक नया टेक्स्ट 'main_menu_message' जोड़ें
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
    text = get_text("main_menu_message", user_lang) # एक नया टेक्स्ट 'main_menu_message' जोड़ें
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
        # VJ-FILTER-BOT की तरह, आपको SHORTENER_WEBSITE और SHORTENER_API की आवश्यकता होगी
        # आपके config.py में SHORTLINK_API_URL और SHORTLINK_API_KEY होना चाहिए
        # यह वह URL है जिसे शॉर्टलिंक किया जाएगा (उदाहरण के लिए, एक खाली "धन्यवाद" पेज, या एक वास्तविक मूवी लिंक)
        target_url = "https://example.com/thank-you-for-visiting-our-site" 
        
        # आपकी Shortlink API के अनुसार पैरामीटर (VJ-FILTER-BOT के समान)
        # VJ-FILTER-BOT में यह 'api' और 'url' लेता है
        # यदि आपकी API 'sub_id' या 'user_id' का समर्थन करती है ताकि आप बाद में क्लिक को ट्रैक कर सकें,
        # तो उसे यहां शामिल करें। यह अंक सत्यापित करने के लिए महत्वपूर्ण है।
        
        # उदाहरण: shortlink-api.com पर एक विशिष्ट API कॉल
        # आपकी API के आधार पर, यह GET या POST अनुरोध हो सकता है।
        # मान लीजिए आपकी API का URL SHORTLINK_API_URL = "https://yourshortener.com/api"
        # और यह पैरामीटर्स के साथ GET अनुरोध लेता है।
        shortlink_api_params = {
            "api": SHORTLINK_API_KEY,
            "url": target_url,
            "data": user_id # VJ-FILTER-BOT में 'data' या 'user_data' के रूप में user_id भेजें
            # अन्य आवश्यक पैरामीटर
        }
        
        response = requests.get(SHORTLINK_API_URL, params=shortlink_api_params)
        response.raise_for_status() # HTTP त्रुटियों के लिए अपवाद उठाएं

        shortlink_data = response.json()
        
        # आपकी Shortlink API के रिस्पांस स्ट्रक्चर के आधार पर शॉर्टलिंक URL निकालें
        # VJ-FILTER-BOT में यह shortlink_data['shortenedUrl'] या shortlink_data['url'] हो सकता है
        if shortlink_data and shortlink_data.get("status") == "success" and shortlink_data.get("shortenedUrl"):
            generated_shortlink = shortlink_data["shortenedUrl"]
            
            # उपयोगकर्ता को शॉर्टलिंक भेजें और उसे बताएं कि पूरा करने के बाद वापस आएं।
            text_message = get_text("earn_points_instructions", user_lang).format(shortlink_url=generated_shortlink)
            
            keyboard = [[
                InlineKeyboardButton(get_text("button_check_completion", user_lang), callback_data=f"check_shortlink_{user_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text_message, reply_markup=reply_markup, disable_web_page_preview=True)
            
            # भविष्य की जांच के लिए उपयोगकर्ता की स्थिति में transaction_id या user_id सहेजें
            # यदि आपकी API एक अद्वितीय transaction ID लौटाती है जिसे आप बाद में उपयोग कर सकते हैं, तो उसे context.user_data में सहेजें
            # context.user_data['last_shortlink_user_id'] = user_id 
            # context.user_data['last_shortlink_gen_time'] = datetime.now()

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

    # यहां Shortlink API को क्वेरी करने का लॉजिक होगा कि उपयोगकर्ता ने शॉर्टलिंक पूरा किया है या नहीं।
    # यह API आपकी Shortlink सेवा द्वारा प्रदान की जानी चाहिए।
    # यदि आपकी Shortlink API ऐसी सुविधा नहीं देती है, तो अंक देना केवल विश्वास पर आधारित होगा।
    try:
        # उदाहरण: Shortlink API से स्थिति जांचें।
        # आपको API दस्तावेज़ की जांच करनी होगी कि यह कैसे काम करता है।
        # अक्सर, आप 'sub_id' (जिसे आपने generate करते समय भेजा था) का उपयोग करेंगे।
        
        # यह एक काल्पनिक API कॉल है। आपको अपनी Shortlink API के अनुसार इसे बदलना होगा।
        # VJ-FILTER-BOT में सीधे स्थिति जांचने का कोई API नहीं है; वह बस लिंक प्रदान करता है।
        # यदि आप अंकों के लिए सत्यापन चाहते हैं, तो आपको एक ऐसी शॉर्टलिंक सेवा का उपयोग करना होगा
        # जो क्लिकों को ट्रैक करने या पूर्णता स्थिति की जांच करने के लिए API प्रदान करती है।
        
        # मान लीजिए आपकी API का URL SHORTLINK_API_URL = "https://yourshortener.com/api/status"
        # और यह 'api' और 'sub_id' लेता है।
        check_api_params = {
            "api": SHORTLINK_API_KEY,
            "sub_id": user_id, # वह ID जिसे आपने शॉर्टलिंक जनरेट करते समय भेजा था
            # अन्य आवश्यक पैरामीटर
        }
        
        # यदि आपकी API POST लेती है, तो requests.post का उपयोग करें और data=json.dumps(params)
        response = requests.get(f"{SHORTLINK_API_URL}/status", params=check_api_params) 
        response.raise_for_status()

        status_data = response.json()
        
        # आपकी Shortlink API के रिस्पांस स्ट्रक्चर के आधार पर स्थिति जांचें
        # उदाहरण: status_data["status"] == "completed" या status_data["clicks"] > 0
        # आपको यह भी सुनिश्चित करना होगा कि यह क्लिक किसी नए क्लिक के लिए है न कि पुराने के लिए।
        # इसके लिए डेटाबेस में उपयोगकर्ता के लिए 'last_checked_click_id' जैसी कुछ जानकारी सहेजनी पड़ सकती है।
        
        if status_data and status_data.get("status") == "completed" and status_data.get("sub_id") == user_id:
            # उपयोगकर्ता ने शॉर्टलिंक पूरा कर लिया है!
            # उसे अंक दें
            current_user_data = get_user_data(user_id)
            if not current_user_data:
                await query.edit_message_text(get_text("user_not_found", user_lang))
                return

            # **महत्वपूर्ण: सुनिश्चित करें कि एक ही शॉर्टलिंक के लिए कई बार अंक न दें**
            # आपको यहां एक मैकेनिज्म जोड़ना होगा। उदाहरण के लिए:
            # 1. जब शॉर्टलिंक जनरेट हो, तो उसे डेटाबेस में "pending" स्थिति के साथ सहेजें।
            # 2. जब यह पूरा हो जाए, तो स्थिति को "completed" में अपडेट करें और केवल तभी अंक दें जब यह पहले से "completed" न हो।
            # 3. आप प्रत्येक शॉर्टलिंक जनरेशन के लिए एक अद्वितीय `transaction_id` का उपयोग कर सकते हैं।
            
            # यदि पहली बार पूरा हुआ है
            update_user_data(user_id, {"$inc": {"points": POINTS_PER_SHORTLINK}})
            new_balance = current_user_data.get("points", 0) + POINTS_PER_SHORTLINK
            
            await query.edit_message_text(get_text("shortlink_completed_success", user_lang).format(points=POINTS_PER_SHORTLINK, balance=new_balance))
            logger.info(f"User {user_id} completed shortlink and received {POINTS_PER_SHORTLINK} points.")
        else:
            # शॉर्टलिंक अभी तक पूरा नहीं हुआ है या कोई त्रुटि है
            await query.edit_message_text(get_text("shortlink_not_completed", user_lang))
            logger.info(f"User {user_id} shortlink not yet completed or status not confirmed.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking shortlink API status for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_api_check", user_lang), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Unexpected error in check_shortlink_completion_callback for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text(get_text("error_general", user_lang), parse_mode='HTML')


# --- अन्य बॉट फ़ंक्शंस (ये आपके मौजूदा कोड से आ सकते हैं) ---
# यदि आपके पास refer_friend_callback, check_balance_callback,
# withdraw_points_callback, help_info_callback, आदि हैं, तो उन्हें यहां पेस्ट करें।
# उदाहरण के लिए:
async def refer_friend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user_lang = get_user_language(user_id)
    # आपका रेफरल लॉजिक यहाँ
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
    # आपका निकासी लॉजिक यहाँ
    await query.edit_message_text(get_text("withdraw_message", user_lang))


# --- Flask एप्लिकेशन सेटअप ---

app = Flask(__name__) # Flask ऐप इंस्टेंस

# Telegram.ext.Application इंस्टेंस
application = Application.builder().token(BOT_TOKEN).build()

# Telegram हैंडलर जोड़ें
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))

# नए हैंडलर:
application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
application.add_handler(CallbackQueryHandler(change_language_callback, pattern="^set_lang_"))
application.add_handler(CallbackQueryHandler(change_language_option_callback, pattern="^change_language_option$"))

# शॉर्टलिंक हैंडलर
application.add_handler(CallbackQueryHandler(earn_points_callback, pattern="^earn_points$"))
application.add_handler(CallbackQueryHandler(check_shortlink_completion_callback, pattern="^check_shortlink_"))

# अन्य सामान्य हैंडलर जोड़ें
application.add_handler(CallbackQueryHandler(refer_friend_callback, pattern="^refer_friend$"))
application.add_handler(CallbackQueryHandler(check_balance_callback, pattern="^check_balance$"))
application.add_handler(CallbackQueryHandler(withdraw_points_callback, pattern="^withdraw_points$"))
# यदि आपके पास 'help_info' के लिए एक अलग कॉलबैक है, तो उसे भी जोड़ें:
# application.add_handler(CallbackQueryHandler(help_info_callback, pattern="^help_info$"))


# Telegram अपडेट्स को हैंडल करने के लिए Flask वेबहुक एंडपॉइंट
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, application.bot)
        # Telegram अपडेट को process_update के माध्यम से भेजें
        await application.process_update(update)
        return "ok"
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)
        return "error", 500

# --- मुख्य फ़ंक्शन जो बॉट और Flask ऐप को चलाता है ---

async def run_bot_and_flask():
    """Sets up webhook and starts the Telegram Application."""
    # सुनिश्चित करें कि Telegram वेबहुक सेट है
    full_webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    try:
        current_webhook_info = await application.bot.get_webhook_info()
        if current_webhook_info.url != full_webhook_url:
            await application.bot.set_webhook(url=full_webhook_url)
            logger.info(f"Telegram webhook set to: {full_webhook_url}")
        else:
            logger.info(f"Telegram webhook already set to: {full_webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set Telegram webhook: {e}", exc_info=True)
        # अगर वेबहुक सेट नहीं होता है तो भी ऐप को चलने दें, लेकिन यह Telegram अपडेट प्राप्त नहीं करेगा

    await application.start() # Telegram Application को शुरू करें
    logger.info("Telegram Application started (webhook mode).")

# यह सुनिश्चित करने के लिए कि Flask ऐप Gunicorn द्वारा उठाया गया है
# मुख्य ब्लॉक में केवल Flask ऐप को रखना चाहिए
if __name__ == "__main__":
    # async run_bot_and_flask() को चलाएं (जो वेबहुक सेट करता है और Telegram ऐप शुरू करता है)
    asyncio.run(run_bot_and_flask())
    
    # Flask ऐप को run करें। Koyeb पर Gunicorn इस 'app' ऑब्जेक्ट को उठाएगा।
    # यदि आप इसे सीधे चला रहे हैं (केवल विकास/परीक्षण के लिए, उत्पादन के लिए नहीं)
    # आप इसे इस प्रकार चला सकते हैं:
    # app.run(host="0.0.0.0", port=8000, debug=True)
    logger.info("Flask application is ready to be served by Gunicorn or local run.")
