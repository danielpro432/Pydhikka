#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AvCh
# Description: Фото, GIF и видео в аватарку с автоматическим ресайзом и сохранением оригиналов
# meta developer: @Dany23s
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import asyncio
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import InputPhoto
from .. import loader, utils
from PIL import Image
import moviepy.editor as mp

logger = logging.getLogger(__name__)

@loader.tds
class AvCh(loader.Module):
    """Смена аватарки с фото, GIF и видео с автоматическим ресайзом"""

    strings = {
        "name": "AvCh",
        "no_reply": "❌ Нужно ответить на фото, GIF или короткое видео",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "unsupported": "❌ Этот тип медиа не поддерживается для аватарки",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        me = await client.get_me()
        result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        self.original_photos = result.photos

    @loader.command()
    async def AvCh(self, message):
        """Ответом на фото/GIF/видео меняет аватарку с авто ресайзом"""
        r = await message.get_reply_message()
        if not r or not (r.photo or getattr(r.media, 'document', None)):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                file_path = os.path.join(tmp, "avatar")
                await message.client.download_media(r.media, file_path)

                ext = ".jpg"
                # фото
                if r.photo:
                    im = Image.open(file_path)
                    im = im.convert("RGB")
                    # crop/resize в квадрат
                    size = max(im.width, im.height)
                    new_im = Image.new("RGB", (size, size), (255, 255, 255))
                    new_im.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
                    new_im.save(file_path)
                # gif или видео
                else:
                    mime = getattr(r.media.document, 'mime_type', '')
                    if mime in ["image/gif", "video/mp4"]:
                        ext = ".mp4"
                        clip = mp.VideoFileClip(file_path)
                        # обрезаем до 5 сек
                        if clip.duration > 5:
                            clip = clip.subclip(0, 5)
                        # ресайз в квадрат
                        size = max(clip.w, clip.h)
                        clip = clip.resize(height=size).crop(x_center=clip.w/2, y_center=clip.h/2, width=size, height=size)
                        clip.write_videofile(file_path, codec="libx264", audio=False, verbose=False, logger=None)
                    else:
                        return await utils.answer(message, self.strings['unsupported'])

                uploaded_file = await self._client.upload_file(file_path)
                new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))

                self.added_photos.append(new_photo)
                if len(self.added_photos) > 1:
                    to_delete = self.added_photos[:-1]
                    await self._client(DeletePhotosRequest(to_delete))
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings['changed'])
        except Exception as e:
            logger.error(f"AvCh error: {e}")
            await utils.answer(message, self.strings['error'])
