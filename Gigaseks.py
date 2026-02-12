#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
#   GigaChat AI с памятью и контекстом

import asyncio
import logging
import time

from .. import loader, utils
import hikkatl

logger = logging.getLogger(__name__)

@loader.tds
class GigaChat(loader.Module):
    """Минимальный GigaChat AI с контекстом"""

    strings = {
        "name": "GigaChat",
        "enabled": "🟢 GigaChat включён в этом чате",
        "disabled": "🔴 GigaChat выключен",
        "thinking": "🔄 Думаю...",
    }

    BLOCKED_WORDS = ["террор", "бомб", "убийств", "насилие"]

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.ggbot = "@GigaChat_Bot"

        # один активный чат
        self.active_chat = self.db.get("GigaChat", "active_chat", None)

        # антифлуд
        self.last_reply = 0

        # память контекста: chat_id -> [(role, text)]
        self.context = self.db.get("GigaChat", "context", {}) or {}

        # стартуем бота, чтобы он был готов
        try:
            async with self._client.conversation(self.ggbot) as conv:
                msg = await conv.send_message("/start")
                r = await conv.get_response()
                await msg.delete()
                await r.delete()
        except:
            pass

    # -----------------------------
    # Запрос к AI
    # -----------------------------
    async def _ask_ai(self, q, chat_id):
        messages = self.context.get(str(chat_id), [])
        prompt_lines = []

        for role, text in messages[-10:]:  # последние 10 сообщений
            prompt_lines.append(f"{role}: {text}")

        prompt_lines.append(f"User: {q}")
        prompt = "\n".join(prompt_lines)

        while True:
            try:
                async with self._client.conversation(self.ggbot) as conv:
                    msg = await conv.send_message(prompt)
                    r = await conv.get_response()
                    await msg.delete()
                    await r.delete()
                return r.text
            except hikkatl.errors.common.AlreadyInConversationError:
                await asyncio.sleep(3)

    # -----------------------------
    # Переключение активного чата
    # -----------------------------
    @loader.command()
    async def giga(self, message):
        """Включить/выключить GigaChat в этом чате"""
        chat_id = utils.get_chat_id(message)

        if self.active_chat == chat_id:
            self.active_chat = None
            self.db.set("GigaChat", "active_chat", None)
            return await utils.answer(message, self.strings["disabled"])

        self.active_chat = chat_id
        self.db.set("GigaChat", "active_chat", chat_id)
        return await utils.answer(message, self.strings["enabled"])

    # -----------------------------
    # Проверка запрещённых слов
    # -----------------------------
    def is_blocked(self, text):
        text = text.lower()
        return any(w in text for w in self.BLOCKED_WORDS)

    # -----------------------------
    # Watcher: автоответ
    # -----------------------------
    async def watcher(self, message):
        if message.out or not message.text:
            return

        chat_id = utils.get_chat_id(message)
        if chat_id != self.active_chat:
            return

        if self.is_blocked(message.text):
            return

        now = time.time()
        delay = 2
        if now - self.last_reply < delay:
            return
        self.last_reply = now
        await asyncio.sleep(delay)

        try:
            answer = await self._ask_ai(message.text, chat_id)

            if self.is_blocked(answer):
                return

            await message.reply(answer)

            # сохраняем контекст
            msgs = self.context.get(str(chat_id), [])
            msgs.append(("User", message.text))
            msgs.append(("Assistant", answer))
            self.context[str(chat_id)] = msgs[-50:]  # последние 50 сообщений
            self.db.set("GigaChat", "context", self.context)

        except Exception as e:
            logger.error(f"GigaChat error: {e}") 
