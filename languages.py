# languages.py
import logging

# डिफ़ॉल्ट भाषा
DEFAULT_LANGUAGE = "en" # आप इसे अपनी पसंद की डिफ़ॉल्ट भाषा में बदल सकते हैं (जैसे "hi" हिंदी के लिए)

# सभी भाषाओं के लिए टेक्स्ट स्ट्रिंग्स
LANGUAGES = {
    "en": {
        "name_in_english": "English",
        "start_message": "Hello! Welcome to the bot. How can I help you today?",
        "main_menu_message": "Welcome back! Here are the options:", # नया मेनू मैसेज
        "start_button_earn": "💰 Earn Points",
        "start_button_refer": "👥 Refer Friend",
        "start_button_balance": "📊 Check Balance",
        "start_button_withdraw": "💸 Withdraw Points",
        "start_button_language": "🌐 Change Language",
        "start_button_help": "❓ Help",
        "help_message": "This bot helps you earn points by completing tasks and referring friends. You can then withdraw these points. For any assistance, contact admin.",
        
        # अनिवार्य चैनल जॉइन टेक्स्ट
        "force_subscribe_message": "To use this bot, you must join our channel: {channel_link}\n\nAfter joining, click the 'I have joined' button.",
        "force_subscribe_button": "🔗 Join Channel",
        "force_subscribe_check_button": "✅ I have joined",
        "force_subscribe_not_joined": "You haven't joined the channel yet. Please join to continue.",
        "force_subscribe_error_no_username": "Could not verify channel. Please contact support.",

        # भाषा चयन टेक्स्ट
        "choose_language": "Please choose your preferred language:",
        "language_set_success": "Language set to {lang_name} successfully!",

        # अर्निंग पॉइंट्स और शॉर्टलिंक टेक्स्ट
        "earn_points_instructions": "Click on the link below to earn points. Complete the steps on the website, then come back and click 'Check Completion':\n\n{shortlink_url}\n\n**Note:** Make sure to complete all steps on the website to receive points.",
        "button_check_completion": "✅ Check Completion",
        "shortlink_completed_success": "Congratulations! You earned {points} points for completing the task. Your new balance is {balance} points.",
        "shortlink_not_completed": "It seems you haven't completed the shortlink yet, or we couldn't verify it. Please try again or ensure you completed all steps.",
        "error_generating_shortlink": "Failed to generate shortlink. Please try again later.",
        "error_api_call": "There was an issue connecting to the shortlink service. Please try again in a moment.",
        "error_api_check": "Could not verify shortlink completion at this time. Please try again.",
        
        # रेफरल टेक्स्ट
        "refer_message": "Invite your friends and earn points! Share your unique referral link:\n\n{referral_link}\n\nYou will receive points for each successful referral.",
        
        # बैलेंस टेक्स्ट
        "balance_message": "Your current balance is: {points} points.",
        
        # निकासी टेक्स्ट
        "withdraw_message": "Withdrawal options will be displayed here. Please follow the instructions to request a withdrawal.",
        
        # सामान्य त्रुटि
        "error_general": "An unexpected error occurred. Please try again.",
        "user_not_found": "User data not found. Please try /start again.",

        # निकासी स्थिति अपडेट (एडमिन के लिए)
        "withdrawal_status_update_messages": {
            "pending": "⏳ Your withdrawal request is pending approval.",
            "approved": "✅ Your withdrawal request has been approved and processed. You should receive your funds shortly.",
            "rejected": "❌ Your withdrawal request was rejected. Reason: {reason}",
            "completed": "✅ Your withdrawal request has been successfully completed. Funds should be in your account.",
            "processing": "🔄 Your withdrawal request is being processed. Please wait.",
        }
    },
    "hi": {
        "name_in_english": "Hindi",
        "start_message": "नमस्ते! बॉट में आपका स्वागत है। मैं आज आपकी क्या मदद कर सकता हूँ?",
        "main_menu_message": "वापस स्वागत है! ये विकल्प हैं:", # नया मेनू मैसेज
        "start_button_earn": "💰 अंक कमाएँ",
        "start_button_refer": "👥 दोस्त को रेफर करें",
        "start_button_balance": "📊 बैलेंस देखें",
        "start_button_withdraw": "💸 अंक निकालें",
        "start_button_language": "🌐 भाषा बदलें",
        "start_button_help": "❓ मदद",
        "help_message": "यह बॉट आपको कार्यों को पूरा करके और दोस्तों को रेफर करके अंक कमाने में मदद करता है। आप इन अंकों को बाद में निकाल सकते हैं। किसी भी सहायता के लिए, एडमिन से संपर्क करें।",

        # अनिवार्य चैनल जॉइन टेक्स्ट
        "force_subscribe_message": "इस बॉट का उपयोग करने के लिए, आपको हमारे चैनल में शामिल होना होगा: {channel_link}\n\nशामिल होने के बाद, 'मैं शामिल हो गया हूँ' बटन पर क्लिक करें।",
        "force_subscribe_button": "🔗 चैनल में शामिल हों",
        "force_subscribe_check_button": "✅ मैं शामिल हो गया हूँ",
        "force_subscribe_not_joined": "आप अभी तक चैनल में शामिल नहीं हुए हैं। कृपया जारी रखने के लिए शामिल हों।",
        "force_subscribe_error_no_username": "चैनल सत्यापित नहीं हो सका। कृपया सहायता से संपर्क करें।",

        # भाषा चयन टेक्स्ट
        "choose_language": "कृपया अपनी पसंदीदा भाषा चुनें:",
        "language_set_success": "भाषा {lang_name} सफलतापूर्वक सेट हो गई है!",

        # अर्निंग पॉइंट्स और शॉर्टलिंक टेक्स्ट
        "earn_points_instructions": "अंक कमाने के लिए नीचे दिए गए लिंक पर क्लिक करें। वेबसाइट पर दिए गए चरणों को पूरा करें, फिर वापस आकर 'कंप्लीशन जांचें' पर क्लिक करें:\n\n{shortlink_url}\n\n**नोट:** अंक प्राप्त करने के लिए वेबसाइट पर सभी चरणों को पूरा करना सुनिश्चित करें।",
        "button_check_completion": "✅ कंप्लीशन जांचें",
        "shortlink_completed_success": "बधाई हो! आपने कार्य पूरा करने के लिए {points} अंक अर्जित किए हैं। आपका नया बैलेंस {balance} अंक है।",
        "shortlink_not_completed": "ऐसा लगता है कि आपने अभी तक शॉर्टलिंक पूरा नहीं किया है, या हम इसे सत्यापित नहीं कर सके। कृपया पुनः प्रयास करें या सुनिश्चित करें कि आपने सभी चरण पूरे कर लिए हैं।",
        "error_generating_shortlink": "शॉर्टलिंक बनाने में विफल रहा। कृपया बाद में पुनः प्रयास करें।",
        "error_api_call": "शॉर्टलिंक सेवा से जुड़ने में समस्या थी। कृपया कुछ देर बाद पुनः प्रयास करें।",
        "error_api_check": "इस समय शॉर्टलिंक पूरा होने का सत्यापन नहीं हो सका। कृपया पुनः प्रयास करें।",

        # रेफरल टेक्स्ट
        "refer_message": "अपने दोस्तों को आमंत्रित करें और अंक कमाएँ! अपनी अद्वितीय रेफरल लिंक साझा करें:\n\n{referral_link}\n\nआपको प्रत्येक सफल रेफरल के लिए अंक प्राप्त होंगे।",

        # बैलेंस टेक्स्ट
        "balance_message": "आपका वर्तमान बैलेंस है: {points} अंक।",
        
        # निकासी टेक्स्ट
        "withdraw_message": "निकासी विकल्प यहां प्रदर्शित किए जाएंगे। निकासी का अनुरोध करने के लिए कृपया निर्देशों का पालन करें।",

        # सामान्य त्रुटि
        "error_general": "एक अप्रत्याशित त्रुटि हुई। कृपया पुनः प्रयास करें।",
        "user_not_found": "उपयोगकर्ता डेटा नहीं मिला। कृपया /start पुनः प्रयास करें।",

        # निकासी स्थिति अपडेट (एडमिन के लिए)
        "withdrawal_status_update_messages": {
            "pending": "⏳ आपकी निकासी का अनुरोध विचाराधीन है।",
            "approved": "✅ आपकी निकासी का अनुरोध स्वीकृत और संसाधित कर दिया गया है। आपको जल्द ही धनराशि प्राप्त हो जानी चाहिए।",
            "rejected": "❌ आपकी निकासी का अनुरोध अस्वीकृत कर दिया गया। कारण: {reason}",
            "completed": "✅ आपकी निकासी का अनुरोध सफलतापूर्वक पूरा हो गया है। धनराशि आपके खाते में होनी चाहिए।",
            "processing": "🔄 आपकी निकासी का अनुरोध संसाधित किया जा रहा है। कृपया प्रतीक्षा करें।",
        }
    }
    # भविष्य में और भाषाएँ यहां जोड़ी जा सकती हैं
}

def get_text(key: str, lang_code: str = DEFAULT_LANGUAGE) -> str:
    """निर्दिष्ट भाषा के लिए टेक्स्ट स्ट्रिंग लौटाता है, यदि उपलब्ध न हो तो डिफ़ॉल्ट पर वापस आता है।"""
    if lang_code in LANGUAGES and key in LANGUAGES[lang_code]:
        return LANGUAGES[lang_code][key]
    elif key in LANGUAGES[DEFAULT_LANGUAGE]:
        return LANGUAGES[DEFAULT_LANGUAGE][key]
    else:
        # यदि कुंजी किसी भी भाषा में नहीं मिलती है, तो एक त्रुटि लॉग करें और कुंजी ही लौटा दें
        logging.warning(f"Missing text key '{key}' for language '{lang_code}'.")
        return f"MISSING_TEXT:{key}"
