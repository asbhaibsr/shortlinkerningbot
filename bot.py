# bot.py

import random
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from bson.objectid import ObjectId

# अपनी कस्टम फ़ाइलों से इंपोर्ट करें
from config import (
    BOT_TOKEN, ADMIN_WITHDRAWAL_CHANNEL_ID, SHORTLINK_API_URL, SHORTLINK_API_KEY,
    POINTS_PER_SHORTLINK, REFERRAL_POINTS_PER_30, MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW,
    CHANNEL_JOIN_POINTS, POINTS_TO_RUPEES_RATE, MIN_WITHDRAWAL_POINTS, CHANNELS_TO_JOIN
)
from languages import LANGUAGES, WITHDRAWAL_STATUS_UPDATE_MESSAGES, DEFAULT_LANGUAGE, get_text
from database_utils import (
    init_db, get_user_data, update_user_data, record_withdrawal_request,
    set_user_language, withdrawal_requests_collection, get_user_language
)

# --- Global variable for the application instance (to access bot methods) ---
application_instance = None

# --- Helper function to create main menu keyboard ---
def main_menu_keyboard(user_id):
    """मुख्य मेनू के लिए ReplyKeyboardMarkup बनाता है।"""
    keyboard = [
        [
            KeyboardButton(get_text(user_id, "earn_button")),
            KeyboardButton(get_text(user_id, "tasks_button"))
        ],
        [
            KeyboardButton(get_text(user_id, "balance_button")),
            KeyboardButton(get_text(user_id, "invite_button"))
        ],
        [
            KeyboardButton(get_text(user_id, "withdraw_button"))
        ]
    ]
    # resize_keyboard=True: कीबोर्ड को छोटा करता है ताकि वह स्क्रीन पर फिट हो सके।
    # one_time_keyboard=False: कीबोर्ड को हर बार छिपाने के बजाय हमेशा दिखाता है।
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# --- Helper function to fetch a shortlink from API ---
async def fetch_new_shortlink_from_api():
    try:
        random_long_url = f"https://example.com/page/{random.randint(1000, 9999)}?user={random.randint(100,999)}"
        
        # --- यहाँ परिवर्तन किया गया है ---
        # API कुंजी को URL पैरामीटर के रूप में शामिल करें
        api_url_with_key = f"{SHORTLINK_API_URL}?api={SHORTLINK_API_KEY}&url={random_long_url}"
        
        # अब headers की आवश्यकता नहीं है क्योंकि API कुंजी सीधे URL में है
        response = requests.get(api_url_with_key) # GET अनुरोध का उपयोग करें क्योंकि PHP उदाहरण भी GET का उपयोग कर रहा है
        # --- परिवर्तन यहाँ समाप्त होता है ---

        response.raise_for_status() # यह 4XX/5XX प्रतिक्रियाओं के लिए HTTPError को बढ़ाएगा
        data = response.json()
        
        # SmallShorts API के JSON रिस्पॉन्स के आधार पर keys बदलें
        # आपने दिखाया है कि 'shortenedUrl' का उपयोग हो सकता है
        if "shortenedUrl" in data:
            return data["shortenedUrl"]
        elif "result" in data and "full_short_link" in data["result"]:
            # यदि API का रिस्पॉन्स पुराना वाला है तो यह भी काम करेगा
            return data["result"]["full_short_link"]
        else:
            print(f"Unexpected API response: {data}")
            return None
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching shortlink from API: {e.response.status_code} {e.response.reason} for url: {e.request.url}")
        print(f"API Response content: {e.response.text}") # अधिक जानकारी के लिए प्रतिक्रिया सामग्री प्रिंट करें
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching shortlink from API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in fetch_new_shortlink_from_api: {e}")
        return None

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    # यदि उपयोगकर्ता ने अभी तक भाषा का चयन नहीं किया है और रेफरल लिंक से नहीं आ रहा है, तो भाषा के लिए संकेत दें
    # user_data.get('language', DEFAULT_LANGUAGE) यह सुनिश्चित करता है कि यदि 'language' कुंजी मौजूद नहीं है तो DEFAULT_LANGUAGE का उपयोग किया जाए।
    if 'language_set_in_session' not in context.user_data and user_data.get('language', DEFAULT_LANGUAGE) == DEFAULT_LANGUAGE and not context.args:
        keyboard = []
        for lang_code, lang_data in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_data["name"], callback_data=f"set_lang_{lang_code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[DEFAULT_LANGUAGE]["language_choice"], # डिफ़ॉल्ट भाषा (अंग्रेजी) में संकेत
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_language'] = True # भाषा चयन की प्रतीक्षा करने के लिए एक फ़्लैग सेट करें
        return # भाषा चुने जाने तक निष्पादन रोकें

    # रेफरल लॉजिक (भाषा सेट होने के बाद या यदि पहले से सेट है तो चलता है)
    # यह ब्लॉक संभावित रूप से भाषा चयन को हैंडल या पुष्टि करने के बाद चलना चाहिए।
    # हमें user_data को फिर से प्राप्त करना होगा यदि भाषा अभी सेट की गई थी, ताकि सही user_lang मिल सके।
    user_data = get_user_data(user_id) # उपयोगकर्ता डेटा को रीफ़्रेश करें ताकि भाषा लोड हो सके
    user_lang = get_user_language(user_id) # उपयोगकर्ता की निर्धारित भाषा प्राप्त करें

    if context.args:
        try:
            referrer_id = int(context.args[0].replace('ref_', ''))
            if referrer_id != user_id:
                referrer_data = get_user_data(referrer_id)
                # जांचें कि उपयोगकर्ता को पहले रेफर नहीं किया गया है
                if referrer_data and user_data["referred_by"] is None:
                    update_user_data(user_id, set_referred_by=referrer_id) # MongoDB अपडेट का उपयोग करके referred_by सेट करें
                    update_user_data(referrer_id, referral_count_change=1) # MongoDB में रेफरर की संख्या बढ़ाएँ
                    await context.bot.send_message(chat_id=referrer_id, text=get_text(referrer_id, "referrer_joined", user_id=user_id))
                    # रेफरल के बाद सीधे मुख्य मेनू भेजें
                    await update.message.reply_text(get_text(user_id, "welcome", first_name=update.effective_user.first_name,
                                                             balance=user_data["balance"],
                                                             shortlinks_solved_count=user_data["shortlinks_solved_count"]),
                                                   reply_markup=main_menu_keyboard(user_id))
                else:
                    # उपयोगकर्ता पहले से रेफर किया गया है या रेफरर मौजूद नहीं है
                    await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=main_menu_keyboard(user_id))
            else:
                await update.message.reply_text(get_text(user_id, "self_referral"), reply_markup=main_menu_keyboard(user_id))
        except ValueError:
            await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=main_menu_keyboard(user_id))
        except Exception as e:
            print(f"Error in referral logic: {e}")
            await update.message.reply_text(get_text(user_id, "generic_error"), reply_markup=main_menu_keyboard(user_id))
        return # महत्वपूर्ण: डबल वेलकम मैसेज से बचने के लिए रेफरल लॉजिक के बाद बाहर निकलें

    # यदि भाषा पहले से सेट है या भाषा चयन/रेफरल हैंडलिंग के बाद, मुख्य वेलकम मैसेज भेजें
    # यह सुनिश्चित करता है कि जब तक भाषा चयन लंबित न हो, वेलकम मैसेज और कीबोर्ड हमेशा भेजे जाते हैं
    user_data = get_user_data(user_id) # संभावित अपडेट के बाद उपयोगकर्ता डेटा को फिर से प्राप्त करें
    await update.message.reply_text(
        get_text(user_id, "welcome", first_name=update.effective_user.first_name,
                 balance=user_data["balance"],
                 shortlinks_solved_count=user_data["shortlinks_solved_count"]),
        reply_markup=main_menu_keyboard(user_id) # हमेशा वेलकम के बाद मुख्य मेनू कीबोर्ड दिखाएं
    )

# --- Language Selection Callback Handler ---
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.replace("set_lang_", "")

    if lang_code not in LANGUAGES:
        await query.answer("Invalid language selection.", show_alert=True)
        return

    set_user_language(user_id, lang_code) # MongoDB में भाषा अपडेट करें
    context.user_data['language_set_in_session'] = True # वर्तमान सत्र के लिए भाषा को सेट के रूप में चिह्नित करें
    if 'waiting_for_language' in context.user_data:
        del context.user_data['waiting_for_language']

    await query.answer(f"भाषा {LANGUAGES[lang_code]['name']} पर सेट की गई।", show_alert=True)

    user_data = get_user_data(user_id) # अपडेटेड उपयोगकर्ता डेटा प्राप्त करें
    await query.edit_message_text(
        get_text(user_id, "welcome", first_name=query.from_user.first_name,
                 balance=user_data["balance"],
                 shortlinks_solved_count=user_data["shortlinks_solved_count"]),
        reply_markup=main_menu_keyboard(user_id) # भाषा चयन के बाद मुख्य मेनू कीबोर्ड दिखाएं
    )

# --- Shortlink Earning Logic ---
async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह निर्धारित करें कि अपडेट एक मैसेज से है या एक कॉलबैक क्वेरी से।
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # कॉलबैक क्वेरी का जवाब दें
        send_func = update.callback_query.message.reply_text # कॉलबैक पर नया मैसेज भेजें
    else:
        return # ऐसा नहीं होना चाहिए

    user_data = get_user_data(user_id)

    current_shortlink = await fetch_new_shortlink_from_api()

    if not current_shortlink:
        await send_func(get_text(user_id, "shortlink_unavailable"), reply_markup=main_menu_keyboard(user_id))
        return

    update_user_data(user_id, new_last_shortlink=current_shortlink)

    keyboard = [[InlineKeyboardButton(get_text(user_id, "shortlink_button"), callback_data="done_shortlink")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_func(
        get_text(user_id, "shortlink_given", shortlink=current_shortlink),
        reply_markup=reply_markup
    )

async def done_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    await query.answer()

    if not user_data["last_given_shortlink"]:
        await context.bot.send_message(chat_id=user_id, text=get_text(user_id, "no_shortlink_started"), reply_markup=main_menu_keyboard(user_id))
        return

    update_user_data(user_id, shortlinks_solved_change=1, balance_change=POINTS_PER_SHORTLINK, new_last_shortlink=None)
    user_data = get_user_data(user_id) # अपडेटेड उपयोगकर्ता डेटा प्राप्त करें

    solved_count = user_data["shortlinks_solved_count"]
    current_balance = user_data["balance"]

    message_text = get_text(user_id, "shortlink_completed",
                            points=POINTS_PER_SHORTLINK,
                            solved_count=solved_count,
                            balance=current_balance)

    keyboard = [[InlineKeyboardButton(get_text(user_id, "next_shortlink_button"), callback_data="generate_next_shortlink")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message_text, reply_markup=reply_markup)

async def generate_next_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह फ़ंक्शन एक कॉलबैक क्वेरी द्वारा कॉल किया जाता है, इसलिए update.callback_query मौजूद होगा
    await earn(update.callback_query, context)


# --- Channel Joining Tasks ---
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह निर्धारित करें कि अपडेट एक मैसेज से है या एक कॉलबैक क्वेरी से।
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # कॉलबैक क्वेरी का जवाब दें
        send_func = update.callback_query.message.edit_text # मौजूदा मैसेज पर कॉलबैक के लिए edit_text का उपयोग करें
    else:
        return # ऐसा नहीं होना चाहिए

    user_data = get_user_data(user_id)

    if not CHANNELS_TO_JOIN:
        await send_func(get_text(user_id, "no_tasks_available"), reply_markup=main_menu_keyboard(user_id))
        return

    keyboard = []
    has_unclaimed_channels = False
    for i, channel in enumerate(CHANNELS_TO_JOIN):
        # channel_ids में लगातार स्टोरेज के लिए चैनल इंडेक्स को स्ट्रिंग में बदलें
        if str(i) not in user_data["claimed_channel_ids"]:
            keyboard.append([InlineKeyboardButton(f"🔗 {channel['name']}", url=channel['link'])]) # सीधा लिंक बटन
            keyboard.append([InlineKeyboardButton(get_text(user_id, "claim_points_button").format(channel_name=channel['name']), callback_data=f"claim_channel_{i}")]) # दावा बटन
            has_unclaimed_channels = True
        else:
            keyboard.append([InlineKeyboardButton(f"✅ Joined: {channel['name']}", url=channel['link'])]) # पहले से जुड़े होने का संकेत दें

    if not has_unclaimed_channels: # यदि सभी चैनल पहले ही दावा किए जा चुके हैं
        await send_func(get_text(user_id, "no_tasks_available"), reply_markup=main_menu_keyboard(user_id))
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_func(
        get_text(user_id, "join_channels_prompt"),
        reply_markup=reply_markup
    )

async def claim_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    channel_index = int(query.data.split('_')[2])

    user_data = get_user_data(user_id)
    if str(channel_index) in user_data["claimed_channel_ids"]:
        await query.answer(get_text(user_id, "claimed_already"), show_alert=True)
        return

    if channel_index < 0 or channel_index >= len(CHANNELS_TO_JOIN):
        await query.answer(get_text(user_id, "invalid_channel"), show_alert=True)
        return

    # TODO: यहाँ यूज़र के चैनल में होने की पुष्टि करें (Telegram API के getChatMember() मेथड का उपयोग करके)
    # यह उचित चैनल जॉइनिंग सत्यापन के लिए महत्वपूर्ण है।
    # वर्तमान कोड मानता है कि यदि वे "दावा करें" पर क्लिक करते हैं तो वे जुड़ गए हैं।
    # उदाहरण:
    # try:
    #    chat_member = await context.bot.get_chat_member(chat_id=CHANNELS_TO_JOIN[channel_index]['id'], user_id=user_id)
    #    if chat_member.status not in ["member", "administrator", "creator"]:
    #        await query.answer(get_text(user_id, "not_yet_joined_channel"), show_alert=True) # यह टेक्स्ट languages.py में जोड़ें
    #        return
    # except Exception as e:
    #    print(f"Error checking channel membership for user {user_id} in channel {CHANNELS_TO_JOIN[channel_index]['name']}: {e}")
    #    await query.answer(get_text(user_id, "generic_error"), show_alert=True)
    #    return


    points_to_add = CHANNEL_JOIN_POINTS
    update_user_data(user_id, balance_change=points_to_add, channel_joined_change=1, add_claimed_channel_id=str(channel_index)) # स्ट्रिंग के रूप में स्टोर करें
    user_data = get_user_data(user_id) # परिवर्तनों के बाद अपडेटेड डेटा प्राप्त करें

    await query.answer(
        get_text(user_id, "channel_claimed_success", channel_name=CHANNELS_TO_JOIN[channel_index]['name'],
                 points_added=points_to_add, balance=user_data['balance']),
        show_alert=True
    )

    # दावा करने के बाद, परिवर्तन को दर्शाने के लिए कार्य मैसेज को रीफ़्रेश करें
    # कार्यों को फिर से कॉल करने से अपडेटेड बटन दिखाई देंगे (या यदि सभी दावा किए गए हैं तो no_tasks_available)
    await tasks(update, context) # सही send_func का उपयोग सुनिश्चित करने के लिए मूल अपडेट ऑब्जेक्ट पास करें


# --- Referral System ---
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह हैंडलर एक कमांड या कीबोर्ड बटन द्वारा कॉल किया जा सकता है।
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # कॉलबैक क्वेरी का जवाब दें
        send_func = update.callback_query.message.reply_text
    else:
        return # ऐसा नहीं होना चाहिए

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    user_data = get_user_data(user_id)
    await send_func(
        get_text(user_id, "referral_link_text", referral_link=referral_link,
                 referral_count=user_data['referral_count'],
                 referral_points=REFERRAL_POINTS_PER_30),
        reply_markup=main_menu_keyboard(user_id) # मुख्य मेनू कीबोर्ड दिखाएं
    )

# --- Check Balance Command ---
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह हैंडलर एक कमांड या कीबोर्ड बटन द्वारा कॉल किया जा सकता है।
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # कॉलबैक क्वेरी का जवाब दें
        send_func = update.callback_query.message.reply_text
    else:
        return # ऐसा नहीं होना चाहिए

    user_data = get_user_data(user_id)
    await send_func(
        get_text(user_id, "balance_text", balance=user_data['balance'],
                 shortlinks_solved_count=user_data['shortlinks_solved_count'],
                 referral_count=user_data['referral_count'],
                 channel_joined_count=user_data['channel_joined_count']),
        reply_markup=main_menu_keyboard(user_id) # मुख्य मेनू कीबोर्ड दिखाएं
    )

# --- Withdrawal System ---
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # यह हैंडलर एक कमांड या कीबोर्ड बटन द्वारा कॉल किया जा सकता है।
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # कॉलबैक क्वेरी का जवाब दें
        send_func = update.callback_query.message.reply_text
    else:
        return # ऐसा नहीं होना चाहिए

    user_data = get_user_data(user_id)

    # पहली जांच: न्यूनतम बैलेंस
    if user_data["balance"] < MIN_WITHDRAWAL_POINTS:
        await send_func(get_text(user_id, "min_withdraw_balance",
                                 balance=user_data['balance'],
                                 min_points=MIN_WITHDRAWAL_POINTS,
                                 min_rupees=MIN_WITHDRAWAL_POINTS * POINTS_TO_RUPEES_RATE),
                        reply_markup=main_menu_keyboard(user_id))
        return

    # दूसरी जांच: निकासी पात्रता के लिए हल किए गए न्यूनतम शॉर्टलिंक
    if user_data["shortlinks_solved_count"] < MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW:
        await send_func(get_text(user_id, "min_shortlinks_for_withdraw",
                                 min_shortlinks=MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW,
                                 solved_count=user_data['shortlinks_solved_count']),
                        reply_markup=main_menu_keyboard(user_id))
        return

    context.user_data['withdraw_state'] = "waiting_amount"
    await send_func(
        get_text(user_id, "withdraw_prompt_amount",
                 balance=user_data['balance'],
                 min_points=MIN_WITHDRAWAL_POINTS,
                 rate=POINTS_TO_RUPEES_RATE)
        # नोट: यहाँ कोई मुख्य मेनू कीबोर्ड नहीं है क्योंकि हम टेक्स्ट इनपुट की उम्मीद करते हैं
    )

async def handle_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.user_data.get('withdraw_state') != "waiting_amount":
        # यदि सही स्थिति में नहीं है, तो साफ़ करें और मुख्य मेनू भेजें
        await update.message.reply_text(get_text(user_id, "command_usage"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data:
            del context.user_data['withdraw_state']
        return

    try:
        amount_points = float(update.message.text)
        user_data = get_user_data(user_id)

        # न्यूनतम निकासी राशि के लिए जांचें
        if amount_points < MIN_WITHDRAWAL_POINTS:
            await update.message.reply_text(get_text(user_id, "min_withdraw_balance",
                                                     balance=user_data['balance'],
                                                     min_points=MIN_WITHDRAWAL_POINTS,
                                                     min_rupees=MIN_WITHDRAWAL_POINTS * POINTS_TO_RUPEES_RATE),
                                            reply_markup=main_menu_keyboard(user_id))
            if 'withdraw_state' in context.user_data: # अमान्य इनपुट होने पर स्थिति साफ़ करें
                del context.user_data['withdraw_state']
            return

        # पर्याप्त बिंदुओं के लिए जांचें
        if amount_points > user_data["balance"]:
            await update.message.reply_text(get_text(user_id, "not_enough_points", balance=user_data['balance']),
                                            reply_markup=main_menu_keyboard(user_id))
            if 'withdraw_state' in context.user_data: # अमान्य इनपुट होने पर स्थिति साफ़ करें
                del context.user_data['withdraw_state']
            return

        amount_rupees = amount_points * POINTS_TO_RUPEES_RATE

        context.user_data['withdraw_amount_points'] = amount_points
        context.user_data['withdraw_amount_rupees'] = amount_rupees
        context.user_data['withdraw_state'] = "waiting_method"

        keyboard = [
            [InlineKeyboardButton(get_text(user_id, "upi_method_button"), callback_data="withdraw_method_upi")],
            [InlineKeyboardButton(get_text(user_id, "bank_method_button"), callback_data="withdraw_method_bank")],
            [InlineKeyboardButton(get_text(user_id, "redeem_method_button"), callback_data="withdraw_method_redeem")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            get_text(user_id, "withdraw_confirm_method",
                     points=amount_points,
                     rupees=amount_rupees), reply_markup=reply_markup
        )

    except ValueError:
        await update.message.reply_text(get_text(user_id, "invalid_amount"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data: # अमान्य इनपुट होने पर स्थिति साफ़ करें
            del context.user_data['withdraw_state']
    except Exception as e:
        print(f"Error in handle_withdrawal_amount: {e}")
        await update.message.reply_text(get_text(user_id, "generic_error"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data:
            del context.user_data['withdraw_state']

async def handle_withdrawal_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if context.user_data.get('withdraw_state') != "waiting_method":
        await query.answer(get_text(user_id, "action_not_valid"), show_alert=True)
        # यदि वे अनुक्रम से बाहर कुछ क्लिक करते हैं तो मुख्य मेनू कीबोर्ड भी भेजें
        await query.message.reply_text(get_text(user_id, "command_usage"), reply_markup=main_menu_keyboard(user_id))
        return

    method = query.data.replace("withdraw_method_", "")
    context.user_data['withdraw_method'] = method
    context.user_data['withdraw_state'] = "waiting_details"

    await query.answer()

    if method == "upi":
        await query.edit_message_text(get_text(user_id, "upi_prompt"))
    elif method == "bank":
        await query.edit_message_text(get_text(user_id, "bank_prompt"))
    elif method == "redeem":
        await query.edit_message_text(get_text(user_id, "redeem_prompt"))
    else:
        await query.edit_message_text(get_text(user_id, "invalid_method"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data: # अमान्य विधि होने पर स्थिति साफ़ करें
            del context.user_data['withdraw_state']

async def handle_withdrawal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if context.user_data.get('withdraw_state') != "waiting_details":
        # यदि सही स्थिति में नहीं है, तो साफ़ करें और मुख्य मेनू भेजें
        await update.message.reply_text(get_text(user_id, "command_usage"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data:
            del context.user_data['withdraw_state']
        return

    details = update.message.text
    amount_points = context.user_data.get('withdraw_amount_points')
    amount_rupees = context.user_data.get('withdraw_amount_rupees')
    method = context.user_data.get('withdraw_method')

    if not amount_points or not method:
        await update.message.reply_text(get_text(user_id, "withdrawal_error"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data:
            del context.user_data['withdraw_state']
        return

    # निकासी अनुरोध रिकॉर्ड करें और ObjectId प्राप्त करें
    withdrawal_doc_id = record_withdrawal_request(user_id, amount_points, amount_rupees, method, details)

    update_user_data(user_id, balance_change=-amount_points) # इंस्टेंस 1 से अंक काटें
    user_data = get_user_data(user_id) # अपडेटेड बैलेंस प्राप्त करें

    await update.message.reply_text(
        get_text(user_id, "withdrawal_success",
                 points=amount_points,
                 rupees=amount_rupees,
                 method=method.upper(),
                 details=details,
                 balance=user_data['balance']),
        reply_markup=main_menu_keyboard(user_id) # सफल निकासी के बाद मुख्य मेनू कीबोर्ड दिखाएं
    )

    # --- एडमिन चैनल को बटनों के साथ सूचना भेजें ---
    try:
        user_info = await context.bot.get_chat(user_id)
        user_name = user_info.first_name
        user_username = user_info.username

        notification_text = (
            "💰 **नई विथड्रॉल रिक्वेस्ट!** 💰\n\n"
            f"**यूज़र ID:** `{user_id}`\n"
            f"**नाम:** {user_name}" + (f" (@{user_username})" if user_username else "") + "\n"
            f"**रिक्वेस्टेड पॉइंट्स:** `{amount_points:.2f}`\n"
            f"**अनुमानित रुपये:** `{amount_rupees:.2f} Rs.`\n"
            f"**तरीका:** `{method.upper()}`\n"
            f"**विवरण:** `{details}`\n"
            f"**समय:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            "स्थिति: `लंबित`\n"
            f"[यूज़र से बात करें](tg://user?id={user_id})"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ मंज़ूर करें", callback_data=f"approve_withdraw_{withdrawal_doc_id}"),
                InlineKeyboardButton("❌ ख़ारिज करें", callback_data=f"reject_withdraw_{withdrawal_doc_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # एडमिन चैनल को मैसेज भेजें और बाद में अपडेट करने के लिए message_id स्टोर करें
        sent_message = await context.bot.send_message(
            chat_id=ADMIN_WITHDRAWAL_CHANNEL_ID,
            text=notification_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        # MongoDB में निकासी अनुरोध को एडमिन मैसेज विवरण के साथ अपडेट करें
        # सुनिश्चित करें कि `withdrawal_requests_collection` database_utils से आयातित है
        withdrawal_requests_collection.update_one(
            {"_id": withdrawal_doc_id},
            {"$set": {
                "admin_channel_message_id": sent_message.message_id,
                "admin_channel_chat_id": ADMIN_WITHDRAWAL_CHANNEL_ID
            }}
        )
        print(f"Withdrawal notification sent to admin channel for user {user_id} with message_id: {sent_message.message_id}")

    except Exception as e:
        print(f"Error sending withdrawal notification to admin channel: {e}")

    # स्थिति साफ़ करें
    context.user_data.pop('withdraw_state', None)
    context.user_data.pop('withdraw_amount_points', None)
    context.user_data.pop('withdraw_amount_rupees', None)
    context.user_data.pop('withdraw_method', None)

# --- Callback Handlers for Admin Actions ---
async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("विथड्रॉल मंज़ूर किया जा रहा है...")

    withdrawal_doc_id_str = query.data.replace("approve_withdraw_", "")

    try:
        withdrawal_doc_id = ObjectId(withdrawal_doc_id_str)
    except Exception as e:
        print(f"Invalid ObjectId in approve_withdrawal: {withdrawal_doc_id_str} - {e}")
        await query.edit_message_text("त्रुटि: अमान्य विथड्रॉल ID।")
        return

    # MongoDB से निकासी अनुरोध प्राप्त करें
    withdrawal_request = withdrawal_requests_collection.find_one({"_id": withdrawal_doc_id})

    if not withdrawal_request:
        await query.edit_message_text("त्रुटि: विथड्रॉल रिक्वेस्ट नहीं मिली।")
        return

    # मैसेज के लिए उपयोगकर्ता की भाषा प्राप्त करने के लिए
    user_lang_code = get_user_language(withdrawal_request["user_id"])

    if withdrawal_request.get("status") != "pending":
        # languages.py से WITHDRAWAL_STATUS_UPDATE_MESSAGES का उपयोग करना
        await query.edit_message_text(WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["already_processed"])
        return

    # MongoDB में निकासी स्थिति अपडेट करें
    withdrawal_requests_collection.update_one(
        {"_id": withdrawal_doc_id},
        {"$set": {"status": "approved", "processed_by_admin_id": query.from_user.id, "processed_timestamp": datetime.now()}}
    )

    # एडमिन चैनल मैसेज अपडेट करें
    original_text = query.message.text
    new_text = original_text.replace("स्थिति: `लंबित`", "स्थिति: `मंज़ूर` ✅")
    new_text += f"\n\nमंज़ूर किया: @{query.from_user.username or query.from_user.first_name}"

    await query.edit_message_text(new_text, parse_mode='Markdown', reply_markup=None) # बटन हटाएँ

    # उपयोगकर्ता को सूचित करें
    user_id_to_notify = withdrawal_request["user_id"]
    amount_points = withdrawal_request["amount_points"]
    amount_rupees = withdrawal_request["amount_rupees"]

    try:
        # languages.py से WITHDRAWAL_STATUS_UPDATE_MESSAGES का उपयोग करना
        await context.bot.send_message(
            chat_id=user_id_to_notify,
            text=WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["approved"].format(points=amount_points, rupees=amount_rupees),
            parse_mode='Markdown'
        )
        print(f"Approval notification sent to user {user_id_to_notify}")
    except Exception as e:
        print(f"Error sending approval notification to user {user_id_to_notify}: {e}")

async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("विथड्रॉल ख़ारिज किया जा रहा है...")

    withdrawal_doc_id_str = query.data.replace("reject_withdraw_", "")

    try:
        withdrawal_doc_id = ObjectId(withdrawal_doc_id_str)
    except Exception as e:
        print(f"Invalid ObjectId in reject_withdrawal: {withdrawal_doc_id_str} - {e}")
        await query.edit_message_text("त्रुटि: अमान्य विथड्रॉल ID।")
        return

    # MongoDB से निकासी अनुरोध प्राप्त करें
    withdrawal_request = withdrawal_requests_collection.find_one({"_id": withdrawal_doc_id})

    if not withdrawal_request:
        await query.edit_message_text("त्रुटि: विथड्रॉल रिक्वेस्ट नहीं मिली।")
        return

    # मैसेज के लिए उपयोगकर्ता की भाषा प्राप्त करने के लिए
    user_lang_code = get_user_language(withdrawal_request["user_id"])

    if withdrawal_request.get("status") != "pending":
        # languages.py से WITHDRAWAL_STATUS_UPDATE_MESSAGES का उपयोग करना
        await query.edit_message_text(WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["already_processed"])
        return

    # MongoDB में निकासी स्थिति अपडेट करें
    withdrawal_requests_collection.update_one(
        {"_id": withdrawal_doc_id},
        {"$set": {"status": "rejected", "processed_by_admin_id": query.from_user.id, "processed_timestamp": datetime.now()}}
    )

    # एडमिन चैनल मैसेज अपडेट करें
    original_text = query.message.text
    new_text = original_text.replace("स्थिति: `लंबित`", "स्थिति: `ख़ारिज` ❌")
    new_text += f"\n\nख़ारिज किया: @{query.from_user.username or query.from_user.first_name}"

    await query.edit_message_text(new_text, parse_mode='Markdown', reply_markup=None) # बटन हटाएँ

    # उपयोगकर्ता को सूचित करें
    user_id_to_notify = withdrawal_request["user_id"]
    amount_points = withdrawal_request["amount_points"]
    amount_rupees = withdrawal_request["amount_rupees"] # यह पहले 'rupees' था, जिसे मैंने 'amount_rupees' में ठीक किया है

    try:
        # languages.py से WITHDRAWAL_STATUS_UPDATE_MESSAGES का उपयोग करना
        await context.bot.send_message(
            chat_id=user_id_to_notify,
            text=WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["rejected"].format(points=amount_points, rupees=amount_rupees),
            parse_mode='Markdown'
        )
        print(f"Rejection notification sent to user {user_id_to_notify}")
    except Exception as e:
        print(f"Error sending rejection notification to user {user_id_to_notify}: {e}")

# --- Generic Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error occurred: {context.error}")
    # डीबगिंग के लिए पूरा ट्रेसबैक लॉग करें
    import traceback
    print(traceback.format_exc())

    if update.effective_message:
        user_id = update.effective_user.id if update.effective_user else None
        # उपयोगकर्ता की भाषा में एक मैसेज भेजने का प्रयास करें, अन्यथा डिफ़ॉल्ट
        try:
            await update.effective_message.reply_text(get_text(user_id, "generic_error"), reply_markup=main_menu_keyboard(user_id))
        except Exception as e:
            print(f"Failed to send generic error message to user {user_id}: {e}")
            # यदि reply_text किसी कारण से विफल हो जाता है तो फ़ॉलबैक करें
            await context.bot.send_message(chat_id=user_id, text="An unexpected error occurred. Please try /start.")

---
### Main function where handlers are added
---

async def post_init(application: Application):
    """
    एप्लिकेशन इनिशियलाइज़ होने के बाद और पोलिंग शुरू होने से पहले कॉल किया जाता है।
    वैश्विक रूप से एप्लिकेशन इंस्टेंस को स्टोर करने के लिए उपयोग किया जाता है।
    """
    global application_instance
    application_instance = application
    print("Application instance set globally.")

def main():
    print("Initializing bot...")
    init_db() # MongoDB कनेक्शन इनिशियलाइज़ करें

    # एप्लिकेशन बनाएँ और अपने बॉट का टोकन पास करें।
    # सेट post_init स्टोर करने के लिए application instance.
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # हैंडलर रजिस्टर करने के लिए डिस्पैचर प्राप्त करें
    # यदि मैसेज भेजने के लिए आवश्यक हो तो वैश्विक application_instance का उपयोग करें या इसे पास करें

    # --- कमांड हैंडलर ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("earn", earn))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("balance", check_balance))
    application.add_handler(CommandHandler("invite", invite))
    application.add_handler(CommandHandler("withdraw", withdraw))


    # --- कॉलबैक क्वेरी हैंडलर (इनलाइन कीबोर्ड बटनों के लिए) ---
    application.add_handler(CallbackQueryHandler(set_language, pattern=r"^set_lang_"))
    application.add_handler(CallbackQueryHandler(done_shortlink, pattern=r"^done_shortlink$"))
    application.add_handler(CallbackQueryHandler(generate_next_shortlink, pattern=r"^generate_next_shortlink$"))
    application.add_handler(CallbackQueryHandler(claim_channel, pattern=r"^claim_channel_"))
    application.add_handler(CallbackQueryHandler(handle_withdrawal_method, pattern=r"^withdraw_method_"))
    application.add_handler(CallbackQueryHandler(approve_withdrawal, pattern=r"^approve_withdraw_"))
    application.add_handler(CallbackQueryHandler(reject_withdrawal, pattern=r"^reject_withdraw_"))

    # --- मैसेज हैंडलर (रिप्लाई कीबोर्ड बटनों और टेक्स्ट इनपुट के लिए) ---
    # इन हैंडलर को कमांड हैंडलर और कॉलबैक क्वेरी हैंडलर के बाद रखा जाना चाहिए
    # ताकि यह सुनिश्चित हो सके कि कमांड और इनलाइन बटन पहले संसाधित होते हैं।

    # रेगुलर कीबोर्ड बटन केवल टेक्स्ट मैसेज होते हैं, इसलिए उन्हें MessageHandler(filters.TEXT) द्वारा हैंडल किया जाता है
    # हम आपके मुख्य मेनू बटनों के विशिष्ट टेक्स्ट से मेल खाने के लिए filters.Regex का उपयोग करते हैं।
    # '|' (OR) ऑपरेटर एक हैंडलर को कई बटनों को कवर करने की अनुमति देता है।
    application.add_handler(MessageHandler(filters.Regex(get_text(None, 'earn_button')) | filters.Regex(get_text(None, 'tasks_button')), earn))
    application.add_handler(MessageHandler(filters.Regex(get_text(None, 'balance_button')) | filters.Regex(get_text(None, 'invite_button')), check_balance))
    application.add_handler(MessageHandler(filters.Regex(get_text(None, 'withdraw_button')), withdraw))

    # निकासी प्रक्रिया के दौरान टेक्स्ट इनपुट के लिए हैंडलर
    # यह सुनिश्चित करता है कि यह केवल उन टेक्स्ट मैसेज को कैप्चर करता है जो कमांड नहीं हैं
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdrawal_amount))


    # --- एरर हैंडलर ---
    application.add_error_handler(error_handler)

    print("Starting bot polling...")
    # उपयोगकर्ता द्वारा Ctrl-C दबाने तक बॉट चलाएँ
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
