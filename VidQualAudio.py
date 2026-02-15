#     t.me/Dany23s This code under AGPL-me

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualAudio(loader.Module):
    strings = {"name": "VidQual-audio"}

    @loader.owner
    async def qvmcmd(self, m):
        ".qvm <реплай на аудио или видео> <уровень от 1 до 6 (по умолчанию 3)>"

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        await m.delete()

        mime = reply.file.mime_type or ""
        if not (mime.startswith("audio") or mime.startswith("video")):
            return

        args = utils.get_args_raw(m)
        # уровни с реально низким битрейтом для сильного ухудшения
        lvls = {
            "1": "32k",
            "2": "24k",
            "3": "16k",
            "4": "12k",
            "5": "8k",
            "6": "4k",
        }
        lvl = lvls.get(args, lvls["3"])

        infile = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + "." +
            ("mp4" if mime.startswith("video") else "mp3")
        )
        outfile = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"

        # ffmpeg: извлекаем и конвертируем аудио
        if mime.startswith("video"):
            os.system(
                f'ffmpeg -y -i "{infile}" -vn -c:a libmp3lame -b:a {lvl} "{outfile}"'
            )
        else:
            os.system(
                f'ffmpeg -y -i "{infile}" -c:a libmp3lame -b:a {lvl} "{outfile}"'
            )

        if os.path.exists(outfile):
            await reply.reply(file=outfile)

        # чистка
        os.remove(infile)
        if os.path.exists(outfile):
            os.remove(outfile) 
