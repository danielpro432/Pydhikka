# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta name: CodeToFileSend
# meta banner: https://raw.githubusercontent.com/Dany23s/code-to-file/main/banner.png

import os
from .. import loader, utils

@loader.tds
class CodeToFileSendMod(loader.Module):
    """Модуль для создания .py файлов прямо из Telegram и отправки их обратно"""

    strings = {
        "name": "CodeToFileSend",
        "saved": "✅ Файл <b>{filename}</b> успешно создан и отправлен!",
        "error": "❌ Произошла ошибка при сохранении файла: {error}",
        "no_code": "❌ Пожалуйста, укажи код после команды или в ответе на сообщение.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "SAVE_DIR",
                default="user_code",
                doc=lambda: "Папка на сервере, куда сохранять .py файлы",
                validator=loader.validators.String()
            ),
        )
        # создаем папку если нет
        if not os.path.exists(self.config["SAVE_DIR"]):
            os.makedirs(self.config["SAVE_DIR"])

    @loader.command()
    async def cvpy(self, message):
        """Отправить код и создать файл .py"""
        code = utils.get_args_raw(message)

        # если команды нет, берем текст из ответа
        if not code:
            reply = await message.get_reply_message()
            if reply and reply.text:
                code = reply.text
            else:
                await utils.answer(message, self.strings["no_code"])
                return

        # имя файла: безопасное + timestamp
        import time, re
        safe_name = re.sub(r"\W", "_", code[:10])
        filename = f"{safe_name}_{int(time.time())}.py"
        filepath = os.path.join(self.config["SAVE_DIR"], filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            # отправка файла в Telegram
            await message.client.send_file(
                message.chat_id,
                filepath,
                caption=f"Файл <b>{filename}</b> создан и готов к использованию.",
                force_document=True,
            )
            await utils.answer(message, self.strings["saved"].format(filename=filename))

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=e))
