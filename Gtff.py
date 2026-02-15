import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualAudio(loader.Module):
    strings = {"name": "VidQual-audio"}

    @loader.owner
    async def qalcmd(self, m):
        " <реплай на аудио> <уровень от 1 до 6 (по умолчанию 3)>\n"

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        # сразу удаляем сообщение с командой
        await m.delete()

        if reply.file.mime_type.split("/")[0] != "audio":
            return

        args = utils.get_args_raw(m)
        lvls = {
            "1": "32k",
            "2": "64k",
            "3": "128k",
            "4": "192k",
            "5": "256k",
            "6": "320k",
        }
        lvl = lvls.get(args, lvls["3"])

        audio = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp3"

        os.system(
            f'ffmpeg -y -i "{audio}" -b:a {lvl} -q:a 9 "{out}"'
        )

        await reply.reply(file=out)

        # чистка
        os.remove(audio)
        os.remove(out)
