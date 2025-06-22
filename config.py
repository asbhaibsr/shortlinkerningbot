# config.py
import os

# --- Bot Token ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE") # <-- यह लाइन ऐसी होनी चाहिए

# --- MongoDB Connection Strings ---
MONGO_URI_1 = os.environ.get("MONGO_URI_1", "YOUR_MONGODB_URI_1") # <-- यह लाइन ऐसी होनी चाहिए
DB_NAME_1 = os.environ.get("DB_NAME_1", "bot_db_1")

MONGO_URI_2 = os.environ.get("MONGO_URI_2", "YOUR_MONGODB_URI_2") # <-- यह लाइन ऐसी होनी चाहिए
DB_NAME_2 = os.environ.get("DB_NAME_2", "bot_db_2")

# --- Admin Notification Channel ---
ADMIN_WITHDRAWAL_CHANNEL_ID = int(os.environ.get("ADMIN_WITHDRAWAL_CHANNEL_ID", "-1002703675582")) # <-- यह लाइन ऐसी होनी चाहिए

# --- Shortlink API Configuration ---
SHORTLINK_API_URL = os.environ.get("SHORTLINK_API_URL", "dashboard.smallshorts.com")
SHORTLINK_API_KEY = os.environ.get("SHORTLINK_API_KEY", "4ca8f20ebd8b02f6fe1f55eb1e49136f69e2f5a0")

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
    {"name": "Movie Channel", "link": "https://t.me/IstreamX"},
    {"name": "Main Channel", "link": "https://t.me/asbhai_bsr"},
    {"name": "Another Channel", "link": "https://t.me/aspremiumapps"},
]

DEFAULT_LANGUAGE = "en" # डिफ़ॉल्ट भाषा
