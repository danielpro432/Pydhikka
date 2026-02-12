#             █ █ ▀ █▄▀ ▄▀█ █▀█ ▀
#             █▀█ █ █ █ █▀█ █▀▄ █
#              © Copyright 2022
#           https://t.me/hikariatama
#
# 🔒      Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# meta pic: https://static.dan.tatar/aniquotes_icon.png
# meta banner: https://mods.hikariatama.ru/badges/aniquotes.jpg
# meta developer: @hikarimods
# scope: hikka_only
# scope: hikka_min 1.2.10

from random import choice
import asyncio
import re
from telethon.tl.types import Message
from .. import loader, utils

from PIL import Image, ImageDraw, ImageFont
import io


@loader.tds
class AnimatedQuotesMod(loader.Module):
    """Universal module to create animated stickers from text or media"""

    strings = {
        "name": "AnimatedQuotes",
        "no_text": "<emoji document_id=5312526098750252863>🚫</emoji> <b>Provide a text or reply to media</b>",
        "processing": "<emoji document_id=5451646226975955576>⌛️</emoji> <b>Processing...</b>",
        "too_long": "<b>⚠️ Текст слишком длинный, разбит на несколько стикеров.</b>",
        "bot_fail": "<b>⚠️ Не удалось обработать текст или медиа.</b>",
    }

    MAX_LEN = 250  # макс. длина текста для одного inline запроса

    async def aniqcmd(self, message: Message):
        """<text> - Create animated sticker from text or media"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message() if message.is_reply else None

        # Получаем текст из цепочки реплаев
        async def get_text_from_reply(msg):
            while msg:
                if msg.message and msg.message.strip():
                    return msg.message
                if msg.is_reply:
                    msg = await msg.get_reply_message()
                else:
                    break
            return None

        text = args or (await get_text_from_reply(reply))
        media = reply.media if reply and reply.media else None

        if not text and not media:
            await utils.answer(message, self.strings("no_text"))
            return

        # Чистим текст
        if text:
            text = re.sub(r"[^\S\r\n]+", " ", text).strip()

        processing_msg = await utils.answer(message, self.strings("processing"))

        # Если есть только медиа или медиа + текст
        if media:
            try:
                # Получаем bytes изображения
                file_bytes = io.BytesIO()
                await self._client.download_media(media, file_bytes)
                file_bytes.seek(0)
                img = Image.open(file_bytes).convert("RGBA")

                # Если есть текст, накладываем
                if text:
                    draw = ImageDraw.Draw(img)
                    font_size = max(20, img.width // 15)
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()

                    # Простое центрирование текста
                    lines = []
                    words = text.split()
                    line = ""
                    for w in words:
                        if len(line + " " + w) < 25:
                            line += " " + w if line else w
                        else:
                            lines.append(line)
                            line = w
                    if line:
                        lines.append(line)

                    y = 10
                    for l in lines:
                        w, h = draw.textsize(l, font=font)
                        draw.text(((img.width - w) / 2, y), l, font=font, fill="white")
                        y += h + 5

                out_bytes = io.BytesIO()
                img.save(out_bytes, format="PNG")
                out_bytes.seek(0)
                await processing_msg.respond(file=out_bytes)
            except Exception:
                await utils.answer(processing_msg, self.strings("bot_fail"))
            await asyncio.sleep(5)
            try:
                await processing_msg.delete()
            except:
                pass
            if message.out:
                await message.delete()
            return

        # Если только текст
        chunks = [text[i:i+self.MAX_LEN] for i in range(0, len(text or ""), self.MAX_LEN)] or [""]
        if len(chunks) > 1:
            await utils.answer(processing_msg, self.strings("too_long"))

        for chunk in chunks:
            try:
                query = await self._client.inline_query("@QuotAfBot", chunk)
                if query:
                    await processing_msg.respond(file=choice(query).document)
                else:
                    await utils.answer(processing_msg, self.strings("bot_fail"))
            except Exception:
                await utils.answer(processing_msg, self.strings("bot_fail"))

        # Автоудаление Processing через 5 секунд
        await asyncio.sleep(5)
        try:
            await processing_msg.delete()
        except:
            pass

        if message.out:
            await message.delete()
