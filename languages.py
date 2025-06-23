# languages.py

DEFAULT_LANGUAGE = "hi" # बॉट के लिए डिफ़ॉल्ट भाषा

LANGUAGES = {
    "en": {
        "name": "English 🇬🇧",
        "language_choice": "Please choose your language:",
        "force_subscribe_text": "🚨 *Important!* 🚨\n\nTo use this bot, you must first join our channel:\n👉 @{channel_username}\n\nAfter joining, click '✅ I have joined!'",
        "join_channel_button": "Join Channel",
        "joined_check_button": "✅ I have joined!",
        "not_joined_error": "❌ It seems you haven't joined the channel yet or I couldn't verify. Please join @{channel_username} and click '✅ I have joined!' again.",
        "welcome": "🎉 *Welcome, {first_name}!* 🎉\n\nYour current balance is: *{balance:.2f} Points*\n\n_Choose an option from the menu below:_ 👇",
        "earn_button": "🔗 Earn Points",
        "profile_button": "👤 My Profile",
        "invite_button": "👨‍👩‍👧‍👦 Invite & Earn",
        "withdraw_button": "💳 Withdraw",
        "help_button": "❓ Help",
        "earn_options_prompt": "Choose how you want to earn points:",
        "solve_shortlinks_button": "🔗 Solve Shortlinks",
        "join_channels_button": "➕ Join Channels/Groups",
        "shortlink_instructions": "📖 *How to Earn with Shortlinks:*\n\n1. Click the shortlink provided below.\n2. Complete all steps (view ads, solve captcha, etc.) on the website.\n3. After successful completion, click '✅ I Completed It!' here.\n\nYou will receive *{points_per_shortlink:.2f} Points* for each completed shortlink.",
        "shortlink_unavailable": "😔 Sorry, I couldn't fetch a shortlink right now. Please try again later.",
        "shortlink_given": "🚀 Here's your shortlink!\n👉 {shortlink}\n\n*Click the 'Done' button after completing the shortlink.*",
        "shortlink_completed_button": "✅ I Completed It!",
        "no_shortlink_started": "🤔 You haven't started any shortlink task yet. Please click 'Solve Shortlinks' first.",
        "shortlink_completed": "✨ Congratulations! You earned {points:.2f} points!\n\nYour new balance: *{balance:.2f} Points*\nTotal shortlinks solved: *{solved_count}*",
        "next_shortlink_button": "➡️ Next Shortlink",
        "channels_to_join_prompt": "Here are channels/groups you can join to earn points. Click 'Joined & Claim' after joining each one.",
        "channel_already_claimed": "❌ You have already claimed points for joining *{channel_username}*.",
        "channel_not_joined": "😔 You must join *{channel_username}* first to claim points.",
        "channel_claim_success": "✅ You earned {points:.2f} points for joining *{channel_username}*!\n\nYour new balance: *{balance:.2f} Points*",
        "no_more_channels": "🎉 You have joined all available channels/groups and claimed your points!",
        "joined_claim_button": "✅ Joined & Claim",
        "profile_text": "👤 *Your Profile:*\n\nName: *{first_name}*\nBalance: *{balance:.2f} Points*\nShortlinks Solved: *{shortlinks_solved_count}*\nTotal Referrals: *{referral_count}*\n\n_Your profile picture is shown above._",
        "min_withdraw_balance": "⛔ *Insufficient Balance!*\n\nYou need at least *{min_points:.2f} Points* ({min_rupees:.2f} Rs) to withdraw.\nYour current balance: *{balance:.2f} Points*.\n\n_Earn more points to reach the minimum._",
        "withdraw_prompt_amount": "💰 *Enter Withdrawal Amount*\n\nYour current balance: *{balance:.2f} Points*\nMinimum withdrawal: *{min_points:.2f} Points* ({min_rupees:.2f} Rs).\n\n_Enter the amount in points you wish to withdraw:_",
        "invalid_amount": "❌ Invalid amount. Please enter a valid number.",
        "not_enough_points": "🚫 You don't have enough points for this withdrawal. Your balance: *{balance:.2f} Points*.",
        "withdraw_confirm_method": "💲 You want to withdraw *{points:.2f} Points* (approx. *{rupees:.2f} Rs*).\n\nPlease choose your withdrawal method:",
        "upi_method_button": "💳 UPI",
        "qr_method_button": "📱 QR Code",
        "bank_method_button": "🏦 Bank Transfer",
        "redeem_method_button": "🎁 Redeem Code (Google Play)",
        "invalid_method": "❌ Invalid withdrawal method selected.",
        "upi_prompt": "✍️ Please send your **UPI ID** (e.g., `yourname@bank`) to proceed with the withdrawal.",
        "qr_prompt": "✍️ Please send your **QR Code image** to proceed with the withdrawal.",
        "bank_prompt": "✍️ Please send your **Bank Account Details** (Account Holder Name, Account Number, IFSC Code, Bank Name) to proceed with the withdrawal.",
        "redeem_prompt": "✍️ Please send the **Google Play Redeem Code value** you want (e.g., `100 Rs`, `250 Rs`).",
        "withdrawal_success": "✅ *Withdrawal Request Submitted!* ✅\n\nAmount: *{points:.2f} Points* (approx. *{rupees:.2f} Rs*)\nMethod: *{method}*\nDetails: *{details}*\n\nYour remaining balance: *{balance:.2f} Points*.\n_Your request is being processed. Please wait 24-48 hours._",
        "withdrawal_error": "🚫 Something went wrong with your withdrawal. Please try again.",
        "command_usage": "⚠️ Please use the buttons to navigate.",
        "referrer_joined": "🎉 *New Referral!* 🎉\n\nYour referral `@{user_username}` has joined the bot!\n\n_You earned {referral_points_per_referral:.2f} points._",
        "invalid_referrer": "🚫 Invalid referral link or you've already been referred.",
        "self_referral": "😅 You can't refer yourself!",
        "referral_link_text": "👨‍👩‍👧‍👦 *Invite your friends and earn!* 👨‍👩‍👧‍👦\n\nShare this link:\n`{referral_link}`\n\nFor each friend who joins through your link, you'll earn *{referral_points_per_referral:.2f} Points*!\n\nYour total referrals: *{referral_count}*",
        "generic_error": "😔 An unexpected error occurred. Please try again later or type /start to go to the main menu.",
        "action_not_valid": "⛔ That action is not valid right now. Please use the menu buttons.",
        "approve_button": "✅ Approve",
        "reject_button": "❌ Reject",
        "back_to_menu": "🏠 Back to Main Menu",
        "help_text": "❓ *Help & Information*\n\nWelcome to our earning bot! Here's how it works:\n\n*1. Earn Points:*\n   - *Solve Shortlinks:* Click 'Earn Points' -> 'Solve Shortlinks'. Follow the instructions, complete the shortlink, and click 'I Completed It!' to earn points.\n   - *Join Channels/Groups:* Click 'Earn Points' -> 'Join Channels/Groups'. Join the listed channels/groups and claim your points once.\n\n*2. Invite & Earn:*\n   - Click 'Invite & Earn' to get your unique referral link. Share it with friends. You earn points for every successful referral!\n\n*3. My Profile:*\n   - Click 'My Profile' to see your current balance, total shortlinks solved, and referrals. You can also start a withdrawal from here.\n\n*4. Withdraw:*\n   - Click 'Withdraw'. You need a minimum of {min_points:.2f} Points ({min_rupees:.2f} Rs) to withdraw.\n   - Enter the amount of points you want to withdraw. The bot will automatically show you the equivalent amount in Rupees.\n   - Choose your preferred method: UPI, QR Code, Bank Transfer (1 point = {upi_qr_bank_rate:.2f} Rs) or Google Play Redeem Code (1 point = {redeem_rate:.2f} Rs).\n   - Provide the requested details.\n   - Your request will be sent to the admin for processing.\n\n_If you have any further questions, please contact the bot admin._",
    },
    "hi": {
        "name": "हिन्दी 🇮🇳",
        "language_choice": "कृपया अपनी भाषा चुनें:",
        "force_subscribe_text": "🚨 *महत्वपूर्ण!* 🚨\n\nइस बॉट का उपयोग करने के लिए, आपको पहले हमारा चैनल जॉइन करना होगा:\n👉 @{channel_username}\n\nजॉइन करने के बाद, '✅ मैंने जॉइन कर लिया!' पर क्लिक करें।",
        "join_channel_button": "चैनल जॉइन करें",
        "joined_check_button": "✅ मैंने जॉइन कर लिया!",
        "not_joined_error": "❌ ऐसा लगता है कि आपने अभी तक चैनल जॉइन नहीं किया है या मैं सत्यापित नहीं कर सका। कृपया @{channel_username} जॉइन करें और '✅ मैंने जॉइन कर लिया!' पर फिर से क्लिक करें।",
        "welcome": "🎉 *स्वागत है, {first_name}!* 🎉\n\nआपका वर्तमान बैलेंस है: *{balance:.2f} पॉइंट्स*\n\n_नीचे दिए गए मेनू से एक विकल्प चुनें:_ 👇",
        "earn_button": "🔗 पॉइंट्स कमाएँ",
        "profile_button": "👤 मेरी प्रोफ़ाइल",
        "invite_button": "👨‍👩‍👧‍👦 इनवाइट करें और कमाएँ",
        "withdraw_button": "💳 विथड्रॉ करें",
        "help_button": "❓ सहायता",
        "earn_options_prompt": "पॉइंट्स कमाने के लिए एक विकल्प चुनें:",
        "solve_shortlinks_button": "🔗 शॉर्टलिंक हल करें",
        "join_channels_button": "➕ चैनल/ग्रुप जॉइन करें",
        "shortlink_instructions": "📖 *शॉर्टलिंक से कमाई कैसे करें:*\n\n1. नीचे दिए गए शॉर्टलिंक पर क्लिक करें।\n2. वेबसाइट पर सभी चरणों (विज्ञापन देखें, कैप्चा हल करें आदि) को पूरा करें।\n3. सफलतापूर्वक पूरा करने के बाद, यहां '✅ मैंने पूरा कर लिया!' पर क्लिक करें।\n\nप्रत्येक पूर्ण शॉर्टलिंक के लिए आपको *{points_per_shortlink:.2f} पॉइंट्स* मिलेंगे।",
        "shortlink_unavailable": "😔 क्षमा करें, अभी शॉर्टलिंक नहीं मिल रहा है। कृपया बाद में पुनः प्रयास करें।",
        "shortlink_given": "🚀 यह रहा आपका शॉर्टलिंक!\n👉 {shortlink}\n\n*_शॉर्टलिंक पूरा करने के बाद 'मैंने पूरा कर लिया!' बटन पर क्लिक करें।_*",
        "shortlink_completed_button": "✅ मैंने पूरा कर लिया!",
        "no_shortlink_started": "🤔 आपने अभी तक कोई शॉर्टलिंक कार्य शुरू नहीं किया है। कृपया पहले 'शॉर्टलिंक हल करें' पर क्लिक करें।",
        "shortlink_completed": "✨ बधाई हो! आपने {points:.2f} पॉइंट्स कमाए!\n\nआपका नया बैलेंस: *{balance:.2f} पॉइंट्स*\nकुल हल किए गए शॉर्टलिंक्स: *{solved_count}*",
        "next_shortlink_button": "➡️ अगला शॉर्टलिंक",
        "channels_to_join_prompt": "यहां वे चैनल/ग्रुप दिए गए हैं जिन्हें आप पॉइंट्स कमाने के लिए जॉइन कर सकते हैं। प्रत्येक को जॉइन करने के बाद 'जॉइन किया और क्लेम करें' पर क्लिक करें।",
        "channel_already_claimed": "❌ आपने *{channel_username}* जॉइन करने के लिए पहले ही पॉइंट्स क्लेम कर लिए हैं।",
        "channel_not_joined": "😔 पॉइंट्स क्लेम करने के लिए आपको पहले *{channel_username}* जॉइन करना होगा।",
        "channel_claim_success": "✅ *{channel_username}* जॉइन करने के लिए आपने {points:.2f} पॉइंट्स कमाए!\n\nआपका नया बैलेंस: *{balance:.2f} पॉइंट्स*",
        "no_more_channels": "🎉 आपने सभी उपलब्ध चैनलों/ग्रुपों को जॉइन करके अपने पॉइंट्स क्लेम कर लिए हैं!",
        "joined_claim_button": "✅ जॉइन किया और क्लेम करें",
        "profile_text": "👤 *आपकी प्रोफ़ाइल:*\n\nनाम: *{first_name}*\nबैलेंस: *{balance:.2f} पॉइंट्स*\nहल किए गए शॉर्टलिंक्स: *{shortlinks_solved_count}*\nकुल रेफरल: *{referral_count}*\n\n_आपकी प्रोफ़ाइल पिक्चर ऊपर दिखाई गई है।_",
        "min_withdraw_balance": "⛔ *अपर्याप्त बैलेंस!* \n\nविथड्रॉ करने के लिए आपको कम से कम *{min_points:.2f} पॉइंट्स* ({min_rupees:.2f} रुपये) चाहिए।\nआपका वर्तमान बैलेंस: *{balance:.2f} पॉइंट्स*।\n\n_न्यूनतम तक पहुँचने के लिए और पॉइंट्स कमाएँ।_",
        "withdraw_prompt_amount": "💰 *विथड्रॉल राशि दर्ज करें*\n\nआपका वर्तमान बैलेंस: *{balance:.2f} पॉइंट्स*\nन्यूनतम विथड्रॉल: *{min_points:.2f} पॉइंट्स* ({min_rupees:.2f} रुपये)।\n\n_जितने पॉइंट्स आप विथड्रॉ करना चाहते हैं, वह राशि दर्ज करें:_",
        "invalid_amount": "❌ अमान्य राशि। कृपया एक वैध संख्या दर्ज करें।",
        "not_enough_points": "🚫 आपके पास इस विथड्रॉल के लिए पर्याप्त पॉइंट्स नहीं हैं। आपका बैलेंस: *{balance:.2f} पॉइंट्स*।",
        "withdraw_confirm_method": "💲 आप *{points:.2f} पॉइंट्स* (लगभग *{rupees:.2f} रुपये*) विथड्रॉ करना चाहते हैं।\n\nकृपया अपनी विथड्रॉल विधि चुनें:",
        "upi_method_button": "💳 यूपीआई (UPI)",
        "qr_method_button": "📱 क्यूआर कोड (QR Code)",
        "bank_method_button": "🏦 बैंक ट्रांसफर",
        "redeem_method_button": "🎁 रिडीम कोड (Google Play)",
        "invalid_method": "❌ अमान्य विथड्रॉल विधि चुनी गई।",
        "upi_prompt": "✍️ विथड्रॉल के साथ आगे बढ़ने के लिए कृपया अपनी **यूपीआई आईडी** (उदाहरण: `आपकानाम@बैंक`) भेजें।",
        "qr_prompt": "✍️ विथड्रॉल के साथ आगे बढ़ने के लिए कृपया अपनी **क्यूआर कोड इमेज** भेजें।",
        "bank_prompt": "✍️ विथड्रॉल के साथ आगे बढ़ने के लिए कृपया अपनी **बैंक खाता विवरण** (खाताधारक का नाम, खाता संख्या, IFSC कोड, बैंक का नाम) भेजें।",
        "redeem_prompt": "✍️ कृपया **गूगल प्ले रिडीम कोड का मूल्य** दर्ज करें (उदाहरण: `100 रुपये`, `250 रुपये`)।",
        "withdrawal_success": "✅ *विथड्रॉल रिक्वेस्ट सबमिट हो गई!* ✅\n\nराशि: *{points:.2f} पॉइंट्स* (लगभग *{rupees:.2f} रुपये*)\nविधि: *{method}*\nविवरण: *{details}*\n\nआपका शेष बैलेंस: *{balance:.2f} पॉइंट्स*।\n_आपकी रिक्वेस्ट प्रोसेस की जा रही है। कृपया 24-48 घंटे प्रतीक्षा करें।_",
        "withdrawal_error": "🚫 आपके विथड्रॉल में कुछ समस्या आ गई। कृपया पुनः प्रयास करें।",
        "command_usage": "⚠️ कृपया बटनों का उपयोग करके नेविगेट करें।",
        "referrer_joined": "🎉 *नया रेफरल!* 🎉\n\nआपका रेफरल `@{user_username}` बॉट में शामिल हो गया है!\n\n_आपने {referral_points_per_referral:.2f} पॉइंट्स कमाए हैं।_",
        "invalid_referrer": "🚫 अमान्य रेफरल लिंक या आप पहले ही रेफर किए जा चुके हैं।",
        "self_referral": "😅 आप खुद को रेफर नहीं कर सकते!",
        "referral_link_text": "👨‍👩‍👧‍👦 *अपने दोस्तों को इनवाइट करें और कमाएँ!* 👨‍👩‍👧‍👦\n\nयह लिंक साझा करें:\n`{referral_link}`\n\nआपके लिंक के माध्यम से जुड़ने वाले प्रत्येक दोस्त के लिए, आप *{referral_points_per_referral:.2f} पॉइंट्स* कमाएँगे!\n\nआपके कुल रेफरल: *{referral_count}*",
        "generic_error": "😔 एक अप्रत्याशित त्रुटि हुई। कृपया बाद में पुनः प्रयास करें या /start टाइप करके मुख्य मेनू पर जाएँ।",
        "action_not_valid": "⛔ वह कार्रवाई अभी मान्य नहीं है। कृपया मेनू बटनों का उपयोग करें।",
        "approve_button": "✅ मंज़ूर करें",
        "reject_button": "❌ ख़ारिज करें",
        "back_to_menu": "🏠 मुख्य मेनू पर वापस",
        "help_text": "❓ *सहायता और जानकारी*\n\nहमारे अर्निंग बॉट में आपका स्वागत है! यह ऐसे काम करता है:\n\n*1. पॉइंट्स कमाएँ:*\n   - *शॉर्टलिंक हल करें:* 'पॉइंट्स कमाएँ' -> 'शॉर्टलिंक हल करें' पर क्लिक करें। निर्देशों का पालन करें, शॉर्टलिंक पूरा करें, और पॉइंट्स कमाने के लिए 'मैंने पूरा कर लिया!' पर क्लिक करें।\n   - *चैनल/ग्रुप जॉइन करें:* 'पॉइंट्स कमाएँ' -> 'चैनल/ग्रुप जॉइन करें' पर क्लिक करें। सूचीबद्ध चैनलों/ग्रुपों को जॉइन करें और अपने पॉइंट्स एक बार क्लेम करें।\n\n*2. इनवाइट करें और कमाएँ:*\n   - अपना यूनिक रेफरल लिंक प्राप्त करने के लिए 'इनवाइट करें और कमाएँ' पर क्लिक करें। इसे दोस्तों के साथ साझा करें। आपको प्रत्येक सफल रेफरल के लिए पॉइंट्स मिलते हैं!\n\n*3. मेरी प्रोफ़ाइल:*\n   - अपना वर्तमान बैलेंस, हल किए गए कुल शॉर्टलिंक्स और रेफरल देखने के लिए 'मेरी प्रोफ़ाइल' पर क्लिक करें। आप यहां से विथड्रॉल भी शुरू कर सकते हैं।\n\n*4. विथड्रॉ करें:*\n   - 'विथड्रॉ करें' पर क्लिक करें। विथड्रॉ करने के लिए आपको कम से कम {min_points:.2f} पॉइंट्स ({min_rupees:.2f} रुपये) चाहिए।\n   - उन पॉइंट्स की संख्या दर्ज करें जिन्हें आप विथड्रॉ करना चाहते हैं। बॉट स्वचालित रूप से आपको रुपये में समकक्ष राशि दिखाएगा।\n   - अपनी पसंदीदा विधि चुनें: UPI, QR कोड, बैंक ट्रांसफर (1 पॉइंट = {upi_qr_bank_rate:.2f} रुपये) या गूगल प्ले रिडीम कोड (1 पॉइंट = {redeem_rate:.2f} रुपये)।\n   - आवश्यक विवरण प्रदान करें।\n   - आपकी रिक्वेस्ट प्रोसेसिंग के लिए एडमिन को भेज दी जाएगी।\n\n_यदि आपके कोई और प्रश्न हैं, तो कृपया बॉट एडमिन से संपर्क करें।_",
    }
}

WITHDRAWAL_STATUS_UPDATE_MESSAGES = {
    "en": {
        "approved": "✅ *Your withdrawal request has been APPROVED!* ✅\n\nAmount: *{points:.2f} Points* (approx. *{rupees:.2f} Rs*)\n\n_The payment should be processed shortly._",
        "rejected": "❌ *Your withdrawal request has been REJECTED!* ❌\n\nAmount: *{points:.2f} Points* (approx. *{rupees:.2f} Rs*)\n\n_Reason: There might be an issue with your details or eligibility. Please check and try again._",
        "already_processed": "⚠️ This withdrawal request has already been processed.",
    },
    "hi": {
        "approved": "✅ *आपकी विथड्रॉल रिक्वेस्ट मंज़ूर कर ली गई है!* ✅\n\nराशि: *{points:.2f} पॉइंट्स* (लगभग *{rupees:.2f} रुपये*)\n\n_भुगतान जल्द ही प्रोसेस हो जाएगा।_",
        "rejected": "❌ *आपकी विथड्रॉल रिक्वेस्ट ख़ारिज कर दी गई है!* ❌\n\nराशि: *{points:.2f} पॉइंट्स* (लगभग *{rupees:.2f} रुपये*)\n\n_कारण: आपके विवरण या पात्रता में कोई समस्या हो सकती है। कृपया जांच करें और पुनः प्रयास करें।_",
        "already_processed": "⚠️ यह विथड्रॉल रिक्वेस्ट पहले ही प्रोसेस हो चुकी है।",
    }
}

def get_text(user_id, key, **kwargs):
    """उपयोगकर्ता की भाषा या डिफ़ॉल्ट के आधार पर टेक्स्ट प्राप्त करता है।"""
    from database_utils import get_user_language # परिपत्र निर्भरता से बचने के लिए स्थानीय रूप से आयात करें

    user_lang = get_user_language(user_id)
    # उपयोगकर्ता की पसंदीदा भाषा से टेक्स्ट प्राप्त करने का प्रयास करें
    if user_lang in LANGUAGES and key in LANGUAGES[user_lang]:
        return LANGUAGES[user_lang][key].format(**kwargs)
    # डिफ़ॉल्ट भाषा पर वापस लौटें
    elif key in LANGUAGES[DEFAULT_LANGUAGE]:
        return LANGUAGES[DEFAULT_LANGUAGE][key].format(**kwargs)
    else:
        return f"KEY: {key} के लिए टेक्स्ट गुम है" # गुम टेक्स्ट के लिए फॉलबैक
