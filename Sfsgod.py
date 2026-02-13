#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta icon: https://t.me/FAmods_icon
# meta banner: https://t.me/FAmods_banner

import asyncio
from .. import loader, utils

@loader.tds
class CodeBuilder(loader.Module):
    """Собирает Python код из сообщений и создаёт .py файл"""

    strings = {"name": "CodeBuilder"}

    def __init__(self):
        self._code_parts = []
        self._filename = None

    @loader.command()
    async def addcode(self, message):
        """Добавить кусок кода"""
        code = utils.get_args_raw(message)
        if not code and message.reply_to_msg_id:
            reply = await message.get_reply_message()
            code = reply.text if reply else ""
        if not code:
            await utils.answer(message, "Нет кода для добавления!")
            return

        self._code_parts.append(code)
        await utils.answer(message, f"Код добавлен. Текущие части: {len(self._code_parts)}")

    @loader.command()
    async def createpy(self, message):
        """Создать файл .py из добавленных частей"""
        if not self._code_parts:
            await utils.answer(message, "Нет кода для сохранения!")
            return

        import time
        self._filename = f"module_{int(time.time())}.py"

        full_code = "\n".join(self._code_parts)

        # Сохраняем файл
        with open(self._filename, "w", encoding="utf-8") as f:
            f.write(full_code)

        # Отправляем файл
        await message.client.send_file(
            message.chat_id,
            self._filename,
            caption=f"Файл **{self._filename}** создан и отправлен."
        )

        # Сбрасываем код
        self._code_parts = []

    @loader.command()
    async def cleancode(self, message):
        """Очистить все добавленные куски кода"""
        self._code_parts = []
        await utils.answer(message, "Все добавленные куски кода очищены.")

    @loader.command()
    async def codeparts(self, message):
        """Показать количество добавленных частей"""
        await utils.answer(message, f"Добавленных частей кода: {len(self._code_parts)}")
