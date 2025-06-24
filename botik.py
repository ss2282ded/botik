import os
import logging
import re
from datetime import datetime
from typing import List
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

MAX_LINKS = 100

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_short_ids(text: str) -> List[str]:
    pattern = r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
    return list({id for id in re.findall(pattern, text) if len(id) == 11})[:MAX_LINKS]

def fetch_short_data(video_id: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if not data["items"]:
            return {"id": video_id, "success": False}

        info = data["items"][0]
        snippet = info["snippet"]
        stats = info["statistics"]

        return {
            "id": video_id,
            "success": True,
            "title": snippet.get("title", "Без названия"),
            "date": snippet.get("publishedAt", "Дата неизвестна")[:10],
            "views": int(stats.get("viewCount", "0")),
            "likes": int(stats.get("likeCount", "0")),
            "comments": int(stats.get("commentCount", "0"))
        }

    except Exception as e:
        return {"id": video_id, "success": False, "error": str(e)}

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[InlineKeyboardButton("📊 Начать парсинг", callback_data='new_parse')]]
    await update.message.reply_text("👋 Добро пожаловать в YouTube Shorts Статистику!", reply_markup=InlineKeyboardMarkup(keyboard))

async def new_parse_button(update: Update, context: CallbackContext) -> None:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📩 Отправь ссылки на YouTube Shorts.")

async def process_shorts(update: Update, context: CallbackContext) -> None:
    message = update.message
    short_ids = extract_short_ids(message.text)

    if not short_ids:
        await message.reply_text("❌ Ссылки не найдены.")
        return

    reply = await message.reply_text("⏳ Обработка видео...")

    results = [fetch_short_data(sid) for sid in short_ids]
    processed = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    zeros = [r for r in processed if r["views"] == 0]

    total_views = sum(r["views"] for r in processed)
    total_likes = sum(r["likes"] for r in processed)
    total_comments = sum(r["comments"] for r in processed)

    avg_views = total_views // len(processed) if processed else 0
    avg_likes = total_likes // len(processed) if processed else 0
    avg_comments = total_comments // len(processed) if processed else 0

    top5 = sorted(processed, key=lambda r: r["views"], reverse=True)[:5]
    top_lines = "\n".join([
        f"{i+1}. [{r['title']}](https://youtube.com/shorts/{r['id']}) 👁️ {r['views']}"
        for i, r in enumerate(top5)
    ])

    time_str = datetime.now().strftime('%d.%m.%Y %H:%M')

    report = (
        f"📊 *Обновлённая статистика* ({len(processed)} из {len(results)} успешно) 📈\n\n"
        f"📌 *Видео успешно обработано:* {len(processed)}\n"
        f"ℹ️ *Не найдено / удалено:* {len(failed)}\n"
        f"⛔ *Нулевые просмотры:* {len(zeros)}\n"
        f"👁️ *Всего просмотров:* {total_views}\n"
        f"❤️ *Всего лайков:* {total_likes}\n"
        f"💬 *Всего комментариев:* {total_comments}\n\n"
        f"📈 *Средние показатели на видео:*\n"
        f"👁️ {avg_views}  ❤️ {avg_likes}  💬 {avg_comments}\n\n"
        f"🌐 *Топ 5 видео:*\n{top_lines}\n\n"
        f"_Обновлено: {escape_markdown(time_str, version=2)}_"
    )

    buttons = [
    [
        InlineKeyboardButton("🔁 Обновить ещё раз", callback_data='new_parse'),
    ]
]
