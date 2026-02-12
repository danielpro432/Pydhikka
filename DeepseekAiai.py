"""
🤖 DeepSeek — AI ассистент через DeepSeek API на Heroku

Команды:
• .ds <вопрос> — задать вопрос AI
• .dsclear — очистить контекст диалога
• .dsmodels — список доступных моделей
"""

__version__ = (1, 0, 0)
# meta developer: @username
# meta pic: https://cdn-icons-png.flaticon.com/512/8637/8637457.png
# scope: hikka_only
# requires: aiohttp, os

import os
import aiohttp
import logging
from .. import loader, utils
from herokutl.types import Message

logger = logging.getLogger(__name__)

@loader.tds
class DeepSeekMod(loader.Module):
    """AI ассистент через DeepSeek API"""
    
    strings = {
        "name": "DeepSeek",
        "no_args": "❌ Укажи вопрос\nИспользование: .ds <текст>",
        "no_api_key": "❌ API ключ не найден\nДобавь DEEPSEEK_API_KEY в Config Vars Heroku",
        "thinking": "🤔 Думаю...",
        "error": "❌ Ошибка API: {}",
        "context_cleared": "🗑 Контекст диалога очищен",
        "models": "📋 Доступные модели:\n• deepseek-chat — обычный чат\n• deepseek-reasoner — с reasoning (R1)",
        "response": "🤖 DeepSeek:\n\n{}",
        "response_with_reasoning": "🤖 DeepSeek:\n\n{}\n\n💭 Reasoning:\n{}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "model",
                "deepseek-chat",
                "Модель для использования",
                validator=loader.validators.Choice(["deepseek-chat","deepseek-reasoner"])
            ),
            loader.ConfigValue(
                "system_prompt",
                "Ты — полезный AI ассистент. Отвечай кратко и по делу на русском языке.",
                "Системный промпт",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "max_tokens",
                4096,
                "Максимум токенов в ответе (1-8192)",
                validator=loader.validators.Integer(minimum=1, maximum=8192)
            ),
            loader.ConfigValue(
                "temperature",
                0.7,
                "Температура (0.0-2.0)",
                validator=loader.validators.Float(minimum=0.0, maximum=2.0)
            ),
            loader.ConfigValue(
                "context_enabled",
                True,
                "Сохранять контекст",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "context_limit",
                10,
                "Максимум сообщений в контексте",
                validator=loader.validators.Integer(minimum=2, maximum=50)
            ),
            loader.ConfigValue(
                "show_reasoning",
                True,
                "Показывать reasoning",
                validator=loader.validators.Boolean()
            )
        )

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self.context = self.pointer("context", {})

    def _get_context(self, chat_id: int):
        chat_key = str(chat_id)
        if chat_key not in self.context:
            self.context[chat_key] = []
        return self.context[chat_key]

    def _add_to_context(self, chat_id: int, role: str, content: str):
        if not self.config["context_enabled"]:
            return
        chat_key = str(chat_id)
        if chat_key not in self.context:
            self.context[chat_key] = []
        self.context[chat_key].append({"role": role, "content": content})
        if len(self.context[chat_key]) > self.config["context_limit"]:
            self.context[chat_key] = self.context[chat_key][-self.config["context_limit"]:]

    def _clear_context(self, chat_id: int):
        chat_key = str(chat_id)
        self.context[chat_key] = []

    async def _api_request(self, messages: list):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise Exception("API ключ не найден")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
            "stream": False
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    error_msg = data.get("error", {}).get("message", str(data))
                    raise Exception(error_msg)
                return data

    @loader.command()
    async def dscmd(self, message: Message):
        """Задать вопрос DeepSeek AI"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        question_parts = []
        if reply and reply.text:
            question_parts.append(f"Контекст сообщения:\n{reply.text}")
        if args:
            question_parts.append(args)
        if not question_parts:
            await utils.answer(message, self.strings("no_args"))
            return

        question = "\n\n".join(question_parts)
        await utils.answer(message, self.strings("thinking"))

        try:
            chat_id = utils.get_chat_id(message)
            messages = [{"role": "system", "content": self.config["system_prompt"]}]
            if self.config["context_enabled"]:
                messages.extend(self._get_context(chat_id))
            messages.append({"role": "user", "content": question})

            response = await self._api_request(messages)
            choice = response["choices"][0]
            answer = choice["message"]["content"]
            reasoning = choice["message"].get("reasoning_content", "")

            self._add_to_context(chat_id, "user", question)
            self._add_to_context(chat_id, "assistant", answer)

            if reasoning and self.config["show_reasoning"]:
                result = self.strings("response_with_reasoning").format(answer, reasoning)
            else:
                result = self.strings("response").format(answer)

            await utils.answer(message, result)

        except Exception as e:
            logger.exception(e)
            await utils.answer(message, self.strings("error").format(str(e)))

    @loader.command()
    async def dsclearcmd(self, message: Message):
        """Очистить контекст диалога"""
        chat_id = utils.get_chat_id(message)
        self._clear_context(chat_id)
        await utils.answer(message, self.strings("context_cleared"))

    @loader.command()
    async def dsmodelscmd(self, message: Message):
        """Показать доступные модели"""
        await utils.answer(message, self.strings("models"))
