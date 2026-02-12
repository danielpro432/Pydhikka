#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
#   GigaChat AI с памятью и контекстом

import asyncio
import logging
import time
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class GigaChat(loader.Module):
    """GigaChat AI с контекстом и промптом"""

    strings = {
        "name": "GigaChat",
        "enabled": "🟢 GigaChat включён в этом чате",
        "disabled": "🔴 GigaChat выключен",
        "thinking": "🔄 Думаю...",
    }

    BLOCKED_WORDS = ["террор", "бомб", "убийств", "насилие"]

    def __init__(self):
        # Настройки модуля
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "system_prompt",
                "Ты — полезный AI ассистент. Отвечай кратко и по делу на русском языке.",
                "📝 Системный промпт",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "context_enabled",
                True,
                "💬 Сохранять контекст диалога",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "context_limit",
                10,
                "📚 Максимум сообщений в контексте (2-50)",
                validator=loader.validators.Integer(minimum=2, maximum=50)
            ),
            loader.ConfigValue(
                "reply_delay",
                2,
                "⏱ Задержка перед ответом (сек)",
                validator=loader.validators.Integer(minimum=1, maximum=10)
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.active_chat = self.db.get("GigaChat", "active_chat", None)
        self.last_reply = 0
        self.context = self.db.get("GigaChat", "context", {}) or {}

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
        for w in self.BLOCKED_WORDS:
            if w in text:
                return True
        return False

    # -----------------------------
    # Генерация ответа AI
    # -----------------------------
    async def _ask_ai(self, q, chat_id):
        # формируем контекст
        messages = self.context.get(str(chat_id), [])
        prompt = self.config["system_prompt"] + "\n\n"
        if self.config["context_enabled"]:
            prompt += "\n".join(messages[-self.config["context_limit"]:] + [f"User: {q}"])
        else:
            prompt += f"User: {q}"

        # тут можно встроить любой AI, пока просто эхо для теста
        # в будущем подключаем OpenAI или Gemini
        await asyncio.sleep(1)  # имитация "думания"
        return f"{q} (ответ AI на основе промпта)"

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
        if now - self.last_reply < self.config["reply_delay"]:
            return

        self.last_reply = now
        await asyncio.sleep(self.config["reply_delay"])

        try:
            answer = await self._ask_ai(message.text, chat_id)
            if self.is_blocked(answer):
                return

            await message.reply(answer)

            # сохраняем контекст
            if self.config["context_enabled"]:
                msgs = self.context.get(str(chat_id), [])
                msgs.append(f"User: {message.text}")
                msgs.append(f"GigaChat: {answer}")
                self.context[str(chat_id)] = msgs[-self.config["context_limit"]:]
                self.db.set("GigaChat", "context", self.context)

        except Exception as e:
            logger.error(f"GigaChat error: {e}") 
