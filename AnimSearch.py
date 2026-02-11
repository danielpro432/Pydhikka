# AniSearch для Hikka — поиск аниме по кадру
# meta developer: @yourname
# name: AniSearch
# description: Ищет аниме по кадру через trace.moe API
# meta banner: https://i.imgur.com/1f6Ue2L.png

import logging
import io
import aiohttp
import asyncio
from telethon.tl.types import Message, DocumentAttributeFilename
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AniSearchMod(loader.Module):
    """Поиск аниме по кадру через trace.moe API"""

    strings = {
        "name": "AniSearch",
        "no_media": "🖼 <b>Пожалуйста, приложи фото или документ с кадром аниме.</b>",
        "searching": "🔎 <b>Ищу аниме...</b>",
        "result": "<b>Название:</b> {title}\n<b>Эпизод:</b> {episode}\n<b>Таймкод:</b> {time}\n<b>Совпадение:</b> {similarity:.2f}%",
        "error": "⚠️ <b>Ошибка при поиске аниме.</b>\n<i>{error}</i>"
    }

    async def client_ready(self, client, db):
        self.client = client

    @loader.command(
        ru_doc="<картинка> — ищет аниме по кадру",
        en_doc="<image> — search anime by frame",
        alias="anisearch"
    )
    async def anisearchcmd(self, message: Message):
        media = None
        if message.reply_to:
            media = message.reply_to.media
        elif message.media:
            media = message.media

        if not media:
            await utils.answer(message, self.strings("no_media"))
            return

        status_msg = await utils.answer(message, self.strings("searching"))

        file_buffer = io.BytesIO()
        file_name = "anime.jpg"

        if hasattr(media, "document") and media.document:
            attrs = media.document.attributes
            for a in attrs:
                if isinstance(a, DocumentAttributeFilename):
                    file_name = a.file_name
                    break

        await self.client.download_media(media, file_buffer)
        file_buffer.seek(0)

        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('image', file_buffer, filename=file_name, content_type='image/jpeg')
                async with session.post("https://api.trace.moe/search?anilistInfo", data=data) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    result_json = await resp.json()

            if "result" not in result_json or not result_json["result"]:
                await status_msg.edit("❌ <b>Аниме не найдено.</b>")
                return

            top_result = result_json["result"][0]
            title = top_result.get("anilist", {}).get("title", {}).get("romaji", "Unknown")
            episode = top_result.get("episode", "Unknown")
            similarity = top_result.get("similarity", 0) * 100
            at_time = top_result.get("from", 0)
            minutes = int(at_time // 60)
            seconds = int(at_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            await status_msg.edit(self.strings("result").format(
                title=title,
                episode=episode,
                time=time_str,
                similarity=similarity
            ))

        except Exception as e:
            logger.exception(e)
            await status_msg.edit(self.strings("error").format(error=str(e))) 
