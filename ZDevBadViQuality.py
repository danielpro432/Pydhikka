#     t.me/Dany23s This code under AGPL-me

import os
import random
import string
import subprocess
from .. import loader, utils


@loader.tds
class VidQualVideo(loader.Module):
    strings = {"name": "VidQual-video"}

    @loader.owner
    async def qvlcmd(self, m):
        """
        .qvl <реплай на видео> <видеобитрейт> <аудиобитрейт>

        Примеры:
        .qvl 500 128
        .qvl 0.5M 0.128M

        По умолчанию: 500k / 128k
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.respond("Нужен реплай на видео.")

        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return await m.respond("Это не видео.")

        args = utils.get_args_raw(m).split()

        vb_input = args[0] if len(args) > 0 else "500"
        ab_input = args[1] if len(args) > 1 else "128"

        vb = vb_input if any(x in vb_input.lower() for x in ["k", "m"]) else f"{vb_input}k"
        ab = ab_input if any(x in ab_input.lower() for x in ["k", "m"]) else f"{ab_input}k"

        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", vid,
            "-preset", "ultrafast",
            "-b:v", vb,
            "-maxrate", vb,
            "-bufsize", vb,
            "-b:a", ab,
            out
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not os.path.exists(out) or os.path.getsize(out) == 0:
                raise Exception("Файл не создался")

            await reply.reply(file=os.path.abspath(out))

        except Exception:
            await m.respond("Ошибка конвертации.")

        finally:
            if os.path.exists(vid):
                os.remove(vid)
            if os.path.exists(out):
                os.remove(out)
