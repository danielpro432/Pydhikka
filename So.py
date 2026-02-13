# meta developer: @Dany23s
# meta name: CVPy Multi
# meta desc: Собирает .py файл из нескольких сообщений
# meta icon: https://raw.githubusercontent.com/favicon.ico

import os
import time
import re
from .. import loader, utils

@loader.tds
class CVPyMultiMod(loader.Module):
    """Собирает .py файл из нескольких сообщений"""

    strings = {
        "name": "CVPyMulti",
        "no_code": "❌ Нет кода для добавления.",
        "saved": "✅ Файл <b>{}</b> создан и отправлен.",
        "error": "❌ Ошибка при создании файла: {}",
        "started": "📌 Начат сбор кода. Отправляйте куски кода, а затем команду <b>.cvpyend</b>.",
        "no_session": "❌ Нет активной сессии. Начните с <b>.cvpy</b>.",
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
        if not os.path.exists(self.config["SAVE_DIR"]):
            os.makedirs(self.config["SAVE_DIR"])
        self.sessions = {}  # chat_id -> [код кусками]

    @loader.command()
    async def cvpy(self, message):
        """Начать сбор кода для файла"""
        chat_id = message.chat_id
        self.sessions[chat_id] = []
        await utils.answer(message, self.strings["started"])

    @loader.command()
    async def addcode(self, message):
        """Добавить кусок кода в текущую сессию"""
        chat_id = message.chat_id
        code = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if reply and hasattr(reply, "text") and reply.text:
            code = reply.text if not code else code + "\n" + reply.text

        if not code:
            await utils.answer(message, self.strings["no_code"])
            return

        if chat_id not in self.sessions:
            await utils.answer(message, self.strings["no_session"])
            return

        self.sessions[chat_id].append(code)
        await utils.answer(message, "✔ Код добавлен в сессию.")

    @loader.command()
    async def cvpyend(self, message):
        """Завершить сбор кода и создать файл"""
        chat_id = message.chat_id
        if chat_id not in self.sessions or not self.sessions[chat_id]:
            await utils.answer(message, self.strings["no_session"])
            return

        all_code = "\n".join(self.sessions[chat_id])
        safe_name = f"cvpy_{int(time.time())}.py"
        filepath = os.path.join(self.config["SAVE_DIR"], safe_name)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(all_code)

            await message.client.send_file(
                chat_id,
                filepath,
                caption=f"Файл <b>{safe_name}</b> готов.",
                force_document=True,
            )

            await utils.answer(message, self.strings["saved"].format(safe_name))
            del self.sessions[chat_id]  # очищаем сессию

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e))
