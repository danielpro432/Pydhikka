#  Dany23s   
# хуй
#член
# нет0

import os
import random
import string
from .. import loader, utils

@loader.tds
class VideoQual(loader.Module):
    strings = {"name": "VidLow-quality"}

    @loader.owner
    async def qvlcmd(self, m):
        ".qvl <реплай на видео> <уровень от 1 до 6 (по умолчанию 3)>\n "

        reply = await m.get_reply_message()
        if not reply:
            return
        if reply.file.mime_type.split("/")[0] != "video":
            return

        args = utils.get_args_raw(m)
        lvls = {
            "1": "0.1M",
            "2": "0.08M",
            "3": "0.05M",
            "4": "0.03M",
            "5": "0.02M",
            "6": "0.01M",
        }
        lvl = lvls.get(args, lvls["3"])

        vid = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"
        )
        out = "".join(random.choice(string.ascii_letters) for _ in range(25)) + ".mp4"

        os.system(
            f'ffmpeg -y -i "{vid}" -b:v {lvl} -maxrate:v {lvl} -b:a {lvl} -maxrate:a {lvl} "{out}"'
        )

        await reply.reply(file=out)
        await m.delete()  # команда удаляется, никакого текста

        # Чистка файлов
        os.remove(vid)
        os.remove(out)
