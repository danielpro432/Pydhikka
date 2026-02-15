#     t.me/Dany23s This code under AGPL-me 

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualAudio(loader.Module):
    strings = {"name": "VidQual-audio"}

    @loader.owner
    async def qacmd(self, m):
        " <реплай на аудио> <уровень от 1 до 6 (по умолчанию 3)>\n"

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        # удаляем команду сразу
        await m.delete()

        # проверяем, что файл аудио
        if reply.file.mime_type.split("/")[0] != "audio":
            return

        args = utils.get_args_raw(m)
        lvls = {
            "1": "320k",
            "2": "256k",
            "3": "192k",
            "4": "128k",
            "5": "96k",
            "6": "64k",
        }
        lvl = lvls.get(args, lvls["3"])

        # скачиваем аудио
        audio_file = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"
        )
        out_file = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"

        # ffmpeg конвертация с битрейтом
        os.system(
            f'ffmpeg -y -i "{audio_file}" -b:a {lvl} "{out_file}"'
        )

        await reply.reply(file=out_file)

        # удаляем временные файлы
        os.remove(audio_file)
        os.remove(out_file) 
