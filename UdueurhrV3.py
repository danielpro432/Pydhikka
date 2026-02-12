# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с автозумом для GIF/видео/стикеров (без чёрных краёв)
# meta developer: @FAmods
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки - фото, видео, GIF, стикеры (без чёрных краёв)"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на фото/видео/GIF/стикер",
        "changed": "✅ Аватарка обновлена",
        "error": "❌ Ошибка при обработке",
        "processing": "⏳ Обработка...",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        try:
            me = await client.get_me()
            result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            self.original_photos = result.photos
        except:
            self.original_photos = []

    @loader.command()
    async def achange(self, message):
        """Меняет аватарку"""
        r = await message.get_reply_message()

        if not r or not (r.photo or r.document or r.video):
            return await utils.answer(message, self.strings["no_reply"])

        try:
            await utils.answer(message, self.strings["processing"])

            with tempfile.TemporaryDirectory() as tmp:

                # Определяем тип
                is_photo = r.photo is not None
                is_video = r.video is not None
                is_doc = r.document is not None

                # Скачиваем
                raw_file = os.path.join(tmp, "raw")
                await message.client.download_media(r, raw_file)

                if not os.path.exists(raw_file):
                    return await utils.answer(message, self.strings["error"])

                # Фото → JPEG
                if is_photo:
                    final_file = await self._photo_to_jpeg(raw_file, tmp)
                    upload_video = False
                else:
                    # Видео/GIF/Стикер → MP4 (с зумом)
                    final_file = await self._to_mp4_video(raw_file, tmp)
                    upload_video = True

                if not final_file or not os.path.exists(final_file):
                    return await utils.answer(message, self.strings["error"])

                uploaded = await self._client.upload_file(final_file)

                if upload_video:
                    new_photo = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )
                else:
                    new_photo = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )

                self.added_photos.append(new_photo)

                # Удаляем старые временные
                if len(self.added_photos) > 1:
                    try:
                        await self._client(DeletePhotosRequest(self.added_photos[:-1]))
                    except:
                        pass
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(f"AChange error: {e}", exc_info=True)
            await utils.answer(message, self.strings["error"])

    # ---------------- PHOTO ----------------

    async def _photo_to_jpeg(self, file_path, tmp_dir):
        try:
            from PIL import Image

            output = os.path.join(tmp_dir, "final.jpg")
            img = Image.open(file_path).convert("RGB")

            img.thumbnail((640, 640), Image.Resampling.LANCZOS)

            final = Image.new("RGB", (640, 640), (255, 255, 255))
            offset = ((640 - img.width) // 2, (640 - img.height) // 2)
            final.paste(img, offset)

            final.save(output, "JPEG", quality=95)
            return output

        except Exception as e:
            logger.error(f"Photo error: {e}")
            return None

    # ---------------- VIDEO / GIF / STICKER ----------------

    async def _to_mp4_video(self, file_path, tmp_dir):
        """Авто-зум без чёрных краёв"""
        try:
            output = os.path.join(tmp_dir, "final.mp4")

            cmd = [
                "ffmpeg",
                "-i", file_path,
                "-t", "10",

                # 🔥 Увеличиваем и обрезаем по центру (без рамок)
                "-vf",
                "scale=600:600:force_original_aspect_ratio=increase,"
                "crop=540:540,fps=30",

                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                "-y",
                output
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode != 0:
                logger.error(result.stderr.decode())
                return None

            return output

        except Exception as e:
            logger.error(f"Video error: {e}", exc_info=True)
            return None
