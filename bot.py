# bot.py

import random
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from datetime import datetime
from bson.objectid import ObjectId # MongoDB ObjectIds के लिए आवश्यक
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import asyncio # Webhook हैंडलर में async कार्यों को चलाने के लिए
import urllib.parse # Webhook GET अनुरोधों को पार्स करने के लिए
import os # पर्यावरण चर तक पहुंचने के लिए

# आपकी कस्टम इम्पोर्ट्स
from config import (
    BOT_TOKEN, ADMIN_WITHDRAWAL_CHANNEL_ID, SHORTLINK_API_URL, SHORTLINK_API_KEY,
    POINTS_PER_SHORTLINK, REFERRAL_POINTS_PER_REFERRAL, POINTS_PER_CHANNEL_JOIN,
    MIN_WITHDRAWAL_POINTS, UPI_QR_BANK_POINTS_TO_RUPEES_RATE, REDEEM_CODE_POINTS_TO_RUPEES_RATE,
    FORCE_SUBSCRIBE_CHANNEL_ID, FORCE_SUBSCRIBE_CHANNEL_USERNAME, JOIN_TO_EARN_CHANNELS,
    WEBHOOK_URL # वेबहुक सेट करने के लिए
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

# --- API से शॉर्टलिंक लाने के लिए हेल्पर फ़ंक्शन ---
async def fetch_new_shortlink_from_api(user_id, target_url=None):
    """
    कॉन्फ़िगर किए गए API (arlinks.in) से एक नया शॉर्टलिंक लाता है।
    """
    try:
        # इस शॉर्टलिंक अनुरोध के लिए एक अद्वितीय task_id जेनरेट करें।
        # यह task_id आदर्श रूप से शॉर्टलिंक प्रक्रिया के माध्यम से पारित किया जाना चाहिए
        # और arlinks.in द्वारा एक वेबहुक के माध्यम से वापस किया जाना चाहिए।
        task_id = str(ObjectId())

        # गंतव्य लिंक का निर्माण करें जिस पर arlinks.in शॉर्टलिंक रीडायरेक्ट करेगा।
        # यह लिंक आपके सर्वर पर होना चाहिए और आदर्श रूप से आपके वेबहुक को ट्रिगर करना चाहिए
        # या user_id और task_id के साथ सफलता का संकेत देना चाहिए।
        # यदि arlinks.in में एक वेबहुक है, तो आप इसे उनके डैशबोर्ड में कॉन्फ़िगर करेंगे
        # जो इंगित करता है: f"{WEBHOOK_URL}/shortlink_completed?user_id={user_id}&task_id={task_id}"
        # (यह एक काल्पनिक उदाहरण है, उनके वेबहुक क्षमताओं के लिए arlinks.in दस्तावेज़ देखें)
        
        # अभी के लिए, मान लें कि शॉर्टलिंक के बाद अंतिम गंतव्य सिर्फ एक सामान्य पृष्ठ है,
        # और हम उपयोगकर्ता द्वारा "मैंने पूरा कर लिया!" पर क्लिक करने या बाहरी वेबहुक सत्यापन पर भरोसा करते हैं।
        # यदि arlinks.in में वेबहुक नहीं है, तो `done_shortlink` बटन प्राथमिक क्रेडिट तंत्र होगा।
        
        # arlinks.in API के लिए एक साधारण डमी गंतव्य लिंक:
        # यह वह जगह है जहां arlinks.in का शॉर्टलिंक अंततः उपयोगकर्ता को ले जाएगा।
        # एक वास्तविक परिदृश्य में, यह बेहतर ट्रैकिंग के लिए आपके डोमेन पर एक पृष्ठ हो सकता है,
        # लेकिन कई शॉर्टनर के लिए, यह कोई भी वैध URL हो सकता है।
        # यदि arlinks.in एक वेबहुक प्रदान करता है, तो इस target_url की वास्तविक सामग्री सत्यापन के लिए ज्यादा मायने नहीं रखती है।
        # इसे सामान्य उद्देश्य के लिए Google बनाते हैं।
        destination_link = "https://www.google.com/" # या यदि आप एक लागू करते हैं तो आपके डोमेन पर एक अद्वितीय सफलता पृष्ठ।

        # Arlinks.in API: https://arlinks.in/api?api=YOUR_API_KEY&url=YOUR_DESTINATION_URL&alias=CUSTOM_ALIAS
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

# --- Webhook हैंडलर (शॉर्टलिंक सत्यापन के लिए) ---
# यह क्लास आपके शॉर्टलिंक प्रदाता से कॉलबैक सुनने के लिए एक साधारण HTTP सर्वर चलाएगी।
# आपको अपने शॉर्टलिंक प्रदाता के विशिष्ट वेबहुक प्रारूप के आधार पर इसे अनुकूलित करने की आवश्यकता हो सकती है।
class ShortlinkWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # यह विधि शॉर्टलिंक प्रदाता से आने वाले POST अनुरोधों को हैंडल करती है।
        # सटीक पार्सिंग आपके शॉर्टलिंक प्रदाता के वेबहुक पेलोड पर निर्भर करती है।
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            logger.info(f"वेबहुक POST अनुरोध प्राप्त हुआ: {payload}")

            # --- सत्यापन लॉजिक (आपके शॉर्टलिंक API पर अत्यधिक निर्भर) ---
            # आपको यह लागू करने की आवश्यकता है कि आपका शॉर्टलिंक प्रदाता पुष्टि कैसे भेजता है।
            # सामान्य पैटर्न:
            # 1. पेलोड में सीधे 'user_id' और 'task_id'।
            # 2. एक 'transaction_id' जिसे आपने पहले स्टोर किया था।
            # 3. पूर्णता का संकेत देने वाला एक 'status' फ़ील्ड।
            # 4. एक सुरक्षा टोकन/हस्ताक्षर जिसे सत्यापित करने की आवश्यकता है।

            # उदाहरण: यह मानते हुए कि आपका शॉर्टनर user_id और task_id वापस भेजता है
            # आपको अपने शॉर्टनर के आधार पर इन कुंजी नामों को समायोजित करने की आवश्यकता हो सकती है।
            user_id = payload.get('user_id')
            task_id = payload.get('task_id')
            status = payload.get('status') # उदाहरण: 'completed', 'success'
            # यदि आपका API एक गुप्त टोकन प्रदान करता है तो उसे सत्यापित करना भी जोड़ें ताकि नकली कॉल को रोका जा सके
            # secret_token = self.headers.get('X-Shortener-Signature')
            # if not verify_shortener_signature(secret_token, payload):
            #    self.send_response(403)
            #    self.end_headers()
            #    return

            if user_id and task_id and status == 'completed': # या जो भी सफलता का संकेत देता है
                # अपने डेटाबेस में लंबित शॉर्टलिंक कार्य खोजें (यदि आपने उन्हें स्टोर किया है)
                # या यदि वेबहुक विश्वसनीय है तो सीधे उपयोगकर्ता को क्रेडिट करें।
                logger.info(f"उपयोगकर्ता {user_id}, कार्य {task_id} के लिए शॉर्टलिंक पूरा हुआ")
                # आपको आदर्श रूप से जांचना चाहिए कि यह task_id वास्तव में इस उपयोगकर्ता को दिया गया था
                # और अभी तक दावा नहीं किया गया है, ताकि रीप्ले हमलों को रोका जा सके।
                # सरलता के लिए यहां, हम सीधे क्रेडिट करेंगे।

                # उपयोगकर्ता को पॉइंट्स क्रेडिट करें
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
                    # हमें यह सुनिश्चित करने की आवश्यकता हो सकती है कि उपयोगकर्ता का अंतिम संदेश ID या चैट ID संग्रहीत है
                    # ताकि सही संदेश को संपादित/उत्तर दिया जा सके। वेबहुक के लिए, एक नया संदेश भेजना सुरक्षित है।
                    asyncio.run_coroutine_threadsafe(
                        application_instance.bot.send_message(
                            chat_id=int(user_id),
                            text=message_text,
                            reply_markup=get_main_menu_keyboard(int(user_id)), # मुख्य मेनू फिर से दिखाएँ
                            parse_mode='Markdown'
                        ),
                        application_instance.loop
                    )
                self.send_response(200)
                self.end_headers()
            else:
                logger.warning(f"अधूरा या असफल वेबहुक पेलोड: {payload}")
                self.send_response(400) # बुरा अनुरोध
                self.end_headers()

        except Exception as e:
            logger.error(f"वेबहुक POST अनुरोध को संसाधित करने में त्रुटि: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        # यह शॉर्टलिंक सफलता रीडायरेक्ट URL के लिए है, यदि आपका शॉर्टनर वेबहुक का उपयोग नहीं करता है।
        # यह विधि कम विश्वसनीय है क्योंकि उपयोगकर्ता रीडायरेक्ट होने से पहले टैब बंद कर सकते हैं।
        # यदि आपका शॉर्टनर एक वेबहुक प्रदान करता है, तो आपको अंक अर्जित करने के लिए इसकी आवश्यकता नहीं है।
        # यह यहां मुख्य रूप से कुछ शॉर्टनर के अंतिम रीडायरेक्ट के लिए एक लक्ष्य के रूप में कार्य करने के लिए है।
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_path.query)

            if parsed_path.path == '/webhook/shortlink_success':
                user_id = query_params.get('user_id', [None])[0]
                task_id = query_params.get('task_id', [None])[0]
                
                if user_id and task_id:
                    logger.info(f"उपयोगकर्ता {user_id}, कार्य {task_id} के लिए GET कॉलबैक प्राप्त हुआ")
                    # आपको आमतौर पर यहां एक डेटाबेस की जांच करनी होगी ताकि यह सुनिश्चित हो सके कि यह task_id
                    # वैध था और इस उपयोगकर्ता के लिए अभी तक दावा नहीं किया गया था।
                    # सरलता के लिए, हम सिर्फ एक पुष्टि भेजेंगे।
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    # *** यह वह जगह है जहां बदलाव किए गए हैं ***
                    self.wfile.write("<html><body><h1>शॉर्टलिंक पूरा हुआ!</h1><p>अब आप टेलीग्राम पर वापस जा सकते हैं।</p></body></html>".encode('utf-8'))
                    
                    # आप यहां पॉइंट क्रेडिट को ट्रिगर करेंगे, POST हैंडलर के समान।
                    # सिंक्रोनस हैंडलर से अतुल्यकालिक भेजना:
                    if application_instance:
                        asyncio.run_coroutine_threadsafe(
                            application_instance.bot.send_message(
                                chat_id=int(user_id),
                                text=get_text(int(user_id), "shortlink_completed",
                                                points=POINTS_PER_SHORTLINK,
                                                solved_count=get_user_data(int(user_id))["shortlinks_solved_count"] + 1, # अस्थायी अपडेट
                                                balance=get_user_data(int(user_id))["balance"] + POINTS_PER_SHORTLINK), # अस्थायी अपडेट
                                reply_markup=get_main_menu_keyboard(int(user_id)),
                                parse_mode='Markdown'
                            ),
                            application_instance.loop
                        )
                else:
                    self.send_response(400) # बुरा अनुरोध
                    self.end_headers()
            else:
                self.send_response(200) # सामान्य वेबहुक पथ परीक्षण के लिए
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                # *** यह वह जगह है जहां बदलाव किए गए हैं ***
                self.wfile.write("<html><body><h1>वेबहुक लिसनर सक्रिय</h1><p>यहां POST अनुरोध भेजें।</p></body></html>".encode('utf-8'))

        except Exception as e:
            logger.error(f"वेबहुक GET अनुरोध को संसाधित करने में त्रुटि: {e}")
            self.send_response(500)
            self.end_headers()


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
                text=get_text(referrer_id, "referrer_joined", user_username=referrer_username, referral_points_per_referral=REFERRAL_POINTS_PER_REFERRAL),
                parse_mode='Markdown'
            )
            logger.info(f"उपयोगकर्ता {user_id} को {referrer_id} द्वारा रेफर किया गया। रेफरर को {REFERRAL_POINTS_PER_REFERRAL} अंक क्रेडिट किए गए।")
            # रेफरल प्रोसेसिंग के बाद स्वागत संदेश भेजें
            user_data = get_user_data(user_id) # उपयोगकर्ता डेटा रीफ्रेश करें
            await update.message.reply_text(
                get_text(user_id, "welcome", first_name=update.effective_user.first_name,
                                 balance=user_data["balance"]),
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode='Markdown'
            )
            return
        else:
            await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=get_main_menu_keyboard(user_id))
            return
    elif referrer_id == user_id:
        await update.message.reply_text(get_text(user_id, "self_referral"), reply_markup=get_main_menu_keyboard(user_id))
        return

    # यदि कोई रेफरल नहीं है या रेफरल पहले ही प्रोसेस हो चुका है तो सामान्य स्वागत संदेश
    await update.message.reply_text(
        get_text(user_id, "welcome", first_name=update.effective_user.first_name,
                         balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode='Markdown'
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
                get_text(user_id, "force_subscribe_text", channel_username=FORCE_SUBSCRIBE_CHANNEL_USERNAME),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return False
    except Exception as e:
        logger.error(f"उपयोगकर्ता {user_id} के लिए अनिवार्य सदस्यता जांचने में त्रुटि: {e}")
        # यदि बॉट एडमिन नहीं है या चैनल ID गलत है, तो मान लें कि जॉइन नहीं किया है या त्रुटि है
        keyboard = [[
            InlineKeyboardButton(get_text(user_id, "join_channel_button"), url=f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_USERNAME}"),
            InlineKeyboardButton(get_text(user_id, "joined_check_button"), callback_data="check_force_subscribe")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await (update.message or update.callback_query.message).reply_text(
            get_text(user_id, "not_joined_error", channel_username=FORCE_SUBSCRIBE_CHANNEL_USERNAME),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return False

async def handle_force_subscribe_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if await check_force_subscribe(update, context, user_id):
        # यदि उपयोगकर्ता शामिल हो गया है, तो भाषा चयन या स्वागत पर आगे बढ़ें
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
                get_text(user_id, "welcome", first_name=query.from_user.first_name,
                                 balance=user_data["balance"]),
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode='Markdown'
            )
    else:
        # यदि अभी भी शामिल नहीं हुआ है, तो check_force_subscribe फ़ंक्शन ने पहले ही त्रुटि संदेश भेज दिया है।
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
        get_text(user_id, "welcome", first_name=query.from_user.first_name,
                                 balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode='Markdown'
    )

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    await query.edit_message_text(
        get_text(user_id, "welcome", first_name=query.from_user.first_name,
                                 balance=user_data["balance"]),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode='Markdown'
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
        parse_mode='Markdown'
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
        parse_mode='Markdown'
    )
    # फिर तुरंत शॉर्टलिंक प्रदान करें
    shortlink, task_id = await fetch_new_shortlink_from_api(user_id)

    if not shortlink:
        await context.bot.send_message(chat_id=user_id, text=get_text(user_id, "shortlink_unavailable"), reply_markup=get_main_menu_keyboard(user_id))
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
        parse_mode='Markdown'
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

        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await query.edit_message_text(get_text(user_id, "no_shortlink_started"), reply_markup=get_main_menu_keyboard(user_id), parse_mode='Markdown')


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
            parse_mode='Markdown'
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
        parse_mode='Markdown'
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
        await query.answer(get_text(user_id, "channel_already_claimed", channel_username=channel_username), show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            update_user_data(user_id, balance_change=POINTS_PER_CHANNEL_JOIN, add_joined_channel=channel_id)
            user_data = get_user_data(user_id) # डेटा रीफ्रेश करें

            await query.answer(get_text(user_id, "channel_claim_success", points=POINTS_PER_CHANNEL_JOIN, channel_username=channel_username, balance=user_data["balance"]), show_alert=True)
            
            # सूची को अपडेट करने के लिए earn_join_channels मेनू को फिर से भेजें
            await earn_join_channels(update, context) # रीफ्रेश करने के लिए हैंडलर को फिर से कॉल करें

        else:
            await query.answer(get_text(user_id, "channel_not_joined", channel_username=channel_username), show_alert=True)
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

    # उपयोगकर्ता का प्रोफ़ाइल फोटो प्राप्त करें
    profile_photos = await context.bot.get_user_profile_photos(user_id)
    profile_photo_file_id = None
    if profile_photos.photos:
        # सबसे बड़ी उपलब्ध फोटो चुनें
        profile_photo_file_id = profile_photos.photos[0][-1].file_id 

    profile_text = get_text(user_id, "profile_text",
                            first_name=query.from_user.first_name,
                            user_id=user_id,
                            balance=user_data["balance"],
                            total_shortlinks_solved=user_data["shortlinks_solved_count"],
                            total_referrals=user_data["referral_count"])

    keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if profile_photo_file_id:
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(media=profile_photo_file_id, caption=profile_text, parse_mode='Markdown'),
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"प्रोफाइल फोटो के साथ संदेश संपादित करने में विफल: {e}. टेक्स्ट के रूप में भेज रहा हूँ।")
            await query.edit_message_text(profile_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await query.edit_message_text(profile_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- आमंत्रण लॉजिक ---
async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    referral_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
    invite_message = get_text(user_id, "invite_text", referral_link=referral_link, referral_points=REFERRAL_POINTS_PER_REFERRAL)

    keyboard = [[InlineKeyboardButton(get_text(user_id, "share_button"), switch_inline_query=invite_message)]]
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(invite_message, reply_markup=reply_markup, parse_mode='Markdown')

# --- निकासी लॉजिक ---

async def start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    if user_data["balance"] < MIN_WITHDRAWAL_POINTS:
        await query.edit_message_text(
            get_text(user_id, "insufficient_points", min_points=MIN_WITHDRAWAL_POINTS),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode='Markdown'
        )
        return

    context.user_data['withdraw_state'] = 'choosing_method'
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "withdraw_method_upi_qr"), callback_data="withdraw_method_upi_qr")],
        [InlineKeyboardButton(get_text(user_id, "withdraw_method_redeem_code"), callback_data="withdraw_method_redeem_code")],
        [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        get_text(user_id, "choose_withdrawal_method"),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def choose_withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    method = query.data.replace("withdraw_method_", "")
    await query.answer()

    context.user_data['withdraw_method'] = method
    context.user_data['withdraw_state'] = 'entering_amount'

    rate = 0
    if method == 'upi_qr':
        rate = UPI_QR_BANK_POINTS_TO_RUPEES_RATE
    elif method == 'redeem_code':
        rate = REDEEM_CODE_POINTS_TO_RUPEES_RATE
    
    current_balance = get_user_data(user_id)["balance"]
    max_rupees = current_balance / rate

    await query.edit_message_text(
        get_text(user_id, "enter_withdrawal_amount",
                 method=get_text(user_id, f"withdraw_method_{method}"),
                 min_points=MIN_WITHDRAWAL_POINTS,
                 current_balance=current_balance,
                 max_rupees=max_rupees,
                 points_per_rupee=rate),
        reply_markup=get_back_to_menu_keyboard(user_id),
        parse_mode='Markdown'
    )

async def handle_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text
    user_data = get_user_data(user_id)
    
    if context.user_data.get('withdraw_state') != 'entering_amount':
        return # उपयोगकर्ता सही स्थिति में नहीं है

    try:
        requested_amount_rupees = float(user_input)
        if requested_amount_rupees <= 0:
            await update.message.reply_text(get_text(user_id, "invalid_amount_positive"), reply_markup=get_back_to_menu_keyboard(user_id))
            return
    except ValueError:
        await update.message.reply_text(get_text(user_id, "invalid_amount_numeric"), reply_markup=get_back_to_menu_keyboard(user_id))
        return

    method = context.user_data['withdraw_method']
    rate = 0
    if method == 'upi_qr':
        rate = UPI_QR_BANK_POINTS_TO_RUPEES_RATE
    elif method == 'redeem_code':
        rate = REDEEM_CODE_POINTS_TO_RUPEES_RATE
    
    points_needed = requested_amount_rupees * rate
    
    if points_needed < MIN_WITHDRAWAL_POINTS:
        await update.message.reply_text(
            get_text(user_id, "withdrawal_below_min", min_points=MIN_WITHDRAWAL_POINTS),
            reply_markup=get_back_to_menu_keyboard(user_id)
        )
        return

    if user_data["balance"] < points_needed:
        await update.message.reply_text(
            get_text(user_id, "insufficient_points_for_withdrawal", requested_points=int(points_needed), current_balance=user_data["balance"]),
            reply_markup=get_back_to_menu_keyboard(user_id),
            parse_mode='Markdown'
        )
        return

    context.user_data['withdraw_amount_rupees'] = requested_amount_rupees
    context.user_data['withdraw_amount_points'] = int(points_needed)
    context.user_data['withdraw_state'] = 'entering_details'

    if method == 'upi_qr':
        prompt_message = get_text(user_id, "enter_upi_id")
    elif method == 'redeem_code':
        prompt_message = get_text(user_id, "enter_redeem_details")
    else:
        prompt_message = get_text(user_id, "generic_error") # अमान्य विधि

    await update.message.reply_text(prompt_message, reply_markup=get_back_to_menu_keyboard(user_id), parse_mode='Markdown')

async def handle_withdrawal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    details = update.message.text
    user_data = get_user_data(user_id)

    if context.user_data.get('withdraw_state') != 'entering_details':
        return # उपयोगकर्ता सही स्थिति में नहीं है

    method = context.user_data.get('withdraw_method')
    amount_points = context.user_data.get('withdraw_amount_points')
    amount_rupees = context.user_data.get('withdraw_amount_rupees')

    if not method or amount_points is None or amount_rupees is None:
        await update.message.reply_text(get_text(user_id, "withdrawal_state_error"), reply_markup=get_main_menu_keyboard(user_id))
        context.user_data.pop('withdraw_state', None) # स्थिति साफ़ करें
        return

    # डेटाबेस में निकासी अनुरोध रिकॉर्ड करें
    request_id = record_withdrawal_request(
        user_id=user_id,
        username=update.effective_user.username,
        amount_points=amount_points,
        amount_rupees=amount_rupees,
        method=method,
        details=details
    )

    # उपयोगकर्ता के बैलेंस से पॉइंट्स घटाएँ
    update_user_data(user_id, balance_change=-amount_points)

    await update.message.reply_text(
        get_text(user_id, "withdrawal_success", amount_points=amount_points, amount_rupees=amount_rupees, method=get_text(user_id, f"withdraw_method_{method}")),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode='Markdown'
    )

    # एडमिन चैनल पर सूचना भेजें
    admin_message = get_text("en", "admin_withdrawal_notification", # एडमिन अधिसूचना के लिए डिफ़ॉल्ट भाषा
                             user_id=user_id,
                             username=update.effective_user.username,
                             amount_points=amount_points,
                             amount_rupees=amount_rupees,
                             method=method,
                             details=details,
                             request_id=str(request_id))

    keyboard = [
        [InlineKeyboardButton("✅ स्वीकृत करें", callback_data=f"approve_withdrawal_{request_id}")],
        [InlineKeyboardButton("❌ अस्वीकृत करें", callback_data=f"reject_withdrawal_{request_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_WITHDRAWAL_CHANNEL_ID,
            text=admin_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"एडमिन चैनल पर निकासी सूचना भेजने में विफल: {e}")

    # उपयोगकर्ता की स्थिति साफ़ करें
    context.user_data.pop('withdraw_state', None)
    context.user_data.pop('withdraw_amount_points', None)
    context.user_data.pop('withdraw_amount_rupees', None)
    context.user_data.pop('withdraw_method', None)

# --- एडमिन हैंडलर ---
async def admin_approve_reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    # सुनिश्चित करें कि केवल एडमिन ही इन बटनों का उपयोग कर सकते हैं
    # यह सिर्फ एक बुनियादी जांच है; एक वास्तविक बॉट में बेहतर एडमिन सत्यापन हो सकता है।
    if str(user_id) not in os.getenv("ADMIN_USER_IDS", "").split(','):
        await query.answer("आपको इस कार्रवाई को करने की अनुमति नहीं है।", show_alert=True)
        return

    parts = data.split('_')
    action = parts[0] # 'approve' या 'reject'
    request_id = parts[2] # ObjectId का स्ट्रिंग

    withdrawal_request = withdrawal_requests_collection.find_one({"_id": ObjectId(request_id)})

    if not withdrawal_request:
        await query.edit_message_text(query.message.text + "\n\n❌ अनुरोध नहीं मिला।", parse_mode='Markdown')
        return

    if withdrawal_request.get('status') != 'pending':
        await query.edit_message_text(query.message.text + f"\n\n⚠️ यह अनुरोध पहले ही *{withdrawal_request['status']}* हो चुका है।", parse_mode='Markdown')
        return

    requester_user_id = withdrawal_request['user_id']
    amount_points = withdrawal_request['amount_points']
    
    new_status = ""
    admin_action_text = ""
    user_notification_key = ""

    if action == "approve":
        new_status = "approved"
        admin_action_text = "✅ स्वीकृत किया गया"
        user_notification_key = "withdrawal_approved_message"
        # बैलेंस से पॉइंट्स काटने की आवश्यकता नहीं है, क्योंकि यह पहले ही 'handle_withdrawal_details' में घटा दिए गए हैं।
    elif action == "reject":
        new_status = "rejected"
        admin_action_text = "❌ अस्वीकृत किया गया"
        user_notification_key = "withdrawal_rejected_message"
        # पॉइंट्स को उपयोगकर्ता के बैलेंस में वापस जोड़ें
        update_user_data(requester_user_id, balance_change=amount_points)
        user_data_after_refund = get_user_data(requester_user_id)
        logger.info(f"उपयोगकर्ता {requester_user_id} को अस्वीकृत निकासी के लिए {amount_points} अंक वापस किए गए।")
    else:
        await query.answer("अमान्य कार्रवाई।", show_alert=True)
        return

    update_withdrawal_request_status(request_id, new_status, user_id) # admin_id को रिकॉर्ड करें

    # एडमिन के लिए संदेश संपादित करें
    await query.edit_message_text(
        query.message.text + f"\n\n`{query.from_user.first_name}` द्वारा *{new_status.upper()}*",
        parse_mode='Markdown'
    )

    # उपयोगकर्ता को सूचित करें
    user_language = get_user_language(requester_user_id)
    notification_message = WITHDRAWAL_STATUS_UPDATE_MESSAGES.get(user_language, {}).get(user_notification_key, "")
    if notification_message:
        try:
            await context.bot.send_message(
                chat_id=requester_user_id,
                text=notification_message.format(
                    amount_points=amount_points,
                    amount_rupees=withdrawal_request['amount_rupees'],
                    method=get_text(user_language, f"withdraw_method_{withdrawal_request['method']}"),
                    details=withdrawal_request['details'],
                    current_balance=user_data_after_refund["balance"] if action == "reject" else get_user_data(requester_user_id)["balance"]
                ),
                parse_mode='Markdown',
                reply_markup=get_main_menu_keyboard(requester_user_id)
            )
        except Exception as e:
            logger.error(f"उपयोगकर्ता {requester_user_id} को निकासी स्थिति संदेश भेजने में विफल: {e}")
    else:
        logger.warning(f"उपयोगकर्ता {requester_user_id} के लिए निकासी स्थिति संदेश कुंजी '{user_notification_key}' नहीं मिली।")

# --- सहायता संदेश ---
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    help_text = get_text(user_id, "help_text")
    await query.edit_message_text(help_text, reply_markup=get_back_to_menu_keyboard(user_id), parse_mode='Markdown')

# --- अप्रत्याशित संदेश हैंडलर ---
async def handle_unrecognized_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # यदि उपयोगकर्ता किसी विशिष्ट स्थिति में नहीं है, तो उसे मुख्य मेनू पर रीडायरेक्ट करें
    if 'withdraw_state' not in context.user_data and 'waiting_for_language' not in context.user_data:
        await update.message.reply_text(get_text(user_id, "unrecognized_command"), reply_markup=get_main_menu_keyboard(user_id), parse_mode='Markdown')
    # यदि वे किसी स्थिति में हैं (जैसे निकासी), तो उन्हें एक उपयुक्त संकेत दें
    elif context.user_data.get('withdraw_state') == 'entering_amount':
        await handle_withdrawal_amount(update, context) # इसे फिर से प्रोसेस करने की कोशिश करें
    elif context.user_data.get('withdraw_state') == 'entering_details':
        await handle_withdrawal_details(update, context) # इसे फिर से प्रोसेस करने की कोशिश करें
    else:
        # किसी भी अन्य अज्ञात स्थिति के लिए, मुख्य मेनू पर वापस जाएँ
        await update.message.reply_text(get_text(user_id, "unrecognized_command"), reply_markup=get_main_menu_keyboard(user_id), parse_mode='Markdown')

# --- HTTP सर्वर को अलग थ्रेड में चलाने के लिए फ़ंक्शन ---
def run_webhook_server(host='0.0.0.0', port=int(os.environ.get("PORT", 8000))):
    server_address = (host, port)
    # वेबहुक हैंडलर के लिए पाथ मैपिंग को समायोजित करें यदि आवश्यक हो
    # वर्तमान में यह 'webhook' पथ पर सभी GET/POST अनुरोधों को मानता है
    httpd = HTTPServer(server_address, ShortlinkWebhookHandler)
    logger.info(f"Webhook सर्वर {host}:{port} पर चल रहा है...")
    httpd.serve_forever()

# --- मुख्य फ़ंक्शन ---
def main():
    global application_instance
    
    # डेटाबेस को इनिशियलाइज़ करें
    init_db()

    # Telegram बॉट एप्लिकेशन बिल्डर
    application = Application.builder().token(BOT_TOKEN).build()
    application_instance = application # ग्लोबल वेरिएबल असाइन करें

    # कमांड हैंडलर
    application.add_handler(CommandHandler("start", start))

    # कॉलबैक क्वेरी हैंडलर
    application.add_handler(CallbackQueryHandler(set_language, pattern=r"^set_lang_"))
    application.add_handler(CallbackQueryHandler(check_force_subscribe, pattern="^check_force_subscribe$"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))
    application.add_handler(CallbackQueryHandler(show_earn_points_menu, pattern="^earn_points_menu$"))
    application.add_handler(CallbackQueryHandler(earn_shortlinks, pattern="^earn_shortlinks$"))
    application.add_handler(CallbackQueryHandler(done_shortlink, pattern="^done_shortlink$"))
    application.add_handler(CallbackQueryHandler(earn_join_channels, pattern="^earn_join_channels$"))
    application.add_handler(CallbackQueryHandler(claim_channel_points, pattern=r"^claim_channel_"))
    application.add_handler(CallbackQueryHandler(show_profile, pattern="^show_profile$"))
    application.add_handler(CallbackQueryHandler(show_invite, pattern="^show_invite$"))
    application.add_handler(CallbackQueryHandler(start_withdraw, pattern="^start_withdraw$"))
    application.add_handler(CallbackQueryHandler(choose_withdraw_method, pattern=r"^withdraw_method_"))
    application.add_handler(CallbackQueryHandler(admin_approve_reject_withdrawal, pattern=r"^(approve|reject)_withdrawal_"))
    application.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))

    # नियमित संदेश हैंडलर (निकासी विवरण के लिए)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unrecognized_message))

    # वेबहुक सर्वर को अलग थ्रेड में चलाएँ
    webhook_thread = threading.Thread(target=run_webhook_server)
    webhook_thread.daemon = True # मुख्य कार्यक्रम समाप्त होने पर थ्रेड को समाप्त करें
    webhook_thread.start()

    # बॉट को पोलिंग मोड में चलाएँ (यदि वेबहुक का उपयोग नहीं कर रहे हैं, लेकिन Koyeb पर आपको वेबहुक का उपयोग करना चाहिए)
    # यदि आप Telegram के वेबहुक को Koyeb पर सेट कर रहे हैं, तो पोलिंग की आवश्यकता नहीं होगी।
    # इसके बजाय, आप Telegram को अपने Koyeb ऐप के Webhook URL पर अपडेट भेजने के लिए कहेंगे।

    # Koyeb के लिए Webhook सेटअप
    # WEBHOOK_URL को config.py में आपकी Koyeb ऐप URL पर सेट किया जाना चाहिए।
    # उदाहरण: https://rotten-barbette-asmwasearchbot-64f1c2e9.koyeb.app/
    # Telegram को अपडेट भेजने के लिए Webhook_url/bot_token पर सेट करना होगा
    # https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WEBHOOK_URL>
    
    # हम यहां सीधे वेबहुक सेट नहीं कर रहे हैं क्योंकि Koyeb को इसे अपने आप करना चाहिए
    # या आप इसे मैन्युअल रूप से एक बार कर सकते हैं।
    
    # यह सुनिश्चित करने के लिए कि आपका bot.py चलता रहे और Koyeb के HTTP सर्वर को बाधित न करे,
    # हम `idle()` का उपयोग करते हैं। Koyeb के Webhook सिस्टम के साथ,
    # आपका बॉट `run_polling()` के बिना भी प्रतिक्रिया देना जारी रखना चाहिए
    # बशर्ते Telegram को आपके Webhook URL पर अपडेट भेजे जा रहे हों।
    
    # हालांकि, Telegram.ext.Application को लगातार चलने की आवश्यकता है।
    # Koyeb पर, यदि आप `run_webhook()` का उपयोग कर रहे हैं (जैसा कि यह कोड में है),
    # तो यह एक इंटरनल सर्वर चलाता है और आपके `HTTPServer` के साथ संघर्ष कर सकता है।
    # सबसे अच्छा Koyeb डिप्लॉयमेंट के लिए, आमतौर पर आप या तो:
    # 1. Koyeb के बिल्ट-इन वेबहुक को Telegram.ext के साथ उपयोग करें (जो एक आंतरिक सर्वर चलाता है)
    # 2. या एक कस्टम HTTP सर्वर चलाएं (जैसे `ShortlinkWebhookHandler`) और फिर Telegram.ext को पोलिंग पर चलाएं।

    # चूंकि हमने एक कस्टम HTTP सर्वर (`ShortlinkWebhookHandler`) बनाया है
    # जो पोर्ट 8000 पर शॉर्टलिंक कॉलबैक के लिए सुनता है,
    # तो हम Telegram बॉट को अपडेट प्राप्त करने के लिए `run_polling()` पर चला सकते हैं।
    # ध्यान दें: यह Koyeb पर दो सर्वरों को एक ही पोर्ट पर चलाने की कोशिश कर सकता है
    # यदि Koyeb स्वतः ही `run_webhook()` चला रहा है।
    # सबसे सरल Koyeb सेटअप के लिए, `run_polling()` या `run_webhook()` में से केवल एक का उपयोग करें,
    # और यदि `ShortlinkWebhookHandler` को शॉर्टलिंक के लिए एक अलग पोर्ट की आवश्यकता है,
    # तो Koyeb डिप्लॉयमेंट कॉन्फ़िगरेशन में इसे अलग से परिभाषित करें।
    
    # सुरक्षित पक्ष पर, बॉट को चलने दें और `ShortlinkWebhookHandler` को एक अलग थ्रेड में चलाएं।
    # Koyeb पर्यावरण में यह अक्सर सर्वोत्तम तरीका होता है जब आपको एक कस्टम HTTP सर्वर की आवश्यकता होती है।

    # मुख्य बॉट एप्लिकेशन को चलाएं
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
