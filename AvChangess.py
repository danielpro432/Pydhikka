#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Фото, GIF и видео в аватарку с сохранением оригиналов
# meta developer: @Dany23s
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import asyncio
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import InputPhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки с фото, GIF и коротких видео с сохранением оригиналов"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на фото, GIF или видео",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "unsupported": "❌ Этот тип медиа не поддерживается для аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        # Получаем оригинальные аватарки пользователя
        me = await client.get_me()
        result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        self.original_photos = result.photos  # Сохраняем все оригинальные аватарки

    @loader.command()
    async def AChange(self, message):
        """Ответом на фото, GIF или короткое видео меняет аватарку"""
        r = await message.get_reply_message()
        if not r or not (r.photo or getattr(r.media, 'document', None)):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                file_path = os.path.join(tmp, "avatar")
                await message.client.download_media(r.media, file_path)

                # Проверка типа: фото или gif/mp4
                if r.photo:
                    # обычное фото
                    ext = ".jpg"
                else:
                    # документ (gif/mp4)
                    mime = getattr(r.media.document, 'mime_type', '')
                    if mime in ["image/gif", "video/mp4"]:
                        ext = ".mp4"  # для анимированной аватарки Telegram
                    else:
                        return await utils.answer(message, self.strings['unsupported'])

                file_path += ext

                uploaded_file = await self._client.upload_file(file_path)
                new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))

                # Добавляем в список скриптом добавленных фото
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
