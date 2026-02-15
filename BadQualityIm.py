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

        # Сразу удаляем команду
        await m.delete()

        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на фото или статичный стикер.")

        mime = reply.file.mime_type or ""
        ext = (reply.file.name.split(".")[-1].lower()
               if reply.file.name else "jpg")

        if not mime.startswith("image") and ext not in ["jpg", "jpeg", "png", "webp"]:
            return await m.respond("Ошибка: это не изображение.")

        lvls = {
            "1": ("2", "0.9"),
            "2": ("5", "0.8"),
            "3": ("10", "0.7"),
            "4": ("20", "0.6"),
            "5": ("30", "0.5"),
            "6": ("40", "0.4"),
        }

        args = utils.get_args_raw(m)
        quality, scale = lvls.get(args, lvls["3"])

        try:
            infile = await reply.download_media(
                "".join(random.choice(string.ascii_letters) for _ in range(25)) + f".{ext}"
            )

            outfile = "".join(random.choice(string.ascii_letters) for _ in range(25)) + f".{ext}"

            result = os.system(
                f'ffmpeg -y -i "{infile}" '
                f'-vf "scale=iw*{scale}:ih*{scale}" '
                f'-q:v {quality} "{outfile}"'
            )

            if result != 0 or not os.path.exists(outfile):
                return await m.respond("Ошибка при обработке изображения.")

            await reply.reply(file=outfile)

        except Exception:
            await m.respond("Произошла ошибка.")

        finally:
            if 'infile' in locals() and os.path.exists(infile):
                os.remove(infile)
            if 'outfile' in locals() and os.path.exists(outfile):
                os.remove(outfile)
