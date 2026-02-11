# -*- coding: utf-8 -*-
# meta developer: @yourusername
# name: AniSearch
# description: Модуль для поиска аниме по кадру через trace.moe
# meta banner: https://i.imgur.com/3Q7VZEv.png
# meta pic: https://i.imgur.com/3Q7VZEv.png

import io
import aiohttp
import logging
from telethon import events
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AniSearchMod(loader.Module):
    """Ищет аниме по кадру через trace.moe"""
    strings = {
        "name": "AniSearch",
        "searching": "🔎 Ищу аниме по кадру...",
        "not_found": "❌ Ничего не найдено.",
        "result": "🎬 Аниме: {title}\n📺 Серия: {episode}\n⏱ Таймкод: {time}\n🎯 Совпадение: {sim}%",
        "no_args": "<b>Отправь фото или ответь на фото командой</b>"
    }

    @loader.unrestricted
    async def anisearchcmd(self, message):
        """[реплай на фото] - ищет аниме по кадру"""
        reply = await message.get_reply_message()
        if not reply or not (reply.photo or reply.document):
            await utils.answer(message, self.strings("no_args"))
            return

        status_msg = await utils.answer(message, self.strings("searching"))

        file = await reply.download_media(bytes)
        file_buffer = io.BytesIO(file)
        file_buffer.name = "frame.jpg"

        api_url = "https://api.trace.moe/search"

        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("image", file_buffer, filename="frame.jpg")
                async with session.post(api_url, data=form) as resp:
                    data = await resp.json()

            if not data.get("result"):
                await status_msg.edit(self.strings("not_found"))
                return

            result = data["result"][0]
            title = result.get("filename", "Неизвестно")
            episode = result.get("episode", "?")
            similarity = round(result.get("similarity", 0) * 100, 2)
            from_time = int(result.get("from", 0))
            minutes = from_time // 60
            seconds = from_time % 60

            text = self.strings("result").format(
                title=title,
                episode=episode,
                time=f"{minutes}:{seconds:02d}",
                sim=similarity
            )

            await status_msg.edit(text)

        except Exception as e:
            logger.exception(e)
            await status_msg.edit("❌ Произошла ошибка при поиске аниме.")
