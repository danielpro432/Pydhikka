# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки (фото / видео / GIF / стикеры / emoji)
# meta developer: @FAmods
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import subprocess

from telethon.tl.functions.photos import (
    UploadProfilePhotoRequest,
    DeletePhotosRequest,
    GetUserPhotosRequest
)

from .. import loader, utils

logger = logging.getLogger(__name__)
ATTEMPTS_COUNT = 10


@loader.tds
class AChange(loader.Module):
    """Смена аватарки"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на медиа (фото/видео/GIF/стикер/emoji)",
        "processing": "⏳ Обработка...",
        "changed": "✅ Аватарка обновлена",
        "error": "❌ Ошибка обработки",
        "no_ffmpeg": "❌ FFmpeg не установлен",
        "no_lottie": "❌ Для emoji нужен: pip install lottie",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        try:
            me = await client.get_me()
            result = await client(
                GetUserPhotosRequest(
                    user_id=me.id,
                    offset=0,
                    max_id=0,
                    limit=100
                )
            )
            self.original_photos = result.photos
        except Exception:
            self.original_photos = []

    @loader.command()
    async def achange(self, message):
        """Ответь на медиа — сменить аватарку"""
        r = await message.get_reply_message()

        if not r:
            return await utils.answer(message, self.strings["no_reply"])

        await utils.answer(message, self.strings["processing"])

        try:
            with tempfile.TemporaryDirectory() as tmp:

                # -------- ОПРЕДЕЛЕНИЕ ТИПА --------
                is_photo = r.photo is not None
                is_video = False
                mime = None

                if r.document:
                    mime = r.document.mime_type or ""

                    if mime.startswith("video/"):
                        is_video = True
                    elif mime == "image/gif":
                        is_video = True
                    elif mime == "application/x-tgsticker":
                        is_video = True

                # -------- СКАЧИВАНИЕ --------
                raw_path = os.path.join(tmp, "input")
                await message.client.download_media(r, raw_path)

                if not os.path.exists(raw_path):
                    return await utils.answer(message, self.strings["error"])

                # -------- КОНВЕРТАЦИЯ --------
                if is_photo:
                    final = await self._photo_to_jpeg(raw_path, tmp)
                    upload_video = False
                else:
                    # emoji (.tgs)
                    if mime == "application/x-tgsticker":
                        raw_path = await self._tgs_to_mp4(raw_path, tmp)
                        if not raw_path:
                            return await utils.answer(message, self.strings["no_lottie"])

                    final = await self._to_mp4(raw_path, tmp)
                    upload_video = True

                if not final:
                    return await utils.answer(message, self.strings["error"])

                uploaded = await self._client.upload_file(final)

                if upload_video:
                    new_photo = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )
                else:
                    new_photo = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )

                self.added_photos.append(new_photo)

                # удаляем старые созданные этим модулем
                if len(self.added_photos) > 1:
                    try:
                        await self._client(
                            DeletePhotosRequest(self.added_photos[:-1])
                        )
                    except:
                        pass
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings["changed"])

        except FileNotFoundError:
            await utils.answer(message, self.strings["no_ffmpeg"])
        except Exception as e:
            logger.error(e, exc_info=True)
            await utils.answer(message, self.strings["error"])

    # -------------------- PHOTO --------------------

    async def _photo_to_jpeg(self, path, tmp):
        try:
            from PIL import Image

            out = os.path.join(tmp, "final.jpg")
            img = Image.open(path)

            img = img.convert("RGB")
            img.thumbnail((640, 640))

            canvas = Image.new("RGB", (640, 640), (255, 255, 255))
            offset = (
                (640 - img.width) // 2,
                (640 - img.height) // 2
            )
            canvas.paste(img, offset)
            canvas.save(out, "JPEG", quality=95)

            return out
        except Exception:
            return None

    # -------------------- VIDEO --------------------

    async def _to_mp4(self, path, tmp):
        out = os.path.join(tmp, "final.mp4")

        cmd = [
            "ffmpeg",
            "-i", path,
            "-t", "10",
            "-vf",
            "scale=min(iw\\,540):min(ih\\,540):force_original_aspect_ratio=decrease,"
            "pad=540:540:(ow-iw)/2:(oh-ih)/2,fps=30",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-b:v", "600k",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            "-y",
            out
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            return None

        if os.path.getsize(out) > 10 * 1024 * 1024:
            return None

        return out

    # -------------------- TGS (emoji) --------------------

    async def _tgs_to_mp4(self, path, tmp):
        try:
            from lottie.importers.tgs import import_tgs
            from lottie.exporters.video import export_video

            animation = import_tgs(path)
            out = os.path.join(tmp, "emoji.mp4")

            export_video(animation, out, fps=30)

            return out
        except Exception:
            return None
