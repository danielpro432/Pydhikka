#     t.me/Dany23s This code under AGPL-me 

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualVideo(loader.Module):
    strings = {"name": "VidQual-video"}

    @loader.owner
    async def qvlcmd(self, m):
        """
        .qvl <реплай на видео> <видеобитрейт> <аудиобитрейт>
        Пример: .qvl 500k 128k
        Если не указаны — берётся 500k / 128k
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на видео.")

        # удаляем команду
        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return await m.respond("Это не видео.")

        args = utils.get_args_raw(m).split()
        vb = args[0] if len(args) > 0 else "500k"   # видеобитрейт по умолчанию
        ab = args[1] if len(args) > 1 else "128k"   # аудиобитрейт по умолчанию

        # скачиваем видео
        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        # ffmpeg с пользовательскими значениями
        os.system(
            f'ffmpeg -y -i "{vid}" -b:v {vb} -maxrate:v {vb} -b:a {ab} -maxrate:a {ab} "{out}"'
        )

        await reply.reply(file=out)

        # удаляем временные файлы
        os.remove(vid)
        os.remove(out)
