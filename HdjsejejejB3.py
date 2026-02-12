# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов (все форматы)
# meta developer: @FAmods
# Попыток: 10 🤦
# ---------------------------------------------------------------------------------

import os
import tempfile
import logging
import subprocess
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import UserProfilePhoto
from .. import loader, utils

logger = logging.getLogger(__name__)

ATTEMPTS_COUNT = 10

@loader.tds
class AChange(loader.Module):
    """Смена аватарки - фото, видео, GIF, стикеры, смайлики"""

    strings = {
        "name": "AChange",
        "no_reply": f"❌ Ответь на фото/видео/GIF/стикер/смайлик\n💬 Попыток: {ATTEMPTS_COUNT} 🤦",
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
                # Определяем тип и скачиваем
                is_photo = r.photo is not None
                is_video = r.video is not None
                is_doc = r.document is not None
                
                if is_photo:
                    raw_file = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw_file)
                    upload_type = "photo"
                elif is_video:
                    raw_file = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video, raw_file)
                    upload_type = "video"
                elif is_doc:
                    raw_file = os.path.join(tmp, "raw.file")
                    await message.client.download_media(r.document, raw_file)
                    # Определяем тип документа
                    doc = r.document
                    mime = getattr(doc, 'mime_type', '').lower()
                    fname = getattr(doc, 'file_name', '').lower()
                    
                    if 'video' in mime or fname.endswith(('.mp4', '.webm', '.mov')):
                        upload_type = "video"
                    elif 'gif' in mime or fname.endswith('.gif'):
                        upload_type = "gif"
                    elif 'webp' in mime or fname.endswith('.webp'):
                        upload_type = "sticker"
                    elif 'tgsticker' in mime or fname.endswith('.tgs'):
                        upload_type = "sticker_anim"
                    else:
                        upload_type = "image"
                else:
                    return await utils.answer(message, self.strings['error'])
                
                if not os.path.exists(raw_file) or os.path.getsize(raw_file) == 0:
                    return await utils.answer(message, self.strings['error'])
                
                logger.info(f"Upload type: {upload_type}, File: {raw_file}")
                
                # Конвертируем в зависимости от типа
                if upload_type == "photo":
                    final_file = await self._photo_to_jpeg(raw_file, tmp)
                    use_video_param = False
                elif upload_type in ["video", "gif"]:
                    final_file = await self._to_mp4_video(raw_file, tmp, 6)  # 6 сек для видео
                    use_video_param = True
                elif upload_type in ["sticker", "sticker_anim"]:
                    final_file = await self._to_mp4_video(raw_file, tmp, 4)  # 4 сек для стикеров
                    use_video_param = True
                else:  # image
                    final_file = await self._photo_to_jpeg(raw_file, tmp)
                    use_video_param = False
                
                if not final_file or not os.path.exists(final_file):
                    logger.error(f"Conversion failed: {final_file}")
                    return await utils.answer(message, self.strings['error'])
                
                file_size = os.path.getsize(final_file)
                logger.info(f"Final file: {final_file} ({file_size} bytes), video={use_video_param}")
                
                # Загружаем
                try:
                    uploaded = await self._client.upload_file(final_file)
                    
                    if use_video_param:
                        logger.info("Uploading as video...")
                        new_photo = await self._client(UploadProfilePhotoRequest(video=uploaded))
                    else:
                        logger.info("Uploading as photo...")
                        new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded))
                except Exception as upload_err:
                    logger.error(f"Upload error: {upload_err}")
                    raise upload_err
                
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
            logger.info(f"JPEG saved: {os.path.getsize(output)} bytes")
            return output
        
        except ImportError:
            import shutil
            output = os.path.join(tmp_dir, "final.jpg")
            shutil.copy(file_path, output)
            return output
        except Exception as e:
            logger.error(f"Photo error: {e}")
            return None

    async def _to_mp4_video(self, file_path, tmp_dir, duration=6):
        """Всё → MP4 видео с правильными параметрами для Telegram"""
        try:
            output = os.path.join(tmp_dir, "final.mp4")
            
            # Критически важные параметры для Telegram:
            # 1. Кодек: h264 (libx264)
            # 2. Profile: main или baseline
            # 3. Level: 3.1 или ниже
            # 4. FPS: 30 или меньше
            # 5. Bitrate: низкий
            
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-t', str(duration),  # Обрезаем по времени
                '-vf', 'scale=trunc(min(iw\\,ih)/2)*2:trunc(min(iw\\,ih)/2)*2',  # Квадрат
                '-c:v', 'libx264',
                '-profile:v', 'baseline',  # ВАЖНО для совместимости
                '-level', '3.1',  # ВАЖНО
                '-preset', 'ultrafast',
                '-crf', '26',
                '-r', '24',  # 24 FPS (не 30)
                '-b:v', '400k',
                '-maxrate', '500k',
                '-bufsize', '1000k',
                '-c:a', 'aac',
                '-b:a', '96k',
                '-ar', '22050',  # 22kHz audio
                '-ac', '1',  # Mono
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',  # ВАЖНО
                '-y',
                output
            ]
            
            logger.info(f"FFmpeg video conversion")
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown"
                logger.error(f"FFmpeg error: {error}")
                return None
            
            size = os.path.getsize(output)
            logger.info(f"Video size: {size} bytes")
            
            if size > 10 * 1024 * 1024:
                logger.warning(f"Video too large, reducing quality")
                return await self._to_mp4_video_low(file_path, tmp_dir, duration)
            
            return output
        
        except FileNotFoundError:
            logger.error("FFmpeg not found")
            return None
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return None
        except Exception as e:
            logger.error(f"Video error: {e}", exc_info=True)
            return None

    async def _to_mp4_video_low(self, file_path, tmp_dir, duration=6):
        """Низкое качество для больших файлов"""
        try:
            output = os.path.join(tmp_dir, "final_low.mp4")
            
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-t', str(duration),
                '-vf', 'scale=trunc(min(iw\\,ih)/2)*2:trunc(min(iw\\,ih)/2)*2',
                '-c:v', 'libx264',
                '-profile:v', 'baseline',
                '-level', '3.1',
                '-preset', 'ultrafast',
                '-crf', '30',
                '-r', '20',
                '-b:v', '200k',
                '-c:a', 'aac',
                '-b:a', '64k',
                '-ar', '22050',
                '-ac', '1',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                '-y',
                output
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode != 0:
                logger.error("Low quality failed")
                return None
            
            return output
        except Exception as e:
            logger.error(f"Low quality error: {e}")
            return None
