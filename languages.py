# languages.py

# --- LANGUAGES Dictionary (सभी बॉट टेक्स्ट अलग-अलग भाषाओं में) ---
# यह डिक्शनरी बॉट के सभी संदेशों का अनुवाद रखती है।
# सुनिश्चित करें कि सभी कुंजियों (keys) का अनुवाद सभी भाषाओं में मौजूद हो।
LANGUAGES = {
    "en": {
        "name": "English",
        "welcome": "Hello {first_name}! I am your earning bot.\n\nYour current balance: **{balance:.2f} points.**\n"
                   "You have solved {shortlinks_solved_count} shortlinks.\n\nCommands:\n"
                   "/earn - Solve shortlinks\n/tasks - Join channels\n/balance - Check your balance\n"
                   "/invite - Invite your friends\n/withdraw - Withdraw money",
        "language_choice": "Please choose your preferred language:",
        "invalid_referrer": "Welcome! Invalid referrer ID or already referred.",
        "self_referral": "Welcome! You cannot refer yourself.",
        "referrer_joined": "🎉 You got a new referral! User {user_id} joined via your link.",
        "shortlink_unavailable": "Could not generate a new shortlink. Please try again later.",
        "shortlink_given": "Here is your next shortlink:\n\n{shortlink}\n\n"
                           "After solving it, click the button below:",
        "shortlink_button": "✅ I have completed the Shortlink",
        "no_shortlink_started": "You haven't started solving any shortlink. Start with the /earn command.",
        "shortlink_completed": "Thank you! You have solved a shortlink. You earned **{points:.2f} point**.\n"
                               "Total solved shortlinks: **{solved_count}**.\nYour current balance: **{balance:.2f} points.**",
        "next_shortlink_button": "➡️ Generate Next Shortlink",
        "no_tasks_available": "No channels available to join right now.",
        "join_channels_prompt": "Join the channels below and then claim points:",
        "claimed_already": "You have already claimed points for this channel.",
        "invalid_channel": "Invalid channel.",
        "channel_claimed_success": "Thank you! You have joined **{channel_name}** channel and claimed **{points_added:.2f} points**.\n"
                                   "Your new balance: **{balance:.2f}**\n\nMore tasks: /tasks",
        "referral_link_text": "Share this link to invite your friends:\n\n`{referral_link}`\n\n"
                              "You have made **{referral_count}** referrals so far.\n"
                              "You will get **{referral_points} points** for every 30 referrals.",
        "balance_text": "Your current balance: **{balance:.2f} points.**\n"
                        "You have solved **{shortlinks_solved_count}** shortlinks.\n"
                        "You have made **{referral_count}** referrals.\n"
                        "You have joined **{channel_joined_count}** channels.",
        "min_withdraw_balance": "Your current balance is **{balance:.2f}** points. Minimum withdrawal amount is **{min_points} points** (which is equal to **{min_rupees:.2f} Rs.**).",
        "min_shortlinks_for_withdraw": "You need to solve at least **{min_shortlinks}** shortlinks to request a withdrawal. You have solved **{solved_count}**.",
        "withdraw_prompt_amount": "Your current balance is **{balance:.2f} points**. Minimum withdrawal **{min_points} points**.\n"
                                  "**1 Point = {rate:.2f} Rs.**\n"
                                  "How many points do you want to withdraw? (Enter only the number, minimum {min_points} points)",
        "invalid_amount": "Invalid amount. Please enter a valid number.",
        "not_enough_points": "You don't have enough points. Your current balance: **{balance:.2f}** points.",
        "withdraw_confirm_method": "You want to withdraw **{points:.2f} points** (which is equal to **{rupees:.2f} Rs.**).\n"
                                   "Which method do you want to withdraw with?",
        "upi_prompt": "Please enter your **UPI ID**:",
        "bank_prompt": "Please enter your **Bank Account Number, IFSC Code, and Account Holder Name** in one message:",
        "redeem_prompt": "Please enter your **email address** where you want to receive the redeem code:",
        "invalid_method": "Invalid method selected.",
        "withdrawal_error": "An error occurred during the withdrawal process. Please try /withdraw again.",
        "withdrawal_success": "Your withdrawal request has been submitted successfully.\n"
                              "Requested Points: **{points:.2f}**\n"
                              "Estimated Rupees: **{rupees:.2f} Rs.**\n"
                              "Method: **{method}**\n"
                              "Details: `{details}`\n\n"
                              "Your new balance: **{balance:.2f} points.**\n"
                              "Our team will process your request soon.",
        "action_not_valid": "This action is not currently valid.",
        "generic_error": "An error occurred. Please try again or /start.",
        "command_usage": "Please use commands. Start with /start or type /help."
    },
    "hi": {
        "name": "हिंदी",
        "welcome": "नमस्ते {first_name}! मैं आपका कमाई करने वाला बॉट हूँ।\n\nआपका मौजूदा बैलेंस: **{balance:.2f} पॉइंट्स।**\n"
                   "आपने {shortlinks_solved_count} शॉर्टलिंक सॉल्व किए हैं।\n\nकमांड्स:\n"
                   "/earn - शॉर्टलिंक सॉल्व करें\n/tasks - चैनल जॉइन करें\n/balance - अपना बैलेंस देखें\n"
                   "/invite - अपने दोस्तों को इन्वाइट करें\n/withdraw - पैसे निकालें",
        "language_choice": "कृपया अपनी पसंदीदा भाषा चुनें:",
        "invalid_referrer": "स्वागत है! अमान्य रेफ़रर आईडी या पहले ही रेफ़र किया जा चुका है।",
        "self_referral": "स्वागत है! आप खुद को रेफ़र नहीं कर सकते।",
        "referrer_joined": "🎉 आपको नया रेफ़रल मिला! यूज़र {user_id} आपके लिंक से जुड़ा।",
        "shortlink_unavailable": "नया शॉर्टलिंक जनरेट नहीं हो पाया। कृपया बाद में फिर से कोशिश करें।",
        "shortlink_given": "यह रहा आपका अगला शॉर्टलिंक:\n\n{shortlink}\n\n"
                           "इसे सॉल्व करने के बाद, नीचे दिए गए बटन पर क्लिक करें:",
        "shortlink_button": "✅ मैंने शॉर्टलिंक पूरा कर लिया",
        "no_shortlink_started": "आपने कोई शॉर्टलिंक सॉल्व करने के लिए शुरू नहीं किया है। /earn कमांड से शुरू करें।",
        "shortlink_completed": "शुक्रिया! आपने एक शॉर्टलिंक सॉल्व कर लिया। आपको **{points:.2f} पॉइंट** मिला है।\n"
                               "कुल सॉल्व किए गए शॉर्टलिंक: **{solved_count}**।\nआपका मौजूदा बैलेंस: **{balance:.2f} पॉइंट्स।**",
        "next_shortlink_button": "➡️ अगला शॉर्टलिंक जनरेट करें",
        "no_tasks_available": "अभी जॉइन करने के लिए कोई चैनल उपलब्ध नहीं हैं।",
        "join_channels_prompt": "नीचे दिए गए चैनलों को जॉइन करें और फिर पॉइंट्स क्लेम करें:",
        "claimed_already": "आप पहले ही इस चैनल के पॉइंट्स क्लेम कर चुके हैं।",
        "invalid_channel": "अमान्य चैनल।",
        "channel_claimed_success": "शुक्रिया! आपने **{channel_name}** चैनल जॉइन कर लिया और **{points_added:.2f} पॉइंट्स** क्लेम कर लिए।\n"
                                   "आपका नया बैलेंस: **{balance:.2f}**\n\nअधिक कार्य: /tasks",
        "referral_link_text": "अपने दोस्तों को इन्वाइट करने के लिए यह लिंक शेयर करें:\n\n`{referral_link}`\n\n"
                              "आपने अब तक **{referral_count}** रेफ़रल किए हैं।\n"
                              "हर 30 रेफ़रल पर आपको **{referral_points} पॉइंट्स** मिलेंगे।",
        "balance_text": "आपका मौजूदा बैलेंस: **{balance:.2f} पॉइंट्स।**\n"
                        "आपने अब तक **{shortlinks_solved_count}** शॉर्टलिंक सॉल्व किए हैं।\n"
                        "आपने अब तक **{referral_count}** रेफ़रल किए हैं।\n"
                        "आपने अब तक **{channel_joined_count}** चैनल जॉइन किए हैं।",
        "min_withdraw_balance": "आपका मौजूदा बैलेंस **{balance:.2f}** पॉइंट्स है। न्यूनतम विड्रॉल राशि **{min_points} पॉइंट्स** है (जो कि **{min_rupees:.2f} रुपये** के बराबर है)।",
        "min_shortlinks_for_withdraw": "आपको विड्रॉल रिक्वेस्ट करने के लिए कम से कम **{min_shortlinks}** शॉर्टलिंक सॉल्व करने होंगे। आपने अभी **{solved_count}** सॉल्व किए हैं।",
        "withdraw_prompt_amount": "आपका मौजूदा बैलेंस **{balance:.2f} पॉइंट्स** है। न्यूनतम विड्रॉल **{min_points} पॉइंट्स** है।\n"
                                  "**1 पॉइंट = {rate:.2f} रुपये।**\n"
                                  "कितने पॉइंट निकालना चाहते हैं? (सिर्फ़ संख्या लिखें, न्यूनतम {min_points} पॉइंट)",
        "invalid_amount": "अमान्य राशि। कृपया सही संख्या दर्ज करें।",
        "not_enough_points": "आपके पास इतने पॉइंट्स नहीं हैं। आपका मौजूदा बैलेंस: **{balance:.2f}** पॉइंट्स।",
        "withdraw_confirm_method": "आप **{points:.2f} पॉइंट्स** (जो कि **{rupees:.2f} रुपये** के बराबर हैं) निकालना चाहते हैं।\n"
                                   "किस विधि से पैसे निकालना चाहते हैं?",
        "upi_prompt": "कृपया अपनी **UPI ID** दर्ज करें:",
        "bank_prompt": "कृपया अपना **बैंक खाता नंबर, IFSC कोड, और खाताधारक का नाम** एक ही संदेश में दर्ज करें:",
        "redeem_prompt": "कृपया अपना **ईमेल पता** दर्ज करें जहाँ आप रिडीम कोड प्राप्त करना चाहते हैं:",
        "invalid_method": "अमान्य विधि चुनी गई।",
        "withdrawal_error": "विड्रॉल प्रक्रिया में कुछ त्रुटि हो गई। कृपया दोबारा /withdraw करें।",
        "withdrawal_success": "आपकी विड्रॉल रिक्वेस्ट सफलतापूर्वक सबमिट हो गई है।\n"
                              "अनुरोधित पॉइंट्स: **{points:.2f}**\n"
                              "अनुमानित रुपये: **{rupees:.2f} रुपये।**\n"
                              "विधि: **{method}**\n"
                              "विवरण: `{details}`\n\n"
                              "आपका नया बैलेंस: **{balance:.2f} पॉइंट्स।**\n"
                              "हमारी टीम आपकी रिक्वेस्ट को जल्द ही प्रोसेस करेगी।",
        "action_not_valid": "यह कार्रवाई अभी मान्य नहीं है।",
        "generic_error": "कुछ त्रुटि हो गई है। कृपया दोबारा कोशिश करें या /start करें।",
        "command_usage": "कृपया कमांड्स का उपयोग करें। /start से शुरू करें या /help टाइप करें।"
    }
}

# --- विथड्रॉल स्टेटस अपडेट मैसेजेस ---
# यह डिक्शनरी विथड्रॉल की मंजूरी या अस्वीकृति के बाद यूज़र को भेजे गए संदेशों को रखती है।
WITHDRAWAL_STATUS_UPDATE_MESSAGES = {
    "en": {
        "approved": "🎉 Good news! Your withdrawal request for **{points:.2f} points** ({rupees:.2f} Rs.) has been **APPROVED** and processed. Your funds should reach your account soon.\n\nThank you for using our bot!",
        "rejected": "😞 Your withdrawal request for **{points:.2f} points** ({rupees:.2f} Rs.) has been **REJECTED**. This might be due to incorrect details or other reasons. Please contact support if you have questions.",
        "already_processed": "This withdrawal request has already been processed."
    },
    "hi": {
        "approved": "🎉 अच्छी खबर! आपकी **{points:.2f} पॉइंट्स** ({rupees:.2f} रुपये) की विथड्रॉल रिक्वेस्ट **मंज़ूर** हो गई है और प्रोसेस कर दी गई है। आपके पैसे जल्द ही आपके खाते में पहुंच जाएंगे।\n\nहमारे बॉट का उपयोग करने के लिए धन्यवाद!",
        "rejected": "😞 आपकी **{points:.2f} पॉइंट्स** ({rupees:.2f} रुपये) की विथड्रॉल रिक्वेस्ट **ख़ारिज** कर दी गई है। यह गलत विवरण या अन्य कारणों से हो सकता है। यदि आपके कोई प्रश्न हैं तो कृपया सहायता से संपर्क करें।",
        "already_processed": "यह विथड्रॉल रिक्वेस्ट पहले ही प्रोसेस की जा चुकी है।"
    }
}


DEFAULT_LANGUAGE = "en" # डिफ़ॉल्ट भाषा

# --- अनुवादित टेक्स्ट प्राप्त करने के लिए हेल्पर फ़ंक्शन ---
# यह फ़ंक्शन यूज़र की भाषा के अनुसार सही अनुवादित टेक्स्ट लौटाता है।
# अगर किसी भाषा में कोई टेक्स्ट मौजूद नहीं है, तो यह डिफ़ॉल्ट भाषा (अंग्रेज़ी) का उपयोग करेगा।
def get_text(user_id, key, **kwargs):
    # **महत्वपूर्ण: get_user_language को डेटाबेस_यूटिल्स.py से इंपोर्ट करना होगा**
    from database_utils import get_user_language # <-- यह लाइन बदल दी गई है

    lang_code = get_user_language(user_id)
    text_dict = LANGUAGES.get(lang_code, LANGUAGES[DEFAULT_LANGUAGE])
    return text_dict.get(key, LANGUAGES[DEFAULT_LANGUAGE].get(key, f"Missing text for key: {key} in {lang_code}")).format(**kwargs)
