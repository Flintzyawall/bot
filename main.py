"""
love_album_bot.py
Единый файл Telegram-бота с поддержкой прокси и альтернативных серверов
"""

import asyncio
import logging
import os
import json
import random
import html
import re
import ssl
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardMarkup,
    FSInputFile, InputMediaPhoto, InputMediaVideo
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from dotenv import load_dotenv

# ==================== НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ====================
# Если у вас проблемы с доступом к Telegram API, измените эти настройки

# Альтернативные серверы Telegram API
# API_BASE = "https://api.telegram.org"  # основной
# API_BASE = "https://api2.telegram.org"  # альтернативный
# API_BASE = "https://149.154.167.220"  # IP адрес (может работать, даже если заблокирован домен)
API_BASE = os.getenv("API_BASE", "https://api.telegram.org")

# Настройка прокси (раскомментируйте и укажите свои данные)
# PROXY = "http://user:pass@proxy_ip:port"  # HTTP с авторизацией
# PROXY = "http://proxy_ip:port"  # HTTP без авторизации
# PROXY = "socks5://user:pass@proxy_ip:port"  # SOCKS5 с авторизацией
PROXY = os.getenv("PROXY", None)  # или укажите прямо здесь

# Таймаут подключения (секунды)
TIMEOUT = int(os.getenv("TIMEOUT", 60))

# ==================== ОСТАЛЬНАЯ КОНФИГУРАЦИЯ ====================

load_dotenv()

_FALLBACK_TOKEN = "8876056043:AAFfvNsxBKf1jkCgiQ1ii33BJkkLZ2AtynU"
BOT_TOKEN = os.getenv("BOT_TOKEN") or _FALLBACK_TOKEN
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

DEFAULT_NAME = os.getenv("USER_NAME", "любимая")

# Дата начала отношений для таймера и статистики (формат YYYY-MM-DD)
# Поменяйте на свою дату через переменную окружения RELATIONSHIP_START_DATE
RELATIONSHIP_START_DATE = os.getenv("RELATIONSHIP_START_DATE", "2024-01-01")

# Пути к папкам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUR_PHOTOS_DIR = os.path.join(BASE_DIR, "our_photos")
HER_PHOTOS_DIR = os.path.join(BASE_DIR, "her_photos")
DATA_DIR = os.path.join(BASE_DIR, "data")
CAPTIONS_FILE = os.path.join(DATA_DIR, "captions.json")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
MUSIC_FILE = os.path.join(DATA_DIR, "music.json")
COMPLIMENTS_STATE_FILE = os.path.join(DATA_DIR, "compliments_state.json")

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

# Комплименты (90 штук, чтобы редко повторялись)
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


# ==================== FSM СОСТОЯНИЯ ====================

class UploadStates(StatesGroup):
    choosing_category = State()
    entering_caption = State()


class MusicStates(StatesGroup):
    awaiting_audio = State()


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

    safe_title = html.escape(title)
    safe_cat_title = html.escape(CATEGORIES[category_key]["title"])
    emoji = CATEGORIES[category_key]["emoji"]

    return (
        f"{emoji} <b>{safe_title}</b>\n"
        f"<i>{safe_cat_title}</i>\n\n"
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


async def save_uploaded_file(bot, file_id: str, category_key: str, original_ext: str) -> str:
    folder = CATEGORIES[category_key]["dir"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"upload_{timestamp}{original_ext}"
    filepath = os.path.join(folder, filename)

    await bot.download(file_id, destination=filepath)
    return filename


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


# ---------- "Воспоминание дня" ----------

_UPLOAD_NAME_RE = re.compile(r"^upload_(\d{8})_")


def get_file_date(category_key: str, filename: str):
    match = _UPLOAD_NAME_RE.match(filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            pass

    filepath = os.path.join(CATEGORIES[category_key]["dir"], filename)
    try:
        return datetime.fromtimestamp(os.path.getmtime(filepath)).date()
    except OSError:
        return None


def get_memory_items() -> list:
    today = datetime.now().date()
    result = []
    for category_key, filename in get_all_media():
        file_date = get_file_date(category_key, filename)
        if file_date and file_date.month == today.month and file_date.day == today.day and file_date.year != today.year:
            result.append((category_key, filename))
    return result


# ---------- Комплимент дня (без повторов, пока не закончатся все) ----------

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
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_OUR)
    builder.button(text=BTN_HER)
    builder.button(text=BTN_RANDOM)
    builder.button(text=BTN_COMPLIMENT)
    builder.button(text=BTN_FAVORITES)
    builder.button(text=BTN_MEMORY)
    builder.button(text=BTN_TIMER)
    builder.button(text=BTN_STATS)
    builder.button(text=BTN_MINIGAME)
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def gallery_inline_kb(list_key: str, index: int, real_category: str, filename: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏪ Предыдущее", callback_data=f"nav:{list_key}:prev:{index}")
    builder.button(text="🎲 Случайное", callback_data=f"nav:{list_key}:random:{index}")
    builder.button(text="⏩ Следующее", callback_data=f"nav:{list_key}:next:{index}")

    fav = is_favorite(real_category, filename)
    builder.button(
        text="💛 Убрать из избранного" if fav else "⭐ В избранное",
        callback_data=f"fav:{list_key}:{index}",
    )

    music = get_music(real_category, filename)
    if music:
        builder.button(text="🎶 Слушать", callback_data=f"music:play:{list_key}:{index}")
        builder.button(text="🚫 Убрать музыку", callback_data=f"music:remove:{list_key}:{index}")
        row_layout = (3, 1, 2, 1, 1)
    else:
        builder.button(text="🎵 Добавить музыку", callback_data=f"music:ask:{list_key}:{index}")
        row_layout = (3, 1, 1, 1, 1)

    builder.button(text="🗑 Удалить", callback_data=f"del:ask:{list_key}:{index}")
    builder.button(text="🔙 В меню", callback_data="nav:menu:back:0")

    builder.adjust(*row_layout)
    return builder.as_markup()


def confirm_delete_kb(list_key: str, index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=f"del:yes:{list_key}:{index}")
    builder.button(text="❌ Нет", callback_data=f"del:no:{list_key}:{index}")
    builder.adjust(2)
    return builder.as_markup()


def upload_destination_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, category in CATEGORIES.items():
        builder.button(text=f"{category['emoji']} {category['title']}", callback_data=f"save:{key}")
    builder.button(text="🚫 Отмена", callback_data="save:cancel")
    builder.adjust(1)
    return builder.as_markup()


def caption_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Хочу добавить подпись", callback_data="caption:custom")
    builder.button(text="✅ Оставить как есть", callback_data="caption:skip")
    builder.adjust(1)
    return builder.as_markup()


def minigame_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Насколько ты меня любишь?", callback_data="game:menu:love_scale")
    builder.button(text="🎁 Получить поцелуй", callback_data="game:menu:kiss")
    builder.button(text="📊 Кто кого любит сильнее?", callback_data="game:menu:love_calc")
    builder.adjust(1)
    return builder.as_markup()


def love_scale_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in range(1, 6):
        builder.button(text="❤️" * n, callback_data=f"game:love:{n}")
    builder.adjust(1)
    return builder.as_markup()


def kiss_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Получить поцелуй", callback_data="game:kiss:get")
    builder.adjust(1)
    return builder.as_markup()


def love_calc_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 Узнать процент любви", callback_data="game:calc:start")
    builder.adjust(1)
    return builder.as_markup()


# ==================== ХЕНДЛЕРЫ ====================

router = Router()

# ---------- START ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or DEFAULT_NAME
    text = (
        f"привет, {name}! 💕\n\n"
        "это наш маленький альбом воспоминаний 📖✨\n"
        "выбирай, что хочешь посмотреть, с помощью кнопок ниже 👇\n\n"
        "а ещё можешь просто прислать мне сюда новое фото или видео "
        "я спрошу, в какой раздел его сохранить, и оно навсегда останется в альбоме 📥💖"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.message(F.text == BTN_BACK)
async def back_to_menu(message: Message):
    await message.answer("Возвращаемся в меню 🏡", reply_markup=main_menu_kb())


# ---------- КОМПЛИМЕНТЫ ----------

@router.message(F.text == BTN_COMPLIMENT)
async def send_compliment(message: Message):
    compliment = get_next_compliment()
    await message.answer(f"💌 {compliment}")


# ---------- ТАЙМЕР И СТАТИСТИКА ----------

@router.message(F.text == BTN_TIMER)
async def show_timer(message: Message):
    days = get_days_together()
    if days <= 0:
        await message.answer(
            "Укажи дату начала отношений в переменной окружения "
            "RELATIONSHIP_START_DATE=2025-05-03 (формат YYYY-MM-DD), чтобы я мог считать дни 💕"
        )
        return
    await message.answer(f"⏳ Мы вместе уже <b>{days}</b> {_days_word(days)} 💕")


@router.message(F.text == BTN_STATS)
async def show_stats(message: Message):
    all_items = get_all_media()
    photos = sum(1 for _, filename in all_items if not is_video(filename))
    videos = sum(1 for _, filename in all_items if is_video(filename))
    favorites_count = len(get_favorite_items())
    days = get_days_together()

    text = (
        "📊 <b>Статистика альбома</b>\n\n"
        f"📸 Фотографий: {photos}\n"
        f"🎬 Видео: {videos}\n"
        f"⭐ Избранных моментов: {favorites_count}\n"
    )
    if days > 0:
        text += f"⏳ Мы вместе уже: {days} {_days_word(days)}\n"

    await message.answer(text)


# ---------- "ВОСПОМИНАНИЕ ДНЯ" ----------

@router.message(F.text == BTN_MEMORY)
async def show_memory(message: Message):
    items = get_memory_items()
    if not items:
        await message.answer(
            "сегодня воспоминаний с прошлых лет пока не нашлось 💫\n"
            "но они обязательно появятся просто продолжай добавлять моменты 💕"
        )
        return
    index = random.randrange(len(items))
    await _send_gallery_item(message, "memory", index)


# ---------- ИЗБРАННОЕ ----------

@router.message(F.text == BTN_FAVORITES)
async def show_favorites(message: Message):
    items = get_favorite_items()
    if not items:
        await message.answer("пока нет избранных моментов ⭐\nотмечай их звёздочкой под фото 💛")
        return
    await _send_gallery_item(message, "fav", 0)


# ---------- ГАЛЕРЕЯ ----------

def _get_list(category_key: str) -> list:
    if category_key == "all":
        return get_all_media()
    if category_key == "fav":
        return get_favorite_items()
    if category_key == "memory":
        return get_memory_items()
    return [(category_key, filename) for filename in get_media_files(category_key)]


def _build_media_and_caption(real_category_key: str, filename: str, index: int, total: int):
    folder = CATEGORIES[real_category_key]["dir"]
    filepath = os.path.join(folder, filename)
    caption = get_caption(real_category_key, filename, index, total)
    return FSInputFile(filepath), caption


async def _send_gallery_item(message: Message, list_key: str, index: int):
    items = _get_list(list_key)
    if not items:
        await message.answer(EMPTY_FOLDER_TEXT)
        return

    index = index % len(items)
    real_category, filename = items[index]
    file_input, caption = _build_media_and_caption(real_category, filename, index, len(items))
    kb = gallery_inline_kb(list_key, index, real_category, filename)

    if is_video(filename):
        await message.answer_video(file_input, caption=caption, reply_markup=kb)
    else:
        await message.answer_photo(file_input, caption=caption, reply_markup=kb)


async def _redisplay_item(callback: CallbackQuery, list_key: str, index: int) -> None:
    items = _get_list(list_key)
    if not items:
        await callback.message.edit_caption(caption=EMPTY_FOLDER_TEXT)
        return

    index = index % len(items)
    real_category, filename = items[index]
    caption = get_caption(real_category, filename, index, len(items))
    kb = gallery_inline_kb(list_key, index, real_category, filename)

    try:
        await callback.message.edit_caption(caption=caption, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.message(F.text == BTN_OUR)
async def show_our_photos(message: Message):
    await _send_gallery_item(message, "our", 0)


@router.message(F.text == BTN_HER)
async def show_her_photos(message: Message):
    await _send_gallery_item(message, "her", 0)


@router.message(F.text == BTN_RANDOM)
async def show_random_moment(message: Message):
    items = _get_list("all")
    if not items:
        await message.answer(EMPTY_FOLDER_TEXT)
        return
    index = random.randrange(len(items))
    await _send_gallery_item(message, "all", index)


@router.callback_query(F.data.startswith("nav:"))
async def navigate_gallery(callback: CallbackQuery):
    _, list_key, action, current_index_str = callback.data.split(":")

    if list_key == "menu":
        await callback.message.delete()
        await callback.message.answer("Возвращаемся в меню 🏡", reply_markup=main_menu_kb())
        await callback.answer()
        return

    items = _get_list(list_key)
    if not items:
        await callback.answer(EMPTY_FOLDER_TEXT, show_alert=True)
        return

    current_index = int(current_index_str)
    total = len(items)

    if action == "next":
        new_index = (current_index + 1) % total
    elif action == "prev":
        new_index = (current_index - 1) % total
    else:
        new_index = random.randrange(total)

    real_category, filename = items[new_index]
    file_input, caption = _build_media_and_caption(real_category, filename, new_index, total)
    kb = gallery_inline_kb(list_key, new_index, real_category, filename)

    media = (
        InputMediaVideo(media=file_input, caption=caption)
        if is_video(filename)
        else InputMediaPhoto(media=file_input, caption=caption)
    )

    try:
        await callback.message.edit_media(media=media, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer()


# ---------- ИЗБРАННОЕ (toggle под фото) ----------

@router.callback_query(F.data.startswith("fav:"))
async def toggle_favorite_cb(callback: CallbackQuery):
    _, list_key, index_str = callback.data.split(":")
    index = int(index_str)

    items = _get_list(list_key)
    if not items or index >= len(items):
        await callback.answer("этот момент уже не найден", show_alert=True)
        return

    real_category, filename = items[index]
    became_favorite = toggle_favorite(real_category, filename)

    kb = gallery_inline_kb(list_key, index, real_category, filename)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("добавлено в избранное ⭐" if became_favorite else "убрано из избранного 💛")


# ---------- МУЗЫКА К ФОТО ----------

@router.callback_query(F.data.startswith("music:ask:"))
async def ask_music(callback: CallbackQuery, state: FSMContext):
    _, _, list_key, index_str = callback.data.split(":")
    index = int(index_str)

    items = _get_list(list_key)
    if not items or index >= len(items):
        await callback.answer("этот момент уже не найден", show_alert=True)
        return

    real_category, filename = items[index]
    await state.set_state(MusicStates.awaiting_audio)
    await state.update_data(list_key=list_key, index=index, category=real_category, filename=filename)

    await callback.message.answer(
        "🎵 пришли мне аудиофайл или голосовое сообщение и я прикреплю его к этому моменту"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("music:play:"))
async def play_music(callback: CallbackQuery):
    _, _, list_key, index_str = callback.data.split(":")
    index = int(index_str)

    items = _get_list(list_key)
    if not items or index >= len(items):
        await callback.answer("этот момент уже не найден", show_alert=True)
        return

    real_category, filename = items[index]
    music = get_music(real_category, filename)
    if not music:
        await callback.answer("к этому моменту пока не прикреплена музыка", show_alert=True)
        return

    if music.get("type") == "voice":
        await callback.message.answer_voice(music["file_id"])
    else:
        await callback.message.answer_audio(music["file_id"])
    await callback.answer()


@router.callback_query(F.data.startswith("music:remove:"))
async def remove_music_cb(callback: CallbackQuery):
    _, _, list_key, index_str = callback.data.split(":")
    index = int(index_str)

    items = _get_list(list_key)
    if not items or index >= len(items):
        await callback.answer("этот момент уже не найден", show_alert=True)
        return

    real_category, filename = items[index]
    _remove_music(real_category, filename)

    kb = gallery_inline_kb(list_key, index, real_category, filename)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("музыка убрана 🚫")


@router.message(MusicStates.awaiting_audio, F.audio | F.voice)
async def receive_music(message: Message, state: FSMContext):
    data = await state.get_data()
    category_key = data.get("category")
    filename = data.get("filename")

    if not category_key or not filename:
        await state.clear()
        await message.answer("что-то пошло не так, попробуй прикрепить музыку ещё раз 🙏")
        return

    if message.audio:
        file_id = message.audio.file_id
        kind = "audio"
    else:
        file_id = message.voice.file_id
        kind = "voice"

    set_music(category_key, filename, file_id, kind)
    await state.clear()
    await message.answer("музыка добавлена к этому моменту 🎶💕", reply_markup=main_menu_kb())


@router.message(MusicStates.awaiting_audio)
async def receive_music_invalid(message: Message):
    await message.answer("пришли, пожалуйста, аудиофайл или голосовое сообщение 🎵")


# ---------- УДАЛЕНИЕ ФОТО ----------

@router.callback_query(F.data.startswith("del:"))
async def handle_delete(callback: CallbackQuery):
    _, action, list_key, index_str = callback.data.split(":")
    index = int(index_str)

    if action == "ask":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await callback.answer("этот момент уже не найден", show_alert=True)
            return
        try:
            await callback.message.edit_caption(
                caption="❗Удалить этот момент?",
                reply_markup=confirm_delete_kb(list_key, index),
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await callback.answer()
        return

    if action == "no":
        await _redisplay_item(callback, list_key, index)
        await callback.answer("Отменено")
        return

    if action == "yes":
        items = _get_list(list_key)
        if not items or index >= len(items):
            await callback.answer()
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

        new_items = _get_list(list_key)
        if not new_items:
            await callback.message.delete()
            await callback.message.answer(
                f"Момент удалён 🗑\n\n{EMPTY_FOLDER_TEXT}",
                reply_markup=main_menu_kb(),
            )
            await callback.answer("Удалено")
            return

        new_index = index % len(new_items)
        next_category, next_filename = new_items[new_index]
        file_input, caption = _build_media_and_caption(
            next_category, next_filename, new_index, len(new_items)
        )
        kb = gallery_inline_kb(list_key, new_index, next_category, next_filename)

        media = (
            InputMediaVideo(media=file_input, caption=caption)
            if is_video(next_filename)
            else InputMediaPhoto(media=file_input, caption=caption)
        )

        try:
            await callback.message.edit_media(media=media, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

        await callback.answer("Момент удалён 🗑")
        return


# ---------- МИНИ-ИГРЫ ----------

@router.message(F.text == BTN_MINIGAME)
async def show_minigame_menu(message: Message):
    await message.answer("Выбирай игру 🎮💕", reply_markup=minigame_menu_kb())


@router.callback_query(F.data.startswith("game:menu:"))
async def launch_minigame(callback: CallbackQuery):
    game = callback.data.split(":")[2]

    if game == "love_scale":
        await callback.message.edit_text("насколько ты меня любишь? 😏", reply_markup=love_scale_kb())
    elif game == "kiss":
        await callback.message.edit_text("готова получить поцелуй? 💕", reply_markup=kiss_kb())
    elif game == "love_calc":
        await callback.message.edit_text("хочешь узнать, кто кого любит сильнее? 😏", reply_markup=love_calc_kb())

    await callback.answer()


@router.callback_query(F.data.startswith("game:love:"))
async def play_love_scale(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "неправильно 😄\n\nправильный ответ:\nБЕСКОНЕЧНО ❤️♾️",
            reply_markup=love_scale_kb(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()


@router.callback_query(F.data == "game:kiss:get")
async def play_kiss(callback: CallbackQuery):
    if random.random() < 0.5:
        result = "💋"
    else:
        result = "😘" * random.randint(2, 7)

    try:
        await callback.message.edit_text(
            f"{result}\n\nвот твой поцелуй 💕",
            reply_markup=kiss_kb(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()


@router.callback_query(F.data == "game:calc:start")
async def play_love_calc(callback: CallbackQuery):
    await callback.answer()

    steps = ["48%", "73%", "91%", "104%", "258%", "999999%", "∞"]
    try:
        for value in steps:
            await callback.message.edit_text(f"считаю проценты любви...\n\n<b>{value}</b>")
            await asyncio.sleep(0.7)
        await callback.message.edit_text(
            "ошибка вычислений ❤️\nлюбовь невозможно измерить.",
            reply_markup=love_calc_kb(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------- ЗАГРУЗКА ФАЙЛОВ ----------

@router.message(StateFilter(None), F.photo | F.video)
async def receive_media(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        ext = ".jpg"
    else:
        file_id = message.video.file_id
        ext = ".mp4"

    await state.update_data(file_id=file_id, ext=ext)
    await state.set_state(UploadStates.choosing_category)

    await message.answer(
        "какая прелесть! 🥰 куда сохранить этот момент?",
        reply_markup=upload_destination_kb(),
    )


@router.callback_query(UploadStates.choosing_category, F.data.startswith("save:"))
async def choose_destination(callback: CallbackQuery, state: FSMContext):
    category_key = callback.data.split(":")[1]

    if category_key == "cancel":
        await state.clear()
        await callback.message.edit_text("загрузка отменена 🚫")
        await callback.answer()
        return

    data = await state.get_data()
    file_id = data["file_id"]
    ext = data["ext"]

    filename = await save_uploaded_file(callback.bot, file_id, category_key, ext)
    await state.update_data(saved_filename=filename)
    await state.set_state(UploadStates.entering_caption)

    cat_title = CATEGORIES[category_key]["title"]
    cat_emoji = CATEGORIES[category_key]["emoji"]
    await callback.message.edit_text(
        f"сохранено в раздел «{cat_emoji} {cat_title}» ✅\n\n"
        "хочешь добавить к нему свою подпись?",
        reply_markup=caption_choice_kb(),
    )
    await callback.answer()


@router.callback_query(UploadStates.entering_caption, F.data == "caption:skip")
async def skip_caption(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("отлично, этот момент уже в альбоме 💕")
    await callback.answer()


@router.callback_query(UploadStates.entering_caption, F.data == "caption:custom")
async def ask_custom_caption(callback: CallbackQuery):
    await callback.message.edit_text("напиши текст подписи к этому моменту ✍️")
    await callback.answer()


@router.message(UploadStates.entering_caption, F.text)
async def save_custom_caption(message: Message, state: FSMContext):
    data = await state.get_data()
    filename = data.get("saved_filename")

    if filename:
        set_caption(filename, message.text)

    await state.clear()
    await message.answer(
        "подпись сохранена! теперь этот момент особенный 💖",
        reply_markup=main_menu_kb(),
    )


# ==================== ЗАПУСК БОТА ====================

def get_bot_session():
    """Создаёт сессию с настройками прокси и таймаута"""
    session = AiohttpSession(
        timeout=TIMEOUT,
    )

    if PROXY:
        print(f"ℹ️ Используется прокси: {PROXY}")
        session.proxy = PROXY

    return session


async def main():
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("💕 БОТ-АЛЬБОМ ВОСПОМИНАНИЙ")
    print("=" * 50)
    print(f"📍 API сервер: {API_BASE}")
    if PROXY:
        print(f"🔗 Прокси: {PROXY}")
    print(f"⏱ Таймаут: {TIMEOUT} сек")
    print("=" * 50)

    # Создаём папки
    ensure_folders()

    # Создаём сессию
    session = get_bot_session()

    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        api_base=API_BASE,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Диспетчер
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Запуск с повторными попытками
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(f"\n🔄 попытка {attempt + 1}/{max_retries}...")

            # Проверяем соединение
            await bot.delete_webhook(drop_pending_updates=True)

            print("✅ Бот успешно подключился!")
            print("🚀 Бот запущен и готов к работе\n")

            await dp.start_polling(bot)
            break

        except Exception as e:
            print(f"❌ Ошибка: {e}")

            if attempt < max_retries - 1:
                print(f"⏳ Повтор через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
            else:
                print("\n" + "=" * 50)
                print("❌ НЕ УДАЛОСЬ ПОДКЛЮЧИТЬСЯ К TELEGRAM API")
                print("=" * 50)
                print("\n🔧 ПОПРОБУЙТЕ:")
                print("1. Включите VPN (Telegram может быть заблокирован)")
                print("2. Проверьте интернет-соединение")
                print("3. Временно отключите антивирус/брандмауэр")
                print("4. Измените API_BASE в настройках (например, на api2.telegram.org)")
                print("5. Настройте прокси в переменной PROXY")
                print("6. Смените DNS на 8.8.8.8 или 1.1.1.1")
                print("=" * 50)
                raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем.")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
