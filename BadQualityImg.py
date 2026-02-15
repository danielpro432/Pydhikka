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

        # scale, qscale (чем больше qscale — тем хуже качество)
        lvls = {
            "1": ("0.97", "2"),
            "2": ("0.94", "3"),
            "3": ("0.9", "5"),
            "4": ("0.85", "8"),
            "5": ("0.8", "12"),
            "6": ("0.75", "18"),
        }

        args = utils.get_args_raw(m)
        scale, q = lvls.get(args, lvls["3"])

        try:
            infile = await reply.download_media(
                "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            )

            outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"

            os.system(
                f'ffmpeg -y -i "{infile}" '
                f'-vf "scale=iw*{scale}:ih*{scale}" '
                f'-qscale:v {q} -pix_fmt yuv420p "{outfile}"'
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
