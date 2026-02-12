import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки с сохранением оригиналов (поддержка фото, видео и GIF с автообрезкой)"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на фото, видео или GIF (JPEG/PNG/MP4/GIF)",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        me = await client.get_me()
        result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        self.original_photos = result.photos

    @loader.command()
    async def AChange(self, message):
        """Ответом на фото/видео/GIF меняет аватарку, заменяя предыдущие добавленные скриптом"""
        r = await message.get_reply_message()
        if not r or (not r.photo and not r.video and not getattr(r, 'document', None)):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                if r.photo:
                    file_path = os.path.join(tmp, "avatar.jpg")
                    await message.client.download_media(r.photo, file_path)
                elif r.video or (getattr(r, 'document', None) and r.document.mime_type in ["video/mp4", "image/gif"]):
                    raw_path = os.path.join(tmp, "raw_media")
                    file_path = os.path.join(tmp, "avatar.mp4")
                    await message.client.download_media(r.media, raw_path)

                    # Конвертируем и обрезаем до 5 секунд, квадрат
                    cmd = [
                        "ffmpeg", "-y", "-i", raw_path, "-t", "5",
                        "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        file_path
                    ]
                    subprocess.run(cmd, check=True)

                # Загружаем новое фото/видео
                uploaded_file = await self._client.upload_file(file_path)
                new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))

                # Сохраняем в список добавленных аватарок
                self.added_photos.append(new_photo)

                # Удаляем все предыдущие добавленные, кроме последней
                if len(self.added_photos) > 1:
                    to_delete = self.added_photos[:-1]
                    await self._client(DeletePhotosRequest(to_delete))
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings['changed'])
        except Exception as e:
            logger.error(f"AChange error: {e}")
            await utils.answer(message, self.strings['error'])
