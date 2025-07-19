import os
import logging
import asyncio
import random
from datetime import datetime, timedelta
from threading import Thread

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
)

from pymongo import MongoClient
from flask import Flask, jsonify # Import Flask and jsonify

# Configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))
CONTENT_CHANNEL_ID = int(os.getenv("CONTENT_CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))

DB_NAME = "telegram_games_db"

# Initialize Pyrogram Client
app = Client(
    "game_bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Initialize Flask app for health check
flask_app = Flask(__name__) # Keep this at the top level

# Flask routes for health check ONLY
@flask_app.route('/')
def home():
    return "Bot is running!"

@flask_app.route('/healthz')
def health_check():
    return jsonify({"status": "healthy"}), 200

# MongoDB setup
mongo_client = None
db = None
users_collection = None
groups_collection = None
game_states_collection = None
channel_content_cache_collection = None

def init_mongo():
    global mongo_client, db, users_collection, groups_collection, game_states_collection, channel_content_cache_collection
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client[DB_NAME]
        users_collection = db["users"]
        groups_collection = db["groups"]
        game_states_collection = db["game_states"]
        channel_content_cache_collection = db["channel_content_cache"]
        logger.info("MongoDB initialized successfully")
    except Exception as e:
        logger.critical(f"MongoDB connection failed: {e}")
        raise

# Game constants
GAME_QUIZ = "Quiz / Trivia"
GAME_WORDCHAIN = "Shabd Shrinkhala"
GAME_GUESSING = "Andaaz Lagaao"
GAME_NUMBER_GUESSING = "Sankhya Anuamaan"

GAMES_LIST = [
    (GAME_QUIZ, "quiz"),
    (GAME_WORDCHAIN, "wordchain"),
    (GAME_GUESSING, "guessing"),
    (GAME_NUMBER_GUESSING, "number_guessing")
]

active_games = {}

# Helper functions
async def get_channel_content(game_type: str):
    """Fetch content for a specific game type from MongoDB"""
    # Corrected check: compare with None
    if channel_content_cache_collection is None:
        logger.error("Channel content collection not initialized")
        return []

    try:
        content = list(channel_content_cache_collection.find({"game_type": game_type}))
        if not content:
            logger.warning(f"No content found for game type: {game_type}")
        return content
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        return []

async def update_user_score(user_id: int, username: str, group_id: int, points: int):
    """Update user score in MongoDB"""
    # Corrected check: compare with None
    if users_collection is None:
        logger.error("Users collection not initialized")
        return

    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"total_score": points, f"group_scores.{group_id}": points},
             "$set": {"username": username, "last_updated": datetime.utcnow()}},
            upsert=True
        )
        logger.info(f"Updated score for user {username} ({user_id})")
    except Exception as e:
        logger.error(f"Error updating score: {e}")

async def get_leaderboard(group_id: int = None):
    """Fetch leaderboard from MongoDB"""
    # Corrected check: compare with None
    if users_collection is None:
        logger.error("Users collection not initialized")
        return []

    try:
        if group_id:
            return list(users_collection.find().sort(f"group_scores.{group_id}", -1).limit(10))
        return list(users_collection.find().sort("total_score", -1).limit(10))
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return []

async def is_admin(chat_id: int, user_id: int, client: Client):
    """Check if user is admin in a chat"""
    try:
        chat_member = await client.get_chat_member(chat_id, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def save_game_state(chat_id: int):
    """Save game state to MongoDB"""
    # Corrected check: compare with None
    if game_states_collection is None or chat_id not in active_games:
        return

    try:
        game_state = active_games[chat_id].copy()
        if "timer_task" in game_state:
            del game_state["timer_task"]

        game_states_collection.update_one(
            {"_id": chat_id},
            {"$set": game_state},
            upsert=True
        )
        logger.info(f"Saved game state for chat {chat_id}")
    except Exception as e:
        logger.error(f"Error saving game state: {e}")

async def load_game_states():
    """Load active games from MongoDB"""
    global active_games
    # Corrected check: compare with None
    if game_states_collection is None:
        logger.error("Game states collection not initialized")
        return

    try:
        active_games = {doc["_id"]: doc for doc in game_states_collection.find()}
        logger.info(f"Loaded {len(active_games)} active games")
    except Exception as e:
        logger.error(f"Error loading game states: {e}")

async def auto_end_game(chat_id: int, client: Client):
    """Automatically end inactive games"""
    while chat_id in active_games and active_games[chat_id]["status"] == "in_progress":
        game_state = active_games.get(chat_id)
        if not game_state:
            break

        last_activity = game_state.get("last_activity_time", datetime.utcnow())
        if (datetime.utcnow() - last_activity).total_seconds() >= 300:  # 5 minutes
            await client.send_message(chat_id, "Game auto-ended due to inactivity")
            del active_games[chat_id]
            # Corrected check: compare with None
            if game_states_collection is not None:
                game_states_collection.delete_one({"_id": chat_id})
            logger.info(f"Auto-ended game in chat {chat_id}")
            break

        await asyncio.sleep(30)

# Game management functions
async def start_game_countdown(chat_id: int, game_type: str, message: Message, client: Client):
    """Countdown before game starts"""
    await asyncio.sleep(60)

    if chat_id in active_games and active_games[chat_id]["status"] == "waiting_for_players":
        game_state = active_games[chat_id]
        game_state["status"] = "in_progress"
        await save_game_state(chat_id)

        players_count = len(game_state["players"])
        if players_count == 0:
            await message.edit_text("Game cancelled - no players joined")
            del active_games[chat_id]
            # Corrected check: compare with None
            if game_states_collection is not None:
                game_states_collection.delete_one({"_id": chat_id})
            return

        game_name = next((name for name, code in GAMES_LIST if code == game_type), "Game")
        await message.edit_text(f"**{game_name} Started!**\n\nPlayers: {players_count}")

        # Start specific game
        if game_type == "quiz":
            await start_quiz_game(chat_id, client)
        elif game_type == "wordchain":
            await start_wordchain_game(chat_id, client)
        elif game_type == "guessing":
            await start_guessing_game(chat_id, client)
        elif game_type == "number_guessing":
            await start_number_guessing_game(chat_id, client)

    if chat_id in active_games:
        active_games[chat_id]["timer_task"] = asyncio.create_task(
            auto_end_game(chat_id, client)
        )

# Quiz game functions
async def start_quiz_game(chat_id: int, client: Client):
    """Initialize quiz game"""
    questions = await get_channel_content("quiz")
    if not questions:
        await client.send_message(chat_id, "Could not load quiz questions")
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        return

    active_games[chat_id].update({
        "quiz_data": random.sample(questions, min(len(questions), 10)),
        "current_round": 0,
        "current_question": {},
        "answered_this_round": False,
        "last_activity_time": datetime.utcnow()
    })
    await save_game_state(chat_id)

    active_games[chat_id]["timer_task"] = asyncio.create_task(
        send_next_quiz_question(chat_id, client)
    )

async def send_next_quiz_question(chat_id: int, client: Client):
    """Send next quiz question with timer"""
    while chat_id in active_games and active_games[chat_id]["status"] == "in_progress":
        game_state = active_games[chat_id]
        if game_state["current_round"] >= len(game_state["quiz_data"]):
            await client.send_message(chat_id, "Quiz completed!")
            del active_games[chat_id]
            # Corrected check: compare with None
            if game_states_collection is not None:
                game_states_collection.delete_one({"_id": chat_id})
            break

        question_data = game_state["quiz_data"][game_state["current_round"]]

        # Removed poll-related message sending
        await client.send_message(
            chat_id=chat_id,
            text=f"**Question {game_state['current_round'] + 1}:**\n\n{question_data['text']}",
            parse_mode="Markdown"
        )
        game_state["current_question"] = {
            "type": "text",
            "correct_answer": question_data["answer"].lower()
        }

        game_state.update({
            "answered_this_round": False,
            "last_activity_time": datetime.utcnow()
        })
        await save_game_state(chat_id)

        await asyncio.sleep(20)

        if not game_state["answered_this_round"]:
            await client.send_message(
                chat_id=chat_id,
                text=f"Time's up! Correct answer: **{game_state['current_question']['correct_answer'].upper()}**"
            )

        game_state["current_round"] += 1

async def handle_quiz_answer_text(message: Message, client: Client):
    """Handle text answers for quiz"""
    chat_id = message.chat.id
    user = message.from_user
    game_state = active_games.get(chat_id)

    if not game_state or game_state["game_type"] != "quiz" or game_state["status"] != "in_progress":
        return

    if user.id not in [p["user_id"] for p in game_state["players"]]:
        return

    if game_state["answered_this_round"]:
        await message.reply("This question was already answered")
        return

    user_answer = message.text.lower()
    correct_answer = game_state["current_question"]["correct_answer"]

    if user_answer == correct_answer:
        await message.reply(f"Correct! +10 points")
        await update_user_score(user.id, user.full_name, chat_id, 10)
        game_state.update({
            "answered_this_round": True,
            "last_activity_time": datetime.utcnow()
        })
        await save_game_state(chat_id)

# Wordchain game functions
async def start_wordchain_game(chat_id: int, client: Client):
    """Initialize wordchain game"""
    words = await get_channel_content("wordchain")
    if not words:
        await client.send_message(chat_id, "Could not load wordchain words")
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        return

    start_word = random.choice(words)["question"].strip().lower()
    players = active_games[chat_id]["players"]

    if not players:
        await client.send_message(chat_id, "Game cancelled - no players")
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        return

    active_games[chat_id].update({
        "current_word": start_word,
        "turn_index": 0,
        "last_activity_time": datetime.utcnow()
    })
    await save_game_state(chat_id)

    random.shuffle(players)
    current_player = players[active_games[chat_id]["turn_index"]]

    await client.send_message(
        chat_id=chat_id,
        text=f"**Wordchain Started!**\n\nFirst word: **{start_word.upper()}**\n\n{current_player['username']}'s turn"
    )

    active_games[chat_id]["timer_task"] = asyncio.create_task(
        turn_timer(chat_id, 60, client, "wordchain")
    )

async def handle_wordchain_answer(message: Message, client: Client):
    """Handle wordchain answers"""
    chat_id = message.chat.id
    user = message.from_user
    game_state = active_games.get(chat_id)

    if not game_state or game_state["game_type"] != "wordchain" or game_state["status"] != "in_progress":
        return

    if not game_state["players"]:
        return

    current_player = game_state["players"][game_state["turn_index"]]
    if user.id != current_player["user_id"]:
        await message.reply("Not your turn!")
        return

    user_word = message.text.strip().lower()
    last_char = game_state["current_word"][-1].lower()

    if user_word.startswith(last_char) and len(user_word) > 1 and user_word.isalpha():
        await update_user_score(user.id, user.full_name, chat_id, 5)
        await message.reply(f"Correct! New word: **{user_word.upper()}**")

        game_state.update({
            "current_word": user_word,
            "turn_index": (game_state["turn_index"] + 1) % len(game_state["players"]),
            "last_activity_time": datetime.utcnow()
        })
        await save_game_state(chat_id)

        if game_state.get("timer_task"):
            game_state["timer_task"].cancel()

        next_player = game_state["players"][game_state["turn_index"]]
        await client.send_message(
            chat_id=chat_id,
            text=f"{next_player['username']}'s turn. Word starting with '{user_word[-1].upper()}'"
        )
        game_state["timer_task"] = asyncio.create_task(
            turn_timer(chat_id, 60, client, "wordchain")
        )
    else:
        await message.reply(f"Invalid word! {user.full_name} is out")

        game_state["players"] = [p for p in game_state["players"] if p["user_id"] != user.id]
        game_state["last_activity_time"] = datetime.utcnow()
        await save_game_state(chat_id)

        if game_state.get("timer_task"):
            game_state["timer_task"].cancel()

        if len(game_state["players"]) < 2:
            await client.send_message(chat_id, "Game ended - not enough players")
            del active_games[chat_id]
            # Corrected check: compare with None
            if game_states_collection is not None:
                game_states_collection.delete_one({"_id": chat_id})
        else:
            if game_state["turn_index"] >= len(game_state["players"]):
                game_state["turn_index"] = 0

            next_player = game_state["players"][game_state["turn_index"]]
            await client.send_message(
                chat_id=chat_id,
                text=f"{next_player['username']}'s turn. Word starting with '{game_state['current_word'][-1].upper()}'"
            )
            game_state["timer_task"] = asyncio.create_task(
                turn_timer(chat_id, 60, client, "wordchain")
            )

# Guessing game functions
async def start_guessing_game(chat_id: int, client: Client):
    """Initialize guessing game"""
    guesses = await get_channel_content("guessing")
    if not guesses:
        await client.send_message(chat_id, "Could not load guessing content")
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        return

    active_games[chat_id].update({
        "guessing_data": random.sample(guesses, min(len(guesses), 5)),
        "current_round": 0,
        "current_guess_item": {},
        "attempts": {},
        "guessed_this_round": False,
        "last_activity_time": datetime.utcnow()
    })
    await save_game_state(chat_id)

    active_games[chat_id]["timer_task"] = asyncio.create_task(
        send_next_guess_item(chat_id, client)
    )

async def send_next_guess_item(chat_id: int, client: Client):
    """Send next guessing game item"""
    game_state = active_games.get(chat_id)
    if not game_state or game_state["status"] != "in_progress" or game_state["game_type"] != "guessing":
        return

    if game_state["current_round"] >= len(game_state["guessing_data"]):
        await client.send_message(chat_id, "Guessing game completed!")
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        return

    guess_item = game_state["guessing_data"][game_state["current_round"]]

    await client.send_message(
        chat_id=chat_id,
        text=f"**Round {game_state['current_round'] + 1}:**\n\nGuess: `{guess_item['question']}`",
        parse_mode="Markdown"
    )

    game_state.update({
        "current_guess_item": {
            "question": guess_item["question"],
            "answer": guess_item["answer"].lower()
        },
        "guessed_this_round": False,
        "attempts": {str(p["user_id"]): 0 for p in game_state["players"]},
        "last_activity_time": datetime.utcnow()
    })
    await save_game_state(chat_id)

    if game_state.get("timer_task"):
        game_state["timer_task"].cancel()
    game_state["timer_task"] = asyncio.create_task(
        turn_timer(chat_id, 60, client, "guessing")
    )

async def handle_guessing_answer(message: Message, client: Client):
    """Handle guessing game answers"""
    chat_id = message.chat.id
    user = message.from_user
    game_state = active_games.get(chat_id)

    if not game_state or game_state["game_type"] != "guessing" or game_state["status"] != "in_progress":
        return

    if user.id not in [p["user_id"] for p in game_state["players"]]:
        return

    if game_state["guessed_this_round"]:
        return

    user_guess = message.text.strip().lower()
    correct_answer = game_state["current_guess_item"]["answer"]

    if user_guess == correct_answer:
        await update_user_score(user.id, user.full_name, chat_id, 15)
        await message.reply(f"Correct! +15 points")
        game_state["guessed_this_round"] = True

        if game_state.get("timer_task"):
            game_state["timer_task"].cancel()

        game_state["current_round"] += 1
        game_state["last_activity_time"] = datetime.utcnow()
        await save_game_state(chat_id)
        active_games[chat_id]["timer_task"] = asyncio.create_task(
            send_next_guess_item(chat_id, client)
        )
    else:
        user_id_str = str(user.id)
        game_state["attempts"][user_id_str] = game_state["attempts"].get(user_id_str, 0) + 1
        await message.reply("Wrong guess, try again!")
        game_state["last_activity_time"] = datetime.utcnow()
        await save_game_state(chat_id)

# Number guessing game functions
async def start_number_guessing_game(chat_id: int, client: Client):
    """Initialize number guessing game"""
    secret_number = random.randint(1, 100)
    active_games[chat_id].update({
        "secret_number": secret_number,
        "guesses_made": {},
        "last_activity_time": datetime.utcnow()
    })
    await save_game_state(chat_id)

    await client.send_message(
        chat_id=chat_id,
        text="**Number Guessing Started!**\n\nGuess a number between 1-100"
    )
    active_games[chat_id]["timer_task"] = asyncio.create_task(
        auto_end_game(chat_id, client)
    )

async def handle_number_guess(message: Message, client: Client):
    """Handle number guessing game answers"""
    chat_id = message.chat.id
    user = message.from_user
    game_state = active_games.get(chat_id)

    if not game_state or game_state["game_type"] != "number_guessing" or game_state["status"] != "in_progress":
        return

    if user.id not in [p["user_id"] for p in game_state["players"]]:
        return

    try:
        user_guess = int(message.text)
        if not 1 <= user_guess <= 100:
            await message.reply("Please guess between 1-100")
            return
    except ValueError:
        await message.reply("Please enter a valid number")
        return

    secret_number = game_state["secret_number"]
    user_id_str = str(user.id)
    game_state["guesses_made"][user_id_str] = game_state["guesses_made"].get(user_id_str, 0) + 1
    game_state["last_activity_time"] = datetime.utcnow()
    await save_game_state(chat_id)

    if user_guess == secret_number:
        guesses_count = game_state["guesses_made"][user_id_str]
        points = max(10, 100 - (guesses_count * 5))
        await update_user_score(user.id, user.full_name, chat_id, points)
        await message.reply(f"Correct! +{points} points (guesses: {guesses_count})")

        if game_state.get("timer_task"):
            game_state["timer_task"].cancel()
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
    elif user_guess < secret_number:
        await message.reply("Higher!")
    else:
        await message.reply("Lower!")

# Timer function
async def turn_timer(chat_id: int, duration: int, client: Client, game_type: str):
    """Handle turn timers for games"""
    await asyncio.sleep(duration)

    game_state = active_games.get(chat_id)
    if not game_state or game_state["status"] != "in_progress":
        return

    if game_type == "wordchain":
        if not game_state["players"]:
            return

        current_player = game_state["players"][game_state["turn_index"]]
        await client.send_message(
            chat_id=chat_id,
            text=f"{current_player['username']} didn't answer in time!"
        )

        game_state["players"].pop(game_state["turn_index"])
        game_state["last_activity_time"] = datetime.utcnow()
        await save_game_state(chat_id)

        if len(game_state["players"]) < 2:
            await client.send_message(chat_id, "Game ended - not enough players")
            del active_games[chat_id]
            # Corrected check: compare with None
            if game_states_collection is not None:
                game_states_collection.delete_one({"_id": chat_id})
        else:
            if game_state["turn_index"] >= len(game_state["players"]):
                game_state["turn_index"] = 0

            next_player = game_state["players"][game_state["turn_index"]]
            await client.send_message(
                chat_id=chat_id,
                text=f"{next_player['username']}'s turn"
            )
            game_state["timer_task"] = asyncio.create_task(
                turn_timer(chat_id, duration, client, "wordchain")
            )

    elif game_type == "guessing":
        if not game_state["guessed_this_round"]:
            correct_answer = game_state["current_guess_item"]["answer"]
            await client.send_message(
                chat_id=chat_id,
                text=f"Time's up! Answer: **{correct_answer.upper()}**"
            )

        game_state["current_round"] += 1
        game_state["last_activity_time"] = datetime.utcnow()
        await save_game_state(chat_id)
        active_games[chat_id]["timer_task"] = asyncio.create_task(
            send_next_guess_item(chat_id, client)
        )

# Command handlers
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    chat = message.chat

    await message.reply(f"Hi {user.mention()}! Use /games to see available games")

    if chat.type == "private":
        log_msg = f"New user: {user.full_name} ({user.id})"
    elif chat.type in ["group", "supergroup"]:
        # Corrected check: compare with None
        if groups_collection is not None:
            groups_collection.update_one(
                {"_id": chat.id},
                {"$set": {"name": chat.title, "active": True, "last_seen": datetime.utcnow()}},
                upsert=True
            )
        log_msg = f"Bot added to group: {chat.title} ({chat.id})"

    if LOG_CHANNEL_ID and "log_msg" in locals():
        try:
            await client.send_message(LOG_CHANNEL_ID, log_msg)
        except Exception as e:
            logger.error(f"Failed to send log: {e}")

@app.on_message(filters.command("games"))
async def games_command(client: Client, message: Message):
    """Handle /games command"""
    keyboard = []
    for game_name, game_callback_data in GAMES_LIST:
        keyboard.append([InlineKeyboardButton(
            game_name,
            callback_data=f"show_rules_{game_callback_data}"
        )])

    await message.reply(
        "Choose a game:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_USER_ID))
async def broadcast_command(client: Client, message: Message):
    """Handle /broadcast command (admin only)"""
    if not message.command or len(message.command) < 2:
        await message.reply("Please provide a message")
        return

    message_content = " ".join(message.command[1:])
    sent_count = 0

    # Corrected check: compare with None
    if groups_collection is not None:
        all_groups = groups_collection.find({"active": True})
        for group in all_groups:
            try:
                await client.send_message(group["_id"], message_content)
                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Broadcast failed for {group['_id']}: {e}")
                if "chat not found" in str(e).lower():
                    groups_collection.update_one(
                        {"_id": group["_id"]},
                        {"$set": {"active": False}}
                    )

    await message.reply(f"Broadcast sent to {sent_count} groups")

@app.on_message(filters.command("endgame") & filters.group)
async def endgame_command(client: Client, message: Message):
    """Handle /endgame command"""
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(chat_id, user_id, client):
        await message.reply("Only admins can end games")
        return

    if chat_id in active_games:
        if active_games[chat_id].get("timer_task"):
            active_games[chat_id]["timer_task"].cancel()
        del active_games[chat_id]
        # Corrected check: compare with None
        if game_states_collection is not None:
            game_states_collection.delete_one({"_id": chat_id})
        await message.reply("Game ended")
    else:
        await message.reply("No active game")

@app.on_message(filters.command("leaderboard"))
async def leaderboard_command(client: Client, message: Message):
    """Handle /leaderboard command"""
    group_id = message.chat.id if message.chat.type in ["group", "supergroup"] else None

    if group_id:
        group_leaders = await get_leaderboard(group_id)
        if group_leaders:
            response = "**Group Leaderboard:**\n"
            for i, user in enumerate(group_leaders, 1):
                score = user.get('group_scores', {}).get(str(group_id), 0)
                response += f"{i}. {user.get('username', 'Unknown')} - {score} points\n"
        else:
            response = "No group scores yet"
        await message.reply(response)

    world_leaders = await get_leaderboard()
    if world_leaders:
        response = "\n**Global Leaderboard:**\n"
        for i, user in enumerate(world_leaders, 1):
            # Corrected f-string syntax here
            response += f"{i}. {user.get('username', 'Unknown')} - {user.get('total_score', 0)} points\n"
    else:
        response = "\nNo global scores yet"
    await message.reply(response)

@app.on_message(filters.command("mystats"))
async def mystats_command(client: Client, message: Message):
    """Handle /mystats command"""
    user_id = message.from_user.id
    # Corrected check: compare with None
    if users_collection is None:
        await message.reply("Stats unavailable")
        return

    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        response = f"**Your Stats:**\nTotal Score: {user_data.get('total_score', 0)}\n"

        # Corrected check: compare with None
        if user_data.get('group_scores') and groups_collection is not None:
            response += "\n**Group Scores:**\n"
            for group_id, score in user_data['group_scores'].items():
                group = groups_collection.find_one({"_id": int(group_id)})
                group_name = group.get("name", f"Group {group_id}") if group else f"Group {group_id}"
                response += f"- {group_name}: {score} points\n"

        await message.reply(response)
    else:
        await message.reply("No stats found")

# Callback query handler
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    await query.answer()
    chat_id = query.message.chat.id
    user = query.from_user
    data = query.data

    if data.startswith("show_rules_"):
        game_type = data.replace("show_rules_", "")
        game_name = next((name for name, code in GAMES_LIST if code == game_type), "Game")

        rules = {
            "quiz": "Answer quiz questions correctly to earn points (text-based answers).",
            "wordchain": "Chain words together using the last letter.",
            "guessing": "Guess the word/phrase from clues.",
            "number_guessing": "Guess the secret number between 1-100."
        }.get(game_type, "No rules available")

        keyboard = [[InlineKeyboardButton(
            f"Start {game_name}",
            callback_data=f"start_game_{game_type}"
        )]]

        await query.edit_message_text(
            f"**{game_name} Rules:**\n\n{rules}\n\nClick below to start",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("start_game_"):
        game_type = data.replace("start_game_", "")

        if chat_id in active_games:
            await query.edit_message_text("A game is already active")
            return

        active_games[chat_id] = {
            "game_type": game_type,
            "players": [],
            "status": "waiting_for_players",
            "current_round": 0,
            "timer_task": None,
            "last_activity_time": datetime.utcnow()
        }
        await save_game_state(chat_id)

        game_name = next((name for name, code in GAMES_LIST if code == game_type), "Game")
        await query.edit_message_text(
            f"**{game_name} Starting!**\n\nPlayers:\n",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Join Game", callback_data=f"join_game_{chat_id}")
            ]])
        )

        active_games[chat_id]["timer_task"] = asyncio.create_task(
            start_game_countdown(chat_id, game_type, query.message, client)
        )

    elif data.startswith("join_game_"):
        game_id = int(data.replace("join_game_", ""))

        if game_id not in active_games or active_games[game_id]["status"] != "waiting_for_players":
            await query.answer("Cannot join now", show_alert=True)
            return

        player_data = {"user_id": user.id, "username": user.full_name}
        if player_data not in active_games[game_id]["players"]:
            active_games[game_id]["players"].append(player_data)
            await save_game_state(game_id)

            player_list = "\n".join([p["username"] for p in active_games[game_id]["players"]])
            try:
                await query.edit_message_text(
                    f"**{next((name for name, code in GAMES_LIST if code == active_games[game_id]['game_type']), 'Game')} Starting!**\n\nPlayers:\n{player_list}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Join Game", callback_data=f"join_game_{game_id}")
                    ]])
                )
            except:
                await client.send_message(
                    chat_id=game_id,
                    text=f"{user.full_name} joined! Players: {len(active_games[game_id]['players'])}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Join Game", callback_data=f"join_game_{game_id}")
                    ]])
                )
            await query.answer("You joined the game!")
        else:
            await query.answer("You already joined", show_alert=True)

# Message handler for game answers
@app.on_message(filters.text & filters.group & ~filters.regex(r"^\/"))
async def handle_game_answers(client: Client, message: Message):
    """Handle all game answer messages"""
    chat_id = message.chat.id
    game_state = active_games.get(chat_id)

    if game_state and game_state["status"] == "in_progress":
        if game_state["game_type"] == "quiz":
            await handle_quiz_answer_text(message, client)
        elif game_state["game_type"] == "wordchain":
            await handle_wordchain_answer(message, client)
        elif game_state["game_type"] == "guessing":
            await handle_guessing_answer(message, client)
        elif game_state["game_type"] == "number_guessing":
            await handle_number_guess(message, client)

# Flask server
def run_flask_server(): # Renamed to avoid confusion with the flask_app variable
    """Run Flask server in a thread"""
    PORT = int(os.environ.get('PORT', 8080)) # Use environment variable for port, default to 8080
    logger.info(f"Flask server starting on port {PORT}")
    flask_app.run(host="0.0.0.0", port=PORT, debug=False) # Set debug to False for production

# Main function
async def main():
    """Start the bot"""
    init_mongo()
    await load_game_states()

    # Start Flask server in a separate thread
    flask_server_thread = Thread(target=run_flask_server)
    flask_server_thread.daemon = True # Allows the main program to exit even if the thread is still running
    flask_server_thread.start()
    logger.info("Flask server thread started.")

    await app.start()
    logger.info("Bot started successfully")

    # Restart any interrupted games
    for chat_id, game_state in active_games.items():
        if game_state["status"] == "in_progress":
            logger.info(f"Restarting game in chat {chat_id}")
            if game_state["game_type"] == "quiz":
                game_state["timer_task"] = asyncio.create_task(
                    send_next_quiz_question(chat_id, app)
                )
            elif game_state["game_type"] == "wordchain":
                game_state["timer_task"] = asyncio.create_task(
                    turn_timer(chat_id, 60, app, "wordchain")
                )
            elif game_state["game_type"] == "guessing":
                game_state["timer_task"] = asyncio.create_task(
                    send_next_guess_item(chat_id, app)
                )
            elif game_state["game_type"] == "number_guessing":
                game_state["timer_task"] = asyncio.create_task(
                    auto_end_game(chat_id, app)
                )

    await idle()
    await app.stop()
    if mongo_client:
        mongo_client.close() # Close MongoDB connection on bot stop
        logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")

