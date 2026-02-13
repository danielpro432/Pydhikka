# meta developer: @Dany23s
# meta name: SafeCodeCollector
# meta icon: 📝

import os
import asyncio
from html import unescape
from .. import loader, utils

@loader.tds
class SafeCodeCollector(loader.Module):
    """Собирает код из сообщений и создаёт безопасный .py файл"""

    strings = {
        "name": "SafeCodeCollector",
        "no_code": "<b>Нет кода для добавления.</b>",
        "added": "<b>Код добавлен к сборке.</b>",
        "file_created": "<b>Файл {filename} создан и отправлен.</b>",
        "cleared": "<b>Сборка очищена.</b>",
    }

    def __init__(self):
        self.buffer = []

    @loader.command()
    async def addcode(self, message):
        """Добавить код в сборку"""
        text = utils.get_args_raw(message)
        if not text:
            reply = await message.get_reply_message()
            if reply and reply.text:
                text = reply.text
            else:
                await utils.answer(message, self.strings["no_code"])
                return

        # Убираем Telegram HTML-форматирование
        safe_text = unescape(text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        self.buffer.append(safe_text)
        await utils.answer(message, self.strings["added"])

    @loader.command()
    async def createpy(self, message):
        """Создать .py файл из собранного кода"""
        if not self.buffer:
            await utils.answer(message, self.strings["no_code"])
            return

        filename = f"CollectedCode_{int(asyncio.get_event_loop().time())}.py"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n\n".join(self.buffer))

        await message.client.send_file(message.chat_id, filename)
        await utils.answer(message, self.strings["file_created"].format(filename=filename))

        # После создания файла буфер очищается
        self.buffer.clear()
        os.remove(filename)

    @loader.command()
    async def clearcode(self, message):
        """Очистить текущую сборку"""
        self.buffer.clear()
        await utils.answer(message, self.strings["cleared"])
