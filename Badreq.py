#   Coded by D4n13l3k00    #
#     t.me/D4n13l3k00      #
# Modified under AGPL-3.0 #

import os
import random
import string

from .. import loader, utils


@loader.tds
class VSHAKALMod(loader.Module):
    strings = {"name": "Media Shakal"}

    @loader.owner
    async def vshcmd(self, m):
        """
        .vsh <реплай> <уровень 1-6 (по умолчанию 3)>
        Шакалит видео / фото / гиф / аудио
        """

        reply = await m.get_reply_message()
        if not reply or not reply.file:
            return await m.edit("Ответь на файл.")

        mime = reply.file.mime_type
        if not mime:
            return await m.edit("Не удалось определить тип файла.")

        args = utils.get_args_raw(m)

        lvls = {
            "1": "0.2M",
            "2": "0.1M",
            "3": "0.05M",
            "4": "0.03M",
            "5": "0.02M",
            "6": "0.01M",
        }

        if args:
            if args in lvls:
                lvl = lvls[args]
            else:
                return await m.edit("Уровень 1-6.")
        else:
            lvl = lvls["3"]

        await m.edit("📥 Скачиваю...")

        filename = "".join(random.choice(string.ascii_letters) for _ in range(20))
        inp = await reply.download_media(filename)
        out = filename + "_shakal"

        await m.edit("🗜 Шакалю...")

        try:
            if mime.startswith("video"):
                out += ".mp4"
                os.system(
                    f'ffmpeg -y -i "{inp}" -b:v {lvl} -maxrate {lvl} -bufsize {lvl} '
                    f'-b:a {lvl} -maxrate:a {lvl} "{out}"'
                )

            elif mime.startswith("image"):
                # gif отдельно
                if "gif" in mime:
                    out += ".gif"
                    os.system(
                        f'ffmpeg -y -i "{inp}" -vf "scale=iw/2:ih/2" '
                        f'-b:v {lvl} "{out}"'
                    )
                else:
                    out += ".jpg"
                    os.system(
                        f'ffmpeg -y -i "{inp}" -qscale:v 31 "{out}"'
                    )

            elif mime.startswith("audio"):
                out += ".mp3"
                os.system(
                    f'ffmpeg -y -i "{inp}" -b:a {lvl} "{out}"'
                )

            else:
                return await m.edit("Этот тип файла не поддерживается.")

        except Exception as e:
            return await m.edit(f"Ошибка: {e}")

        if not os.path.exists(out):
            return await m.edit("Ошибка обработки.")

        await m.edit("📤 Отправляю...")
        await reply.reply(file=out)
        await m.delete()

        os.remove(inp)
        os.remove(out)
