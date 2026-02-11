import os
import asyncio
import tempfile
import logging

from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AvaChanger(loader.Module):
    """Смена аватарки по времени. Старые, добавленные скриптом, удаляются, оригинальные сохраняются"""

    strings = {
        "name": "AvaChanger",
        "no_args": "<emoji document_id=5440381017384822513>❌</emoji> <b>Нужно <code>{}avatarl [сколько раз] [сколько ждать перед сменой каждой аватарки]</code></b>",
        "no_reply": "<emoji document_id=5440381017384822513>❌</emoji> <b>Нужно ответить на сообщение с фоткой</b>",
        "changing_avatars": "<emoji document_id=5328274090262275771>🔄</emoji> <b>Меняю аватарки...</b>\n<i>⏳ Это займёт {} секунд</i>",
        "was_off": "<emoji document_id=5440381017384822513>❌</emoji> <b>Смена аватарки была выключена!</b>",
        "off": "<b><emoji document_id=5212932275376759608>✅</emoji> Выключил смену аватарки</b>",
        "completed": "<b><emoji document_id=5212932275376759608>✅</emoji> Готово. Сменил аватарку {} раз за {} секунд/</b>",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.original_photos = []  # Оригинальные аватарки
        self.added_photos = []     # Фото, добавленные скриптом
        self.m = None

        me = await self._client.get_me()
        self.original_photos = me.photo.photos if me.photo else []

    @loader.command()
    async def avatarl(self, message):
        """Смена аватарки по времени, старые удаляются, оригинальные сохраняются"""

        args = utils.get_args_raw(message)
        try:
            counts, time_c = map(int, args.split())
        except:
            return await utils.answer(message, self.strings['no_args'].format(self.get_prefix()))

        r = await message.get_reply_message()
        if not r:
            return await utils.answer(message, self.strings['no_reply'])

        m = await utils.answer(message, self.strings['changing_avatars'].format(time_c * counts))
        self.m = m

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "avatar.jpg")
            await message.client.download_media(r.media.photo, file_path)

            for i in range(counts):
                if not self.m:
                    return

                # Загружаем новую аватарку
                uploaded_file = await self.client.upload_file(file_path)
                new_photo = await self.client(UploadProfilePhotoRequest(file=uploaded_file))

                # Сохраняем добавленное фото, чтобы удалить его позже
                self.added_photos.append(new_photo)

                # Удаляем все предыдущие добавленные фото, кроме последней
                if len(self.added_photos) > 1:
                    to_delete = self.added_photos[:-1]
                    await self.client(DeletePhotosRequest(to_delete))
                    self.added_photos = self.added_photos[-1:]

                await asyncio.sleep(time_c)

        self.m = None
        await utils.answer(message, self.strings['completed'].format(counts, time_c * counts))

    @loader.command()
    async def avatarl_stop(self, message):
        """Выключить смену аватарки по времени"""

        m = self.m
        self.m = None
        await utils.answer(m, self.strings['was_off'])
        await utils.answer(message, self.strings['off'])
