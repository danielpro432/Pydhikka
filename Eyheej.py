import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChangeVideo(loader.Module):
    """Смена аватарки на видео (только обрезка до 5 секунд)"""

    strings = {
        "name": "AChangeVideo",
        "no_reply": "❌ Нужно ответить на видео (MP4/GIF)",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    @loader.command()
    async def AChange(self, message):
        """Ответом на видео меняет аватарку"""
        r = await message.get_reply_message()
        if not r or (not r.video and not getattr(r, 'document', None)):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                raw_path = os.path.join(tmp, "raw_video")
                file_path = os.path.join(tmp, "avatar_cut.mp4")

                await message.client.download_media(r.media, raw_path)

                # Обрезаем до 5 секунд, без конвертации
                cmd = [
                    "ffmpeg", "-y", "-i", raw_path, "-t", "5", "-c", "copy", file_path
                ]
                subprocess.run(cmd, check=True)

                # Загружаем на аватарку
                uploaded_file = await self._client.upload_file(file_path)
                await self._client(UploadProfilePhotoRequest(file=uploaded_file))

            await utils.answer(message, self.strings['changed'])

        except Exception as e:
            logger.error(f"AChangeVideo error: {e}")
            await utils.answer(message, self.strings['error'])
