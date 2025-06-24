# config.py

# आपका टेलीग्राम बॉट टोकन (BotFather से प्राप्त करें)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # CHANGE_THIS_LINE: यहाँ अपना BotFather से मिला टोकन डालें

# निकासी सूचनाओं के लिए एडमिन चैनल ID (उदाहरण: -1001234567890)
# सुनिश्चित करें कि आपका बॉट इस चैनल में एक एडमिन है।
ADMIN_WITHDRAWAL_CHANNEL_ID = -1001234567890 # CHANGE_THIS_LINE: यहाँ अपने एडमिन निकासी चैनल की ID डालें

# अनिवार्य सदस्यता चैनल (उदाहरण: -1001234567890 या @username)
# यदि यूजरनेम का उपयोग कर रहे हैं, तो सदस्य्ता जांचने के लिए बॉट को एडमिन होना चाहिए।
# यदि ID का उपयोग कर रहे हैं, तो बॉट को एडमिन होने की आवश्यकता नहीं है।
FORCE_SUBSCRIBE_CHANNEL_ID = -1001234567890 # CHANGE_THIS_LINE: यहाँ अनिवार्य सदस्यता चैनल की ID डालें
FORCE_SUBSCRIBE_CHANNEL_USERNAME = "ASBHAI_BSR" # CHANGE_THIS_LINE: यहाँ अनिवार्य सदस्यता चैनल का यूजरनेम डालें (जैसे, "YOUR_CHANNEL_USERNAME")

# शॉर्टलिंक API कॉन्फ़िगरेशन
# इसे अपने वास्तविक शॉर्टलिंक API एंडपॉइंट और कुंजी से बदलें।
# महत्वपूर्ण: आपके शॉर्टलिंक प्रदाता को वेरिफिकेशन के लिए Callbacks/Webhooks का समर्थन करना चाहिए।
# यदि आपके शॉर्टलिंक API को कॉलबैक के लिए विशिष्ट पैरामीटर की आवश्यकता है,
# तो आपको bot.py में fetch_new_shortlink_from_api फ़ंक्शन और वेबहुक हैंडलर को एडजस्ट करना होगा।
# Arlinks.in API के लिए:
SHORTLINK_API_URL = "https://arlinks.in/api"
SHORTLINK_API_KEY = "YOUR_ARLINKS_IN_API_KEY_HERE" # CHANGE_THIS_LINE: अपनी arlinks.in डैशबोर्ड से अपनी API कुंजी प्राप्त करें और यहाँ डालें

# कमाई पॉइंट्स कॉन्फ़िगरेशन
POINTS_PER_SHORTLINK = 10.0  # प्रत्येक शॉर्टलिंक हल करने पर अर्जित अंक
REFERRAL_POINTS_PER_REFERRAL = 0.80 # जब कोई नया उपयोगकर्ता उनके लिंक के माध्यम से जुड़ता है तो रेफरर को मिलने वाले अंक
POINTS_PER_CHANNEL_JOIN = 5.0 # चैनल/समूह में शामिल होने पर अर्जित अंक

# पॉइंट्स के लिए शामिल होने वाले चैनलों/समूहों की सूची (फॉर्मेट: [(-100XXXXXXXXXX, "CHANNEL_USERNAME")])
# उपयोगकर्ता को पॉइंट्स प्राप्त करने के लिए इन्हें एक बार जॉइन करना होगा। आवश्यकतानुसार और जोड़ें।
# सदस्य्ता जांचने के लिए बॉट को इनमें एडमिन होना चाहिए।
JOIN_TO_EARN_CHANNELS = [
    (-1001234567891, "ISTREAMX"), # CHANGE_THIS_LINE: यहाँ अपने चैनल की ID और यूजरनेम डालें
    # (-100XXXXXXXXX, "AnotherChannelUsername"), # आवश्यकतानुसार और जोड़ें
]

# निकासी कॉन्फ़िगरेशन
MIN_WITHDRAWAL_POINTS = 50.0 # निकालने के लिए आवश्यक न्यूनतम अंक (उदाहरण: 50 अंक)

# रूपांतरण दरें: 1 पॉइंट = X रुपये
UPI_QR_BANK_POINTS_TO_RUPEES_RATE = 0.40 # 50 पॉइंट्स = 20 रुपये (50 * 0.40)
REDEEM_CODE_POINTS_TO_RUPEES_RATE = 0.50 # 300 पॉइंट्स = 150 रुपये (300 * 0.50)

# MongoDB कॉन्फ़िगरेशन
# Koyeb के लिए, अपनी MongoDB Atlas कनेक्शन स्ट्रिंग का उपयोग करें।
MONGO_URI = "YOUR_MONGODB_ATLAS_URI_HERE" # CHANGE_THIS_LINE: यहाँ अपनी MongoDB Atlas कनेक्शन स्ट्रिंग डालें
DB_NAME = "your_shortlink_bot_db" # CHANGE_THIS_LINE: अपने डेटाबेस का नाम चुनें (या इसे डिफ़ॉल्ट रहने दें)

# Koyeb डिप्लॉयमेंट के लिए वेबहुक कॉन्फ़िगरेशन
WEBHOOK_URL = "https://rotten-barbette-asmwasearchbot-64f1c2e9.koyeb.app/webhook" # CHANGE_THIS_LINE: यहाँ अपनी Koyeb ऐप का URL डालें (जो मैंने आपको पहले दिया था)
# यह URL डिप्लॉयमेंट के बाद Koyeb द्वारा प्रदान किया जाएगा। आपको इसे config.py में अपडेट करना होगा
# और फिर से डिप्लॉय करना होगा या इसे Koyeb में सीक्रेट के रूप में सेट करना होगा (उत्पादन के लिए अनुशंसित)।

# बॉट के लिए डिफ़ॉल्ट भाषा सेटिंग
DEFAULT_LANGUAGE = "en" # <--- यह नई लाइन है जिसे आपको जोड़ना है
