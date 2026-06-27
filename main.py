"""
love_album_bot.py
Единый файл Telegram-бота с поддержкой прокси и альтернативных серверов
Адаптирован для Render.com с Flask-оберткой
Переписан для python-telegram-bot v20.x
"""

import asyncio
import html
import json
import logging
import os
import random
import threading
from datetime import datetime, timedelta

# ==================== ИМПОРТЫ ДЛЯ PYTHON-TELEGRAM-BOT ====================
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

from dotenv import load_dotenv

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
from flask import Flask, jsonify

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return jsonify({
        "status": "alive",
        "bot": "Love Album Bot",
        "version": "2.0"
    })

@web_app.route('/health')
def health():
    return jsonify({"status": "ok"})

def run_web_server():
    """Запускает веб-сервер для health checks на Render"""
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Веб-сервер запущен на порту {port}")
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ====================
API_BASE = os.getenv("API_BASE", "https://api.telegram.org")
PROXY = os.getenv("PROXY", None)
TIMEOUT = int(os.getenv("TIMEOUT", 60))

# ==================== ОСТАЛЬНАЯ КОНФИГУРАЦИЯ ====================

load_dotenv()

_FALLBACK_TOKEN = "8876056043:AAFfvNsxBKf1jkCgiQ1ii33BJkkLZ2AtynU"
BOT_TOKEN = os.getenv("BOT_TOKEN") or _FALLBACK_TOKEN
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

DEFAULT_NAME = os.getenv("USER_NAME", "любимая")
RELATIONSHIP_START_DATE = os.getenv("RELATIONSHIP_START_DATE", "2025-05-03")
MEMORY_TIME_HOUR = int(os.getenv("MEMORY_TIME_HOUR", "9"))
MEMORY_TIME_MINUTE = int(os.getenv("MEMORY_TIME_MINUTE", "0"))
MEMORY_CHAT_ID = os.getenv("MEMORY_CHAT_ID", None)

# Пути к папкам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUR_PHOTOS_DIR = os.path.join(BASE_DIR, "our_photos")
HER_PHOTOS_DIR = os.path.join(BASE_DIR, "her_photos")
DATA_DIR = os.path.join(BASE_DIR, "data")
CAPTIONS_FILE = os.path.join(DATA_DIR, "captions.json")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
MUSIC_FILE = os.path.join(DATA_DIR, "music.json")
COMPLIMENTS_STATE_FILE = os.path.join(DATA_DIR, "compliments_state.json")
MEMORY_DATES_FILE = os.path.join(DATA_DIR, "memory_dates.json")

# Поддерживаемые расширения
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS + VIDEO_EXTENSIONS

# Категории альбома
CATEGORIES = {
    "our": {"dir": OUR_PHOTOS_DIR, "title": "Наши моменты", "emoji": "📸"},
    "her": {"dir": HER_PHOTOS_DIR, "title": "Её сияние", "emoji": "💖"},
}

# Тексты кнопок главного меню
BTN_OUR = "📸 Наши моменты"
BTN_HER = "💖 Её сияние"
BTN_RANDOM = "🎲 Случайный момент"
BTN_COMPLIMENT = "❤️ Комплимент дня"
BTN_FAVORITES = "⭐ Избранное"
BTN_MEMORY = "📅 Воспоминание дня"
BTN_TIMER = "⏳ Таймер отношений"
BTN_STATS = "📊 Статистика"
BTN_MINIGAME = "🎮 Мини-игра"
BTN_BACK = "🔙 В меню"

# Милые имена для раздела "Её сияние"
CUTE_NAMES = [
    "Ангел мой 👼", "Солнышко моё ☀️", "Красотка 😍",
    "Моя принцесса 👑", "Милая 🥰", "Чудо моё ✨",
    "Звездочка моя", "Прекрасная💎",
    "Любовь моя 💞",
]

# Комплименты
COMPLIMENTS = [
    "ты самое прекрасное, что есть в моей жизни 🌹",
    "твои глаза невероятны ✨",
    "ты красивее любого закатa 🌅",
    "с тобой хочется прожить тысячу жизней ❤️",
    "ты моё любимое чудо 💖",
    "каждый день рядом с тобой становится праздником 🎉",
    "твоя улыбка лечит любые плохие дни 😊",
    "ты невероятная 🥹",
    "ты делаешь этот мир красивее 🌸",
    "я бесконечно счастлив, что именно ты рядом 💞",
    "ты моя самая любимая ❤️",
    "ты выглядишь прекрасно даже тогда, когда сама так не думаешь 🥰",
    "ты вдохновляешь меня становиться лучше ✨",
    "ты словно маленькое солнце ☀️",
    "мне нравится в тебе абсолютно всё 💕",
    "ты лучшее, что случалось со мной 🍀",
    "каждая секунда с тобой бесценна ⏳💕",
    "твоя улыбка — это моё самое любимое зрелище 😊",
    "рядом с тобой я чувствую себя самым счастливым человеком на свете 🥹💗",
    "ты делаешь мою жизнь ярче просто тем, что существуешь 🌟",
    "твой голос это рай для ушей",
    "ты умеешь делать мир добрее одним своим присутствием 🌷",
    "твои объятия моё любимое место 🤗",
    "я влюбляюсь в тебя заново каждый день 💘",
    "ты заставляешь меня верить в настоящую любовь 💫",
    "с тобой даже молчание прекрасно 🤍",
    "твоя нежность бесценна 🌼",
    "ты делаешь обычные моменты волшебными ✨",
    "я благодарен судьбе за за такую рандомную встречу с тобой 🙏💕",
    "ты моё самое тёплое чувство ❤️",
    "рядом с тобой исчезают все тревоги 🌙",
    "твои руки самое безопасное место в мире 🤲",
    "ты умнее, добрее и красивее, чем ты думаешь 💎",
    "я люблю, как ты смеёшься 😄💕",
    "с тобой я чувствую себя дома, где бы мы ни были 🏡",
    "ты вдохновляешь меня на лучшую версию себя 🚀",
    "твоя забота согревает лучше всего",
    "ты причина моих самых искренних улыбок 😁",
    "я благодарен за каждый момент вмкесте 🥰",
    "с тобой время летит незаметно 💞",
    "ты делаешь меня лучше просто своим существованием 🌿",
    "твоя доброта меняет всё вокруг 🌈",
    "я обожаю тебя",
    "у тебя идеальная прекрасная фигура 🤗",
    "рядом с тобой я снова верю в чудеса ✨",
    "я люблю в тебе всё даже то, что ты считаешь недостатками 💗",
    "ты мой самый ценный подарок от жизни 🎁",
    "твоя искренность редкость, и я ценю это 💎",
    "я никогда не устаю смотреть на тебя 👀💕",
    "рядом с тобой я не боюсь быть собой 🌷",
    "твоя забота заметна в каждой мелочи 🥰",
    "ты делаешь даже дождливые дни уютными ☔💞",
    "я благодарен за каждую твою улыбку, направленную мне 😊",
    "ты моя самая красивая случайность, ставшая судьбой 🍀",
    "с тобой я чувствую себя нужным и любимым 🤗",
    "ты умеешь превращать обычный вечер в особенный 🌃",
    "твои слова всегда находят дорогу к моему сердцу 💌",
    "я люблю засыпать, думая о тебе 🌙💕",
    "ты лучшее доказательство того, что чудеса существуют ✨",
    "рядом с тобой исчезает всё плохое 🍃",
    "твоя любовь делает меня сильнее 💪❤️",
    "я счастлив просто от того, что ты есть",
    "ты делаешь мою жизнь полной смысла 🌟",
    "С тобой даже обычное утро кажется добрым 🌅",
    "ты причина, по которой я верю в светлое будущее 🌈",
    "я люблю каждую мелочь в тебе 🌼",
    "с тобой я наконец чувствую себя на своём месте 🏠💕",
    "я не устаю благодарить судьбу за тебя 🙏",
    "ты самое уютное чувство, которое я знаю 🧸",
    "ты делаешь меня счастливым самим фактом своего существования 💖",
    "с тобой я готов проживать заново каждый обычный день 🔁❤️",
    "ты — лучшее, что подарила мне эта жизнь 🌹",
]

EMPTY_FOLDER_TEXT = "Здесь пока пусто, но я обязательно это исправлю 💕"

# Храним последний активный чат для отправки утренних воспоминаний
last_active_chat_id = None

# ==================== РАБОТА С ФАЙЛАМИ ====================

def ensure_folders() -> None:
    for category in CATEGORIES.values():
        os.makedirs(category["dir"], exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    defaults = (
        (CAPTIONS_FILE, {}),
        (FAVORITES_FILE, []),
        (MUSIC_FILE, {}),
        (COMPLIMENTS_STATE_FILE, {"used": []}),
        (MEMORY_DATES_FILE, {}),
    )
    for filepath, default_value in defaults:
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(default_value, f, ensure_ascii=False, indent=2)


def _load_captions() -> dict:
    try:
        with open(CAPTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_captions(captions: dict) -> None:
    with open(CAPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(captions, f, ensure_ascii=False, indent=2)


def get_media_files(category_key: str) -> list:
    folder = CATEGORIES[category_key]["dir"]
    try:
        return [
            f for f in sorted(os.listdir(folder))
            if f.lower().endswith(MEDIA_EXTENSIONS)
        ]
    except FileNotFoundError:
        return []


def get_all_media() -> list:
    result = []
    for key in CATEGORIES:
        for filename in get_media_files(key):
            result.append((key, filename))
    return result


def is_video(filename: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def get_caption(category_key: str, filename: str, index: int, total: int) -> str:
    captions = _load_captions()

    if filename in captions:
        title = captions[filename]
    elif category_key == "her":
        title = random.choice(CUTE_NAMES)
        captions[filename] = title
        _save_captions(captions)
    else:
        title = f"Момент №{index + 1}"

    memory_date = get_memory_date(category_key, filename)
    date_str = ""
    if memory_date:
        date_str = f"\n📅 <i>Воспоминание на {memory_date.strftime('%d.%m.%Y')}</i>"

    safe_title = html.escape(title)
    safe_cat_title = html.escape(CATEGORIES[category_key]["title"])
    emoji = CATEGORIES[category_key]["emoji"]

    return (
        f"{emoji} <b>{safe_title}</b>\n"
        f"<i>{safe_cat_title}</i>{date_str}\n\n"
        f"Фото {index + 1} из {total}"
    )


def set_caption(filename: str, caption_text: str) -> None:
    captions = _load_captions()
    captions[filename] = caption_text.strip()
    _save_captions(captions)


def _remove_caption(filename: str) -> None:
    captions = _load_captions()
    if filename in captions:
        del captions[filename]
        _save_captions(captions)


def save_uploaded_file(file_obj, category_key: str, original_ext: str) -> str:
    """Сохраняет загруженный файл локально"""
    folder = CATEGORIES[category_key]["dir"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"upload_{timestamp}{original_ext}"
    filepath = os.path.join(folder, filename)
    
    # В python-telegram-bot file_obj - это объект File
    file_obj.download(filepath)
    return filename


# ---------- Даты для воспоминаний ----------

def _load_memory_dates() -> dict:
    try:
        with open(MEMORY_DATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_memory_dates(dates: dict) -> None:
    with open(MEMORY_DATES_FILE, "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False, indent=2)


def set_memory_date(category_key: str, filename: str, date_obj: datetime.date) -> None:
    dates = _load_memory_dates()
    key = f"{category_key}:{filename}"
    dates[key] = date_obj.strftime("%Y-%m-%d")
    _save_memory_dates(dates)


def get_memory_date(category_key: str, filename: str) -> datetime.date:
    dates = _load_memory_dates()
    key = f"{category_key}:{filename}"
    date_str = dates.get(key)
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def remove_memory_date(category_key: str, filename: str) -> None:
    dates = _load_memory_dates()
    key = f"{category_key}:{filename}"
    if key in dates:
        del dates[key]
        _save_memory_dates(dates)


def get_memory_items_for_date(target_date: datetime.date) -> list:
    result = []
    for category_key, filename in get_all_media():
        memory_date = get_memory_date(category_key, filename)
        if memory_date and memory_date.month == target_date.month and memory_date.day == target_date.day:
            result.append((category_key, filename))
    return result


def get_memory_items_for_today() -> list:
    today = datetime.now().date()
    return get_memory_items_for_date(today)


# ---------- Избранное ----------

def _load_favorites() -> list:
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_favorites(favorites: list) -> None:
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)


def _item_key(category_key: str, filename: str) -> str:
    return f"{category_key}:{filename}"


def is_favorite(category_key: str, filename: str) -> bool:
    return _item_key(category_key, filename) in _load_favorites()


def toggle_favorite(category_key: str, filename: str) -> bool:
    favorites = _load_favorites()
    key = _item_key(category_key, filename)
    if key in favorites:
        favorites.remove(key)
        _save_favorites(favorites)
        return False
    favorites.append(key)
    _save_favorites(favorites)
    return True


def _remove_favorite(category_key: str, filename: str) -> None:
    favorites = _load_favorites()
    key = _item_key(category_key, filename)
    if key in favorites:
        favorites.remove(key)
        _save_favorites(favorites)


def get_favorite_items() -> list:
    result = []
    for key in _load_favorites():
        if ":" not in key:
            continue
        category_key, filename = key.split(":", 1)
        if category_key in CATEGORIES and os.path.exists(
            os.path.join(CATEGORIES[category_key]["dir"], filename)
        ):
            result.append((category_key, filename))
    return result


# ---------- Музыка к фото ----------

def _load_music() -> dict:
    try:
        with open(MUSIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_music(data: dict) -> None:
    with open(MUSIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_music(category_key: str, filename: str):
    return _load_music().get(_item_key(category_key, filename))


def set_music(category_key: str, filename: str, file_id: str, kind: str) -> None:
    data = _load_music()
    data[_item_key(category_key, filename)] = {"file_id": file_id, "type": kind}
    _save_music(data)


def _remove_music(category_key: str, filename: str) -> None:
    data = _load_music()
    key = _item_key(category_key, filename)
    if key in data:
        del data[key]
        _save_music(data)


# ---------- Комплимент дня ----------

def _load_compliment_state() -> list:
    try:
        with open(COMPLIMENTS_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("used", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_compliment_state(used: list) -> None:
    with open(COMPLIMENTS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"used": used}, f, ensure_ascii=False, indent=2)


def get_next_compliment() -> str:
    used = [i for i in _load_compliment_state() if 0 <= i < len(COMPLIMENTS)]
    available = [i for i in range(len(COMPLIMENTS)) if i not in used]

    if not available:
        used = []
        available = list(range(len(COMPLIMENTS)))

    idx = random.choice(available)
    used.append(idx)
    _save_compliment_state(used)
    return COMPLIMENTS[idx]


# ---------- Таймер отношений / статистика ----------

def get_days_together() -> int:
    try:
        start_date = datetime.strptime(RELATIONSHIP_START_DATE, "%Y-%m-%d").date()
    except ValueError:
        return 0
    delta = datetime.now().date() - start_date
    return max(delta.days, 0)


def _days_word(n: int) -> str:
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return "дней"
    last_digit = n_abs % 10
    if last_digit == 1:
        return "день"
    if 2 <= last_digit <= 4:
        return "дня"
    return "дней"


# ==================== КЛАВИАТУРЫ ====================

def main_menu_kb() -> ReplyKeyboardMarkup:
    keyboard = [
        [BTN_OUR, BTN_HER],
        [BTN_RANDOM, BTN_COMPLIMENT],
        [BTN_FAVORITES, BTN_MEMORY],
        [BTN_TIMER, BTN_STATS],
        [BTN_MINIGAME]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def gallery_inline_kb(list_key: str, index: int, real_category: str, filename: str) -> InlineKeyboardMarkup:
    keyboard = []
    
    # Верхняя строка навигации
    row1 = []
    row1.append(InlineKeyboardButton("⏪ Предыдущее", callback_data=f"nav:{list_key}:prev:{index}"))
    row1.append(InlineKeyboardButton("🎲 Случайное", callback_data=f"nav:{list_key}:random:{index}"))
    row1.append(InlineKeyboardButton("⏩ Следующее", callback_data=f"nav:{list_key}:next:{index}"))
    keyboard.append(row1)
    
    # Избранное
    fav = is_favorite(real_category, filename)
    fav_text = "💛 Убрать из избранного" if fav else "⭐ В избранное"
    keyboard.append([InlineKeyboardButton(fav_text, callback_data=f"fav:{list_key}:{index}")])
    
    # Музыка
    music = get_music(real_category, filename)
    if music:
        keyboard.append([InlineKeyboardButton("🎶 Слушать", callback_data=f"music:play:{list_key}:{index}")])
        keyboard.append([InlineKeyboardButton("🚫 Убрать музыку", callback_data=f"music:remove:{list_key}:{index}")])
    else:
        keyboard.append([InlineKeyboardButton("🎵 Добавить музыку", callback_data=f"music:ask:{list_key}:{index}")])
    
    # Удаление и меню
    keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"del:ask:{list_key}:{index}")])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="nav:menu:back:0")])
    
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_kb(list_key: str, index: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data=f"del:yes:{list_key}:{index}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"del:no:{list_key}:{index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def upload_destination_kb() -> InlineKeyboardMarkup:
    keyboard = []
    for key, category in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(f"{category['emoji']} {category['title']}", callback_data=f"save:{key}")])
    keyboard.append([InlineKeyboardButton("🚫 Отмена", callback_data="save:cancel")])
    return InlineKeyboardMarkup(keyboard)


def caption_choice_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✏️ Хочу добавить подпись", callback_data="caption:custom")],
        [InlineKeyboardButton("✅ Оставить как есть", callback_data="caption:skip")]
    ]
    return InlineKeyboardMarkup(keyboard)


def memory_date_choice_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="memory:date:today")],
        [InlineKeyboardButton("📅 Вчера", callback_data="memory:date:yesterday")],
        [InlineKeyboardButton("✏️ Своя дата", callback_data="memory:date:custom")],
        [InlineKeyboardButton("❌ Без даты", callback_data="memory:date:skip")]
    ]
    return InlineKeyboardMarkup(keyboard)


def memory_date_confirm_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="memory:confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="memory:cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def minigame_menu_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("❤️ Насколько ты меня любишь?", callback_data="game:menu:love_scale")],
        [InlineKeyboardButton("🎁 Получить поцелуй", callback_data="game:menu:kiss")],
        [InlineKeyboardButton("📊 Кто кого любит сильнее?", callback_data="game:menu:love_calc")]
    ]
    return InlineKeyboardMarkup(keyboard)


def love_scale_kb() -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for n in range(1, 6):
        row.append(InlineKeyboardButton("❤️" * n, callback_data=f"game:love:{n}"))
    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def kiss_kb() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("🎁 Получить поцелуй", callback_data="game:kiss:get")]]
    return InlineKeyboardMarkup(keyboard)


def love_calc_kb() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("🎲 Узнать процент любви", callback_data="game:calc:start")]]
    return InlineKeyboardMarkup(keyboard)


# ==================== ХЕНДЛЕРЫ ====================

# Состояния для ConversationHandler
CHOOSING_CATEGORY, ENTERING_CAPTION, ENTERING_MEMORY_DATE = range(3)
AWAITING_AUDIO = range(3, 4)

# Хранилище данных для FSM
user_data_storage = {}

# ---------- START ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_active_chat_id
    if update.effective_chat:
        last_active_chat_id = update.effective_chat.id
    
    name = update.effective_user.first_name or DEFAULT_NAME
    text = (
        f"привет, {name}! 💕\n\n"
        "это наш маленький альбом воспоминаний 📖✨\n"
        "выбирай, что хочешь посмотреть, с помощью кнопок ниже 👇\n\n"
        "а ещё можешь просто прислать мне сюда новое фото или видео "
        "я спрошу, в какой раздел его сохранить, и оно навсегда останется в альбоме 📥💖"
    )
    await update.message.reply_text(text, reply_markup=main_menu_kb())


# ---------- ОБРАБОТЧИКИ ТЕКСТА ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == BTN_OUR:
        await show_gallery(update, "our", 0)
    elif text == BTN_HER:
        await show_gallery(update, "her", 0)
    elif text == BTN_RANDOM:
        await show_random_moment(update)
    elif text == BTN_COMPLIMENT:
        await send_compliment(update)
    elif text == BTN_FAVORITES:
        await show_favorites(update)
    elif text == BTN_MEMORY:
        await show_memory(update)
    elif text == BTN_TIMER:
        await show_timer(update)
    elif text == BTN_STATS:
        await show_stats(update)
    elif text == BTN_MINIGAME:
        await update.message.reply_text("Выбирай игру 🎮💕", reply_markup=minigame_menu_kb())
    elif text == BTN_BACK:
        await update.message.reply_text("Возвращаемся в меню 🏡", reply_markup=main_menu_kb())


# ---------- ГАЛЕРЕЯ ----------

def _get_list(category_key: str) -> list:
    if category_key == "all":
        return get_all_media()
    if category_key == "fav":
        return get_favorite_items()
    if category_key == "memory":
        return get_memory_items_for_today()
    return [(category_key, filename) for filename in get_media_files(category_key)]


async def show_gallery(update: Update, list_key: str, index: int):
    items = _get_list(list_key)
    if not items:
        await update.message.reply_text(EMPTY_FOLDER_TEXT)
        return

    index = index % len(items)
    real_category, filename = items[index]
    folder = CATEGORIES[real_category]["dir"]
    filepath = os.path.join(folder, filename)
    
    caption = get_caption(real_category, filename, index, len(items))
    kb = gallery_inline_kb(list_key, index, real_category, filename)

    try:
        if is_video(filename):
            with open(filepath, 'rb') as video_file:
                await update.message.reply_video(video_file, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            with open(filepath, 'rb') as photo_file:
                await update.message.reply_photo(photo_file, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    except FileNotFoundError:
        await update.message.reply_text("Файл не найден 😔")


async def show_random_moment(update: Update):
    items = _get_list("all")
    if not items:
        await update.message.reply_text(EMPTY_FOLDER_TEXT)
        return
    index = random.randrange(len(items))
    await show_gallery(update, "all", index)


async def send_compliment(update: Update):
    compliment = get_next_compliment()
    await update.message.reply_text(f"💌 {compliment}")


async def show_timer(update: Update):
    days = get_days_together()
    if days <= 0:
        await update.message.reply_text(
            "Укажи дату начала отношений в переменной окружения "
            "RELATIONSHIP_START_DATE=2025-05-03 (формат YYYY-MM-DD), чтобы я мог считать дни 💕"
        )
        return
    await update.message.reply_text(f"⏳ Мы вместе уже <b>{days}</b> {_days_word(days)} 💕", parse_mode=ParseMode.HTML)


async def show_stats(update: Update):
    all_items = get_all_media()
    photos = sum(1 for _, filename in all_items if not is_video(filename))
    videos = sum(1 for _, filename in all_items if is_video(filename))
    favorites_count = len(get_favorite_items())
    days = get_days_together()

    memory_count = 0
    for category_key, filename in all_items:
        if get_memory_date(category_key, filename):
            memory_count += 1

    text = (
        "📊 <b>Статистика альбома</b>\n\n"
        f"📸 Фотографий: {photos}\n"
        f"🎬 Видео: {videos}\n"
        f"⭐ Избранных моментов: {favorites_count}\n"
        f"📅 Воспоминаний с датами: {memory_count}\n"
    )
    if days > 0:
        text += f"⏳ Мы вместе уже: {days} {_days_word(days)}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def show_memory(update: Update):
    items = get_memory_items_for_today()
    if not items:
        await update.message.reply_text(
            "сегодня воспоминаний пока нет 💫\n"
            "но ты можешь добавить дату к любому фото при загрузке, "
            "и в этот день я пришлю его как воспоминание 💕"
        )
        return
    index = random.randrange(len(items))
    await show_gallery(update, "memory", index)


async def show_favorites(update: Update):
    items = get_favorite_items()
    if not items:
        await update.message.reply_text("пока нет избранных моментов ⭐\nотмечай их звёздочкой под фото 💛")
        return
    await show_gallery(update, "fav", 0)


# ---------- CALLBACK QUERY ХЕНДЛЕРЫ ----------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("nav:"):
        await navigate_gallery(query, data)
    elif data.startswith("fav:"):
        await toggle_favorite_cb(query, data)
    elif data.startswith("music:"):
        await handle_music_callback(query, data, context)
    elif data.startswith("del:"):
        await handle_delete(query, data)
    elif data.startswith("game:"):
        await handle_game_callback(query, data)
    elif data.startswith("save:"):
        await choose_destination(query, data, context)
    elif data.startswith("caption:"):
        await handle_caption_callback(query, data, context)
    elif data.startswith("memory:"):
        await handle_memory_callback(query, data, context)


async def navigate_gallery(query, data):
    _, list_key, action, current_index_str = data.split(":")

    if list_key == "menu":
        await query.message.delete()
        await query.message.reply_text("Возвращаемся в меню 🏡", reply_markup=main_menu_kb())
        return

    items = _get_list(list_key)
    if not items:
        await query.answer(EMPTY_FOLDER_TEXT, show_alert=True)
        return

    current_index = int(current_index_str)
    total = len(items)

    if action == "next":
        new_index = (current_index + 1) % total
    elif action == "prev":
        new_index = (current_index - 1) % total
    else:  # random
        new_index = random.randrange(total)

    real_category, filename = items[new_index]
    folder = CATEGORIES[real_category]["dir"]
    filepath = os.path.join(folder, filename)
    caption = get_caption(real_category, filename, new_index, total)
    kb = gallery_inline_kb(list_key, new_index, real_category, filename)

    try:
        if is_video(filename):
            with open(filepath, 'rb') as video_file:
                await query.message.edit_media(
                    media=InputMediaVideo(video_file, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=kb
                )
        else:
            with open(filepath, 'rb') as photo_file:
                await query.message.edit_media(
                    media=InputMediaPhoto(photo_file, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=kb
                )
    except Exception as e:
        print(f"Error editing media: {e}")


async def toggle_favorite_cb(query, data):
    _, list_key, index_str = data.split(":")
    index = int(index_str)

    items = _get_list(list_key)
    if not items or index >= len(items):
        await query.answer("этот момент уже не найден", show_alert=True)
        return

    real_category, filename = items[index]
    became_favorite = toggle_favorite(real_category, filename)

    kb = gallery_inline_kb(list_key, index, real_category, filename)
    await query.message.edit_reply_markup(reply_markup=kb)
    await query.answer("добавлено в избранное ⭐" if became_favorite else "убрано из избранного 💛")


async def handle_music_callback(query, data, context):
    parts = data.split(":")
    action = parts[1]
    list_key = parts[2]
    index = int(parts[3])

    if action == "ask":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await query.answer("этот момент уже не найден", show_alert=True)
            return

        real_category, filename = items[index]
        context.user_data['music_data'] = {
            'list_key': list_key,
            'index': index,
            'category': real_category,
            'filename': filename
        }
        context.user_data['state'] = AWAITING_AUDIO
        await query.message.reply_text("🎵 пришли мне аудиофайл или голосовое сообщение и я прикреплю его к этому моменту")
        return

    elif action == "play":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await query.answer("этот момент уже не найден", show_alert=True)
            return

        real_category, filename = items[index]
        music = get_music(real_category, filename)
        if not music:
            await query.answer("к этому моменту пока не прикреплена музыка", show_alert=True)
            return

        if music.get("type") == "voice":
            await query.message.reply_voice(music["file_id"])
        else:
            await query.message.reply_audio(music["file_id"])

    elif action == "remove":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await query.answer("этот момент уже не найден", show_alert=True)
            return

        real_category, filename = items[index]
        _remove_music(real_category, filename)

        kb = gallery_inline_kb(list_key, index, real_category, filename)
        await query.message.edit_reply_markup(reply_markup=kb)
        await query.answer("музыка убрана 🚫")


async def handle_delete(query, data):
    _, action, list_key, index_str = data.split(":")
    index = int(index_str)

    if action == "ask":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await query.answer("этот момент уже не найден", show_alert=True)
            return
        await query.message.edit_caption(
            caption="❗Удалить этот момент?",
            reply_markup=confirm_delete_kb(list_key, index)
        )
        return

    if action == "no":
        await redisplay_item(query, list_key, index)
        await query.answer("Отменено")
        return

    if action == "yes":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await query.answer()
            return

        real_category, filename = items[index]
        filepath = os.path.join(CATEGORIES[real_category]["dir"], filename)
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

        _remove_caption(filename)
        _remove_favorite(real_category, filename)
        _remove_music(real_category, filename)
        remove_memory_date(real_category, filename)

        new_items = _get_list(list_key)
        if not new_items:
            await query.message.delete()
            await query.message.reply_text(
                f"Момент удалён 🗑\n\n{EMPTY_FOLDER_TEXT}",
                reply_markup=main_menu_kb()
            )
            await query.answer("Удалено")
            return

        new_index = index % len(new_items)
        await redisplay_item(query, list_key, new_index)
        await query.answer("Момент удалён 🗑")


async def redisplay_item(query, list_key, index):
    items = _get_list(list_key)
    if not items:
        await query.message.edit_caption(caption=EMPTY_FOLDER_TEXT)
        return

    index = index % len(items)
    real_category, filename = items[index]
    folder = CATEGORIES[real_category]["dir"]
    filepath = os.path.join(folder, filename)
    caption = get_caption(real_category, filename, index, len(items))
    kb = gallery_inline_kb(list_key, index, real_category, filename)

    try:
        if is_video(filename):
            with open(filepath, 'rb') as video_file:
                await query.message.edit_media(
                    media=InputMediaVideo(video_file, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=kb
                )
        else:
            with open(filepath, 'rb') as photo_file:
                await query.message.edit_media(
                    media=InputMediaPhoto(photo_file, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=kb
                )
    except Exception as e:
        print(f"Error editing media: {e}")


async def handle_game_callback(query, data):
    parts = data.split(":")
    game = parts[2]

    if game == "love_scale":
        await query.message.edit_text("насколько ты меня любишь? 😏", reply_markup=love_scale_kb())
    elif game == "kiss":
        await query.message.edit_text("готова получить поцелуй? 💕", reply_markup=kiss_kb())
    elif game == "love_calc":
        await query.message.edit_text("хочешь узнать, кто кого любит сильнее? 😏", reply_markup=love_calc_kb())
    elif data.startswith("game:love:"):
        await query.message.edit_text(
            "неправильно 😄\n\nправильный ответ:\nБЕСКОНЕЧНО ❤️♾️",
            reply_markup=love_scale_kb()
        )
    elif data == "game:kiss:get":
        result = "💋" if random.random() < 0.5 else "😘" * random.randint(2, 7)
        await query.message.edit_text(
            f"{result}\n\nвот твой поцелуй 💕",
            reply_markup=kiss_kb()
        )
    elif data == "game:calc:start":
        steps = ["48%", "73%", "91%", "104%", "258%", "999999%", "∞"]
        for value in steps:
            await query.message.edit_text(f"считаю проценты любви...\n\n<b>{value}</b>", parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.7)
        await query.message.edit_text(
            "ошибка вычислений ❤️\nлюбовь невозможно измерить.",
            reply_markup=love_calc_kb()
        )


# ---------- ЗАГРУЗКА ФАЙЛОВ ----------

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_active_chat_id
    if update.effective_chat:
        last_active_chat_id = update.effective_chat.id

    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        ext = ".jpg"
    elif update.message.video:
        file_obj = await update.message.video.get_file()
        ext = ".mp4"
    else:
        return

    context.user_data['file_data'] = {
        'file_obj': file_obj,
        'ext': ext
    }
    context.user_data['state'] = CHOOSING_CATEGORY

    await update.message.reply_text(
        "какая прелесть! 🥰 куда сохранить этот момент?",
        reply_markup=upload_destination_kb()
    )


async def choose_destination(query, data, context):
    category_key = data.split(":")[1]

    if category_key == "cancel":
        context.user_data['state'] = None
        await query.message.edit_text("загрузка отменена 🚫")
        return

    file_data = context.user_data.get('file_data')
    if not file_data:
        await query.message.edit_text("ошибка: файл не найден 😔")
        return

    file_obj = file_data['file_obj']
    ext = file_data['ext']

    filename = save_uploaded_file(file_obj, category_key, ext)
    context.user_data['saved_filename'] = filename
    context.user_data['state'] = ENTERING_CAPTION

    cat_title = CATEGORIES[category_key]["title"]
    cat_emoji = CATEGORIES[category_key]["emoji"]
    await query.message.edit_text(
        f"сохранено в раздел «{cat_emoji} {cat_title}» ✅\n\n"
        "хочешь добавить к нему свою подпись?",
        reply_markup=caption_choice_kb()
    )


async def handle_caption_callback(query, data, context):
    action = data.split(":")[1]

    if action == "skip":
        context.user_data['state'] = ENTERING_MEMORY_DATE
        await query.message.edit_text(
            "отлично! теперь давай выберем дату для этого момента, "
            "чтобы он показывался в воспоминаниях 📅\n\n"
            "этот день будет особенным каждый год 💕",
            reply_markup=memory_date_choice_kb()
        )
    elif action == "custom":
        await query.message.edit_text("напиши текст подписи к этому моменту ✍️")
        context.user_data['state'] = ENTERING_CAPTION


async def handle_caption_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != ENTERING_CAPTION:
        return

    filename = context.user_data.get('saved_filename')
    if filename:
        set_caption(filename, update.message.text)

    context.user_data['state'] = ENTERING_MEMORY_DATE
    await update.message.reply_text(
        "подпись сохранена! теперь давай выберем дату для этого момента, "
        "чтобы он показывался в воспоминаниях 📅\n\n"
        "этот день будет особенным каждый год 💕",
        reply_markup=memory_date_choice_kb()
    )


async def handle_memory_callback(query, data, context):
    parts = data.split(":")
    action = parts[2]

    if action == "skip":
        context.user_data['state'] = None
        await query.message.edit_text("отлично! если захочешь добавить дату позже, просто нажми кнопку 'Изменить дату' под фото 💕")
        return

    if action == "today":
        date_obj = datetime.now().date()
        context.user_data['memory_date'] = date_obj.strftime("%Y-%m-%d")
        await query.message.edit_text(
            f"✅ выбрана дата: <b>{date_obj.strftime('%d.%m.%Y')}</b> (сегодня)\n\n"
            "в этот день каждый год я буду присылать это воспоминание 💕",
            reply_markup=memory_date_confirm_kb(),
            parse_mode=ParseMode.HTML
        )
    elif action == "yesterday":
        date_obj = datetime.now().date() - timedelta(days=1)
        context.user_data['memory_date'] = date_obj.strftime("%Y-%m-%d")
        await query.message.edit_text(
            f"✅ выбрана дата: <b>{date_obj.strftime('%d.%m.%Y')}</b> (вчера)\n\n"
            "в этот день каждый год я буду присылать это воспоминание 💕",
            reply_markup=memory_date_confirm_kb(),
            parse_mode=ParseMode.HTML
        )
    elif action == "custom":
        await query.message.edit_text(
            "напиши дату в формате <b>ДД.ММ.ГГГГ</b> (например, 03.05.2025)\n\n"
            "это будет день, когда я буду присылать это воспоминание каждый год 💕",
            parse_mode=ParseMode.HTML
        )
        context.user_data['state'] = ENTERING_MEMORY_DATE
        return
    elif action == "confirm":
        await confirm_memory_date(query, context)
        return
    elif action == "cancel":
        context.user_data['state'] = None
        await query.message.edit_text("отлично, этот момент уже в альбоме 💕")
        return


async def handle_memory_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != ENTERING_MEMORY_DATE:
        return

    try:
        date_obj = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
        context.user_data['memory_date'] = date_obj.strftime("%Y-%m-%d")
        await update.message.reply_text(
            f"✅ выбрана дата: <b>{date_obj.strftime('%d.%m.%Y')}</b>\n\n"
            "в этот день каждый год я буду присылать это воспоминание 💕",
            reply_markup=memory_date_confirm_kb(),
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text(
            "❌ неверный формат даты!\n\n"
            "пожалуйста, напиши дату в формате <b>ДД.ММ.ГГГГ</b>\n"
            "например: <b>03.05.2025</b>",
            parse_mode=ParseMode.HTML
        )


async def confirm_memory_date(query, context):
    filename = context.user_data.get('saved_filename')
    date_str = context.user_data.get('memory_date')

    if filename and date_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        category_key = None
        for key, category in CATEGORIES.items():
            if os.path.exists(os.path.join(category["dir"], filename)):
                category_key = key
                break

        if category_key:
            set_memory_date(category_key, filename, date_obj)

    context.user_data['state'] = None
    await query.message.edit_text(
        "💕 отлично! теперь этот момент будет приходить к нам в этот день каждый год!\n\n"
        "я буду присылать его утром, чтобы напомнить о прекрасном моменте ✨"
    )


# ---------- МУЗЫКА ----------

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != AWAITING_AUDIO:
        return

    music_data = context.user_data.get('music_data')
    if not music_data:
        await update.message.reply_text("что-то пошло не так, попробуй прикрепить музыку ещё раз 🙏")
        return

    category_key = music_data.get('category')
    filename = music_data.get('filename')

    if update.message.audio:
        file_id = update.message.audio.file_id
        kind = "audio"
    elif update.message.voice:
        file_id = update.message.voice.file_id
        kind = "voice"
    else:
        await update.message.reply_text("пожалуйста, отправь аудиофайл или голосовое сообщение 🎵")
        return

    set_music(category_key, filename, file_id, kind)
    context.user_data['state'] = None
    context.user_data['music_data'] = None
    await update.message.reply_text("музыка добавлена к этому моменту 🎶💕", reply_markup=main_menu_kb())


# ==================== ФОНОВАЯ ЗАДАЧА ====================

async def send_daily_memories(application: Application):
    """Отправляет воспоминания каждый день в заданное время"""
    global last_active_chat_id

    while True:
        now = datetime.now()
        target_time = now.replace(hour=MEMORY_TIME_HOUR, minute=MEMORY_TIME_MINUTE, second=0, microsecond=0)

        if now >= target_time:
            target_time += timedelta(days=1)

        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            memories = get_memory_items_for_today()

            if not memories:
                continue

            chat_id = MEMORY_CHAT_ID or last_active_chat_id
            if not chat_id:
                continue

            await application.bot.send_message(
                chat_id,
                f"🌅 <b>Доброе утро, любимая!</b>\n\n"
                f"сегодня особенный день, ведь ровно {len(memories)} год назад произошёл этот прекрасный момент ✨\n"
                f"давай вспомним его вместе 💕",
                parse_mode=ParseMode.HTML
            )

            for idx, (category_key, filename) in enumerate(memories, 1):
                folder = CATEGORIES[category_key]["dir"]
                filepath = os.path.join(folder, filename)

                caption = get_caption(category_key, filename, idx, len(memories))
                caption += f"\n\n📅 <i>Воспоминание на {datetime.now().strftime('%d.%m.%Y')}</i>"

                with open(filepath, 'rb') as file:
                    if is_video(filename):
                        await application.bot.send_video(chat_id, file, caption=caption, parse_mode=ParseMode.HTML)
                    else:
                        await application.bot.send_photo(chat_id, file, caption=caption, parse_mode=ParseMode.HTML)

                await asyncio.sleep(1)

            await application.bot.send_message(
                chat_id,
                "💕 пусть эти воспоминания согревают тебя весь день!\n\n"
                "ты - лучшее, что случилось в моей жизни ❤️",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logging.error(f"Ошибка при отправке утренних воспоминаний: {e}")
            await asyncio.sleep(60)


# ==================== ЗАПУСК БОТА ====================

def main():
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("💕 БОТ-АЛЬБОМ ВОСПОМИНАНИЙ (python-telegram-bot)")
    print("=" * 50)
    print(f"📍 API сервер: {API_BASE}")
    if PROXY:
        print(f"🔗 Прокси: {PROXY}")
    print(f"⏱ Таймаут: {TIMEOUT} сек")
    print(f"⏰ Время отправки воспоминаний: {MEMORY_TIME_HOUR:02d}:{MEMORY_TIME_MINUTE:02d}")
    print("=" * 50)

    ensure_folders()

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчики для загрузки медиа
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    
    # Обработчики для подписей
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_caption_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_memory_date_text))
    
    # Обработчики для аудио
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))

    # Запускаем фоновую задачу
    asyncio.create_task(send_daily_memories(application))

    # Запускаем polling с повторными попытками
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(f"\n🔄 попытка {attempt + 1}/{max_retries}...")
            print("✅ Бот успешно подключился!")
            print("🚀 Бот запущен и готов к работе\n")
            
            application.run_polling(stop_signals=None)
            break

        except Exception as e:
            print(f"❌ Ошибка: {e}")

            if attempt < max_retries - 1:
                print(f"⏳ Повтор через {retry_delay} секунд...")
                time.sleep(retry_delay)
            else:
                print("\n" + "=" * 50)
                print("❌ НЕ УДАЛОСЬ ПОДКЛЮЧИТЬСЯ К TELEGRAM API")
                print("=" * 50)
                raise


if __name__ == "__main__":
    import time
    try:
        # Запускаем веб-сервер в отдельном потоке для Render
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        print("🌐 Веб-сервер запущен в фоновом режиме")
        
        # Запускаем бота
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем.")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
