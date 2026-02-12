#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
#   GigaChat AI с памятью и контекстом через DeepSeek API

import asyncio
import logging
import aiohttp
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class GigaChatDS(loader.Module):
    """GigaChat AI через DeepSeek API с контекстом"""

    strings = {
        "name": "GigaChatDS",
        "enabled": "🟢 GigaChat включён в этом чате",
        "disabled": "🔴 GigaChat выключен",
        "thinking": "🤖 Думаю...",
        "context_cleared": "🗑 Контекст очищен",
        "error": "❌ Ошибка: {}",
    }

    BLOCKED_WORDS = ["террор", "бомб", "убийств", "насилие"]

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                "",
                "🔑 DeepSeek API ключ (platform.deepseek.com)",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "model",
                "deepseek-chat",
                "🤖 Модель для использования",
                validator=loader.validators.Choice(["deepseek-chat", "deepseek-reasoner"]),
            ),
            loader.ConfigValue(
                "system_prompt",
                "Ты — полезный AI ассистент. Отвечай кратко и по делу на русском языке.",
                "📝 Системный промпт",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "max_tokens",
                4096,
                "📏 Максимум токенов в ответе (1-8192)",
                validator=loader.validators.Integer(1, 8192),
            ),
            loader.ConfigValue(
                "temperature",
                0.7,
                "🌡 Температура (0.0-2.0)",
                validator=loader.validators.Float(0.0, 2.0),
            ),
            loader.ConfigValue(
                "context_enabled",
                True,
                "💬 Сохранять контекст диалога",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "context_limit",
                10,
                "📚 Максимум сообщений в контексте",
                validator=loader.validators.Integer(2, 50),
            ),
        )

        self.active_chat = None
        self.context = {}
        self.last_reply = 0

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.active_chat = self.db.get("GigaChatDS", "active_chat", None)
        self.context = self.db.get("GigaChatDS", "context", {}) or {}

    # -----------------------------
    # Проверка запрещённых слов
    # -----------------------------
    def is_blocked(self, text):
        text = text.lower()
        return any(w in text for w in self.BLOCKED_WORDS)

    # -----------------------------
    # Включение/выключение бота
    # -----------------------------
    @loader.command()
    async def giga(self, message):
        """Включить/выключить GigaChat в этом чате"""
        chat_id = utils.get_chat_id(message)
        if self.active_chat == chat_id:
            self.active_chat = None
            self.db.set("GigaChatDS", "active_chat", None)
            return await utils.answer(message, self.strings["disabled"])
        self.active_chat = chat_id
        self.db.set("GigaChatDS", "active_chat", chat_id)
        return await utils.answer(message, self.strings["enabled"])

    # -----------------------------
    # Очистка контекста
    # -----------------------------
    @loader.command()
    async def gclear(self, message):
        """Очистить контекст чата"""
        chat_id = utils.get_chat_id(message)
        self.context[str(chat_id)] = []
        self.db.set("GigaChatDS", "context", self.context)
        await utils.answer(message, self.strings["context_cleared"])

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

        # антифлуд
        import time
        now = time.time()
        if now - self.last_reply < 2:
            return
        self.last_reply = now

        await asyncio.sleep(2)
        try:
            answer = await self._ask_deepseek(message.text, chat_id)
            if self.is_blocked(answer):
                return
            await message.reply(answer)

            # сохраняем контекст
            if self.config["context_enabled"]:
                msgs = self.context.get(str(chat_id), [])
                msgs.append(f"User: {message.text}")
                msgs.append(f"GigaChat: {answer}")
                self.context[str(chat_id)] = msgs[-self.config["context_limit"] :]
                self.db.set("GigaChatDS", "context", self.context)

        except Exception as e:
            logger.error(f"GigaChatDS error: {e}")
            await utils.answer(message, self.strings["error"].format(e))

    # -----------------------------
    # Запрос к DeepSeek API
    # -----------------------------
    async def _ask_deepseek(self, text, chat_id):
        api_key = self.config["api_key"]
        if not api_key:
            return "❌ API ключ не задан"

        messages = [{"role": "system", "content": self.config["system_prompt"]}]
        if self.config["context_enabled"]:
            messages.extend(self.context.get(str(chat_id), []))
        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
            "stream": False,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(data.get("error", {}).get("message", str(data)))
                choice = data["choices"][0]["message"]
                return choice.get("content", "") 
