# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AvatarSwFull
# Description: Смена аватарки без белых полей (фулл 1:1 crop)
# developer: @Dany23s
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

ATTEMPTS_COUNT = 9


@loader.tds
class AvatarSwFull(loader.Module):
    """Смена аватарки без пустых полей (full 1:1)"""

    strings = {
        "name": "AvatarSwFull",
        "no_reply": f"❌ Ответь на фото/видео/GIF/стикер\n💬 Попыток: {ATTEMPTS_COUNT}",
        "changed": "✅ Аватарка установлена без полей!",
        "error": "❌ Ошибка при установке",
        "processing": "⏳ Обработка..."
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        try:
            me = await client.get_me()
            result = await client(
                GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100)
            )
            self.original_photos = result.photos
        except Exception as e:
            logger.error(e)
            self.original_photos = []

    @loader.command()
    async def av(self, message):
        """Ответь на медиа — установить аватар"""
        r = await message.get_reply_message()

        if not r or not (r.photo or r.video or r.document):
            return await utils.answer(message, self.strings["no_reply"])

        try:
            await utils.answer(message, self.strings["processing"])

            with tempfile.TemporaryDirectory() as tmp:

                is_photo = r.photo is not None
                is_video = r.video is not None
                is_doc = r.document is not None

                if is_photo:
                    raw = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw)
                elif is_video:
                    raw = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video, raw)
                else:
                    raw = os.path.join(tmp, "raw.file")
                    await message.client.download_media(r.document, raw)

                if not os.path.exists(raw):
                    return await utils.answer(message, self.strings["error"])

                if is_photo:
                    final = await self._photo_to_square(raw, tmp)
                    upload_video = False
                else:
                    final = await self._video_to_square(raw, tmp)
                    upload_video = True

                if not final or not os.path.exists(final):
                    return await utils.answer(message, self.strings["error"])

                uploaded = await self._client.upload_file(final)

                if upload_video:
                    result = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )
                else:
                    result = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )

                self.added_photos.append(result)

                if len(self.added_photos) > 1:
                    try:
                        await self._client(
                            DeletePhotosRequest(self.added_photos[:-1])
                        )
                    except:
                        pass
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(e, exc_info=True)
            await utils.answer(message, self.strings["error"])

    # --------------------------------------------------
    # PHOTO → FULL SQUARE
    # --------------------------------------------------

    async def _photo_to_square(self, path, tmp):
        from PIL import Image

        try:
            out = os.path.join(tmp, "final.jpg")
            img = Image.open(path)

            if img.mode != "RGB":
                img = img.convert("RGB")

            # Центр-кроп в квадрат
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            img = img.crop((left, top, left + size, top + size))

            img = img.resize((640, 640), Image.Resampling.LANCZOS)
            img.save(out, "JPEG", quality=95)

            return out
        except Exception as e:
            logger.error(e)
            return None

    # --------------------------------------------------
    # VIDEO / GIF → FULL SQUARE MP4
    # --------------------------------------------------

    async def _video_to_square(self, path, tmp):
        try:
            out = os.path.join(tmp, "final.mp4")

            cmd = [
                "ffmpeg",
                "-i", path,
                "-t", "10",
                "-vf",
                "scale=540:540:force_original_aspect_ratio=increase,"
                "crop=540:540",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",
                out
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode != 0:
                logger.error(result.stderr.decode())
                return None

            # если >10MB — уменьшаем
            if os.path.getsize(out) > 10 * 1024 * 1024:
                return await self._video_low_quality(path, tmp)

            return out

        except Exception as e:
            logger.error(e)
            return None

    async def _video_low_quality(self, path, tmp):
        try:
            out = os.path.join(tmp, "final_low.mp4")

            cmd = [
                "ffmpeg",
                "-i", path,
                "-t", "10",
                "-vf",
                "scale=360:360:force_original_aspect_ratio=increase,"
                "crop=360:360",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "32",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",
                out
            ]

            subprocess.run(cmd, capture_output=True, timeout=120)

            return out if os.path.exists(out) else None

        except Exception as e:
            logger.error(e)
            return None
