#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов
# meta developer: @FAmods
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки с сохранением оригиналов"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на фото (JPEG/PNG)",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []  # Фото, которые добавляем скриптом

        # Сохраняем оригинальные аватарки
        me = await client.get_me()
        result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        self.original_photos = result.photos  # Список UserProfilePhoto

    @loader.command()
    async def AChange(self, message):
        """Ответом на фото меняет аватарку, заменяя предыдущие добавленные скриптом"""
        r = await message.get_reply_message()
        if not r or not r.photo:
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                file_path = os.path.join(tmp, "avatar.jpg")
                await message.client.download_media(r.photo, file_path)

                # Загружаем новое фото
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
