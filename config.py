# config.py

# --- Bot Token ---
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # <-- इसे अपने असली बॉटफादर टोकन से बदलें

# --- MongoDB Connection Strings ---
# MongoDB Instance 1 (यूज़र डेटा, बैलेंस, शॉर्टलिंक काउंट, भाषा के लिए)
MONGO_URI_1 = "YOUR_MONGODB_URI_1"  # <-- अपने पहले MongoDB URI से बदलें (e.g., "mongodb://localhost:27017/bot_db_1")
DB_NAME_1 = "bot_db_1"              # <-- अपने पहले डेटाबेस का नाम

# MongoDB Instance 2 (विथड्रॉल रिक्वेस्ट के लिए)
MONGO_URI_2 = "YOUR_MONGODB_URI_2"  # <-- अपने दूसरे MongoDB URI से बदलें (e.g., "mongodb://localhost:27017/bot_db_2")
DB_NAME_2 = "bot_db_2"              # <-- अपने दूसरे डेटाबेस का नाम

# --- Admin Notification Channel ---
ADMIN_WITHDRAWAL_CHANNEL_ID = -1001234567890  # <-- इसे अपने एडमिन चैनल की असली ID से बदलें (यह -100 से शुरू होती है)

# --- Shortlink API Configuration ---
SHORTLINK_API_URL = "https://api.shrtco.de/v2/shorten" # यह एक उदाहरण API है। इसे अपनी सेवा के URL से बदलें।
SHORTLINK_API_KEY = "YOUR_SHORTLINK_API_KEY_HERE"     # अपनी सेवा की API कुंजी (यदि आवश्यक हो)।

# --- Global Constants ---
POINTS_PER_SHORTLINK = 1.0  # प्रत्येक शॉर्टलिंक को सॉल्व करने पर यूज़र को 1 पॉइंट मिलता है

REFERRAL_POINTS_PER_30 = 10 # हर 30 रेफरल पर मिलने वाले पॉइंट्स
MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW = 20 # रेफरल और विथड्रॉल के लिए न्यूनतम शॉर्टलिंक संख्या
CHANNEL_JOIN_POINTS = 0.50  # चैनल जॉइन करने पर मिलने वाले पॉइंट्स

# --- Conversion Rate for Withdrawal ---
POINTS_TO_RUPEES_RATE = 0.50  # 1 पॉइंट = 0.50 रुपये
MIN_WITHDRAWAL_POINTS = 40    # विथड्रॉल के लिए न्यूनतम 40 पॉइंट्स (20 रुपये के बराबर)

# --- Channels to Join (एडमिन इसे कंट्रोल कर सकता है) ---
# अपनी वास्तविक चैनल लिंक से बदलें
CHANNELS_TO_JOIN = [
    {"name": "Movie Channel", "link": "https://t.me/your_movie_channel"},
    {"name": "Main Channel", "link": "https://t.me/your_main_channel"},
    {"name": "Another Channel", "link": "https://t.me/another_channel"},
]

DEFAULT_LANGUAGE = "en" # डिफ़ॉल्ट भाषा
