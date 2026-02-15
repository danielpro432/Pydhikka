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

        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return await m.respond("Это не видео.")

        args = utils.get_args_raw(m).split()

        vb_input = args[0] if len(args) > 0 else "500"
        ab_input = args[1] if len(args) > 1 else "128"

        vb = vb_input if any(x in vb_input.lower() for x in ["k", "m"]) else f"{vb_input}k"
        ab = ab_input if any(x in ab_input.lower() for x in ["k", "m"]) else f"{ab_input}k"

        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        # ffmpeg: убираем баннер и выводим только ошибки
        os.system(
            f'ffmpeg -y -hide_banner -loglevel error -i "{vid}" -b:v {vb} -maxrate:v {vb} -b:a {ab} -maxrate:a {ab} "{out}"'
        )

        await reply.reply(file=os.path.abspath(out))

        os.remove(vid)
        os.remove(out)
