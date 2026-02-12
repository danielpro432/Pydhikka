#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# Name: AChange
# Description: Фото / GIF / Видео → авто 7 сек

import os
import tempfile
import subprocess
import logging
from telethon.tl.functions.photos import (
    UploadProfilePhotoRequest,
    DeletePhotosRequest,
    GetUserPhotosRequest,
)
from .. import loader, utils

logger = logging.getLogger(__name__)

MAX_DURATION = 7


@loader.tds
class AChange(loader.Module):
    """Смена аватарки (фото / GIF / видео) с автообрезкой до 7 сек"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на фото, GIF или видео",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        # Сохраняем оригинальные аватарки
        me = await client.get_me()
        result = await client(
            GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100)
        )
        self.original_photos = result.photos

    @loader.command()
    async def AChange(self, message):
        r = await message.get_reply_message()

        if not r or not r.media:
            return await utils.answer(message, self.strings["no_reply"])

        try:
            with tempfile.TemporaryDirectory() as tmp:

                input_path = os.path.join(tmp, "input.mp4")
                output_path = os.path.join(tmp, "output.mp4")

                # ВСЕГДА скачиваем как файл
                await message.client.download_media(r.media, input_path)

                if r.photo:
                    # Фото — просто загружаем
                    uploaded = await self._client.upload_file(input_path)
                    result = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )

                else:
                    # Видео / GIF → режем до 7 сек
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-i", input_path,
                        "-t", str(MAX_DURATION),
                        "-vf", "crop='min(iw,ih)':'min(iw,ih)'",
                        "-an",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-pix_fmt", "yuv420p",
                        output_path,
                    ]

                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                    uploaded = await self._client.upload_file(output_path)
                    result = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )

                # Сохраняем добавленные
                self.added_photos.append(result.photo)

                # Удаляем старые добавленные (но не оригинальные)
                if len(self.added_photos) > 1:
                    await self._client(
                        DeletePhotosRequest(self.added_photos[:-1])
                    )
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(f"AChange error: {e}")
            await utils.answer(message, self.strings["error"])
