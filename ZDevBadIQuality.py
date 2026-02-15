#   Coded by Dany
#     t.me/Dany23s
# This code under AGPL-3.0

import os
import random
import string
from .. import loader, utils

@loader.tds
class VidQualImage(loader.Module):
    strings = {"name": "VidQual-image"}

    @loader.owner  
    async def qvicmd(self, m):  
        ".qvi <масштаб:0.1-1.0> <качество jpeg:1-50> <реплай на фото/статичный стикер>"  

        args = utils.get_args_raw(m).split()
        await m.delete()  # удаляем команду сразу

        # ищем изображение
        reply = await m.get_reply_message()
        if reply and reply.file:
            msg_with_file = reply
        elif m.file:
            msg_with_file = m
        else:
            return await m.respond("Ошибка: нужен реплай или изображение с командой qvi.")

        mime = msg_with_file.file.mime_type or ""
        if not mime.startswith("image"):
            return await m.respond("Ошибка: это не изображение.")

        # масштаб и качество
        try:
            scale = float(args[0]) if len(args) > 0 else 0.5
            q = int(args[1]) if len(args) > 1 else 20
        except:
            return await m.respond("Ошибка: аргументы должны быть числами. Пример: .qvi 0.4 30")

        try:
            infile = await msg_with_file.download_media(
                "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            )
            temp = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"
            outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".jpg"

            # уменьшение
            os.system(
                f'ffmpeg -hide_banner -loglevel error -y -i "{infile}" '
                f'-vf "scale=iw*{scale}:ih*{scale}" '
                f'-qscale:v {q} -pix_fmt yuv420p "{temp}"'
            )

            # восстановление размера
            os.system(
                f'ffmpeg -hide_banner -loglevel error -y -i "{temp}" '
                f'-vf "scale=iw/{scale}:ih/{scale}" '
                f'-qscale:v {q} -pix_fmt yuv420p "{outfile}"'
            )

            if not os.path.exists(outfile):
                return await m.respond("Ошибка обработки.")

            await msg_with_file.reply(file=os.path.abspath(outfile))

        except Exception as e:
            await m.respond(f"Произошла ошибка: {e}")

        finally:
            for f in ["infile", "temp", "outfile"]:
                if f in locals() and os.path.exists(locals()[f]):
                    os.remove(locals()[f])
