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
        Пример:
        .qvl 500 128     → 500k / 128k
        .qvl 0.5M 0.128M → 0.5M / 0.128M
        Если аргументы не указаны — берётся 500k / 128k
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на видео.")

        # удаляем команду
        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return await m.respond("Это не видео.")

        args = utils.get_args_raw(m).split()

        # значения по умолчанию
        vb_input = args[0] if len(args) > 0 else "500"
        ab_input = args[1] if len(args) > 1 else "128"

        # автоматическое добавление k если пользователь не написал M/k
        vb = vb_input if any(x in vb_input.lower() for x in ["k", "m"]) else f"{vb_input}k"
        ab = ab_input if any(x in ab_input.lower() for x in ["k", "m"]) else f"{ab_input}k"

        # создаём случайные имена для файлов
        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        # запускаем ffmpeg
        os.system(
            f'ffmpeg -y -i "{vid}" -b:v {vb} -maxrate:v {vb} -b:a {ab} -maxrate:a {ab} "{out}"'
        )

        # отправка видео
        await reply.reply(file=os.path.abspath(out))

        # удаляем временные файлы
        os.remove(vid)
        os.remove(out)
