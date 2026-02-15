#   Coded by Dany    #
#     t.me/Dany23s      #
# This code under AGPL-3.0 #

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualImage(loader.Module):
    strings = {"name": "VidQual-image"}

    @loader.owner
    async def qvicmd(self, m):
        ".qvi <реплай на фото/статичный стикер> <уровень 1-6>"

        reply = await m.get_reply_message()
        await m.delete()

        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на изображение.")

        mime = reply.file.mime_type or ""
        if not mime.startswith("image"):
            return await m.respond("Ошибка: это не изображение.")

        lvls = {
            "1": "200k",
            "2": "150k",
            "3": "100k",
            "4": "70k",
            "5": "40k",
            "6": "20k",
        }

        args = utils.get_args_raw(m)
        bitrate = lvls.get(args, lvls["3"])

        try:
            infile = await reply.download_media(
                "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            )

            outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"

            os.system(
                f'ffmpeg -y -i "{infile}" '
                f'-b:v {bitrate} -maxrate {bitrate} -bufsize {bitrate} '
                f'-pix_fmt yuv420p "{outfile}"'
            )

            if not os.path.exists(outfile):
                return await m.respond("Ошибка обработки.")

            await reply.reply(file=outfile)

        except Exception:
            await m.respond("Произошла ошибка.")

        finally:
            for f in ["infile", "outfile"]:
                if f in locals() and os.path.exists(locals()[f]):
                    os.remove(locals()[f])
