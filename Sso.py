# meta developer: @Dany23s
# meta name: CodeCollector
# meta icon: 📝

import asyncio
from .. import loader, utils

@loader.tds
class CodeCollector(loader.Module):
    """Собирает код из сообщений и делает файл .py"""

    strings = {"name": "CodeCollector"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "FILENAME",
                "collected_code.py",
                lambda: "Имя файла для сохранения кода",
                validator=loader.validators.String()
            ),
        )
        self._buffer = []

    @loader.command()
    async def cvstart(self, message):
        """Начать сбор кода"""
        self._buffer = []
        await utils.answer(message, "<b>Сбор кода начат. Отправляй части кода.</b>")

    @loader.command()
    async def cvadd(self, message):
        """Добавить кусок кода"""
        text = utils.get_args_raw(message)
        if not text:
            reply = await message.get_reply_message()
            if reply and reply.text:
                text = reply.text
        if not text:
            await utils.answer(message, "<b>Нет текста для добавления.</b>")
            return
        self._buffer.append(text)
        await utils.answer(message, f"<b>Добавлено {len(text.splitlines())} строк кода.</b>")

    @loader.command()
    async def cvsave(self, message):
        """Сохранить собранный код в файл и прислать"""
        if not self._buffer:
            await utils.answer(message, "<b>Буфер пуст, нечего сохранять.</b>")
            return

        filename = self.config["FILENAME"]
        code_text = "\n".join(self._buffer)

        # Сохраняем в файл
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code_text)

        # Отправляем файл в чат
        await message.client.send_file(message.chat_id, filename)
        await utils.answer(message, f"<b>Файл <code>{filename}</code> создан и отправлен.</b>")

        # Очищаем буфер
        self._buffer = []

    @loader.command()
    async def cvclear(self, message):
        """Очистить буфер без сохранения"""
        self._buffer = []
        await utils.answer(message, "<b>Буфер очищен.</b>")
