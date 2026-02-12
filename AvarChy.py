# ---------------------------------------------------------------------------------
# Name: AvCh
# Description: Простая смена аватарки (фото, GIF, видео) без конвертации
# meta developer: @Dany23s
# ---------------------------------------------------------------------------------

import tempfile
import logging

from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AvCh(loader.Module):
    """Смена аватарки без конвертации"""

    strings = {
        "name": "AvCh",
        "no_reply": "❌ Ответь на фото, GIF или видео",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.added = []

    @loader.command()
    async def AvCh(self, message):
        """Ответом на медиа меняет аватарку"""
        reply = await message.get_reply_message()

        if not reply or not reply.media:
            return await utils.answer(message, self.strings["no_reply"])

        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file_path = await message.client.download_media(reply.media, tmp.name)

            uploaded = await self._client.upload_file(file_path)

            result = await self._client(
                UploadProfilePhotoRequest(file=uploaded)
            )

            # Удаляем старые, добавленные модулем
            self.added.append(result.photo)
            if len(self.added) > 1:
                await self._client(DeletePhotosRequest(self.added[:-1]))
                self.added = self.added[-1:]

            await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(f"AvCh error: {e}")
            await utils.answer(message, self.strings["error"])
