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
        ".qvi <уровень 1-6> или реплай на фото/статичный стикер"

        # сразу удаляем команду
        await m.delete()

        args = utils.get_args_raw(m)
        lvl = args if args in ["1","2","3","4","5","6"] else "3"

        # ищем картинку: либо реплай, либо само сообщение
        reply = await m.get_reply_message()
        if reply and reply.file:
            msg_with_file = reply
        elif m.file:  # если пользователь прислал фото вместе с командой
            msg_with_file = m
        else:
            return await m.respond("Ошибка: нужно прислать изображение или сделать реплай на него.")

        mime = msg_with_file.file.mime_type or ""
        if not mime.startswith("image"):
            return await m.respond("Ошибка: это не изображение.")

        # scale и качество JPEG
        lvls = {
            "1": ("0.97", "5"),
            "2": ("0.94", "10"),
            "3": ("0.91", "15"),
            "4": ("0.88", "20"),
            "5": ("0.85", "25"),
            "6": ("0.82", "30"),
        }
        scale, q = lvls[lvl]

        try:
            infile = await msg_with_file.download_media(
                "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            )
            temp = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"

            # уменьшаем + сжимаем
            os.system(
                f'ffmpeg -y -i "{infile}" '
                f'-vf "scale=iw*{scale}:ih*{scale}" '
                f'-qscale:v {q} -pix_fmt yuv444p "{temp}"'
            )

            # возвращаем размер
            os.system(
                f'ffmpeg -y -i "{temp}" '
                f'-vf "scale=iw/{scale}:ih/{scale}" '
                f'-qscale:v {q} -pix_fmt yuv444p "{outfile}"'
            )

            if not os.path.exists(outfile):
                return await m.respond("Ошибка обработки.")

            await msg_with_file.reply(file=outfile)

        except Exception:
            await m.respond("Произошла ошибка.")

        finally:
            for f in ["infile", "temp", "outfile"]:
                if f in locals() and os.path.exists(locals()[f]):
                    os.remove(locals()[f])
