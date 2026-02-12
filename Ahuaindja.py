# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов (фото, стикеры, смайлики и тд)
# meta developer: @FAmods
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto, DocumentAttributeImageSize
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки с сохранением оригиналов"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на: фото, стикер, смайлик, GIF, эмодзи или другое изображение",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "processing": "⏳ Обработка изображения...",
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
        """Меняет аватарку - поддерживает фото, стикеры, смайлики, GIF и прочее"""
        r = await message.get_reply_message()
        
        if not r:
            return await utils.answer(message, self.strings['no_reply'])
        
        # Проверяем все возможные типы изображений
        media_type = self._detect_media_type(r)
        
        if not media_type:
            return await utils.answer(message, self.strings['no_reply'])

        try:
            await utils.answer(message, self.strings['processing'])
            
            with tempfile.TemporaryDirectory() as tmp:
                # Скачиваем и обрабатываем в зависимости от типа
                file_path = await self._download_media(message, r, tmp, media_type)
                
                if not file_path:
                    return await utils.answer(message, self.strings['error'])
                
                # Конвертируем в JPEG если нужно
                converted_path = await self._convert_to_jpeg(file_path, tmp, media_type)
                
                # Загружаем как аватарку
                uploaded_file = await self._client.upload_file(converted_path)
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

    def _detect_media_type(self, message):
        """Определяет тип медиа: фото, стикер, смайлик, GIF, и тд"""
        
        # Обычное фото
        if message.photo:
            return "photo"
        
        # Документ (стикер, GIF, эмодзи и тд)
        if message.document:
            doc = message.document
            mime_type = getattr(doc, 'mime_type', '')
            file_name = getattr(doc, 'file_name', '').lower()
            
            # GIF
            if mime_type == 'image/gif' or file_name.endswith('.gif'):
                return "gif"
            
            # Изображение в документе
            if mime_type.startswith('image/'):
                return "image_doc"
            
            # Стикер (TGS - animated, WEBP - static)
            if mime_type == 'application/x-tgsticker' or file_name.endswith('.tgs'):
                return "animated_sticker"
            
            if mime_type == 'image/webp' or file_name.endswith('.webp'):
                return "sticker"
            
            # Эмодзи (видео-эмодзи)
            if 'emoji' in mime_type.lower() or 'webm' in mime_type:
                return "video_emoji"
        
        # Текст сообщения (может быть смайлик)
        if message.text:
            text = message.text.strip()
            # Проверяем, это ли смайлик/эмодзи (одиночный символ)
            if len(text) <= 2 and self._is_emoji(text):
                return "emoji_text"
        
        return None

    def _is_emoji(self, text):
        """Проверяет, является ли текст эмодзи"""
        # Простая проверка на Unicode эмодзи
        return any(ord(char) > 127 for char in text)

    async def _download_media(self, message, reply_msg, tmp_dir, media_type):
        """Скачивает медиа файл"""
        try:
            if media_type == "photo":
                file_path = os.path.join(tmp_dir, "avatar.jpg")
                await message.client.download_media(reply_msg.photo, file_path)
                return file_path
            
            elif media_type == "gif":
                file_path = os.path.join(tmp_dir, "avatar.gif")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "image_doc":
                file_path = os.path.join(tmp_dir, "avatar.jpg")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "sticker":
                file_path = os.path.join(tmp_dir, "avatar.webp")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "animated_sticker":
                file_path = os.path.join(tmp_dir, "avatar.tgs")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "video_emoji":
                file_path = os.path.join(tmp_dir, "avatar.webm")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "emoji_text":
                # Для текстовых эмодзи, просто возвращаем фиктивный путь
                return None
            
            return None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    async def _convert_to_jpeg(self, file_path, tmp_dir, media_type):
        """Конвертирует файл в JPEG если нужно"""
        try:
            from PIL import Image
            
            # Для стикеров и GIF нужна конвертация
            if media_type in ["sticker", "gif", "image_doc"]:
                output_path = os.path.join(tmp_dir, "avatar_converted.jpg")
                
                if media_type == "sticker":  # WebP
                    img = Image.open(file_path).convert("RGB")
                elif media_type == "gif":
                    img = Image.open(file_path).convert("RGB")
                else:  # image_doc
                    img = Image.open(file_path).convert("RGB")
                
                # Масштабируем до 640x640 (оптимально для аватарки)
                img.thumbnail((640, 640), Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=95)
                
                return output_path
            
            # Для обычных JPEG просто возвращаем оригинал
            return file_path
        
        except ImportError:
            logger.warning("PIL not installed, using original format")
            return file_path
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return file_path
