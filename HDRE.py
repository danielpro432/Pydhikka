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
        .qvm <битрейт в k>
        Портит аудио/видео как плохое микро
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return

        await m.delete()

        mime = reply.file.mime_type or ""
        if not (mime.startswith("video") or mime.startswith("audio")):
            return

        # битрейт от пользователя, без ограничений
        args = utils.get_args_raw(m)
        try:
            br = int(args)
            if br < 1:
                br = 1
        except:
            br = 16  # default — заметно ломает

        lvl_a = f"{br}k"

        infile = await reply.download_media(
            "".join(random.choice(string.ascii_letters) for _ in range(20)) + "." +
            ("mp4" if mime.startswith("video") else "mp3")
        )
        outfile = "".join(random.choice(string.ascii_letters) for _ in range(20)) + ".mp3"

        # ffmpeg: ломаем звук как плохое микро
        os.system(
            f'ffmpeg -y -i "{infile}" -vn -c:a libmp3lame -b:a {lvl_a} -af "aresample=resampler=soxr:osf=s16:ocl=stereo" "{outfile}"'
        )

        if os.path.exists(outfile):
            await reply.reply(file=outfile)

        # чистка
        os.remove(infile)
        if os.path.exists(outfile):
            os.remove(outfile)
