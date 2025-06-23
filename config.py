# config.py

# Bot Token from BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" 

# Admin Channel ID for withdrawal notifications (e.g., -1001234567890)
ADMIN_WITHDRAWAL_CHANNEL_ID = -1001234567890 

# Shortlink API Configuration
SHORTLINK_API_URL = "YOUR_SHORTLINK_API_ENDPOINT" # Example: "https://some-shortener.com/api/v1/shorten"
SHORTLINK_API_KEY = "YOUR_SHORTLINK_API_KEY" # Leave empty string if no API key is needed: ""

# Earning Points Configuration
POINTS_PER_SHORTLINK = 10.0 # Points earned per shortlink solved
REFERRAL_POINTS_PER_30 = 50.0 # Points referrer gets when their referral solves 30 shortlinks
MIN_SHORTLINKS_FOR_REFERRAL_WITHDRAW = 50 # Minimum shortlinks a user needs to solve for referral points to be withdrawable

CHANNEL_JOIN_POINTS = 20.0 # Points earned for joining a channel

# Withdrawal Configuration
POINTS_TO_RUPEES_RATE = 0.01 # 1 point = 0.01 Rupee (100 points = 1 Rupee)
MIN_WITHDRAWAL_POINTS = 500.0 # Minimum points required to withdraw (e.g., 500 points = 5 Rs)

# Channels to Join for Tasks (List of dictionaries)
# 'id' is the channel's numerical ID (e.g., -1001234567890) - IMPORTANT for get_chat_member
# 'name' is a user-friendly name for the channel
# 'link' is the invite link for the channel
CHANNELS_TO_JOIN = [
    {"id": -1001234567891, "name": "Official Channel 1", "link": "https://t.me/your_channel_link_1"},
    {"id": -1001234567892, "name": "Announcements Channel", "link": "https://t.me/your_channel_link_2"},
    # Add more channels as needed
]

# MongoDB Configuration
MONGO_URI = "mongodb://localhost:27017/" # Or your MongoDB Atlas connection string
MONGO_DB_NAME = "your_bot_db" # Name of your database
