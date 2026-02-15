#     t.me/Dany23s This code under AGPL-me

import os
import random
import string
from .. import loader, utils

@loader.tds
class FileSizer(loader.Module):
    strings = {"name": "FileSizer"}

    @loader.owner
    async def qfs_cmd(self, m):
        """
        .qfs <размер в k/M> 
        Регулирует размер медиа файла
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        await m.delete()

        # читаем размер от пользователя
        args = utils.get_args_raw(m)
        if not args:
            return  # ничего не делаем

        try:
            if args.lower().endswith("m"):
                size_target = float(args[:-1]) * 1024  # МБ → кБ
            else:
                size_target = float(args)  # кБ
        except:
            return  # неверный ввод

        infile = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(20)) + "." +
            reply.file.name.split('.')[-1]
        )
        outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + "." + infile.split('.')[-1]

        mime = reply.file.mime_type or ""

        if mime.startswith("video"):
            # Пример: для видео подбираем битрейт под размер
            import math
            duration = float(os.popen(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{infile}"').read() or 1)
            br = int((size_target*8)/duration)  # кбит/с примерно
            br = max(br, 16)  # минимум, чтобы ffmpeg принял
            os.system(f'ffmpeg -y -i "{infile}" -b:v {br}k -b:a {br//10}k "{outfile}"')

        elif mime.startswith("audio"):
            # Подбираем аудио битрейт под размер
            duration = float(os.popen(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{infile}"').read() or 1)
            br = int((size_target*8)/duration)
            br = max(br, 8)
            os.system(f'ffmpeg -y -i "{infile}" -c:a libmp3lame -b:a {br}k "{outfile}"')

        elif mime.startswith("image"):
            # Для фото можно использовать qscale
            q = max(2, min(31, int(31 - size_target/10)))  # грубая формула
            os.system(f'ffmpeg -y -i "{infile}" -q:v {q} "{outfile}"')

        if os.path.exists(outfile):
            await reply.reply(file=outfile)

        os.remove(infile)
        if os.path.exists(outfile):
            os.remove(outfile)
