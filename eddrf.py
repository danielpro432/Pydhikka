# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta name: CodeBuilder
# meta banner: https://t.me/FAmods_banner

import asyncio
import os
from .. import loader, utils

@loader.tds
class CodeBuilder(loader.Module):
    """Собирает текст Python кода и создаёт .py файл с правильными отступами"""

    strings = {"name": "CodeBuilder"}

    def __init__(self):
        self._code_parts = []
        self.temp_dir = "/tmp"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def normalize_indentation(self, code):
        """Нормализует отступы: табы → 4 пробела"""
        lines = code.split('\n')
        normalized = []
        
        for line in lines:
            if line.strip():
                line = line.replace('\t', '    ')
            normalized.append(line)
        
        return '\n'.join(normalized)

    @loader.command()
    async def addcode(self, message):
        """Добавить кусок кода (ответ на сообщение или текст после команды)"""
        code = utils.get_args_raw(message)
        
        if not code and message.reply_to_msg_id:
            reply = await message.get_reply_message()
            code = reply.text or ""
            if reply.document:
                try:
                    file = await reply.download_media()
                    with open(file, 'r', encoding='utf-8') as f:
                        code = f.read()
                    os.remove(file)
                except:
                    pass
        
        if not code:
            await utils.answer(message, "❌ Нет кода для добавления!")
            return

        normalized = self.normalize_indentation(code)
        self._code_parts.append(normalized)
        await utils.answer(message, f"✅ Добавлено. Частей: {len(self._code_parts)}")

    @loader.command()
    async def buildpy(self, message):
        """Создать .py файл из всех добавленных частей"""
        if not self._code_parts:
            await utils.answer(message, "❌ Нет кода для сохранения!")
            return

        try:
            import time
            filename = f"module_{int(time.time())}.py"
            filepath = os.path.join(self.temp_dir, filename)

            full_code = "\n".join(self._code_parts)
            full_code = self.normalize_indentation(full_code)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_code)

            await message.client.send_file(
                message.chat_id,
                filepath,
                caption=f"📄 Файл **{filename}** готов\n\n`.lm {filename}`"
            )

            self._code_parts = []

            if os.path.exists(filepath):
                os.remove(filepath)
                
            await utils.answer(message, "✅ Файл отправлен")

        except Exception as e:
            await utils.answer(message, f"❌ Ошибка: {str(e)}")

    @loader.command()
    async def showcode(self, message):
        """Показать весь код"""
        if not self._code_parts:
            await utils.answer(message, "❌ Нет кода!")
            return

        full_code = "\n".join(self._code_parts)

        if len(full_code) > 3500:
            await utils.answer(message, f"```python\n{full_code[:3490]}\n```\n⚠️ Показаны первые 3500 символов")
        else:
            await utils.answer(message, f"```python\n{full_code}\n```")

    @loader.command()
    async def clearcode(self, message):
        """Очистить весь код"""
        self._code_parts = []
        await utils.answer(message, "🗑️ Код очищен")

    @loader.command()
    async def codecount(self, message):
        """Количество частей"""
        await utils.answer(message, f"📊 Частей: {len(self._code_parts)}")

    @loader.command()
    async def delcode(self, message):
        """Удалить последнюю часть"""
        if not self._code_parts:
            await utils.answer(message, "❌ Нечего удалять!")
            return
        
        self._code_parts.pop()
        await utils.answer(message, f"❌ Удалено. Осталось: {len(self._code_parts)}")
