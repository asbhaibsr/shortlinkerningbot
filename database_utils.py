# database_utils.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime
from config import MONGO_URI, DB_NAME, DEFAULT_LANGUAGE
import logging

logger = logging.getLogger(__name__)

# MongoDB क्लाइंट और कलेक्शन (आसान पहुंच के लिए ग्लोबल)
client = None
db = None
users_collection = None
withdrawal_requests_collection = None

def init_db():
    """MongoDB कनेक्शन और कलेक्शन को इनिशियलाइज़ करता है।"""
    global client, db, users_collection, withdrawal_requests_collection
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping') # कनेक्शन का परीक्षण करें
        db = client[DB_NAME]
        users_collection = db["users"]
        withdrawal_requests_collection = db["withdrawal_requests"]
        logger.info("MongoDB कनेक्शन सफल!")

        # यदि मौजूद नहीं है तो user_id के लिए अद्वितीय इंडेक्स बनाएं
        if "user_id_1" not in users_collection.index_information():
            users_collection.create_index("user_id", unique=True)
            logger.info("उपयोगकर्ता संग्रह में user_id के लिए अद्वितीय इंडेक्स बनाया गया।")

    except ConnectionFailure as e:
        logger.error(f"MongoDB कनेक्शन विफल: {e}. कृपया अपनी MongoDB URI जांचें और सुनिश्चित करें कि इंस्टेंस चल रहा है।")
        # एप्लिकेशन से बाहर निकलें या शालीनता से हैंडल करें
        import sys
        sys.exit(1)
    except Exception as e:
        logger.error(f"MongoDB इनिशियलाइज़ेशन के दौरान एक अप्रत्याशित त्रुटि हुई: {e}")
        import sys
        sys.exit(1)

def get_user_data(user_id: int):
    """
    उपयोगकर्ता डेटा प्राप्त करता है। यदि उपयोगकर्ता मौजूद नहीं है, तो एक नई एंट्री बनाता है।
    नए और मौजूदा उपयोगकर्ताओं के लिए सभी आवश्यक फ़ील्ड मौजूद हैं, यह सुनिश्चित करता है।
    """
    if users_collection is None:
        init_db() # सुनिश्चित करें कि मुख्य से पहले कॉल किए जाने पर DB इनिशियलाइज़ हो जाए

    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        # नया उपयोगकर्ता निर्माण
        new_user = {
            "user_id": user_id,
            "balance": 0.0,
            "shortlinks_solved_count": 0,
            "referral_count": 0,
            "referred_by": None,
            "last_given_shortlink": None,
            "language": DEFAULT_LANGUAGE,
            "joined_channels": [], # पॉइंट्स के लिए क्लेम किए गए चैनल_आईडी की सूची
            "joined_at": datetime.now()
        }
        users_collection.insert_one(new_user)
        logger.info(f"DB में नया उपयोगकर्ता {user_id} बनाया गया।")
        return new_user
    else:
        # सुनिश्चित करें कि मौजूदा उपयोगकर्ताओं के लिए सभी आवश्यक फ़ील्ड मौजूद हैं (पिछली संगतता के लिए)
        updated = False
        if "referred_by" not in user_data:
            user_data["referred_by"] = None
            updated = True
        if "language" not in user_data:
            user_data["language"] = DEFAULT_LANGUAGE
            updated = True
        if "last_given_shortlink" not in user_data:
            user_data["last_given_shortlink"] = None
            updated = True
        if "joined_channels" not in user_data:
            user_data["joined_channels"] = []
            updated = True

        if updated:
            users_collection.update_one({"user_id": user_id}, {"$set": user_data})
            logger.info(f"उपयोगकर्ता {user_id} डेटा नए फ़ील्ड के साथ माइग्रेट/अपडेट किया गया।")

        return user_data

def update_user_data(user_id: int, balance_change: float = 0,
                     shortlinks_solved_change: int = 0,
                     referral_count_change: int = 0,
                     set_referred_by: int = None,
                     new_last_shortlink: str = None,
                     add_joined_channel: int = None): # जॉइन किए गए चैनलों के लिए नया पैरामीटर
    """डेटाबेस में उपयोगकर्ता डेटा अपडेट करता है।"""
    if users_collection is None:
        init_db()

    update_fields = {}
    if balance_change != 0:
        update_fields["$inc"] = {"balance": balance_change}
    if shortlinks_solved_change != 0:
        update_fields.setdefault("$inc", {})["shortlinks_solved_count"] = shortlinks_solved_change
    if referral_count_change != 0:
        update_fields.setdefault("$inc", {})["referral_count"] = referral_count_change
    if set_referred_by is not None:
        update_fields.setdefault("$set", {})["referred_by"] = set_referred_by
    if new_last_shortlink is not None:
        update_fields.setdefault("$set", {})["last_given_shortlink"] = new_last_shortlink
    if add_joined_channel is not None:
        # आइटम को केवल तभी जोड़ने के लिए $addToSet का उपयोग करना जब वह पहले से मौजूद न हो
        update_fields.setdefault("$addToSet", {})["joined_channels"] = add_joined_channel

    if update_fields:
        users_collection.update_one({"user_id": user_id}, update_fields)
        logger.info(f"उपयोगकर्ता {user_id} डेटा अपडेट किया गया: {update_fields}")

def set_user_language(user_id: int, lang_code: str):
    """उपयोगकर्ता की पसंदीदा भाषा सेट करता है।"""
    if users_collection is None:
        init_db()
    users_collection.update_one({"user_id": user_id}, {"$set": {"language": lang_code}}, upsert=True)
    logger.info(f"उपयोगकर्ता {user_id} की भाषा {lang_code} पर सेट की गई।")

def get_user_language(user_id: int):
    """उपयोगकर्ता की पसंदीदा भाषा प्राप्त करता है, या यदि सेट नहीं है तो डिफ़ॉल्ट।"""
    if users_collection is None:
        init_db()
    user_data = users_collection.find_one({"user_id": user_id}, {"language": 1})
    return user_data.get("language", DEFAULT_LANGUAGE) if user_data else DEFAULT_LANGUAGE

def record_withdrawal_request(user_id: int, amount_points: float, amount_rupees: float, method: str, details: str, qr_photo_file_id: str = None):
    """एक नई निकासी रिक्वेस्ट रिकॉर्ड करता है।"""
    if withdrawal_requests_collection is None:
        init_db()

    withdrawal_request = {
        "user_id": user_id,
        "amount_points": amount_points,
        "amount_rupees": amount_rupees,
        "method": method,
        "details": details,
        "qr_photo_file_id": qr_photo_file_id, # यदि QR कोड है तो file_id स्टोर करें
        "status": "pending", # लंबित, स्वीकृत, अस्वीकृत
        "requested_at": datetime.now(),
        "processed_by_admin_id": None,
        "processed_timestamp": None,
        "admin_channel_message_id": None, # एडमिन चैनल में मैसेज अपडेट करने के लिए
        "admin_channel_chat_id": None
    }
    result = withdrawal_requests_collection.insert_one(withdrawal_request)
    logger.info(f"उपयोगकर्ता {user_id} के लिए निकासी रिक्वेस्ट रिकॉर्ड की गई। ID: {result.inserted_id}")
    return result.inserted_id # डाले गए डॉक्यूमेंट की ObjectId लौटाएं

def update_withdrawal_request_status(request_id, status, admin_id, admin_message_id, admin_chat_id):
    """निकासी रिक्वेस्ट की स्थिति अपडेट करता है।"""
    if withdrawal_requests_collection is None:
        init_db()
    
    withdrawal_requests_collection.update_one(
        {"_id": request_id},
        {"$set": {
            "status": status,
            "processed_by_admin_id": admin_id,
            "processed_timestamp": datetime.now(),
            "admin_channel_message_id": admin_message_id,
            "admin_channel_chat_id": admin_chat_id
        }}
    )
    logger.info(f"निकासी रिक्वेस्ट {request_id} की स्थिति एडमिन {admin_id} द्वारा {status} में अपडेट की गई।")
