# database_utils.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime
from bson.objectid import ObjectId

# config.py से आवश्यक कॉन्फ़िगरेशन इंपोर्ट करें
from config import (
    MONGO_URI_1, DB_NAME_1, MONGO_URI_2, DB_NAME_2, DEFAULT_LANGUAGE
)

# MongoDB क्लाइंट्स (बाद में init_db में इनिशियलाइज़ किए जाएंगे)
client1 = None
db1 = None
users_collection = None

client2 = None
db2 = None
withdrawal_requests_collection = None

# --- MongoDB कनेक्शन इनिशियलाइज़ेशन ---
def init_db():
    global client1, db1, users_collection
    global client2, db2, withdrawal_requests_collection

    try:
        # Client 1 for user data, balance, shortlink counts, languages
        client1 = MongoClient(MONGO_URI_1, serverSelectionTimeoutMS=5000)
        client1.admin.command('ping') # कनेक्शन टेस्ट करें
        db1 = client1[DB_NAME_1]
        users_collection = db1["users"]
        # यूज़र_आईडी पर तेज़ लुकअप के लिए यूनिक इंडेक्स सुनिश्चित करें
        users_collection.create_index("user_id", unique=True)
        print("Connected to MongoDB Instance 1 (User Data) successfully!")

        # Client 2 for withdrawal requests
        client2 = MongoClient(MONGO_URI_2, serverSelectionTimeoutMS=5000)
        client2.admin.command('ping') # कनेक्शन टेस्ट करें
        db2 = client2[DB_NAME_2]
        withdrawal_requests_collection = db2["withdrawal_requests"]
        # त्वरित लुकअप के लिए _id पर और फ़िल्टरिंग के लिए स्टेटस पर इंडेक्स सुनिश्चित करें
        withdrawal_requests_collection.create_index("_id", unique=True)
        withdrawal_requests_collection.create_index("status")
        print("Connected to MongoDB Instance 2 (Withdrawal Data) successfully!")

    except ConnectionFailure as e:
        print(f"MongoDB connection failed: {e}. कृपया अपने MongoDB URIs की जाँच करें और सुनिश्चित करें कि इंस्टेंस चल रहे हैं।")
        exit(1) # यदि डेटाबेस से कनेक्ट नहीं हो सकता तो बाहर निकलें
    except OperationFailure as e:
        print(f"MongoDB ऑपरेशन इनिशियलाइज़ेशन के दौरान विफल रहा (जैसे, प्रमाणीकरण त्रुटि): {e}")
        exit(1)
    except Exception as e:
        print(f"DB इनिशियलाइज़ेशन के दौरान एक अप्रत्याशित त्रुटि हुई: {e}")
        exit(1)

# --- डेटाबेस इंटरैक्शन के लिए यूटिलिटी फ़ंक्शंस ---

def get_user_data(user_id):
    # डेटा इंस्टेंस 1 से आता है
    user_doc = users_collection.find_one({"user_id": user_id})
    if not user_doc:
        # यदि यूज़र मौजूद नहीं है, तो डिफ़ॉल्ट मानों के साथ एक नया दस्तावेज़ डालें
        new_user = {
            "user_id": user_id,
            "balance": 0.0,
            "shortlinks_solved_count": 0,
            "last_given_shortlink": None,
            "referred_by": None,
            "referral_count": 0,
            "channel_joined_count": 0,
            "claimed_channel_ids": [], # MongoDB में एक सूची के रूप में संग्रहीत
            "language": DEFAULT_LANGUAGE
        }
        users_collection.insert_one(new_user)
        user_doc = new_user
    
    # सुनिश्चित करें कि claimed_channel_ids एक सूची है
    if 'claimed_channel_ids' not in user_doc or not isinstance(user_doc['claimed_channel_ids'], list):
        user_doc['claimed_channel_ids'] = []

    return {
        "balance": user_doc.get("balance", 0.0),
        "shortlinks_solved_count": user_doc.get("shortlinks_solved_count", 0),
        "last_given_shortlink": user_doc.get("last_given_shortlink", None),
        "referred_by": user_doc.get("referred_by", None),
        "referral_count": user_doc.get("referral_count", 0),
        "channel_joined_count": user_doc.get("channel_joined_count", 0),
        "claimed_channel_ids": user_doc.get("claimed_channel_ids", []),
        "language": user_doc.get("language", DEFAULT_LANGUAGE)
    }

def update_user_data(user_id, balance_change=0, shortlinks_solved_change=0, new_last_shortlink=None, referral_count_change=0, channel_joined_change=0, add_claimed_channel_id=None, set_referred_by=None):
    # यह इंस्टेंस 1 में यूज़र डेटा को अपडेट करता है
    update_fields = {}
    if balance_change != 0:
        update_fields["balance"] = balance_change
    if shortlinks_solved_change != 0:
        update_fields["shortlinks_solved_count"] = shortlinks_solved_change
    if referral_count_change != 0:
        update_fields["referral_count"] = referral_count_change
    if channel_joined_change != 0:
        update_fields["channel_joined_count"] = channel_joined_change

    set_fields = {}
    if new_last_shortlink is not None:
        set_fields["last_given_shortlink"] = new_last_shortlink
    if set_referred_by is not None:
        set_fields["referred_by"] = set_referred_by

    update_query = {}
    if update_fields:
        update_query["$inc"] = update_fields # मौजूदा मानों में वृद्धि करें
    if set_fields:
        update_query["$set"] = set_fields # नए मान सेट करें
    if add_claimed_channel_id is not None:
        update_query["$addToSet"] = {"claimed_channel_ids": str(add_claimed_channel_id)} # यदि मौजूद न हो तो ऐरे में जोड़ें

    if update_query:
        users_collection.update_one({"user_id": user_id}, update_query, upsert=True)

def record_withdrawal_request(user_id, amount_points, amount_rupees, method, details):
    # विथड्रॉल रिक्वेस्ट इंस्टेंस 2 में जाती हैं
    result = withdrawal_requests_collection.insert_one({
        "user_id": user_id,
        "amount_points": amount_points,
        "amount_rupees": amount_rupees,
        "method": method,
        "details": details,
        "status": "pending",
        "timestamp": datetime.now(),
        "admin_channel_message_id": None, # इसे बाद में अपडेट किया जाएगा
        "admin_channel_chat_id": None    # इसे बाद में अपडेट किया जाएगा
    })
    return result.inserted_id # ObjectId लौटाएँ

# --- भाषा यूटिलिटी फ़ंक्शंस ---
def set_user_language(user_id, lang_code):
    # भाषा अपडेट इंस्टेंस 1 में होते हैं
    users_collection.update_one({"user_id": user_id}, {"$set": {"language": lang_code}})

def get_user_language(user_id):
    # भाषा इंस्टेंस 1 से प्राप्त की जाती है
    user_doc = users_collection.find_one({"user_id": user_id}, {"language": 1})
    return user_doc.get("language", DEFAULT_LANGUAGE) if user_doc else DEFAULT_LANGUAGE

# डमी set_user_referred_by को पिछली कोड संरचना के अनुरूप बनाने के लिए,
# हालाँकि इसका लॉजिक अब update_user_data के अंदर है
def set_user_referred_by(user_id, referrer_id):
    update_user_data(user_id, set_referred_by=referrer_id)
