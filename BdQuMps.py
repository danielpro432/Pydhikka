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
        " <реплай на видео> <уровень от 1 до 6 (по умолчанию 3)>\n"

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        # сразу удаляем сообщение с командой
        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return

        args = utils.get_args_raw(m)

        # уровни для видео (как раньше)
        lvls_video = {
            "1": "0.1M",
            "2": "0.08M",
            "3": "0.05M",
            "4": "0.03M",
            "5": "0.02M",
            "6": "0.01M",
        }
        lvl_v = lvls_video.get(args, lvls_video["3"])

        # уровни для аудио (чем меньше битрейт — тем хуже звук)
        lvls_audio = {
            "1": "32k",
            "2": "24k",
            "3": "16k",
            "4": "12k",
            "5": "8k",
            "6": "4k",
        }
        lvl_a = lvls_audio.get(args, lvls_audio["3"])

        # скачиваем видео
        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        # ухудшаем видео и звук отдельно
        os.system(
            f'ffmpeg -y -i "{vid}" '
            f'-b:v {lvl_v} -maxrate:v {lvl_v} '
            f'-b:a {lvl_a} -maxrate:a {lvl_a} '
            f'"{out}"'
        )

        # отправляем обратно
        await reply.reply(file=out)

        # чистка
        os.remove(vid)
        os.remove(out)
