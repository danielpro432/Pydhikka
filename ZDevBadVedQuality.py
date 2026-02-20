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
        .qvl <реплай на видео> <crf> <аудио kbps>

        Примеры:
        .qvl           → CRF 28 / 128k
        .qvl 30        → CRF 30 / 128k
        .qvl 26 96     → CRF 26 / 96k

        Чем меньше CRF — тем выше качество.
        23 = хорошее
        28 = среднее
        30+ = сильное сжатие
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на видео.")

        await m.delete()

        if reply.file.mime_type.split("/")[0] != "video":
            return await m.respond("Это не видео.")

        args = utils.get_args_raw(m).split()

        crf = args[0] if len(args) > 0 else "28"
        ab = args[1] if len(args) > 1 else "128"

        if "k" not in ab.lower():
            ab = f"{ab}k"

        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp4"

        # --- Проверяем кодек видео ---
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                vid
            ],
            capture_output=True,
            text=True
        )

        video_codec = probe.stdout.strip()

        # --- Если уже h264 → просто копируем (очень быстро) ---
        if video_codec == "h264":
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "quiet",
                    "-i", vid,
                    "-c", "copy",
                    "-movflags", "+faststart",
                    out
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # --- Перекодировка (быстро + чисто) ---
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "quiet",
                    "-i", vid,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", crf,
                    "-tune", "zerolatency",
                    "-c:a", "aac",
                    "-b:a", ab,
                    "-movflags", "+faststart",
                    out
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        await reply.reply(file=os.path.abspath(out))

        os.remove(vid)
        os.remove(out)
