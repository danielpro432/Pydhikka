# meta developer: @Dany23s
# meta name: CVPy
# meta desc: Превращает код из сообщения в .py файл и отправляет в чат
# meta icon: https://raw.githubusercontent.com/favicon.ico

import os
import time
import re
from .. import loader, utils

@loader.tds
class CVPyMod(loader.Module):
    """Сохраняет код в .py и отправляет файл в чат"""

    strings = {
        "name": "CVPy",
        "no_code": "❌ Код не найден. Ответь на сообщение с кодом или напиши после команды.",
        "saved": "✅ Файл <b>{}</b> создан и отправлен.",
        "error": "❌ Ошибка при создании файла: {}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "SAVE_DIR",
                "cvpy_files",
                lambda: "Папка для сохранения файлов",
                validator=loader.validators.String()
            ),
        )
        # Создаём папку если её нет
        if not os.path.exists(self.config["SAVE_DIR"]):
            os.makedirs(self.config["SAVE_DIR"])

    @loader.command()
    async def cvpy(self, message):
        """Создать .py файл из кода"""
        code = utils.get_args_raw(message)

        # Если нет текста после команды — пробуем взять reply
        if not code:
            reply = await message.get_reply_message()
            if reply and hasattr(reply, "text") and reply.text:
                code = reply.text
            else:
                await utils.answer(message, self.strings["no_code"])
                return

        # Дополнительно: собрать все split сообщения (если текст > 4096 символов)
        # В reply может быть split, просто объединяем все строки
        if code and len(code) > 4096:
            code = "\n".join(code.splitlines())

        # Генерация безопасного имени файла
        safe_name = re.sub(r"\W", "_", code[:15])
        filename = f"{safe_name}_{int(time.time())}.py"
        filepath = os.path.join(self.config["SAVE_DIR"], filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            await message.client.send_file(
                message.chat_id,
                filepath,
                caption=f"Файл <b>{filename}</b> готов.",
                force_document=True,
            )
            await utils.answer(message, self.strings["saved"].format(filename))

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e))
