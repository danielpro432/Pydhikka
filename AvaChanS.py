# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AvatarSwDual
# Description: .av = без полей (crop) | .avs = с полями (fit)
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


@loader.tds
class AvatarSwDual(loader.Module):
    """Смена аватарки: crop и fit режим"""

    strings = {
        "name": "AvatarSwDual",
        "no_reply": "❌ Ответь на фото / видео / GIF / стикер",
        "processing": "⏳ Обработка...",
        "done_crop": "✅ Установлено без полей (crop)",
        "done_fit": "✅ Установлено с полями (fit)",
        "error": "❌ Ошибка"
    }

    async def client_ready(self, client, db):
        self._client = client
        self.added_photos = []

    # ==================================================
    #                КОМАНДЫ
    # ==================================================

    @loader.command()
    async def av(self, message):
        """Ответь на медиа — без полей (crop)"""
        await self._process(message, mode="crop")

    @loader.command()
    async def avs(self, message):
        """Ответь на медиа — с полями (fit)"""
        await self._process(message, mode="fit")

    # ==================================================
    #                ОСНОВНАЯ ЛОГИКА
    # ==================================================

    async def _process(self, message, mode="crop"):
        r = await message.get_reply_message()

        if not r or not (r.photo or r.video or r.document):
            return await utils.answer(message, self.strings["no_reply"])

        try:
            await utils.answer(message, self.strings["processing"])

            with tempfile.TemporaryDirectory() as tmp:

                if r.photo:
                    raw = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw)
                    final = await self._photo(raw, tmp, mode)
                    upload_video = False

                else:
                    raw = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video or r.document, raw)
                    final = await self._video(raw, tmp, mode)
                    upload_video = True

                if not final:
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

            text = self.strings["done_crop"] if mode == "crop" else self.strings["done_fit"]
            await utils.answer(message, text)

        except Exception as e:
            logger.error(e, exc_info=True)
            await utils.answer(message, self.strings["error"])

    # ==================================================
    #                  PHOTO
    # ==================================================

    async def _photo(self, path, tmp, mode):
        from PIL import Image

        try:
            out = os.path.join(tmp, "final.jpg")
            img = Image.open(path)

            if img.mode != "RGB":
                img = img.convert("RGB")

            if mode == "crop":
                size = min(img.width, img.height)
                left = (img.width - size) // 2
                top = (img.height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                img = img.resize((640, 640), Image.Resampling.LANCZOS)

            else:  # fit с полями
                img.thumbnail((640, 640), Image.Resampling.LANCZOS)
                bg = Image.new("RGB", (640, 640), (255, 255, 255))
                offset = ((640 - img.width) // 2, (640 - img.height) // 2)
                bg.paste(img, offset)
                img = bg

            img.save(out, "JPEG", quality=95)
            return out

        except Exception as e:
            logger.error(e)
            return None

    # ==================================================
    #                  VIDEO
    # ==================================================

    async def _video(self, path, tmp, mode):
        try:
            out = os.path.join(tmp, "final.mp4")

            if mode == "crop":
                vf = (
                    "scale=540:540:force_original_aspect_ratio=increase,"
                    "crop=540:540"
                )
            else:
                vf = (
                    "scale=540:540:force_original_aspect_ratio=decrease,"
                    "pad=540:540:(ow-iw)/2:(oh-ih)/2"
                )

            cmd = [
                "ffmpeg",
                "-i", path,
                "-t", "10",
                "-vf", vf,
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

            return out

        except Exception as e:
            logger.error(e)
            return None
