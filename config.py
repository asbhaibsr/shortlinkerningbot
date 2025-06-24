# config.py

# आपका टेलीग्राम बॉट टोकन (BotFather से प्राप्त करें)
BOT_TOKEN = "8084485088:AAHUCtZyDcY5hcVFsW-5JfWubD4y058bByw" # (या Koyeb से ली गई वैल्यू)

# निकासी सूचनाओं के लिए एडमिन चैनल ID
ADMIN_WITHDRAWAL_CHANNEL_ID = -1002703675582 # (Koyeb से ली गई वैल्यू)

# अनिवार्य सदस्यता चैनल
FORCE_SUBSCRIBE_CHANNEL_ID = -1002283182645 # (Koyeb से ली गई वैल्यू)
FORCE_SUBSCRIBE_CHANNEL_USERNAME = "asbhai_bsr" # (Koyeb से ली गई वैल्यू)

# शॉर्टलिंक API कॉन्फ़िगरेशन
SHORTLINK_API_URL = "https://arlinks.in/api"
SHORTLINK_API_KEY = "50caa11e0df0429f55ee2b43f0ff3d5cdee28a" # (Koyeb से ली गई वैल्यू)

# कमाई पॉइंट्स कॉन्फ़िगरेशन
POINTS_PER_SHORTLINK = 10.0
REFERRAL_POINTS_PER_REFERRAL = 0.80
POINTS_PER_CHANNEL_JOIN = 5.0

# पॉइंट्स के लिए शामिल होने वाले चैनलों/समूहों की सूची
JOIN_TO_EARN_CHANNELS = [
    (-1001234567891, "ISTREAMX"),
]

# निकासी कॉन्फ़िगरेशन
MIN_WITHDRAWAL_POINTS = 50.0

# रूपांतरण दरें
UPI_QR_BANK_POINTS_TO_RUPEES_RATE = 0.40
REDEEM_CODE_POINTS_TO_RUPEES_RATE = 0.50

# MongoDB कॉन्फ़िगरेशन
MONGO_URI = "mongodb+srv://xonide3955:U9C9hrp7yABlbUeq@cluster0.nscd3zg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" # <--- इस लाइन को सही MongoDB URI के साथ जोड़ें/अनकमेंट करें
DB_NAME = "your_shortlink_bot_db"

# Koyeb डिप्लॉयमेंट के लिए वेबहुक कॉन्फ़िगरेशन
WEBHOOK_URL = "https://rotten-barbette-asmwasearchbot-64f1c2e9.koyeb.app/webhook"

# बॉट के लिए डिफ़ॉल्ट भाषा सेटिंग
DEFAULT_LANGUAGE = "en"
