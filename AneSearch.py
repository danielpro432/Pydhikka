# -*- coding: utf-8 -*-
# meta developer: @your_username
# meta name: AniSearch
# meta description: Ищет аниме по кадру через trace.moe API
# meta version: 1.0.0

import io
import logging
import aiohttp
from telethon.tl.types import DocumentAttributeFilename
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AniSearchMod(loader.Module):
    """Модуль поиска аниме по кадру"""
    strings = {
        "name": "AniSearch",
        "no_media": "<b>❌ Реплай на изображение или прикрепи фото к сообщению.</b>",
        "searching": "<b>🔍 Ищу аниме...</b>",
        "result": ("✅ <b>Результат поиска:</b>\n"
                   "• Название: <b>{title}</b>\n"
                   "• Эпизод: <b>{episode}</b>\n"
                   "• Время: <b>{time}</b>\n"
                   "• Сходство: <b>{similarity:.2f}%</b>\n"
                   "• [Ссылка на аниме](https://anilist.co/anime/{anilist_id})"),
        "error": "<b>❌ Ошибка при поиске:</b> {error}"
    }

    @loader.command(
        ru_doc="<картинка> — ищет аниме по кадру",
        en_doc="<image> — search anime by frame",
        alias="anisearch"
    )
    async def anisearchcmd(self, message):
        """Команда для поиска аниме по изображению"""
        # Получаем объект сообщения, на которое делается reply
        reply_msg = await message.get_reply_message() if message.is_reply else message
        media = getattr(reply_msg, "media", None)

        if not media:
            await utils.answer(message, self.strings("no_media"))
            return

        status_msg = await utils.answer(message, self.strings("searching"))

        # Загружаем изображение в память
        file_buffer = io.BytesIO()
        file_name = "anime.jpg"

        if hasattr(media, "document") and media.document:
            for attr in media.document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_name = attr.file_name
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

            if not result_json.get("result"):
                await status_msg.edit("<b>❌ Аниме не найдено.</b>")
                return

            top = result_json["result"][0]
            anilist_id = top.get("anilist", {}).get("id", 0)
            title = top.get("anilist", {}).get("title", {}).get("romaji", "Unknown")
            episode = top.get("episode", "Unknown")
            similarity = top.get("similarity", 0) * 100
            at_time = top.get("from", 0)
            minutes, seconds = divmod(int(at_time), 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            await status_msg.edit(self.strings("result").format(
                title=title,
                episode=episode,
                time=time_str,
                similarity=similarity,
                anilist_id=anilist_id
            ), link_preview=False)

        except Exception as e:
            logger.exception(e)
            await status_msg.edit(self.strings("error").format(error=str(e)))
