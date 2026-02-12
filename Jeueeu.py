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
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки с сохранением оригиналов"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на: фото, стикер, смайлик, GIF или другое изображение",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "processing": "⏳ Обработка изображения...",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        # Сохраняем оригинальные аватарки
        me = await client.get_me()
        result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        self.original_photos = result.photos

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
                # Скачиваем медиа
                raw_path = await self._download_media(message, r, tmp, media_type)
                
                if not raw_path or not os.path.exists(raw_path):
                    return await utils.answer(message, self.strings['error'])
                
                # Конвертируем в JPEG с правильны�� расширением
                jpeg_path = await self._convert_to_jpeg(raw_path, tmp, media_type)
                
                if not jpeg_path or not os.path.exists(jpeg_path):
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Uploading avatar from: {jpeg_path}")
                logger.info(f"File size: {os.path.getsize(jpeg_path)} bytes")
                
                # Загружаем как аватарку - ТОЛЬКО JPEG!
                uploaded_file = await self._client.upload_file(jpeg_path)
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
        """Определяет тип медиа"""
        
        # Обычное фото
        if message.photo:
            return "photo"
        
        # Документ (стикер, GIF, эмодзи и тд)
        if message.document:
            doc = message.document
            mime_type = getattr(doc, 'mime_type', '').lower()
            file_name = getattr(doc, 'file_name', '').lower()
            
            logger.info(f"Document detected - MIME: {mime_type}, Name: {file_name}")
            
            # GIF
            if mime_type == 'image/gif' or file_name.endswith('.gif'):
                return "gif"
            
            # Стикер WebP (статичный)
            if mime_type == 'image/webp' or file_name.endswith('.webp'):
                return "sticker_webp"
            
            # Анимированный стикер
            if mime_type == 'application/x-tgsticker' or file_name.endswith('.tgs'):
                return "sticker_animated"
            
            # Обычное изображение в документе
            if mime_type.startswith('image/'):
                return "image_doc"
        
        return None

    async def _download_media(self, message, reply_msg, tmp_dir, media_type):
        """Скачи��ает медиа файл"""
        try:
            if media_type == "photo":
                file_path = os.path.join(tmp_dir, "avatar.jpg")
                await message.client.download_media(reply_msg.photo, file_path)
                return file_path
            
            elif media_type == "gif":
                file_path = os.path.join(tmp_dir, "avatar.gif")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "sticker_webp":
                file_path = os.path.join(tmp_dir, "avatar.webp")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "sticker_animated":
                file_path = os.path.join(tmp_dir, "avatar.tgs")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            elif media_type == "image_doc":
                file_path = os.path.join(tmp_dir, "avatar.img")
                await message.client.download_media(reply_msg.document, file_path)
                return file_path
            
            return None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    async def _convert_to_jpeg(self, file_path, tmp_dir, media_type):
        """Конвертирует ВСЕ форматы в JPEG"""
        try:
            from PIL import Image
            
            output_path = os.path.join(tmp_dir, "avatar_final.jpg")
            
            # Пытаемся открыть файл и конвертировать в JPEG
            try:
                img = Image.open(file_path)
                
                # Конвертируем в RGB (убираем альфа канал если есть)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Создаём белый фон для прозрачных пикселей
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                else:
                    img = img.convert('RGB')
                
                # Масштабируем до 640x640
                img.thumbnail((640, 640), Image.Resampling.LANCZOS)
                
                # Создаём квадратное изображение с белым фоном
                final_img = Image.new('RGB', (640, 640), (255, 255, 255))
                offset = ((640 - img.width) // 2, (640 - img.height) // 2)
                final_img.paste(img, offset)
                
                # Сохраняем как JPEG с максимальным качеством
                final_img.save(output_path, 'JPEG', quality=95, optimize=False)
                
                logger.info(f"Converted to JPEG: {output_path} ({os.path.getsize(output_path)} bytes)")
                return output_path
            
            except Exception as e:
                logger.error(f"Conversion failed: {e}")
                # Если конвертация не сработала, копируем оригинальный файл
                # и переименовываем в .jpg
                import shutil
                shutil.copy(file_path, output_path)
                return output_path
        
        except ImportError:
            logger.warning("PIL not installed, copying file as JPEG")
            import shutil
            output_path = os.path.join(tmp_dir, "avatar_final.jpg")
            shutil.copy(file_path, output_path)
            return output_path
        
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return None
