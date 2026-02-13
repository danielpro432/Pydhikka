import os
import time
from .. import loader, utils

@loader.tds
class TxtPyMaker(loader.Module):
    """Создает редактируемый TXT файл и превращает его в PY с авто-очисткой"""

    strings = {"name": "TxtPyMaker"}

    @loader.command()
    async def newtxt(self, message):
        """Создать новый TXT файл"""
        file_name = f"code_{int(time.time())}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("")
        # Отправляем как файл, а не как текст
        await message.client.send_file(message.chat_id, file_name)
        os.remove(file_name)  # удаляем сразу после отправки
        await utils.answer(message, f"Создан новый TXT файл: **{file_name}**")

    @loader.command()
    async def txt2py(self, message):
        """Превратить TXT файл в PY"""
        reply = await message.get_reply_message()
        if not reply or not reply.file:
            return await utils.answer(message, "Ответьте на файл TXT.")
        file_path = await message.client.download_media(reply)
        py_name = file_path.replace(".txt", ".py")
        os.rename(file_path, py_name)
        # Отправляем как Python файл
        await message.client.send_file(message.chat_id, py_name)
        os.remove(py_name)  # удаляем сразу после отправки
        await utils.answer(message, f"TXT -> PY файл создан: **{py_name}**")
