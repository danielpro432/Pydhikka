import asyncio
import os
from .. import loader, utils

@loader.tds
class CodeBuilder(loader.Module):
    """Собирает Python код из сообщений и создаёт .py файл"""

    strings = {"name": "CodeBuilder"}

    def __init__(self):
        self._code_parts = []
        self._filename = None
        # Создаём временную директорию для Heroku
        self.temp_dir = "/tmp"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    @loader.command()
    async def addcode(self, message):
        """Добавить кусок кода"""
        code = utils.get_args_raw(message)
        if not code and message.reply_to_msg_id:
            reply = await message.get_reply_message()
            code = reply.text if reply else ""
        if not code:
            await utils.answer(message, "❌ Нет кода для добавления!")
            return

        self._code_parts.append(code)
        await utils.answer(
            message, 
            f"✅ Код добавлен. Текущие части: {len(self._code_parts)}"
        )

    @loader.command()
    async def createpy(self, message):
        """Создать файл .py из добавленных частей"""
        if not self._code_parts:
            await utils.answer(message, "❌ Нет кода для сохранения!")
            return

        try:
            import time
            filename = f"module_{int(time.time())}.py"
            self._filename = os.path.join(self.temp_dir, filename)

            full_code = "\n".join(self._code_parts)

            # Сохраняем файл во временную папку
            with open(self._filename, "w", encoding="utf-8") as f:
                f.write(full_code)

            # Отправляем файл
            await message.client.send_file(
                message.chat_id,
                self._filename,
                caption=f"📄 Файл **{filename}** создан и отправлен."
            )

            # Сбрасываем код
            self._code_parts = []

            # Удаляем файл после отправки (для экономии места на Heroku)
            if os.path.exists(self._filename):
                os.remove(self._filename)

        except Exception as e:
            await utils.answer(message, f"❌ Ошибка при создании файла: {str(e)}")

    @loader.command()
    async def cleancode(self, message):
        """Очистить все добавленные куски кода"""
        self._code_parts = []
        await utils.answer(message, "🗑️ Все добавленные куски кода очищены.")

    @loader.command()
    async def codeparts(self, message):
        """Показать количество добавленных частей"""
        count = len(self._code_parts)
        await utils.answer(message, f"📊 Добавленных частей кода: {count}")

    @loader.command()
    async def showcode(self, message):
        """Показать весь собранный код"""
        if not self._code_parts:
            await utils.answer(message, "❌ Нет добавленного кода!")
            return
        
        full_code = "\n".join(self._code_parts)
        
        if len(full_code) > 4000:
            await utils.answer(
                message, 
                f"```python\n{full_code[:3990]}\n```\n⚠️ ... (текст обрезан)"
            )
        else:
            await utils.answer(message, f"```python\n{full_code}\n```")

    @loader.command()
    async def setfilename(self, message):
        """Установить имя файла"""
        filename = utils.get_args_raw(message)
        if not filename:
            await utils.answer(message, "❌ Укажите имя файла!")
            return
        
        if not filename.endswith('.py'):
            filename += '.py'
        
        self._filename = filename
        await utils.answer(message, f"✅ Имя файла установлено: {filename}")
