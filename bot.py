# bot.py

import random
import requests
import logging
import os
import json
import threading
import asyncio
import urllib.parse
from datetime import datetime
from bson.objectid import ObjectId # MongoDB ObjectIds के लिए आवश्यक

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode # ParseMode के लिए इंपोर्ट
from telegram.helpers import escape_markdown # Markdown वर्णों को एस्केप करने के लिए इंपोर्ट

# आपकी कस्टम इम्पोर्ट्स
# सुनिश्चित करें कि config.py में आपके सभी आवश्यक चर हैं,
# और WEBHOOK_URL पर्यावरण चर से पढ़ा जा रहा है।
from config import (
    BOT_TOKEN, ADMIN_WITHDRAWAL_CHANNEL_ID, SHORTLINK_API_URL, SHORTLINK_API_KEY,
    POINTS_PER_SHORTLINK, REFERRAL_POINTS_PER_REFERRAL, POINTS_PER_CHANNEL_JOIN,
    MIN_WITHDRAWAL_POINTS, UPI_QR_BANK_POINTS_TO_RUPEES_RATE, REDEEM_CODE_POINTS_TO_RUPEES_RATE,
    FORCE_SUBSCRIBE_CHANNEL_ID, FORCE_SUBSCRIBE_CHANNEL_USERNAME, JOIN_TO_EARN_CHANNELS,
    WEBHOOK_URL # वेबहुक सेट करने के लिए, सुनिश्चित करें कि यह पर्यावरण से आ रहा है।
)
from languages import LANGUAGES, WITHDRAWAL_STATUS_UPDATE_MESSAGES, DEFAULT_LANGUAGE, get_text
from database_utils import (
    init_db, get_user_data, update_user_data, record_withdrawal_request,
    set_user_language, withdrawal_requests_collection, users_collection,
    get_user_language, update_withdrawal_request_status
)

# --- लॉगिंग कॉन्फ़िगर करें ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- एप्लिकेशन इंस्टेंस के लिए ग्लोबल वेरिएबल (बॉट विधियों तक पहुंचने के लिए) ---
application_instance = None
# Flask ऐप इंस्टेंस
app = Flask(__name__)

# --- मुख्य मेनू कीबोर्ड बनाने के लिए हेल्पर फ़ंक्शन ---
def get_main_menu_keyboard(user_id):
    """मुख्य मेनू के लिए InlineKeyboardMarkup बनाता है।"""
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, "earn_button"), callback_data="earn_points_menu"),
            InlineKeyboardButton(get_text(user_id, "profile_button"), callback_data="show_profile")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "invite_button"), callback_data="show_invite"),
            InlineKeyboardButton(get_text(user_id, "withdraw_button"), callback_data="start_withdraw")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "help_button"), callback_data="show_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard(user_id):
    """'मुख्य मेनू पर वापस' बटन के साथ एक इनलाइन कीबोर्ड बनाता है।"""
    keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]]
    return InlineKeyboardMarkup(keyboard)

# --- API से शॉर्टलिंक लाने के लिए हेल्per फ़ंक्शन ---
async def fetch_new_shortlink_from_api(user_id, target_url=None):
    """
    कॉन्फ़िगर किए गए API (arlinks.in) से एक नया शॉर्टलिंक लाता है।
    """
    try:
        task_id = str(ObjectId())

        # गंतव्य लिंक का निर्माण करें जिस पर arlinks.in शॉर्टलिंक रीडायरेक्ट करेगा।
        # यह लिंक आपके सर्वर पर होना चाहिए और आदर्श रूप से आपके वेबहुक को ट्रिगर करना चाहिए
        # या user_id और task_id के साथ सफलता का संकेत देना चाहिए।
        # यदि arlinks.in में एक वेबहुक है, तो आप इसे उनके डैशबोर्ड में कॉन्फ़िगर करेंगे
        # जो इंगित करता है: f"{WEBHOOK_URL}/shortlink_webhook?user_id={user_id}&task_id={task_id}"
        # (यह एक काल्पनिक उदाहरण है, उनके वेबहुक क्षमताओं के लिए arlinks.in दस्तावेज़ देखें)
        destination_link = f"{WEBHOOK_URL}/shortlink_webhook_success_page?user_id={user_id}&task_id={task_id}"

        api_url = SHORTLINK_API_URL # यह "https://arlinks.in/api" होना चाहिए
        api_key = SHORTLINK_API_KEY # यह arlinks.in के लिए आपकी API कुंजी है

        params = {
            "api": api_key,
            "url": destination_link,
            # "alias": task_id # वैकल्पिक: यदि arlinks.in गतिशील उपनामों का समर्थन करता है तो आप task_id को एक उपनाम के रूप में उपयोग कर सकते हैं
        }

        response = requests.get(api_url, params=params, timeout=15)
        response.raise_for_status() # खराब स्टेटस कोड (4xx या 5xx) के लिए एक अपवाद उठाएँ
        data = response.json()

        if data.get('status') == 'success':
            shortlink = data.get('shortenedUrl')
            if shortlink:
                logger.info(f"उपयोगकर्ता {user_id} के लिए arlinks.in शॉर्टलिंक जेनरेट किया गया: {shortlink}")
                return shortlink, task_id # शॉर्टलिंक और जेनरेटेड task_id लौटाएँ
            else:
                logger.error(f"arlinks.in API ने सफलता लौटाई लेकिन उपयोगकर्ता {user_id} के लिए 'shortenedUrl' नहीं: {data}")
                return None, None
        else:
            error_message = data.get('message', 'arlinks.in API से अज्ञात त्रुटि')
            logger.error(f"उपयोगकर्ता {user_id} के लिए arlinks.in शॉर्टलिंक जेनरेट करने में विफल: {error_message} | पूर्ण प्रतिक्रिया: {data}")
            return None, None

    except requests.exceptions.HTTPError as e:
        logger.error(f"arlinks.in API (उपयोगकर्ता {user_id}) से शॉर्टलिंक लाते समय HTTP त्रुटि: {e.response.status_code} {e.response.reason} - {e.response.text}")
        return None, None
    except requests.exceptions.RequestException as e:
        logger.error(f"arlinks.in API (उपयोगकर्ता {user_id}) से शॉर्टलिंक लाते समय नेटवर्क त्रुटि: {e}")
        return None, None
    except Exception as e:
        logger.error(f"fetch_new_shortlink_from_api (arlinks.in, उपयोगकर्ता {user_id}) में एक अप्रत्याशित त्रुटि हुई: {e}")
        return None, None

# --- Flask Webhook हैंडलर (शॉर्टलिंक सत्यापन के लिए) ---
# यह Flask ऐप आपके शॉर्टलिंक प्रदाता से कॉलबैक सुनने के लिए एक HTTP सर्वर चलाएगा।
@app.route('/shortlink_webhook', methods=['POST'])
async def handle_shortlink_webhook_post():
    # यह विधि शॉर्टलिंक प्रदाता से आने वाले POST अनुरोधों को हैंडल करती है।
    try:
        payload = request.json
        logger.info(f"Flask को शॉर्टलिंक वेबहुक POST अनुरोध प्राप्त हुआ: {payload}")

        user_id = payload.get('user_id') # आपको इसे arlinks.in से पास करना होगा
        task_id = payload.get('task_id') # आपको इसे arlinks.in से पास करना होगा
        status = payload.get('status') # उदाहरण: 'completed', 'success' (arlinks.in के अनुसार)

        # यदि आपका API एक गुप्त टोकन प्रदान करता है तो उसे सत्यापित करना भी जोड़ें ताकि नकली कॉल को रोका जा सके
        # secret_token = request.headers.get('X-Shortener-Signature')
        # if not verify_shortener_signature(secret_token, payload):
        #    return jsonify({"status": "error", "message": "अनधिकृत"}), 403

        if user_id and task_id and status == 'completed': # या जो भी सफलता का संकेत देता है
            # यहां, आपको आदर्श रूप से जांचना चाहिए कि यह task_id वास्तव में इस उपयोगकर्ता को दिया गया था
            # और अभी तक दावा नहीं किया गया है, ताकि रीप्ले हमलों को रोका जा सके।
            # सरलता के लिए, हम सीधे क्रेडिट करेंगे।

            update_user_data(int(user_id), balance_change=POINTS_PER_SHORTLINK, shortlinks_solved_change=1)
            user_data = get_user_data(int(user_id))
            current_balance = user_data["balance"]
            solved_count = user_data["shortlinks_solved_count"]

            # टेलीग्राम के माध्यम से उपयोगकर्ता को सूचित करें
            if application_instance:
                message_text = get_text(int(user_id), "shortlink_completed",
                                        points=POINTS_PER_SHORTLINK,
                                        solved_count=solved_count,
                                        balance=current_balance)
                # असिंक्रोनस टेलीग्राम send_message को सिंक्रोनस Flask हैंडलर से चलाएँ
                try:
                    await application_instance.bot.send_message(
                        chat_id=int(user_id),
                        text=message_text,
                        reply_markup=get_main_menu_keyboard(int(user_id)),
                        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
                    )
                except Exception as e:
                    logger.error(f"Flask से टेलीग्राम संदेश भेजने में त्रुटि (उपयोगकर्ता {user_id}): {e}")

            return jsonify({"status": "success"}), 200
        else:
            logger.warning(f"अधूरा या असफल वेबहुक पेलोड: {payload}")
            return jsonify({"status": "error", "message": "बुरा अनुरोध"}), 400

    except Exception as e:
        logger.error(f"Flask वेबहुक POST अनुरोध को संसाधित करने में त्रुटि: {e}")
        return jsonify({"status": "error", "message": "आंतरिक सर्वर त्रुटि"}), 500

@app.route('/shortlink_webhook_success_page', methods=['GET'])
async def handle_shortlink_webhook_get():
    # यह शॉर्टलिंक सफलता रीडायरेक्ट URL के लिए है, यदि आपका शॉर्टनर वेबहुक का उपयोग नहीं करता है।
    # यह विधि कम विश्वसनीय है क्योंकि उपयोगकर्ता रीडायरेक्ट होने से पहले टैब बंद कर सकते हैं।
    try:
        user_id = request.args.get('user_id')
        task_id = request.args.get('task_id')

        if user_id and task_id:
            logger.info(f"उपयोगकर्ता {user_id}, कार्य {task_id} के लिए Flask GET कॉलबैक प्राप्त हुआ")
            # आदर्श रूप से यहां भी सत्यापन करें (जैसे सुनिश्चित करना कि task_id इस उपयोगकर्ता के लिए वैध था)

            # यहां पॉइंट क्रेडिट को ट्रिगर करें (POST हैंडलर के समान)।
            # आपको आदर्श रूप से जांचना चाहिए कि यह कार्य पहले ही वेबहुक द्वारा क्रेडिट नहीं किया गया है।
            update_user_data(int(user_id), shortlinks_solved_change=1, balance_change=POINTS_PER_SHORTLINK)
            user_data = get_user_data(int(user_id))

            if application_instance:
                message_text = get_text(int(user_id), "shortlink_completed",
                                        points=POINTS_PER_SHORTLINK,
                                        solved_count=user_data["shortlinks_solved_count"], # अस्थायी अपडेट
                                        balance=user_data["balance"]) # अस्थायी अपडेट
                try:
                    await application_instance.bot.send_message(
                        chat_id=int(user_id),
                        text=message_text,
                        reply_markup=get_main_menu_keyboard(int(user_id)),
                        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
                    )
                except Exception as e:
                    logger.error(f"Flask से टेलीग्राम संदेश भेजने में त्रुटि (उपयोगकर्ता {user_id}): {e}")

            return "<html><body><h1>शॉर्टलिंक पूरा हुआ!</h1><p>अब आप टेलीग्राम पर वापस जा सकते हैं।</p></body></html>", 200
        else:
            return "<html><body><h1>बुरा अनुरोध</h1><p>गायब पैरामीटर।</p></body></html>", 400

    except Exception as e:
        logger.error(f"Flask वेबहुक GET अनुरोध को संसाधित करने में त्रुटि: {e}")
        return "<html><body><h1>आंतरिक सर्वर त्रुटि</h1></body></html>", 500

# --- मुख्य बॉट हैंडलर ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id) # यह भी सुनिश्चित करता है कि उपयोगकर्ता DB में मौजूद है

    # चरण 1: अनिवार्य सदस्यता जांच
    if not await check_force_subscribe(update, context, user_id):
        return

    # चरण 2: यदि भाषा सेट नहीं है तो भाषा चयन
    if 'language_set_in_session' not in context.user_data and user_data.get('language') == DEFAULT_LANGUAGE:
        keyboard = []
        for lang_code, lang_data in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_data["name"], callback_data=f"set_lang_{lang_code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[DEFAULT_LANGUAGE]["language_choice"],
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_language'] = True
        return

    # चरण 3: यदि लागू हो तो रेफरल हैंडल करें
    referrer_id = None
    if context.args:
        try:
            if context.args[0].startswith("ref_"):
                referrer_id = int(context.args[0].replace('ref_', ''))
        except ValueError:
            logger.warning(f"अमान्य रेफरल आर्ग्यूमेंट: {context.args[0]}")
            referrer_id = None

    if referrer_id and referrer_id != user_id and user_data["referred_by"] is None:
        referrer_data = get_user_data(referrer_id)
        if referrer_data:
            update_user_data(user_id, set_referred_by=referrer_id)
            update_user_data(referrer_id, referral_count_change=1, balance_change=REFERRAL_POINTS_PER_REFERRAL)

            referrer_user_info = await context.bot.get_chat(user_id) # संदर्भित उपयोगकर्ता के बारे में जानकारी प्राप्त करें
            referrer_username = referrer_user_info.username if referrer_user_info.username else str(user_id)

            await context.bot.send_message(
                chat_id=referrer_id,
                text=get_text(referrer_id, "referrer_joined", user_username=escape_markdown(referrer_username, version=2), referral_points_per_referral=REFERRAL_POINTS_PER_REFERRAL),
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
            logger.info(f"उपयोगकर्ता {user_id} को {referrer_id} द्वारा रेफर किया गया। रेफरर को {REFERRAL_POINTS_PER_REFERRAL} अंक क्रेडिट किए गए।")
            # रेफरल प्रोसेसिंग के बाद स्वागत संदेश भेजें
            user_data = get_user_data(user_id) # उपयोगकर्ता डेटा रीफ्रेश करें
            await update.message.reply_text(
                get_text(user_id, "welcome", first_name=escape_markdown(update.effective_user.first_name, version=2),
                                 balance=user_data["balance"]),
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
            return
        else:
            await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
            return
    elif referrer_id == user_id:
        await update.message.reply_text(get_text(user_id, "self_referral"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        return

    # यदि कोई रेफरल नहीं है या रेफरल पहले ही प्रोसेस हो चुका है तो सामान्य स्वागत संदेश
    await update.message.reply_text(
        get_text(user_id, "welcome", first_name=escape_markdown(update.effective_user.first_name, version=2),
                                 balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def check_force_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """जांचता है कि उपयोगकर्ता ने अनिवार्य चैनल जॉइन किया है या नहीं।"""
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_SUBSCRIBE_CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        else:
            keyboard = [[
                InlineKeyboardButton(get_text(user_id, "join_channel_button"), url=f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_USERNAME}"),
                InlineKeyboardButton(get_text(user_id, "joined_check_button"), callback_data="check_force_subscribe")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await (update.message or update.callback_query.message).reply_text(
                get_text(user_id, "force_subscribe_text", channel_username=escape_markdown(FORCE_SUBSCRIBE_CHANNEL_USERNAME, version=2)),
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
            return False
    except Exception as e:
        logger.error(f"उपयोगकर्ता {user_id} के लिए अनिवार्य सदस्यता जांचने में त्रुटि: {e}")
        keyboard = [[
            InlineKeyboardButton(get_text(user_id, "join_channel_button"), url=f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_USERNAME}"),
            InlineKeyboardButton(get_text(user_id, "joined_check_button"), callback_data="check_force_subscribe")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await (update.message or update.callback_query.message).reply_text(
            get_text(user_id, "not_joined_error", channel_username=escape_markdown(FORCE_SUBSCRIBE_CHANNEL_USERNAME, version=2)),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
        return False

async def handle_force_subscribe_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if await check_force_subscribe(update, context, user_id):
        user_data = get_user_data(user_id) # उपयोगकर्ता डेटा रीफ्रेश करें
        if 'waiting_for_language' in context.user_data and user_data.get('language') == DEFAULT_LANGUAGE:
            keyboard = []
            for lang_code, lang_data in LANGUAGES.items():
                keyboard.append([InlineKeyboardButton(lang_data["name"], callback_data=f"set_lang_{lang_code}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                LANGUAGES[DEFAULT_LANGUAGE]["language_choice"],
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                get_text(user_id, "welcome", first_name=escape_markdown(query.from_user.first_name, version=2),
                                 balance=user_data["balance"]),
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
    else:
        pass # कुछ न करें, क्योंकि पिछले फ़ंक्शन ने पहले ही संदेश को हैंडल कर लिया है।

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.replace("set_lang_", "")

    if lang_code not in LANGUAGES:
        await query.answer("अमान्य भाषा चयन।", show_alert=True)
        return

    set_user_language(user_id, lang_code)
    context.user_data['language_set_in_session'] = True
    if 'waiting_for_language' in context.user_data:
        del context.user_data['waiting_for_language']

    await query.answer(f"भाषा {LANGUAGES[lang_code]['name']} पर सेट की गई।", show_alert=True)

    user_data = get_user_data(user_id)
    await query.edit_message_text(
        get_text(user_id, "welcome", first_name=escape_markdown(query.from_user.first_name, version=2),
                                 balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    await query.edit_message_text(
        get_text(user_id, "welcome", first_name=escape_markdown(query.from_user.first_name, version=2),
                                 balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )
    # यदि उपयोगकर्ता मुख्य मेनू पर वापस जाता है तो किसी भी सक्रिय स्थिति को साफ़ करें
    context.user_data.pop('withdraw_state', None)
    context.user_data.pop('withdraw_amount_points', None)
    context.user_data.pop('withdraw_amount_rupees', None)
    context.user_data.pop('withdraw_method', None)
    context.user_data.pop('last_given_shortlink', None)


# --- अंक कमाएँ मेनू ---
async def show_earn_points_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "solve_shortlinks_button"), callback_data="earn_shortlinks")],
        [InlineKeyboardButton(get_text(user_id, "join_channels_button"), callback_data="earn_join_channels")],
        [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        get_text(user_id, "earn_options_prompt"),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

# --- शॉर्टलिंक कमाई लॉजिक ---
async def earn_shortlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    user_data = get_user_data(user_id)

    # सबसे पहले, निर्देश भेजें
    await query.edit_message_text(
        get_text(user_id, "shortlink_instructions", points_per_shortlink=POINTS_PER_SHORTLINK),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )
    # फिर तुरंत शॉर्टलिंक प्रदान करें
    shortlink, task_id = await fetch_new_shortlink_from_api(user_id)

    if not shortlink:
        await context.bot.send_message(chat_id=user_id, text=get_text(user_id, "shortlink_unavailable"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        return

    # बाद में सत्यापन के लिए task_id (या शॉर्टलिंक यदि task_id का उपयोग शॉर्टनर द्वारा नहीं किया जाता है) स्टोर करें
    # यह वेबहुक दृष्टिकोण के लिए महत्वपूर्ण है यदि आपको किसी दिए गए लिंक के साथ एक पूर्णता का मिलान करने की आवश्यकता है
    # अभी के लिए, हम बस यह तथ्य स्टोर करेंगे कि एक शॉर्टलिंक कार्य शुरू किया गया था।
    # एक वास्तविक वेबहुक सिस्टम में, आप user_data में या एक अलग संग्रह में task_id स्टोर करेंगे
    # और इसे 'लंबित' के रूप में चिह्नित करेंगे।
    context.user_data['last_given_shortlink_task_id'] = task_id # जेनरेटेड task_id स्टोर करें
    context.user_data['last_given_shortlink_user_id'] = user_id # सुनिश्चित करें कि हम जानते हैं कि यह कार्य किसके लिए है

    keyboard = [[InlineKeyboardButton(get_text(user_id, "shortlink_completed_button"), callback_data="done_shortlink")]]
    # कमाई विकल्पों के मेनू पर लौटने के लिए एक बटन जोड़ें
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="earn_points_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message( # निर्देशों को संपादित करने से बचने के लिए एक नए संदेश के रूप में भेजें
        chat_id=user_id,
        text=get_text(user_id, "shortlink_given", shortlink=shortlink),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def done_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    await query.answer("शॉर्टलिंक पूर्णता की जाँच कर रहा है...", show_alert=True) # तत्काल प्रतिक्रिया

    # यह वह जगह है जहां वेबहुक सत्यापन आदर्श रूप से काम आएगा।
    # यदि वेबहुक का उपयोग कर रहे हैं, तो यह बटन अनिवार्य रूप से उपयोगकर्ता को सत्यापन की प्रतीक्षा करने के लिए कहता है।
    # इस उदाहरण के लिए, यदि वेबहुक सिस्टम पूरी तरह से सेट अप/काम नहीं कर रहा है,
    # तो यह बटन सीधे पॉइंट्स क्रेडिट करेगा एक फॉलबैक के रूप में।
    # एक उत्पादन सेटअप में वेबहुक के साथ, आप यहां क्रेडिट नहीं करेंगे;
    # आप क्रेडिट को ट्रिगर करने के लिए वेबहुक कॉलबैक की प्रतीक्षा करेंगे।

    # --- फॉलबैक/परीक्षण: यदि वेबहुक सक्रिय/पूरी तरह से काम नहीं कर रहा है तो सीधा क्रेडिट ---
    # यदि आपके पास एक मजबूत वेबहुक सेटअप है तो इस भाग को हटा दिया जाना चाहिए या टिप्पणी कर दी जानी चाहिए।
    # यदि उपयोगकर्ता "मैंने पूरा कर लिया" पर क्लिक करता है और वेबहुक अभी तक फायर नहीं हुआ है,
    # तो हम मान लेंगे कि उन्होंने इसे किया और प्रदर्शन के लिए क्रेडिट करेंगे।
    # एक वास्तविक प्रणाली में, आप जांचेंगे कि context.user_data['last_given_shortlink_task_id']
    # को आपके डेटाबेस में वेबहुक द्वारा 'पूर्ण' के रूप में चिह्नित किया गया है या नहीं।

    # यदि कोई वेबहुक सिस्टम पूरी तरह से एकीकृत नहीं है तो वेबहुक सफलता का अनुकरण करें
    if 'last_given_shortlink_task_id' in context.user_data and context.user_data['last_given_shortlink_user_id'] == user_id:
        # बटन से दोहरी दावा रोकने के लिए
        del context.user_data['last_given_shortlink_task_id']
        del context.user_data['last_given_shortlink_user_id']

        update_user_data(user_id, shortlinks_solved_change=1, balance_change=POINTS_PER_SHORTLINK)
        user_data = get_user_data(user_id) # अपडेटेड उपयोगकर्ता डेटा प्राप्त करें

        solved_count = user_data["shortlinks_solved_count"]
        current_balance = user_data["balance"]

        message_text = get_text(user_id, "shortlink_completed",
                                points=POINTS_PER_SHORTLINK,
                                solved_count=solved_count,
                                balance=current_balance)

        keyboard = [[InlineKeyboardButton(get_text(user_id, "next_shortlink_button"), callback_data="earn_shortlinks")]]
        keyboard.append([InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="earn_points_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
    else:
        await query.edit_message_text(get_text(user_id, "no_shortlink_started"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें


# --- चैनल/ग्रुप जॉइन कमाई लॉजिक ---
async def earn_join_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    channels_to_display = []
    for channel_id, channel_username in JOIN_TO_EARN_CHANNELS:
        if channel_id not in user_data["joined_channels"]:
            channels_to_display.append((channel_id, channel_username))

    if not channels_to_display:
        await query.edit_message_text(
            get_text(user_id, "no_more_channels"),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
        return

    keyboard = []
    for channel_id, channel_username in channels_to_display:
        keyboard.append([
            InlineKeyboardButton(f"🔗 @{channel_username}", url=f"https://t.me/{channel_username.replace('@', '')}"),
            InlineKeyboardButton(get_text(user_id, "joined_claim_button"), callback_data=f"claim_channel_{channel_id}")
        ])
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="earn_points_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        get_text(user_id, "channels_to_join_prompt"),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def claim_channel_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    channel_id_str = query.data.replace("claim_channel_", "")
    channel_id = int(channel_id_str)

    user_data = get_user_data(user_id)

    # कॉन्फ़िग से channel_username ढूंढें
    channel_username = "अज्ञात चैनल"
    for cid, cuser in JOIN_TO_EARN_CHANNELS:
        if cid == channel_id:
            channel_username = cuser
            break

    if channel_id in user_data["joined_channels"]:
        await query.answer(get_text(user_id, "channel_already_claimed", channel_username=escape_markdown(channel_username, version=2)), show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            update_user_data(user_id, balance_change=POINTS_PER_CHANNEL_JOIN, add_joined_channel=channel_id)
            user_data = get_user_data(user_id) # डेटा रीफ्रेश करें

            await query.answer(get_text(user_id, "channel_claim_success", points=POINTS_PER_CHANNEL_JOIN, channel_username=escape_markdown(channel_username, version=2), balance=user_data["balance"]), show_alert=True)

            # सूची को अपडेट करने के लिए earn_join_channels मेनू को फिर से भेजें
            await earn_join_channels(update, context) # रीफ्रेश करने के लिए हैंडलर को फिर से कॉल करें

        else:
            await query.answer(get_text(user_id, "channel_not_joined", channel_username=escape_markdown(channel_username, version=2)), show_alert=True)
            return

    except Exception as e:
        logger.error(f"चैनल {channel_id} पर उपयोगकर्ता {user_id} के लिए चैनल पॉइंट्स का दावा करने में त्रुटि: {e}")
        await query.answer(get_text(user_id, "generic_error"), show_alert=True)


# --- प्रोफ़ाइल और बैलेंस ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    # 'user_id=user_id' को हटाया गया क्योंकि यह पहले से ही पहले तर्क के रूप में पास किया गया है।
    profile_text = get_text(user_id, "profile_text",
                            balance=user_data["balance"],
                            shortlinks_solved_count=user_data["shortlinks_solved_count"],
                            referral_count=user_data["referral_count"],
                            total_withdrawn=user_data["total_withdrawn"])

    await query.edit_message_text(
        profile_text,
        reply_markup=get_back_to_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    referral_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    invite_text = get_text(user_id, "invite_text",
                           referral_points_per_referral=REFERRAL_POINTS_PER_REFERRAL,
                           referral_link=referral_link) # referral_link को escape_markdown() की आवश्यकता नहीं है यदि यह [text](url) के भीतर है।

    await query.edit_message_text(
        invite_text,
        reply_markup=get_back_to_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2, # ParseMode.MARKDOWN_V2 का उपयोग करें
        disable_web_page_preview=True
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # KeyError: 'min_points' को हल करने के लिए min_points पास किया गया
    help_text = get_text(user_id, "help_text", min_points=MIN_WITHDRAWAL_POINTS)
    await query.edit_message_text(
        help_text,
        reply_markup=get_back_to_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

# --- निकासी लॉजिक ---
async def start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    if user_data["balance"] < MIN_WITHDRAWAL_POINTS:
        await query.edit_message_text(
            get_text(user_id, "not_enough_points",
                     balance=user_data["balance"],
                     min_withdrawal_points=MIN_WITHDRAWAL_POINTS),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
        return

    context.user_data['withdraw_state'] = 'awaiting_amount'
    keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        get_text(user_id, "enter_withdrawal_amount",
                 min_withdrawal_points=MIN_WITHDRAWAL_POINTS,
                 current_balance=user_data["balance"]),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def handle_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.user_data.get('withdraw_state') != 'awaiting_amount':
        return # अगर सही स्थिति में नहीं है तो अनदेखा करें

    try:
        amount_points = int(update.message.text)
        if amount_points < MIN_WITHDRAWAL_POINTS:
            await update.message.reply_text(
                get_text(user_id, "withdrawal_amount_too_low", min_withdrawal_points=MIN_WITHDRAWAL_POINTS),
                reply_markup=get_back_to_menu_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
            return
        user_data = get_user_data(user_id)
        if amount_points > user_data["balance"]:
            await update.message.reply_text(
                get_text(user_id, "insufficient_balance", balance=user_data["balance"]),
                reply_markup=get_back_to_menu_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
            )
            return

        context.user_data['withdraw_amount_points'] = amount_points
        context.user_data['withdraw_state'] = 'awaiting_method'

        keyboard = [
            [InlineKeyboardButton(get_text(user_id, "upi_qr_button"), callback_data="withdraw_method_upi_qr")],
            [InlineKeyboardButton(get_text(user_id, "redeem_code_button"), callback_data="withdraw_method_redeem_code")],
            [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            get_text(user_id, "choose_withdrawal_method", points=amount_points),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )

    except ValueError:
        await update.message.reply_text(
            get_text(user_id, "invalid_amount_format"),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )

async def handle_withdrawal_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if context.user_data.get('withdraw_state') != 'awaiting_method':
        await query.edit_message_text(get_text(user_id, "unexpected_action"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        return

    method = query.data.replace("withdraw_method_", "")
    context.user_data['withdraw_method'] = method

    amount_points = context.user_data['withdraw_amount_points']
    amount_rupees = 0

    if method == "upi_qr":
        amount_rupees = amount_points / UPI_QR_BANK_POINTS_TO_RUPEES_RATE
        context.user_data['withdraw_amount_rupees'] = amount_rupees
        context.user_data['withdraw_state'] = 'awaiting_upi_id'
        await query.edit_message_text(
            get_text(user_id, "enter_upi_id", points=amount_points, rupees=amount_rupees),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
    elif method == "redeem_code":
        amount_rupees = amount_points / REDEEM_CODE_POINTS_TO_RUPEES_RATE
        context.user_data['withdraw_amount_rupees'] = amount_rupees
        context.user_data['withdraw_state'] = 'confirm_redeem_code'

        keyboard = [
            [InlineKeyboardButton(get_text(user_id, "confirm_withdrawal_button"), callback_data="confirm_redeem_code_withdrawal")],
            [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            get_text(user_id, "confirm_redeem_code_withdrawal_prompt", points=amount_points, rupees=amount_rupees),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
    else:
        await query.edit_message_text(get_text(user_id, "invalid_method"), reply_markup=get_back_to_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        context.user_data.pop('withdraw_state', None)

async def handle_upi_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.user_data.get('withdraw_state') != 'awaiting_upi_id':
        return

    upi_id = update.message.text.strip()
    if not upi_id: # आप यहां एक अधिक मजबूत UPI ID सत्यापन जोड़ सकते हैं
        await update.message.reply_text(get_text(user_id, "invalid_upi_id"), reply_markup=get_back_to_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        return

    context.user_data['upi_id'] = upi_id
    context.user_data['withdraw_state'] = 'confirm_upi'

    amount_points = context.user_data['withdraw_amount_points']
    amount_rupees = context.user_data['withdraw_amount_rupees']

    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "confirm_withdrawal_button"), callback_data="confirm_upi_withdrawal")],
        [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_text(user_id, "confirm_upi_withdrawal_prompt", points=amount_points, rupees=amount_rupees, upi_id=escape_markdown(upi_id, version=2)), # UPI ID को एस्केप करें
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    method = context.user_data.get('withdraw_method')
    current_state = context.user_data.get('withdraw_state')

    if not (method and (current_state == 'confirm_redeem_code' and query.data == 'confirm_redeem_code_withdrawal') or
            (current_state == 'confirm_upi' and query.data == 'confirm_upi_withdrawal')):
        await query.edit_message_text(get_text(user_id, "unexpected_action"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        context.user_data.pop('withdraw_state', None)
        return

    amount_points = context.user_data['withdraw_amount_points']
    amount_rupees = context.user_data['withdraw_amount_rupees']
    upi_id = context.user_data.get('upi_id', 'N/A')

    user_data = get_user_data(user_id)
    if amount_points > user_data["balance"]:
        await query.edit_message_text(
            get_text(user_id, "insufficient_balance", balance=user_data["balance"]),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
        context.user_data.pop('withdraw_state', None)
        return

    # डेटाबेस से अंक घटाएँ
    update_user_data(user_id, balance_change=-amount_points, total_withdrawn_change=amount_points)

    # निकासी अनुरोध रिकॉर्ड करें
    request_id = record_withdrawal_request(
        user_id=user_id,
        username=query.from_user.username or str(user_id),
        first_name=query.from_user.first_name, # first_name जोड़ा गया
        amount_points=amount_points,
        amount_rupees=amount_rupees,
        method=method,
        upi_id=upi_id
    )

    await query.edit_message_text(
        get_text(user_id, "withdrawal_submitted_user",
                 points=amount_points, rupees=amount_rupees,
                 method=method.upper().replace('_', ' '),
                 upi_id=escape_markdown(upi_id, version=2)), # UPI ID को एस्केप करें
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
    )

    # एडमिन को सूचना भेजें
    admin_message_text = get_text(user_id, "admin_new_withdrawal_request",
                                  user_id=user_id,
                                  username=escape_markdown(query.from_user.username or "N/A", version=2), # username को एस्केप करें
                                  first_name=escape_markdown(query.from_user.first_name, version=2), # first_name को एस्केप करें
                                  points=amount_points,
                                  rupees=f"{amount_rupees:.2f}",
                                  method=method.upper().replace('_', ' '),
                                  upi_id=escape_markdown(upi_id, version=2), # UPI ID को एस्केप करें
                                  request_id=str(request_id))

    admin_keyboard = [[
        InlineKeyboardButton("✅ स्वीकृत करें", callback_data=f"approve_{request_id}"),
        InlineKeyboardButton("❌ अस्वीकृत करें", callback_data=f"reject_{request_id}")
    ]]
    admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_WITHDRAWAL_CHANNEL_ID,
            text=admin_message_text,
            reply_markup=admin_reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2 # ParseMode.MARKDOWN_V2 का उपयोग करें
        )
    except Exception as e:
        logger.error(f"एडमिन चैनल पर निकासी सूचना भेजने में त्रुटि: {e}")

    context.user_data.pop('withdraw_state', None)
    context.user_data.pop('withdraw_amount_points', None)
    context.user_data.pop('withdraw_amount_rupees', None)
    context.user_data.pop('withdraw_method', None)
    context.user_data.pop('upi_id', None)

# --- एडमिन हैंडलर ---
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    admin_user_ids = [int(uid) for uid in os.getenv("ADMIN_USER_IDS", "").split(',') if uid.strip()]

    if user_id not in admin_user_ids:
        await query.answer("आपको इस कमांड का उपयोग करने की अनुमति नहीं है।", show_alert=True)
        return

    action, request_id_str = data.split('_', 1)
    request_id = ObjectId(request_id_str)

    # निकासी अनुरोध को डेटाबेस से प्राप्त करें
    withdrawal_request = withdrawal_requests_collection.find_one({"_id": request_id})

    if not withdrawal_request:
        await query.edit_message_text("त्रुटि: निकासी अनुरोध नहीं मिला।")
        return

    if withdrawal_request.get('status') != 'Pending':
        await query.edit_message_text(f"यह अनुरोध पहले ही **{withdrawal_request['status']}** किया जा चुका है।", parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
        return

    requester_user_id = withdrawal_request['user_id']
    amount_points = withdrawal_request['amount_points']
    amount_rupees = withdrawal_request['amount_rupees']
    method = withdrawal_request['method']
    upi_id = withdrawal_request.get('upi_id', 'N/A')
    username = withdrawal_request.get('username', 'N/A')
    first_name = withdrawal_request.get('first_name', 'N/A')

    new_status = ""
    user_message_key = ""
    admin_update_message_key = ""

    if action == "approve":
        new_status = "Approved"
        user_message_key = "withdrawal_approved_user"
        admin_update_message_key = "withdrawal_approved_admin"
        # यदि आवश्यकता हो तो उपयोगकर्ता को UPI / रिडीम कोड भेजें
        # इस बिंदु पर, आपको मैन्युअल रूप से भुगतान करना होगा।
        # यदि रिडीम कोड है, तो आप इसे यहां उपयोगकर्ता को भेज सकते हैं:
        # await context.bot.send_message(chat_id=requester_user_id, text="आपका रिडीम कोड: XXXXX")

    elif action == "reject":
        new_status = "Rejected"
        user_message_key = "withdrawal_rejected_user"
        admin_update_message_key = "withdrawal_rejected_admin"
        # अंक उपयोगकर्ता को वापस कर दें
        update_user_data(requester_user_id, balance_change=amount_points, total_withdrawn_change=-amount_points)
        logger.info(f"उपयोगकर्ता {requester_user_id} को {amount_points} अंक वापस किए गए क्योंकि अनुरोध अस्वीकृत किया गया था।")

    # डेटाबेस में स्टेटस अपडेट करें
    update_withdrawal_request_status(request_id, new_status, query.from_user.id, query.from_user.username)

    # एडमिन को अपडेट करें
    admin_updated_text = WITHDRAWAL_STATUS_UPDATE_MESSAGES[admin_update_message_key].format(
        admin_username=escape_markdown(query.from_user.username or str(user_id), version=2), # एडमिन username को एस्केप करें
        user_id=requester_user_id,
        username=escape_markdown(username, version=2), # username को एस्केप करें
        first_name=escape_markdown(first_name, version=2), # first_name को एस्केप करें
        points=amount_points,
        rupees=f"{amount_rupees:.2f}",
        method=method.upper().replace('_', ' '),
        upi_id=escape_markdown(upi_id, version=2), # UPI ID को एस्केप करें
        request_id=str(request_id)
    )
    await query.edit_message_text(admin_updated_text, parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें

    # उपयोगकर्ता को सूचित करें
    user_final_message = WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_message_key].format(
        points=amount_points,
        rupees=f"{amount_rupees:.2f}",
        method=method.upper().replace('_', ' '),
        upi_id=escape_markdown(upi_id, version=2) # UPI ID को एस्केप करें
    )
    try:
        await context.bot.send_message(chat_id=requester_user_id, text=user_final_message, parse_mode=ParseMode.MARKDOWN_V2) # ParseMode.MARKDOWN_V2 का उपयोग करें
    except Exception as e:
        logger.error(f"उपयोगकर्ता {requester_user_id} को स्टेटस अपडेट संदेश भेजने में विफल: {e}")

    context.user_data.pop('withdraw_state', None)
    context.user_data.pop('withdraw_amount_points', None)
    context.user_data.pop('withdraw_amount_rupees', None)
    context.user_data.pop('withdraw_method', None)
    context.user_data.pop('upi_id', None)

async def handle_unrecognized_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(get_text(user_id, "unrecognized_command"), reply_markup=get_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN_V2)


# --- मुख्य फ़ंक्शन जो बॉट को चलाता है ---
async def run_bot():
    """बॉट को वेबहुक मोड में शुरू करता है।"""
    global application_instance
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()
    application_instance = application

    # कमांड हैंडलर
    application.add_handler(CommandHandler("start", start))

    # कॉलबैक क्वेरी हैंडलर
    application.add_handler(CallbackQueryHandler(handle_force_subscribe_check_callback, pattern="^check_force_subscribe$"))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^set_lang_"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(show_earn_points_menu, pattern="^earn_points_menu$"))
    application.add_handler(CallbackQueryHandler(earn_shortlinks, pattern="^earn_shortlinks$"))
    application.add_handler(CallbackQueryHandler(done_shortlink, pattern="^done_shortlink$"))
    application.add_handler(CallbackQueryHandler(earn_join_channels, pattern="^earn_join_channels$"))
    application.add_handler(CallbackQueryHandler(claim_channel_points, pattern="^claim_channel_"))
    application.add_handler(CallbackQueryHandler(show_profile, pattern="^show_profile$"))
    application.add_handler(CallbackQueryHandler(show_invite, pattern="^show_invite$"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(start_withdraw, pattern="^start_withdraw$"))
    application.add_handler(CallbackQueryHandler(handle_withdrawal_method, pattern="^withdraw_method_"))
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_redeem_code_withdrawal$|^confirm_upi_withdrawal$"))

    # मैसेज हैंडलर (निकासी राशि और UPI ID के लिए)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(lambda user: 'withdraw_state' in application.user_data[user.id] and application.user_data[user.id]['withdraw_state'] == 'awaiting_amount'), handle_withdrawal_amount))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(lambda user: 'withdraw_state' in application.user_data[user.id] and application.user_data[user.id]['withdraw_state'] == 'awaiting_upi_id'), handle_upi_id))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unrecognized_message)) # अज्ञात संदेशों को हैंडल करें

    # एडमिन हैंडलर
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(approve|reject)_"))

    logger.info("टेलीग्राम बॉट वेबहुक मोड में शुरू हो रहा है...")

    # Telegram.ext.Application के वेबहुक सर्वर को एक अलग थ्रेड में चलाएँ।
    # Flask ऐप मुख्य थ्रेड में Gunicorn द्वारा चलाया जाएगा।
    # यह सुनिश्चित करता है कि दोनों एक ही पोर्ट का उपयोग कर सकते हैं लेकिन अलग-अलग थ्रेड/प्रोसेस में।
    # Koyeb पर, Gunicorn सभी HTTP ट्रैफ़िक को हैंडल करेगा और इसे Flask ऐप पर रूट करेगा।
    # Flask ऐप के भीतर, हम Telegram अपडेट को ptb एप्लिकेशन में मैन्युअल रूप से पास करेंगे।

    # PtB Application को रन करने के लिए एक अलग इवेंट लूप बनाएं।
    # यह तरीका Flask के साथ PtB को चलाने के लिए सबसे मजबूत है।
    loop = asyncio.get_event_loop()
    loop.create_task(application.run_polling()) # या application.run_webhook() यदि आप Flask को सिर्फ एक प्रॉक्सी के रूप में उपयोग कर रहे हैं।
    # लेकिन Koyeb पर, Gunicorn मुख्य सर्वर होगा।
    # हम Flask को चलाएंगे और Telegram अपडेट को Flask से ptb में पास करेंगे।

    # Gunicorn Flask ऐप को चलाएगा। Telegram अपडेट को Flask के माध्यम से ptb में भेजा जाएगा।
    # हम telegram_app को app.py के भीतर चला नहीं रहे हैं, बल्कि इसे अपडेट दे रहे हैं।
    # इसे 'long-polling' की आवश्यकता नहीं होगी यदि वेबहुक ठीक से सेट हैं।

    # --- Flask को Koyeb पर चलाने के लिए सेटअप करें ---
    # `run_bot()` फ़ंक्शन को सीधे नहीं चलाया जाएगा।
    # Gunicorn `app` ऑब्जेक्ट को चलाएगा।
    # हमें Telegram Application को भी `app` के साथ शुरू करना होगा।
    # इसलिए, हम `application` को `app.before_first_request` में आरंभ करेंगे।
    pass # run_bot() को main() में ले जाया जाएगा

# Flask ऐप के लिए वेबहुक हैंडलर
@app.route('/telegram', methods=['POST'])
async def telegram_webhook():
    """टेलीग्राम अपडेट के लिए वेबहुक हैंडलर।"""
    global application_instance
    if not application_instance:
        # बॉट इंस्टेंस को आरंभ करें यदि यह पहले से नहीं हुआ है (केवल एक बार होना चाहिए)
        init_db()
        application_instance = Application.builder().token(BOT_TOKEN).build()
        # अपने सभी हैंडलर यहां जोड़ें
        application_instance.add_handler(CommandHandler("start", start))
        application_instance.add_handler(CallbackQueryHandler(handle_force_subscribe_check_callback, pattern="^check_force_subscribe$"))
        application_instance.add_handler(CallbackQueryHandler(set_language, pattern="^set_lang_"))
        application_instance.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
        application_instance.add_handler(CallbackQueryHandler(show_earn_points_menu, pattern="^earn_points_menu$"))
        application_instance.add_handler(CallbackQueryHandler(earn_shortlinks, pattern="^earn_shortlinks$"))
        application_instance.add_handler(CallbackQueryHandler(done_shortlink, pattern="^done_shortlink$"))
        application_instance.add_handler(CallbackQueryHandler(earn_join_channels, pattern="^earn_join_channels$"))
        application_instance.add_handler(CallbackQueryHandler(claim_channel_points, pattern="^claim_channel_"))
        application_instance.add_handler(CallbackQueryHandler(show_profile, pattern="^show_profile$"))
        application_instance.add_handler(CallbackQueryHandler(show_invite, pattern="^show_invite$"))
        application_instance.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
        application_instance.add_handler(CallbackQueryHandler(start_withdraw, pattern="^start_withdraw$"))
        application_instance.add_handler(CallbackQueryHandler(handle_withdrawal_method, pattern="^withdraw_method_"))
        application_instance.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_redeem_code_withdrawal$|^confirm_upi_withdrawal$"))
        application_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(lambda user: 'withdraw_state' in application_instance.user_data[user.id] and application_instance.user_data[user.id]['withdraw_state'] == 'awaiting_amount'), handle_withdrawal_amount))
        application_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(lambda user: 'withdraw_state' in application_instance.user_data[user.id] and application_instance.user_data[user.id]['withdraw_state'] == 'awaiting_upi_id'), handle_upi_id))
        application_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unrecognized_message)) # अज्ञात संदेशों को हैंडल करें
        application_instance.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(approve|reject)_"))

        # एक बार बॉट इनिशियलाइज़ होने के बाद पोस्ट-इनिशियलाइज़ेशन हुक।
        # यह `async` फ़ंक्शन के अंदर async operations को सुरक्षित रूप से चलाता है।
        await application_instance.post_init()


    update = Update.de_json(request.json, application_instance.bot)
    await application_instance.process_update(update)
    return 'ok'

if __name__ == '__main__':
    # यह भाग केवल स्थानीय परीक्षण के लिए है।
    # Koyeb पर, Gunicorn `app` ऑब्जेक्ट को चलाएगा।
    init_db() # डेटाबेस को शुरू करें
    # Koyeb के लिए, हम Flask ऐप को सीधे चलाते हैं और Gunicorn इसे संभालेगा।
    # हम यहां बॉट को रन नहीं करते हैं क्योंकि Flask वेबहुक को हैंडल करेगा।
    # लोकल डेवलपमेंट के लिए, आप Flask ऐप को चला सकते हैं।
    PORT = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=PORT, debug=True)
