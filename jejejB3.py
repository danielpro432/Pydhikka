# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов
# meta developer: @FAmods
# Попыток: 11 (видеоаватарки - миф) 🤦
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AChange(loader.Module):
    """Смена аватарки - фото, GIF, стикеры"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на фото/GIF/стикер/видео\n💬 Попыток: 11 (видеоаватарки - миф) 🤦",
        "changed": "✅ Готово!\n💬 Попыток: 11 🤦",
        "error": "❌ Ошибка\n💬 Попыток: 11 🤦",
        "processing": "⏳ Обработка...",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.added_photos = []

        try:
            me = await client.get_me()
            result = await client(GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            self.original_photos = result.photos
        except Exception as e:
            logger.error(f"Error: {e}")
            self.original_photos = []

    @loader.command()
    async def achange(self, message):
        """Меняет аватарку - ответь на фото/GIF/видео/стикер"""
        r = await message.get_reply_message()
        
        if not r or not (r.photo or r.document or r.video):
            return await utils.answer(message, self.strings['no_reply'])
        
        try:
            await utils.answer(message, self.strings['processing'])
            
            with tempfile.TemporaryDirectory() as tmp:
                raw_file = None
                media_type = None
                
                # Определяем тип и скачиваем
                if r.photo:
                    raw_file = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw_file)
                    media_type = "photo"
                    
                elif r.video:
                    raw_file = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video, raw_file)
                    media_type = "video"
                    
                elif r.document:
                    raw_file = os.path.join(tmp, "raw.file")
                    await message.client.download_media(r.document, raw_file)
                    
                    doc = r.document
                    mime = getattr(doc, 'mime_type', '').lower()
                    fname = getattr(doc, 'file_name', '').lower()
                    
                    if 'gif' in mime or fname.endswith('.gif'):
                        media_type = "gif"
                    elif 'webp' in mime or fname.endswith('.webp'):
                        media_type = "sticker"
                    elif 'tgsticker' in mime or fname.endswith('.tgs'):
                        media_type = "sticker_anim"
                    elif 'video' in mime or fname.endswith(('.mp4', '.webm', '.mov')):
                        media_type = "video"
                    else:
                        media_type = "image"
                
                if not raw_file or not os.path.exists(raw_file) or os.path.getsize(raw_file) == 0:
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Media type: {media_type}")
                
                # Конвертируем в зависимости от типа
                if media_type == "photo":
                    final_file = await self._convert_photo(raw_file, tmp)
                    
                elif media_type in ["gif", "video"]:
                    # Видео/GIF → первый кадр JPEG или анимированный GIF
                    final_file = await self._video_to_image(raw_file, tmp, keep_gif=(media_type == "gif"))
                    
                elif media_type in ["sticker", "sticker_anim"]:
                    # Стикер → JPEG
                    final_file = await self._sticker_to_jpeg(raw_file, tmp)
                    
                else:  # image
                    final_file = await self._convert_photo(raw_file, tmp)
                
                if not final_file or not os.path.exists(final_file):
                    logger.error(f"Conversion failed")
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Final: {final_file} ({os.path.getsize(final_file)} bytes)")
                
                # Загружаем как обычное фото (без video параметра!)
                uploaded = await self._client.upload_file(final_file)
                new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded))
                
                self.added_photos.append(new_photo)
                
                if len(self.added_photos) > 1:
                    try:
                        await self._client(DeletePhotosRequest(self.added_photos[:-1]))
                    except:
                        pass
                    self.added_photos = self.added_photos[-1:]

            await utils.answer(message, self.strings['changed'])
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await utils.answer(message, self.strings['error'])

    async def _convert_photo(self, file_path, tmp_dir):
        """Фото → JPEG"""
        try:
            from PIL import Image
            
            output = os.path.join(tmp_dir, "final.jpg")
            img = Image.open(file_path)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if 'A' in img.mode:
                    bg.paste(img, mask=img.split()[-1])
                else:
                    bg.paste(img)
                img = bg
            else:
                img = img.convert('RGB')
            
            img.thumbnail((640, 640), Image.Resampling.LANCZOS)
            
            final = Image.new('RGB', (640, 640), (255, 255, 255))
            offset = ((640 - img.width) // 2, (640 - img.height) // 2)
            final.paste(img, offset)
            
            final.save(output, 'JPEG', quality=95)
            return output
        except ImportError:
            import shutil
            output = os.path.join(tmp_dir, "final.jpg")
            shutil.copy(file_path, output)
            return output
        except Exception as e:
            logger.error(f"Photo error: {e}")
            return None

    async def _video_to_image(self, file_path, tmp_dir, keep_gif=False):
        """Видео → JPEG (первый кадр) или GIF (если был GIF)"""
        try:
            if keep_gif and file_path.endswith('.gif'):
                # Для GIF просто копируем
                import shutil
                output = os.path.join(tmp_dir, "final.gif")
                shutil.copy(file_path, output)
                return output
            
            # Видео → первый кадр
            from PIL import Image
            
            frame_file = os.path.join(tmp_dir, "frame.jpg")
            output = os.path.join(tmp_dir, "final.jpg")
            
            # Извлекаем первый кадр FFmpeg
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-vframes', '1',
                '-q:v', '2',
                frame_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode != 0 or not os.path.exists(frame_file):
                logger.error("FFmpeg frame extraction failed")
                return None
            
            # Конвертируем кадр в аватарку
            img = Image.open(frame_file)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if 'A' in img.mode:
                    bg.paste(img, mask=img.split()[-1])
                else:
                    bg.paste(img)
                img = bg
            else:
                img = img.convert('RGB')
            
            img.thumbnail((640, 640), Image.Resampling.LANCZOS)
            
            final = Image.new('RGB', (640, 640), (255, 255, 255))
            offset = ((640 - img.width) // 2, (640 - img.height) // 2)
            final.paste(img, offset)
            
            final.save(output, 'JPEG', quality=95)
            return output
            
        except Exception as e:
            logger.error(f"Video to image error: {e}")
            return None

    async def _sticker_to_jpeg(self, file_path, tmp_dir):
        """Стикер (WEBP/TGS) → JPEG"""
        try:
            from PIL import Image
            
            output = os.path.join(tmp_dir, "final.jpg")
            img = Image.open(file_path)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if 'A' in img.mode:
                    bg.paste(img, mask=img.split()[-1])
                else:
                    bg.paste(img)
                img = bg
            else:
                img = img.convert('RGB')
            
            img.thumbnail((640, 640), Image.Resampling.LANCZOS)
            
            final = Image.new('RGB', (640, 640), (255, 255, 255))
            offset = ((640 - img.width) // 2, (640 - img.height) // 2)
            final.paste(img, offset)
            
            final.save(output, 'JPEG', quality=95)
            return output
            
        except Exception as e:
            logger.error(f"Sticker error: {e}")
            return None
