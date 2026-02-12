# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением ориги��алов (статичные + анимированные)
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
        "no_reply": "❌ Нужно ответить на медиа (фото, стикер, GIF и т.д.)",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "processing": "⏳ Обработка изображения...",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        # Сохраняем оригинальные аватарки
        try:
            me = await client.get_me()
            result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            self.original_photos = result.photos
        except Exception as e:
            logger.error(f"Failed to get original photos: {e}")
            self.original_photos = []

    @loader.command()
    async def achange(self, message):
        """Меняет аватарку - ответь на фото, стикер, GIF"""
        r = await message.get_reply_message()
        
        logger.info(f"AChange command triggered")
        
        if not r:
            logger.info("No reply message found")
            return await utils.answer(message, self.strings['no_reply'])
        
        logger.info(f"Reply has photo: {r.photo}")
        logger.info(f"Reply has document: {r.document}")
        
        # Проверяем есть ли медиа вообще
        if not (r.photo or r.document):
            logger.info("No media found in reply")
            return await utils.answer(message, self.strings['no_reply'])
        
        # Определяем тип медиа
        media_type, is_animated = self._detect_media_type(r)
        logger.info(f"Detected media type: {media_type}, animated: {is_animated}")
        
        if not media_type:
            logger.info("Unable to detect media type")
            return await utils.answer(message, self.strings['no_reply'])

        try:
            await utils.answer(message, self.strings['processing'])
            
            with tempfile.TemporaryDirectory() as tmp:
                # Скачиваем медиа
                raw_path = await self._download_media(message, r, tmp, media_type)
                
                logger.info(f"Downloaded to: {raw_path}")
                
                if not raw_path or not os.path.exists(raw_path):
                    logger.error(f"Download failed or file doesn't exist: {raw_path}")
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"File size: {os.path.getsize(raw_path)} bytes")
                
                # Для статичных фото конвертируем в JPEG
                # Для GIF и анимированных - оставляем как есть
                if media_type == "photo" and not is_animated:
                    final_path = await self._convert_to_jpeg(raw_path, tmp)
                    upload_as_video = False
                elif is_animated or media_type in ["gif", "sticker_animated"]:
                    final_path = raw_path
                    upload_as_video = True
                else:
                    final_path = await self._convert_to_jpeg(raw_path, tmp)
                    upload_as_video = False
                
                if not final_path or not os.path.exists(final_path):
                    logger.error(f"Preparation failed: {final_path}")
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Final file: {final_path} ({os.path.getsize(final_path)} bytes), upload_as_video: {upload_as_video}")
                
                # Загружаем как аватарку
                uploaded_file = await self._client.upload_file(final_path)
                
                if upload_as_video:
                    logger.info("Uploading as video...")
                    new_photo = await self._client(UploadProfilePhotoRequest(video=uploaded_file))
                else:
                    logger.info("Uploading as photo...")
                    new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))
                
                logger.info(f"Avatar uploaded successfully")
                
                # Сохраняем в список
                self.added_photos.append(new_photo)

                # Удаляем старые добавленные аватарки
                if len(self.added_photos) > 1:
                    to_delete = self.added_photos[:-1]
                    try:
                        await self._client(DeletePhotosRequest(to_delete))
                    except Exception as e:
                        logger.error(f"Failed to delete old photos: {e}")
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings['changed'])
        except Exception as e:
            logger.error(f"AChange error: {e}", exc_info=True)
            await utils.answer(message, self.strings['error'])

    def _detect_media_type(self, message):
        """Определяет тип медиа и является ли оно анимированным"""
        
        is_animated = False
        
        # Обычное фото
        if message.photo:
            logger.info("Detected: Photo")
            return "photo", False
        
        # Документ (стикер, GIF, и тд)
        if message.document:
            doc = message.document
            mime_type = getattr(doc, 'mime_type', '').lower()
            file_name = getattr(doc, 'file_name', '').lower()
            
            logger.info(f"Document MIME: {mime_type}, Name: {file_name}")
            
            # GIF - АНИМИРОВАННОЕ
            if 'gif' in mime_type or file_name.endswith('.gif'):
                return "gif", True
            
            # WebP стикер - может быть анимированным
            if 'webp' in mime_type or file_name.endswith('.webp'):
                # Проверяем размер - анимированные обычно больше
                is_anim = getattr(doc, 'size', 0) > 50000
                return "sticker_webp", is_anim
            
            # Анимированный стикер TGS
            if 'tgsticker' in mime_type or file_name.endswith('.tgs'):
                return "sticker_animated", True
            
            # WEBM видео-эмодзи
            if 'webm' in mime_type or file_name.endswith('.webm'):
                return "video_emoji", True
            
            # Просто изображение
            if mime_type.startswith('image/'):
                return "image_doc", False
            
            # PNG, JPG в документе
            if file_name.endswith(('.png', '.jpg', '.jpeg')):
                return "image_doc", False
        
        return None, False

    async def _download_media(self, message, reply_msg, tmp_dir, media_type):
        """Скачивает медиа файл"""
        try:
            if media_type == "photo":
                file_path = os.path.join(tmp_dir, "avatar.jpg")
                await message.client.download_media(reply_msg.photo, file_path)
            
            elif media_type == "gif":
                file_path = os.path.join(tmp_dir, "avatar.gif")
                await message.client.download_media(reply_msg.document, file_path)
            
            elif media_type == "sticker_webp":
                file_path = os.path.join(tmp_dir, "avatar.webp")
                await message.client.download_media(reply_msg.document, file_path)
            
            elif media_type == "sticker_animated":
                file_path = os.path.join(tmp_dir, "avatar.tgs")
                await message.client.download_media(reply_msg.document, file_path)
            
            elif media_type == "video_emoji":
                file_path = os.path.join(tmp_dir, "avatar.webm")
                await message.client.download_media(reply_msg.document, file_path)
            
            elif media_type == "image_doc":
                file_path = os.path.join(tmp_dir, "avatar.img")
                await message.client.download_media(reply_msg.document, file_path)
            
            else:
                return None
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
            return None
            
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return None

    async def _convert_to_jpeg(self, file_path, tmp_dir):
        """Конвертирует в JPEG только статичные изображения"""
        try:
            from PIL import Image
            
            output_path = os.path.join(tmp_dir, "avatar_final.jpg")
            
            try:
                logger.info(f"Converting to JPEG: {file_path}")
                img = Image.open(file_path)
                logger.info(f"Image mode: {img.mode}, size: {img.size}")
                
                # RGB конвертация
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if 'A' in img.mode:
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                else:
                    img = img.convert('RGB')
                
                # Масштабирование
                img.thumbnail((640, 640), Image.Resampling.LANCZOS)
                
                # Квадратный размер
                final_img = Image.new('RGB', (640, 640), (255, 255, 255))
                offset = ((640 - img.width) // 2, (640 - img.height) // 2)
                final_img.paste(img, offset)
                
                # Сохранение
                final_img.save(output_path, 'JPEG', quality=95, optimize=False)
                
                logger.info(f"Saved JPEG: {output_path}")
                return output_path
            
            except Exception as e:
                logger.error(f"Conversion error: {e}", exc_info=True)
                # Fallback: копируем оригинал
                import shutil
                output_path = os.path.join(tmp_dir, "avatar_final.jpg")
                shutil.copy(file_path, output_path)
                return output_path
        
        except ImportError:
            logger.warning("PIL not installed, using original file")
            import shutil
            output_path = os.path.join(tmp_dir, "avatar_final.jpg")
            shutil.copy(file_path, output_path)
            return output_path
