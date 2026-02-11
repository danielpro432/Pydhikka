#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

#   https://t.me/famods

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов
# meta developer: @FAmods
# ---------------------------------------------------------------------------------

import os
import asyncio
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
        "no_reply": "<emoji document_id=5440381017384822513>❌</emoji> Нужно ответить на фото/гиф/стикер",
        "changed": "<emoji document_id=5328274090262275771>✅</emoji> Аватарка обновлена!",
        "error": "<emoji document_id=5440381017384822513>❌</emoji> Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []  # Фото, которые добавляем скриптом
        self.original_photos = []  # Оригинальные аватарки
        self.m = None

        # Получаем все аватарки пользователя, чтобы сохранить оригинальные
        me = await self._client.get_me()
        result = await self._client(GetUserPhotosRequest(
            user_id=me.id,
            offset=0,
            max_id=0,
            limit=100
        ))
        self.original_photos = result.photos  # Сохраняем все текущие аватарки

    @loader.command()
    async def AChange(self, message):
        """Ответом на фото/гиф/стикер меняет аватарку, заменяя предыдущие добавленные скриптом"""

        r = await message.get_reply_message()
        if not r or not (r.photo or getattr(r.media, 'document', None)):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = os.path.join(temp_dir, "avatar")
                await message.client.download_media(r.media, file_path)

                # Загружаем новое фото
                uploaded_file = await self._client.upload_file(file_path)
                new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))

                # Добавляем его в список добавленных
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
