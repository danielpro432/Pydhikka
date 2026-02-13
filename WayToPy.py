#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta icon: https://t.me/FAmods_icon
# meta banner: https://t.me/FAmods_banner

import os
import time
from .. import loader, utils

@loader.tds
class TxtToPy(loader.Module):
    """Редактируемый TXT → PY модуль"""

    strings = {"name": "TxtToPy"}

    def __init__(self):
        # имя текущего файла
        self.filename = f"code_{int(time.time())}.txt"

    @loader.command()
    async def sendtxt(self, message):
        """Отправить текущий TXT файл для редактирования вручную"""
        # создаём файл, если его ещё нет
        if not os.path.exists(self.filename):
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write("# Здесь можешь писать код для будущего .py\n")

        await message.client.send_file(
            message.chat_id,
            self.filename,
            caption=f"Файл **{self.filename}** готов к редактированию. После правок используй .txt2py"
        )

    @loader.command()
    async def txt2py(self, message):
        """Преобразовать TXT файл в PY и отправить"""
        if not os.path.exists(self.filename):
            await utils.answer(message, "Сначала отправь TXT с помощью .sendtxt")
            return

        py_filename = self.filename.replace(".txt", ".py")
        with open(self.filename, "r", encoding="utf-8") as f:
            code = f.read()

        with open(py_filename, "w", encoding="utf-8") as f:
            f.write(code)

        await message.client.send_file(
            message.chat_id,
            py_filename,
            caption=f"Файл **{py_filename}** создан из TXT и отправлен."
        )

    @loader.command()
    async def newtxt(self, message):
        """Создать новый TXT файл (старый можно удалить вручную)"""
        self.filename = f"code_{int(time.time())}.txt"
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write("# Новый TXT файл для кода\n")
        await utils.answer(message, f"Создан новый TXT файл: **{self.filename}**")
