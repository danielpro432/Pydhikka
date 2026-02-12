# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов (все форматы)
# meta developer: @FAmods
# Попыток: 9 🤦
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

ATTEMPTS_COUNT = 9

@loader.tds
class AChange(loader.Module):
    """Смена аватарки - фото, видео, GIF, стикеры"""

    strings = {
        "name": "AChange",
        "no_reply": f"❌ Ответь на фото/видео/GIF/стикер\n💬 Попыток: {ATTEMPTS_COUNT} 🤦",
        "changed": f"✅ Готово!\n💬 Попыток: {ATTEMPTS_COUNT} 🤦",
        "error": f"❌ Ошибка\n💬 Попыток: {ATTEMPTS_COUNT} 🤦",
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
        """Меняет аватарку"""
        r = await message.get_reply_message()
        
        if not r or not (r.photo or r.document or r.video):
            return await utils.answer(message, self.strings['no_reply'])
        
        try:
            await utils.answer(message, self.strings['processing'])
            
            with tempfile.TemporaryDirectory() as tmp:
                # Определяем тип
                is_photo = r.photo is not None
                is_video = r.video is not None
                is_doc = r.document is not None
                
                # Скачиваем
                if is_photo:
                    raw_file = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw_file)
                elif is_video:
                    raw_file = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video, raw_file)
                elif is_doc:
                    raw_file = os.path.join(tmp, "raw.file")
                    await message.client.download_media(r.document, raw_file)
                else:
                    return await utils.answer(message, self.strings['error'])
                
                if not os.path.exists(raw_file) or os.path.getsize(raw_file) == 0:
                    return await utils.answer(message, self.strings['error'])
                
                # Конвертируем
                if is_photo:
                    # Фото → JPEG
                    final_file = await self._photo_to_jpeg(raw_file, tmp)
                    upload_video = False
                else:
                    # Видео/GIF/Стикер → MP4 видео
                    final_file = await self._to_mp4_video(raw_file, tmp)
                    upload_video = True
                
                if not final_file or not os.path.exists(final_file):
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Final: {final_file} ({os.path.getsize(final_file)} bytes), video={upload_video}")
                
                # Загружаем
                uploaded = await self._client.upload_file(final_file)
                
                if upload_video:
                    new_photo = await self._client(UploadProfilePhotoRequest(video=uploaded))
                else:
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

    async def _photo_to_jpeg(self, file_path, tmp_dir):
        """Фото → JPEG"""
        try:
            from PIL import Image
            
            output = os.path.join(tmp_dir, "final.jpg")
            img = Image.open(file_path)
            
            # RGB
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

    async def _to_mp4_video(self, file_path, tmp_dir):
        """Всё → MP4 видео для аватарки (макс 10 сек, макс 10MB)"""
        try:
            output = os.path.join(tmp_dir, "final.mp4")
            
            # FFmpeg команда для конвертации с ограничениями Телеграма
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-t', '10',  # Максимум 10 секунд
                '-vf', 'scale=min(iw\\,540):min(ih\\,540):force_original_aspect_ratio=decrease,pad=540:540:(ow-iw)/2:(oh-ih)/2,fps=30',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',  # Быстро кодировать
                '-crf', '28',
                '-b:v', '600k',
                '-maxrate', '800k',
                '-bufsize', '1600k',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',  # Для быстрой загрузки
                '-y',
                output
            ]
            
            logger.info(f"FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown"
                logger.error(f"FFmpeg error: {error}")
                return None
            
            # Проверяем размер
            size = os.path.getsize(output)
            logger.info(f"Video size: {size} bytes")
            
            if size > 10 * 1024 * 1024:  # > 10MB
                logger.warning(f"Video too large ({size}), re-encoding with lower bitrate")
                return await self._to_mp4_video_low_quality(file_path, tmp_dir)
            
            return output
        
        except FileNotFoundError:
            logger.error("FFmpeg not found - install with: apt-get install ffmpeg")
            return None
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return None
        except Exception as e:
            logger.error(f"Video error: {e}", exc_info=True)
            return None

    async def _to_mp4_video_low_quality(self, file_path, tmp_dir):
        """Пересчёт с низким качеством если файл слишком большой"""
        try:
            output = os.path.join(tmp_dir, "final_low.mp4")
            
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-t', '10',
                '-vf', 'scale=360:360:force_original_aspect_ratio=decrease,pad=360:360:(ow-iw)/2:(oh-ih)/2,fps=24',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '32',
                '-b:v', '300k',
                '-c:a', 'aac',
                '-b:a', '64k',
                '-movflags', '+faststart',
                '-y',
                output
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode != 0:
                logger.error("Low quality encoding failed")
                return None
            
            return output
        except Exception as e:
            logger.error(f"Low quality error: {e}")
            return None
