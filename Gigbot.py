#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

#   https://t.me/famods

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: GigaChat
# Description: GigaChat AI. Без спама. Работает только в одном чате.
# meta developer: @FAmods
# requires: aiohttp
# ---------------------------------------------------------------------------------

import asyncio
import logging
import time
import hikkatl

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class GigaChat(loader.Module):
    """GigaChat AI. Safe single chat mode."""

    strings = {
        "name": "GigaChat",
        "enabled": "🟢 GigaChat включён в этом чате",
        "disabled": "🔴 GigaChat выключен",
        "asking": "🔄 Думаю...",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.ggbot = "@GigaChat_Bot"

        # один активный чат
        self.active_chat = self.db.get("GigaChat", "active_chat", None)

        # антифлуд таймер
        self.last_reply = 0

        try:
            async with self._client.conversation(self.ggbot) as conv:
                msg = await conv.send_message("/start")
                r = await conv.get_response()
                await msg.delete()
                await r.delete()
        except:
            pass

    async def _ask_ai(self, q):
        while True:
            try:
                async with self._client.conversation(self.ggbot) as conv:
                    msg = await conv.send_message(q)
                    r = await conv.get_response()
                    await msg.delete()
                    await r.delete()
                return r.text
            except hikkatl.errors.common.AlreadyInConversationError:
                await asyncio.sleep(5)

    # ----------------------------
    # Переключатель режима
    # ----------------------------
    @loader.command()
    async def giga(self, message):
        """Включить/выключить GigaChat в текущем чате"""
        chat_id = utils.get_chat_id(message)

        if self.active_chat == chat_id:
            self.active_chat = None
            self.db.set("GigaChat", "active_chat", None)
            return await utils.answer(message, self.strings["disabled"])

        # включаем в новом чате и заменяем старый
        self.active_chat = chat_id
        self.db.set("GigaChat", "active_chat", chat_id)
        return await utils.answer(message, self.strings["enabled"])

    # ----------------------------
    # Автоответчик (умный)
    # ----------------------------
    async def watcher(self, message):
        if message.out or not message.text:
            return

        chat_id = utils.get_chat_id(message)

        # работает только в активном чате
        if chat_id != self.active_chat:
            return

        # антифлуд: минимальная задержка
        now = time.time()
        delay = 3  # 2 сек для ЛС

        # увеличиваем задержку в группе, если сообщений много
        if getattr(message.chat, "participants_count", 0) > 5:
            delay = max(5, min(20, delay))  # 5–20 сек для активных групп

        if now - self.last_reply < delay:
            return

        self.last_reply = now

        await asyncio.sleep(delay)  # "печатает..."

        try:
            answer = await self._ask_ai(message.text)
            await message.reply(answer)
        except Exception as e:
            logger.error(f"GigaChat error: {e}") 
