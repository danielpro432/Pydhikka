#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
#   GigaChat AI с памятью, контекстом и cfg-настройками

import asyncio
import logging
import time
from .. import loader, utils
import hikkatl

logger = logging.getLogger(__name__)

@loader.tds
class GigaChat(loader.Module):
    """GigaChat AI с конфигом и системным промптом"""

    strings = {
        "name": "GigaChat",
        "enabled": "🟢 GigaChat включён в этом чате",
        "disabled": "🔴 GigaChat выключен",
        "thinking": "🔄 Думаю...",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "system_prompt",
                "Ты — дружелюбный AI ассистент, отвечай вежливо и кратко.",
                "📝 Роль бота (можно писать: Ты — Халк, Шерлок, кто угодно)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "max_context",
                10,
                "📚 Сколько последних сообщений хранить в контексте",
                validator=loader.validators.Integer(minimum=1, maximum=50),
            ),
            loader.ConfigValue(
                "blocked_words",
                "террор,бомб,убийств,насилие",
                "⛔️ Запрещённые слова через запятую",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "reply_delay",
                2.0,
                "⏱ Задержка перед ответом в секундах",
                validator=loader.validators.Float(minimum=0.5, maximum=10.0),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.ggbot = "@GigaChat_Bot"

        self.active_chat = self.db.get("GigaChat", "active_chat", None)
        self.last_reply = 0
        self.context = self.db.get("GigaChat", "context", {}) or {}

        try:
            async with self._client.conversation(self.ggbot) as conv:
                msg = await conv.send_message("/start")
                r = await conv.get_response()
                await msg.delete()
                await r.delete()
        except:
            pass

    async def _ask_ai(self, q, chat_id):
        # Формируем контекст для AI
        messages = self.context.get(str(chat_id), [])
        prompt_lines = [f"{role}: {text}" for role, text in messages[-self.config["max_context"]:]]
        prompt_lines.append(f"{self.config['system_prompt']}")
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

    def is_blocked(self, text):
        text = text.lower()
        words = [w.strip() for w in self.config["blocked_words"].split(",")]
        return any(w in text for w in words)

    async def watcher(self, message):
        if message.out or not message.text:
            return

        chat_id = utils.get_chat_id(message)
        if chat_id != self.active_chat:
            return

        if self.is_blocked(message.text):
            return

        now = time.time()
        delay = self.config["reply_delay"]
        if now - self.last_reply < delay:
            return
        self.last_reply = now
        await asyncio.sleep(delay)

        try:
            answer = await self._ask_ai(message.text, chat_id)
            if self.is_blocked(answer):
                return

            # Отправка ответа без скобок
            answer = answer.replace("()", "").strip()
            await message.reply(answer)

            # Сохраняем контекст
            msgs = self.context.get(str(chat_id), [])
            msgs.append(("User", message.text))
            msgs.append(("Assistant", answer))
            self.context[str(chat_id)] = msgs[-50:]
            self.db.set("GigaChat", "context", self.context)

        except Exception as e:
            logger.error(f"GigaChat error: {e}")
