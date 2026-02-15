#   Coded by Dany
#     t.me/Dany23s
# This code under AGPL-3.0

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualVideo(loader.Module):
    strings = {"name": "VidQual-video"}

    @loader.owner
    async def qvlcmd(self, m):
        ".qvl <реплай на видео> <битрейт: например 500k или 2M>"

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        await m.delete()  # сразу удаляем команду

        if reply.file.mime_type.split("/")[0] != "video":
            return

        # читаем аргумент битрейта
        args = utils.get_args_raw(m).split()
        try:
            lvl = args[0] if len(args) > 0 else "500k"
        except:
            lvl = "500k"

        # скачиваем видео
        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        # конвертация ffmpeg тихо
        os.system(
            f'ffmpeg -hide_banner -loglevel error -y -i "{vid}" '
            f'-b:v {lvl} -maxrate:v {lvl} -b:a {lvl} -maxrate:a {lvl} "{out}"'
        )

        await reply.reply(file=out)

        # чистка
        os.remove(vid)
        os.remove(out) 
