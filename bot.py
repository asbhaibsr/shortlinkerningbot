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
    set_user_language, withdrawal_requests_collection, get_user_language # get_user_language यहाँ इंपोर्ट करना आवश्यक है
)

# --- Global variable for the application instance (to access bot methods) ---
application_instance = None

# --- Helper function to create main menu keyboard ---
def main_menu_keyboard(user_id):
    """मुख्य मेनू के लिए ReplyKeyboardMarkup बनाता है।"""
    keyboard = [
        [
            KeyboardButton(get_text(user_id, "earn_button")), # Assuming you'll add "earn_button" key to languages.py
            KeyboardButton(get_text(user_id, "tasks_button")) # Assuming you'll add "tasks_button" key to languages.py
        ],
        [
            KeyboardButton(get_text(user_id, "balance_button")), # Assuming you'll add "balance_button" key to languages.py
            KeyboardButton(get_text(user_id, "invite_button")) # Assuming you'll add "invite_button" key to languages.py
        ],
        [
            KeyboardButton(get_text(user_id, "withdraw_button")) # Assuming you'll add "withdraw_button" key to languages.py
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# --- Helper function to fetch a shortlink from API ---
async def fetch_new_shortlink_from_api():
    try:
        random_long_url = f"https://example.com/page/{random.randint(1000, 9999)}?user={random.randint(100,999)}"
        payload = {"url": random_long_url}
        headers = {"Authorization": f"Bearer {SHORTLINK_API_KEY}"} if SHORTLINK_API_KEY else {}
        response = requests.post(SHORTLINK_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "result" in data and "full_short_link" in data["result"]:
            return data["result"]["full_short_link"]
        elif "shortlink" in data: # Some APIs use 'shortlink'
            return data["shortlink"]
        else:
            print(f"Unexpected API response: {data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching shortlink from API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id) # Gets user data from MongoDB

    # If user hasn't selected a language yet and not coming from a referral link, prompt for language
    # 'language_set_in_session' flag is for the current session. 'user_data['language'] == DEFAULT_LANGUAGE' checks DB.
    # We also check if context.args is empty, meaning it's not a /start ref_ID
    if 'language_set_in_session' not in context.user_data and user_data['language'] == DEFAULT_LANGUAGE and not context.args:
        keyboard = []
        for lang_code, lang_data in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_data["name"], callback_data=f"set_lang_{lang_code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[DEFAULT_LANGUAGE]["language_choice"], # Prompt in default language (English)
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_language'] = True # Set a flag to wait for language selection
        return # Stop execution until language is chosen

    # Referral logic (runs after language is set or if already set)
    if context.args:
        try:
            referrer_id = int(context.args[0].replace('ref_', ''))
            if referrer_id != user_id:
                referrer_data = get_user_data(referrer_id) # Get referrer data from MongoDB
                if referrer_data and user_data["referred_by"] is None:
                    update_user_data(user_id, set_referred_by=referrer_id) # Set referred_by using MongoDB update
                    update_user_data(referrer_id, referral_count_change=1) # Increment referrer's count in MongoDB
                    await context.bot.send_message(chat_id=referrer_id, text=get_text(referrer_id, "referrer_joined", user_id=user_id))
                else:
                    await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=main_menu_keyboard(user_id))
            else:
                await update.message.reply_text(get_text(user_id, "self_referral"), reply_markup=main_menu_keyboard(user_id))
        except ValueError:
            await update.message.reply_text(get_text(user_id, "invalid_referrer"), reply_markup=main_menu_keyboard(user_id))
        except Exception as e:
            print(f"Error in referral logic: {e}")
            await update.message.reply_text(get_text(user_id, "generic_error"), reply_markup=main_menu_keyboard(user_id))

    # If language is already set or after language selection/referral handling, send the main welcome message
    user_data = get_user_data(user_id) # Refresh user data after potential updates
    await update.message.reply_text(
        get_text(user_id, "welcome", first_name=update.effective_user.first_name,
                 balance=user_data["balance"],
                 shortlinks_solved_count=user_data["shortlinks_solved_count"]),
        reply_markup=main_menu_keyboard(user_id) # Always show main menu keyboard after welcome
    )

# --- Language Selection Callback Handler ---
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.replace("set_lang_", "")

    if lang_code not in LANGUAGES:
        await query.answer("Invalid language selection.", show_alert=True)
        return

    set_user_language(user_id, lang_code) # Update language in MongoDB
    context.user_data['language_set_in_session'] = True # Mark language as set for current session
    if 'waiting_for_language' in context.user_data:
        del context.user_data['waiting_for_language']

    await query.answer(f"भाषा {LANGUAGES[lang_code]['name']} पर सेट की गई।", show_alert=True)

    user_data = get_user_data(user_id) # Get updated user data
    await query.edit_message_text(
        get_text(user_id, "welcome", first_name=query.from_user.first_name,
                 balance=user_data["balance"],
                 shortlinks_solved_count=user_data["shortlinks_solved_count"]),
        reply_markup=main_menu_keyboard(user_id) # Show main menu keyboard after language selection
    )

# --- Shortlink Earning Logic ---
async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler can be called by a command or a keyboard button.
    # We need to determine if it's a message or a callback query.
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # Answer the callback query
        send_func = update.callback_query.message.reply_text
    else:
        return # Should not happen

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
    user_data = get_user_data(user_id) # Get updated user data

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
    # This function is called by a callback query, so update.callback_query will exist
    await earn(update.callback_query, context)


# --- Channel Joining Tasks ---
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler can be called by a command or a keyboard button.
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # Answer the callback query
        send_func = update.callback_query.message.reply_text
    else:
        return # Should not happen

    user_data = get_user_data(user_id)

    if not CHANNELS_TO_JOIN:
        await send_func(get_text(user_id, "no_tasks_available"), reply_markup=main_menu_keyboard(user_id))
        return

    keyboard = []
    for i, channel in enumerate(CHANNELS_TO_JOIN):
        # Convert channel index to string for consistent storage in claimed_channel_ids
        if str(i) not in user_data["claimed_channel_ids"]:
            keyboard.append([InlineKeyboardButton(f"🔗 {channel['name']}", url=channel['link'])]) # Direct link button
            keyboard.append([InlineKeyboardButton(get_text(user_id, "claim_points_button").format(channel_name=channel['name']), callback_data=f"claim_channel_{i}")]) # Claim button
        else:
            keyboard.append([InlineKeyboardButton(f"✅ Joined: {channel['name']}", url=channel['link'])]) # Indicate already joined

    if not keyboard: # If all channels are already claimed
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

    # TODO: यहाँ यूज़र के चैनल में होने की पुष्टि करें
    # यह Telegram API के getChatMember() मेथड का उपयोग करके किया जा सकता है।
    # उदाहरण:
    # try:
    #     chat_member = await context.bot.get_chat_member(chat_id=CHANNELS_TO_JOIN[channel_index]['id'], user_id=user_id)
    #     if chat_member.status not in ["member", "administrator", "creator"]:
    #         await query.answer(get_text(user_id, "not_yet_joined_channel"), show_alert=True) # नया टेक्स्ट जोड़ें
    #         return
    # except Exception as e:
    #     print(f"Error checking channel membership for user {user_id} in channel {CHANNELS_TO_JOIN[channel_index]['name']}: {e}")
    #     await query.answer(get_text(user_id, "generic_error"), show_alert=True)
    #     return


    points_to_add = CHANNEL_JOIN_POINTS
    update_user_data(user_id, balance_change=points_to_add, channel_joined_change=1, add_claimed_channel_id=channel_index)
    user_data = get_user_data(user_id) # Get updated data after changes

    await query.answer(get_text(user_id, "channel_claimed_success", channel_name=CHANNELS_TO_JOIN[channel_index]['name'],
                                 points_added=points_to_add, balance=user_data['balance']), show_alert=True)
    
    # After claiming, refresh the tasks message to reflect the change
    # Re-calling tasks will show updated buttons (or no_tasks_available if all are claimed)
    await tasks(update.callback_query, context)


# --- Referral System ---
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler can be called by a command or a keyboard button.
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # Answer the callback query
        send_func = update.callback_query.message.reply_text
    else:
        return # Should not happen

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    user_data = get_user_data(user_id)
    await send_func(
        get_text(user_id, "referral_link_text", referral_link=referral_link,
                 referral_count=user_data['referral_count'],
                 referral_points=REFERRAL_POINTS_PER_30),
        reply_markup=main_menu_keyboard(user_id) # Show main menu keyboard
    )

# --- Check Balance Command ---
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler can be called by a command or a keyboard button.
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # Answer the callback query
        send_func = update.callback_query.message.reply_text
    else:
        return # Should not happen

    user_data = get_user_data(user_id)
    await send_func(
        get_text(user_id, "balance_text", balance=user_data['balance'],
                 shortlinks_solved_count=user_data['shortlinks_solved_count'],
                 referral_count=user_data['referral_count'],
                 channel_joined_count=user_data['channel_joined_count']),
        reply_markup=main_menu_keyboard(user_id) # Show main menu keyboard
    )

# --- Withdrawal System ---
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler can be called by a command or a keyboard button.
    if update.message:
        user_id = update.message.from_user.id
        send_func = update.message.reply_text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer() # Answer the callback query
        send_func = update.callback_query.message.reply_text
    else:
        return # Should not happen

    user_data = get_user_data(user_id)

    # First check: minimum balance
    if user_data["balance"] < MIN_WITHDRAWAL_POINTS:
        await send_func(get_text(user_id, "min_withdraw_balance",
                                 balance=user_data['balance'],
                                 min_points=MIN_WITHDRAWAL_POINTS,
                                 min_rupees=MIN_WITHDRAWAL_POINTS * POINTS_TO_RUPEES_RATE),
                        reply_markup=main_menu_keyboard(user_id))
        return

    # Second check: minimum shortlinks solved for withdrawal eligibility
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
        # Note: No main menu keyboard here as we expect text input
    )

async def handle_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.user_data.get('withdraw_state') != "waiting_amount":
        # If not in the correct state, clear and send main menu
        await update.message.reply_text(get_text(user_id, "command_usage"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data:
            del context.user_data['withdraw_state']
        return

    try:
        amount_points = float(update.message.text)
        user_data = get_user_data(user_id)

        # Check for minimum withdrawal amount
        if amount_points < MIN_WITHDRAWAL_POINTS:
            await update.message.reply_text(get_text(user_id, "min_withdraw_balance",
                                                     balance=user_data['balance'],
                                                     min_points=MIN_WITHDRAWAL_POINTS,
                                                     min_rupees=MIN_WITHDRAWAL_POINTS * POINTS_TO_RUPEES_RATE),
                                            reply_markup=main_menu_keyboard(user_id))
            if 'withdraw_state' in context.user_data: # Clear state if invalid input
                del context.user_data['withdraw_state']
            return

        # Check for sufficient points
        if amount_points > user_data["balance"]:
            await update.message.reply_text(get_text(user_id, "not_enough_points", balance=user_data['balance']),
                                            reply_markup=main_menu_keyboard(user_id))
            if 'withdraw_state' in context.user_data: # Clear state if invalid input
                del context.user_data['withdraw_state']
            return

        amount_rupees = amount_points * POINTS_TO_RUPEES_RATE

        context.user_data['withdraw_amount_points'] = amount_points
        context.user_data['withdraw_amount_rupees'] = amount_rupees
        context.user_data['withdraw_state'] = "waiting_method"

        keyboard = [
            [InlineKeyboardButton(get_text(user_id, "upi_method_button"), callback_data="withdraw_method_upi")], # Assuming "upi_method_button" key
            [InlineKeyboardButton(get_text(user_id, "bank_method_button"), callback_data="withdraw_method_bank")], # Assuming "bank_method_button" key
            [InlineKeyboardButton(get_text(user_id, "redeem_method_button"), callback_data="withdraw_method_redeem")] # Assuming "redeem_method_button" key
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            get_text(user_id, "withdraw_confirm_method",
                     points=amount_points,
                     rupees=amount_rupees), reply_markup=reply_markup
        )

    except ValueError:
        await update.message.reply_text(get_text(user_id, "invalid_amount"), reply_markup=main_menu_keyboard(user_id))
        if 'withdraw_state' in context.user_data: # Clear state if invalid input
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
        # Also send main menu keyboard if they click something out of sequence
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
        if 'withdraw_state' in context.user_data: # Clear state if invalid method
            del context.user_data['withdraw_state']

async def handle_withdrawal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if context.user_data.get('withdraw_state') != "waiting_details":
        # If not in the correct state, clear and send main menu
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

    # Record withdrawal request and get the ObjectId
    withdrawal_doc_id = record_withdrawal_request(user_id, amount_points, amount_rupees, method, details)

    update_user_data(user_id, balance_change=-amount_points) # Deduct points from Instance 1
    user_data = get_user_data(user_id) # Get updated balance

    await update.message.reply_text(
        get_text(user_id, "withdrawal_success",
                 points=amount_points,
                 rupees=amount_rupees,
                 method=method.upper(),
                 details=details,
                 balance=user_data['balance']),
        reply_markup=main_menu_keyboard(user_id) # Show main menu keyboard after successful withdrawal
    )

    # --- Send notification to admin channel with buttons ---
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

        # Send message to admin channel and store message_id to update later
        sent_message = await context.bot.send_message(
            chat_id=ADMIN_WITHDRAWAL_CHANNEL_ID,
            text=notification_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Update the withdrawal request in MongoDB with admin message details
        # Ensure `withdrawal_requests_collection` is imported from database_utils
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

    # Clean up state
    if 'withdraw_state' in context.user_data:
        del context.user_data['withdraw_state']
    if 'withdraw_amount_points' in context.user_data:
        del context.user_data['withdraw_amount_points']
    if 'withdraw_amount_rupees' in context.user_data:
        del context.user_data['withdraw_amount_rupees']
    if 'withdraw_method' in context.user_data:
        del context.user_data['withdraw_method']

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

    # Fetch the withdrawal request from MongoDB
    withdrawal_request = withdrawal_requests_collection.find_one({"_id": withdrawal_doc_id})

    if not withdrawal_request:
        await query.edit_message_text("त्रुटि: विथड्रॉल रिक्वेस्ट नहीं मिली।")
        return

    # To get the user's language for the message
    user_lang_code = get_user_language(withdrawal_request["user_id"])

    if withdrawal_request.get("status") != "pending":
        # Using WITHDRAWAL_STATUS_UPDATE_MESSAGES from languages.py
        await query.edit_message_text(WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["already_processed"])
        return

    # Update withdrawal status in MongoDB
    withdrawal_requests_collection.update_one(
        {"_id": withdrawal_doc_id},
        {"$set": {"status": "approved", "processed_by_admin_id": query.from_user.id, "processed_timestamp": datetime.now()}}
    )

    # Update the admin channel message
    original_text = query.message.text
    new_text = original_text.replace("स्थिति: `लंबित`", "स्थिति: `मंज़ूर` ✅")
    new_text += f"\n\nमंज़ूर किया: @{query.from_user.username or query.from_user.first_name}"

    await query.edit_message_text(new_text, parse_mode='Markdown', reply_markup=None) # Remove buttons

    # Notify the user
    user_id_to_notify = withdrawal_request["user_id"]
    amount_points = withdrawal_request["amount_points"]
    amount_rupees = withdrawal_request["amount_rupees"]

    try:
        # Using WITHDRAWAL_STATUS_UPDATE_MESSAGES from languages.py
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

    # Fetch the withdrawal request from MongoDB
    withdrawal_request = withdrawal_requests_collection.find_one({"_id": withdrawal_doc_id})

    if not withdrawal_request:
        await query.edit_message_text("त्रुटि: विथड्रॉल रिक्वेस्ट नहीं मिली।")
        return
    
    # To get the user's language for the message
    user_lang_code = get_user_language(withdrawal_request["user_id"])

    if withdrawal_request.get("status") != "pending":
        # Using WITHDRAWAL_STATUS_UPDATE_MESSAGES from languages.py
        await query.edit_message_text(WITHDRAWAL_STATUS_UPDATE_MESSAGES[user_lang_code]["already_processed"])
        return

    # Update withdrawal status in MongoDB
    withdrawal_requests_collection.update_one(
        {"_id": withdrawal_doc_id},
        {"$set": {"status": "rejected", "processed_by_admin_id": query.from_user.id, "processed_timestamp": datetime.now()}}
    )

    # Update the admin channel message
    original_text = query.message.text
    new_text = original_text.replace("स्थिति: `लंबित`", "स्थिति: `ख़ारिज` ❌")
    new_text += f"\n\nख़ारिज किया: @{query.from_user.username or query.from_user.first_name}"

    await query.edit_message_text(new_text, parse_mode='Markdown', reply_markup=None) # Remove buttons

    # Notify the user
    user_id_to_notify = withdrawal_request["user_id"]
    amount_points = withdrawal_request["amount_points"]
    amount_rupees = withdrawal_request["amount_rupees"]

    try:
        # Using WITHDRAWAL_STATUS_UPDATE_MESSAGES from languages.py
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
    if update.effective_message:
        user_id = update.effective_user.id if update.effective_user else None
        await update.effective_message.reply_text(get_text(user_id, "generic_error"), reply_markup=main_menu_keyboard(user_id))
    if update.effective_user and 'withdraw_state' in context.user_data:
        del context.user_data['withdraw_state']

# --- Message Handler for text inputs (like withdrawal amount/details) ---
async def handle_text_input_for_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_state = context.user_data.get('withdraw_state')

    if current_state == "waiting_amount":
        await handle_withdrawal_amount(update, context)
    elif current_state == "waiting_details":
        await handle_withdrawal_details(update, context)
    else:
        # If text is received when not in a withdrawal state, send usage message with main menu
        await update.message.reply_text(get_text(user_id, "command_usage"), reply_markup=main_menu_keyboard(user_id))

# --- Main function to run the bot ---
def main():
    """Bot को स्टार्ट करता है।"""
    global application_instance # Globalize the application instance
    application_instance = Application.builder().token(BOT_TOKEN).build()

    # --- Command Handlers ---
    # These are still needed if users type commands, but buttons will be primary
    application_instance.add_handler(CommandHandler("start", start))
    application_instance.add_handler(CommandHandler("earn", earn))
    application_instance.add_handler(CommandHandler("tasks", tasks))
    application_instance.add_handler(CommandHandler("balance", check_balance))
    application_instance.add_handler(CommandHandler("invite", invite))
    application_instance.add_handler(CommandHandler("withdraw", withdraw))


    # --- Message Handler for text inputs (like withdrawal amount/details) and general text messages ---
    # IMPORTANT: This must be added BEFORE the CommandHandlers if you want buttons to also trigger handlers.
    # We will use this to catch text that matches our button texts.
    application_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input_for_withdrawal))

    # --- Callback Query Handlers (for Inline Buttons) ---
    application_instance.add_handler(CallbackQueryHandler(set_language, pattern="^set_lang_"))
    application_instance.add_handler(CallbackQueryHandler(done_shortlink, pattern="^done_shortlink$"))
    application_instance.add_handler(CallbackQueryHandler(generate_next_shortlink, pattern="^generate_next_shortlink$"))
    application_instance.add_handler(CallbackQueryHandler(claim_channel, pattern="^claim_channel_\\d+$"))
    application_instance.add_handler(CallbackQueryHandler(handle_withdrawal_method, pattern="^withdraw_method_"))
    
    # --- Callback Query Handlers for Admin Actions ---
    application_instance.add_handler(CallbackQueryHandler(approve_withdrawal, pattern="^approve_withdraw_"))
    application_instance.add_handler(CallbackQueryHandler(reject_withdrawal, pattern="^reject_withdraw_"))
    
    # --- Handler for Main Menu Buttons (text matching) ---
    # These handlers will call the same functions as the commands
    application_instance.add_handler(MessageHandler(filters.Regex(LANGUAGES[DEFAULT_LANGUAGE]['earn_button']) | filters.Regex(LANGUAGES['hi']['earn_button']), earn))
    application_instance.add_handler(MessageHandler(filters.Regex(LANGUAGES[DEFAULT_LANGUAGE]['tasks_button']) | filters.Regex(LANGUAGES['hi']['tasks_button']), tasks))
    application_instance.add_handler(MessageHandler(filters.Regex(LANGUAGES[DEFAULT_LANGUAGE]['balance_button']) | filters.Regex(LANGUAGES['hi']['balance_button']), check_balance))
    application_instance.add_handler(MessageHandler(filters.Regex(LANGUAGES[DEFAULT_LANGUAGE]['invite_button']) | filters.Regex(LANGUAGES['hi']['invite_button']), invite))
    application_instance.add_handler(MessageHandler(filters.Regex(LANGUAGES[DEFAULT_LANGUAGE]['withdraw_button']) | filters.Regex(LANGUAGES['hi']['withdraw_button']), withdraw))


    # --- Error Handler ---
    application_instance.add_error_handler(error_handler)

    application_instance.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    init_db() # पहले डेटाबेस कनेक्शन इनिशियलाइज़ करें
    main() # फिर बॉट स्टार्ट करें
