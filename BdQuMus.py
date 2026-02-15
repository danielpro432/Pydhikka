#     t.me/Dany23s This code under AGPL-me

import os
import random
import string
from .. import loader, utils

@loader.tds
class AudioQual(loader.Module):
    strings = {"name": "AudioQual"}

    @loader.owner
    async def qvmcmd(self, m):
        """
        .qvm <реплай на видео/аудио> <уровень 1-6>
        Извлекает аудио и ухудшает его в mp3
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.respond("Ошибка: нужен реплай на видео или аудио.")

        await m.delete()

        mime = reply.file.mime_type or ""
        if not (mime.startswith("video") or mime.startswith("audio")):
            return await m.respond("Ошибка: нужен видео или аудио файл.")

        args = utils.get_args_raw(m)

        # уровни для аудио (битрейт в kbps, чем меньше — тем хуже)
        lvls_audio = {
            "1": "128k",
            "2": "96k",
            "3": "64k",
            "4": "48k",
            "5": "32k",
            "6": "16k",
        }
        lvl_a = lvls_audio.get(args, lvls_audio["3"])

        # скачиваем файл
        infile = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(20)) + "." +
            ("mp4" if mime.startswith("video") else "mp3")
        )

        outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp3"

        # ffmpeg: извлекаем и ухудшаем аудио
        os.system(
            f'ffmpeg -y -i "{infile}" -vn -c:a libmp3lame -b:a {lvl_a} "{outfile}"'
        )

        if not os.path.exists(outfile):
            return await m.respond("Ошибка обработки аудио.")

        await reply.reply(file=outfile)

        # чистка
        os.remove(infile)
        os.remove(outfile)
