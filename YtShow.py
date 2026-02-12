# -*- coding: utf-8 -*-
# name: YouTubePro
# description: Advanced YouTube search module with smart query handling

import time
import logging
import yt_dlp
from collections import defaultdict
from .. import loader, utils

logger = logging.getLogger(__name__)

CACHE_TIME = 600  # 10 минут

@loader.tds
class YouTubePro(loader.Module):
    strings = {"name": "YouTubePro"}

    def __init__(self):
        self.cache = {}

    def format_views(self, views):
        if not views:
            return "?"
        if views >= 1_000_000:
            return f"{views/1_000_000:.1f}M"
        if views >= 1_000:
            return f"{views/1_000:.1f}K"
        return str(views)

    @loader.command(
        ru_doc="Продвинутый поиск YouTube",
        en_doc="Advanced YouTube search"
    )
    async def yt(self, message):
        """Usage: .yt <query>"""
        query = utils.get_args_raw(message)
        if not query:
            return await utils.answer(message, "❌ Укажи поисковый запрос.")

        await utils.answer(message, "🔎 Ищу на YouTube...")

        # Проверка кеша
        now = time.time()
        if query in self.cache:
            cached_time, cached_result = self.cache[query]
            if now - cached_time < CACHE_TIME:
                return await utils.answer(message, cached_result)

        try:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "extract_flat": False,
                "noplaylist": True,
                "default_search": "ytsearch",
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"ytsearch10:{query}",
                    download=False
                )

            entries = info.get("entries", [])
            if not entries:
                return await utils.answer(message, "❌ Ничего не найдено.")

            # Сортировка по просмотрам (умный приоритет)
            entries = sorted(
                entries,
                key=lambda x: x.get("view_count") or 0,
                reverse=True
            )

            text = f"<b>🎬 Результаты по запросу:</b> <code>{query}</code>\n\n"

            for i, v in enumerate(entries[:5], 1):
                title = v.get("title", "No title")
                url = v.get("webpage_url", "")
                duration = v.get("duration") or 0
                views = self.format_views(v.get("view_count"))
                uploader = v.get("uploader", "Unknown")

                minutes, seconds = divmod(duration, 60)

                text += (
                    f"{i}. <b>{title}</b>\n"
                    f"👤 {uploader}\n"
                    f"👁 {views} | ⏱ {minutes}:{seconds:02d}\n"
                    f"{url}\n\n"
                )

            # Сохраняем в кеш
            self.cache[query] = (now, text)

            await utils.answer(message, text)

        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            await utils.answer(message, "❌ Ошибка при поиске.")
