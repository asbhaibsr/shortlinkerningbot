# config.py

# Bot Token from BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # यहां अपने बॉट का टोकन डालें

# Admin Channel ID for withdrawal notifications (e.g., -1001234567890)
ADMIN_WITHDRAWAL_CHANNEL_ID = -1001234567890 # विथड्रॉल नोटिफिकेशन के लिए अपने एडमिन चैनल का ID डालें

# Shortlink API Configuration
SHORTLINK_API_URL = "YOUR_SHORTLINK_API_ENDPOINT" # अपनी शॉर्टलिंक API का एंडपॉइंट URL डालें (उदाहरण: "https://some-shortener.com/api/v1/shorten")
SHORTLINK_API_KEY = "YOUR_SHORTLINK_API_KEY" # अपनी शॉर्टलिंक API कुंजी डालें (यदि आवश्यक हो, नहीं तो "" छोड़ दें)

# Earning Points Configuration
POINTS_PER_SHORTLINK = 10.0 # एक शॉर्टलिंक हल करने पर मिलने वाले पॉइंट
REFERRAL_POINTS_PER_30 = 50.0 # जब रेफर किया गया यूज़र 30 शॉर्टलिंक हल करता है तो रेफर करने वाले को मिलने वाले पॉइंट
MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW = 50 # विथड्रॉल के लिए रेफरल पॉइंट प्राप्त करने हेतु यूज़र द्वारा हल किए जाने वाले न्यूनतम शॉर्टलिंक

CHANNEL_JOIN_POINTS = 20.0 # चैनल जॉइन करने पर मिलने वाले पॉइंट

# Withdrawal Configuration
POINTS_TO_RUPEES_RATE = 0.01 # 1 पॉइंट = 0.01 रुपये (यानी 100 पॉइंट = 1 रुपया)
MIN_WITHDRAWAL_POINTS = 500.0 # विथड्रॉल के लिए आवश्यक न्यूनतम पॉइंट (उदाहरण: 500 पॉइंट = 5 रुपये)

# Channels to Join for Tasks (List of dictionaries)
# 'id' is the channel's numerical ID (e.g., -1001234567890) - Telegram API से get_chat_member() के लिए महत्वपूर्ण
# 'name' is a user-friendly name for the channel
# 'link' is the invite link for the channel
CHANNELS_TO_JOIN = [
    {"id": -1001234567891, "name": "Official Channel 1", "link": "https://t.me/your_channel_link_1"}, # अपने चैनल का ID और लिंक डालें
    {"id": -1001234567892, "name": "Announcements Channel", "link": "https://t.me/your_channel_link_2"}, # अपने चैनल का ID और लिंक डालें
    # आवश्यकतानुसार और चैनल जोड़ें
]

# MongoDB Configuration for Instance 1 (पहला MongoDB इंस्टेंस)
# यदि आप एक ही MongoDB डेटाबेस का उपयोग कर रहे हैं, तो MONGO_URI_1 और DB_NAME_1 को अपनी मुख्य सेटिंग्स पर सेट करें।
# MONGO_URI_2 और DB_NAME_2 को MONGO_URI_1 और DB_NAME_1 के समान मान पर सेट कर सकते हैं यदि एक ही डीबी है।
MONGO_URI_1 = "mongodb://localhost:27017/" # या अपनी पहली MongoDB Atlas कनेक्शन स्ट्रिंग डालें
DB_NAME_1 = "your_bot_db_1" # अपने पहले डेटाबेस का नाम डालें

# MongoDB Configuration for Instance 2 (दूसरा MongoDB इंस्टेंस)
# यदि आपको केवल एक डेटाबेस की आवश्यकता है, तो MONGO_URI_2 को MONGO_URI_1 के समान सेट करें
# और DB_NAME_2 को DB_NAME_1 के समान सेट करें।
MONGO_URI_2 = "mongodb://localhost:27017/" # या अपनी दूसरी MongoDB Atlas कनेक्शन स्ट्रिंग डालें
DB_NAME_2 = "your_bot_db_2" # अपने दूसरे डेटाबेस का नाम डालें

# Default Language (डिफ़ॉल्ट भाषा)
DEFAULT_LANGUAGE = "en" # बॉट के लिए डिफ़ॉल्ट भाषा कोड (जैसे "en" अंग्रेजी के लिए, "hi" हिंदी के लिए)
