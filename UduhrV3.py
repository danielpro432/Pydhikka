# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с поддержкой видео, GIF, стикеров и анимированных эмодзи
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
    """Смена аватарки: фото, видео, GIF, стикеры, анимированные эмодзи"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на фото/видео/GIF/стикер/аним. эмодзи",
        "changed": "✅ Аватарка обновлена",
        "error": "❌ Ошибка при обработке",
        "processing": "⏳ Обработка...",
    }

    async def client_ready(self, client, db):
        self._client = client
        self.added_photos = []

    @loader.command()
    async def achange(self, message):
        """Меняет аватарку"""
        r = await message.get_reply_message()
        if not r or not (r.photo or r.document or r.video):
            return await utils.answer(message, self.strings["no_reply"])

        try:
            await utils.answer(message, self.strings["processing"])

            with tempfile.TemporaryDirectory() as tmp:
                raw_file = os.path.join(tmp, "raw")

                await message.client.download_media(r, raw_file)
                if not os.path.exists(raw_file) or os.path.getsize(raw_file) == 0:
                    return await utils.answer(message, self.strings["error"])

                mime_type = getattr(r.document, 'mime_type', '') if r.document else ''
                upload_video = False

                # ---------------- Фото ----------------
                if r.photo:
                    final_file = await self._photo_to_jpeg(raw_file, tmp)

                # ---------------- Видео / GIF / Стикеры ----------------
                elif r.video or (r.document and mime_type.startswith("video")) or (r.document and mime_type == "image/gif"):
                    final_file = await self._to_mp4_video(raw_file, tmp)
                    upload_video = True

                # ---------------- Анимированные эмодзи ----------------
                elif r.document and mime_type == "application/x-tgsticker":
                    final_file = await self._tgs_to_mp4(raw_file, tmp)
                    upload_video = True

                else:
                    return await utils.answer(message, self.strings["error"])

                if not final_file or not os.path.exists(final_file):
                    return await utils.answer(message, self.strings["error"])

                uploaded = await self._client.upload_file(final_file)

                if upload_video:
                    new_photo = await self._client(UploadProfilePhotoRequest(video=uploaded))
                else:
                    new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded))

                self.added_photos.append(new_photo)
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
        try:
            output = os.path.join(tmp_dir, "final.mp4")

            # FFprobe чтобы узнать длительность
            probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
            duration = float(subprocess.check_output(probe_cmd).decode().strip())
            max_time = min(duration, 5)  # обрезаем до 5 сек, если больше

            cmd = [
                "ffmpeg",
                "-i", file_path,
                "-t", str(max_time),
                "-vf", "scale=min(iw\\,540):min(ih\\,540):force_original_aspect_ratio=decrease,"
                       "pad=540:540:(ow-iw)/2:(oh-ih)/2,fps=30",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                "-y",
                output
            ]
            subprocess.run(cmd, capture_output=True, timeout=120)
            if not os.path.exists(output):
                return None
            return output
        except Exception as e:
            logger.error(f"Video error: {e}", exc_info=True)
            return None

    # ---------------- TGS (анимированные эмодзи) ----------------
    async def _tgs_to_mp4(self, file_path, tmp_dir):
        try:
            from lottie.parsers.tgs import parse_tgs
            anim = parse_tgs(file_path)
            output = os.path.join(tmp_dir, "final.mp4")
            anim.render(output, fps=30, loop=0)  # рендерим в mp4
            return output
        except Exception as e:
            logger.error(f"TGS -> MP4 error: {e}")
            return None
