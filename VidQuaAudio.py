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
        lvls = {
            "1": "64k",
            "2": "48k",
            "3": "32k",
            "4": "24k",
            "5": "16k",
            "6": "8k",
        }
        lvl = lvls.get(args, lvls["3"])

        infile = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + "." +
            ("mp4" if mime.startswith("video") else "mp3")
        )
        outfile = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"

        # ffmpeg: извлекаем и конвертируем только аудио
        if mime.startswith("video"):
            cmd = f'ffmpeg -y -i "{infile}" -vn -ar 44100 -ac 2 -b:a {lvl} "{outfile}"'
        else:
            cmd = f'ffmpeg -y -i "{infile}" -ar 44100 -ac 2 -b:a {lvl} "{outfile}"'

        os.system(cmd)

        if os.path.exists(outfile):
            await reply.reply(file=outfile)

        # чистка
        os.remove(infile)
        if os.path.exists(outfile):
            os.remove(outfile)
