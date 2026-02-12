# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки с сохранением оригиналов (фото, видео, GIF)
# meta developer: @FAmods
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
    """Смена аватарки с сохранением оригиналов (фото, видео, GIF)"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Нужно ответить на фото, видео или GIF (JPEG/PNG/MP4/GIF)",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
        "processing": "⏳ Обработка видео...",
        "video_error": "❌ Видео не подходит. Telegram требует: MP4, 10сек макс, вертикальное",
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
        """Ответом на фото/видео/GIF меняет аватарку, заменяя предыдущие добавленные скриптом"""
        r = await message.get_reply_message()
        
        # Проверяем наличие фото, видео или GIF
        if not r:
            return await utils.answer(message, self.strings['no_reply'])
        
        has_photo = r.photo
        has_video = r.video
        has_gif = r.document and self._is_gif(r.document)
        
        if not (has_photo or has_video or has_gif):
            return await utils.answer(message, self.strings['no_reply'])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                if has_photo:
                    # Загружаем фото
                    file_path = os.path.join(tmp, "avatar.jpg")
                    await message.client.download_media(r.photo, file_path)
                    uploaded_file = await self._client.upload_file(file_path)
                    new_photo = await self._client(UploadProfilePhotoRequest(file=uploaded_file))
                    
                elif has_video:
                    # Показываем статус обработки
                    await utils.answer(message, self.strings['processing'])
                    
                    # Загружаем видео
                    file_path = os.path.join(tmp, "avatar.mp4")
                    await message.client.download_media(r.video, file_path)
                    
                    # Проверяем и обрезаем видео до 6 секунд
                    output_path = os.path.join(tmp, "avatar_trimmed.mp4")
                    if not self._trim_video(file_path, output_path, duration=6):
                        return await utils.answer(message, self.strings['video_error'])
                    
                    # Загружаем обработанное видео
                    uploaded_file = await self._client.upload_file(output_path)
                    new_photo = await self._client(UploadProfilePhotoRequest(video=uploaded_file))
                    
                elif has_gif:
                    # Загружаем GIF
                    file_path = os.path.join(tmp, "avatar.gif")
                    await message.client.download_media(r.document, file_path)
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

    def _is_gif(self, document):
        """Проверяет, является ли документ GIF"""
        if not document:
            return False
        mime_type = getattr(document, 'mime_type', '')
        return mime_type == 'image/gif' or (hasattr(document, 'file_name') and document.file_name.lower().endswith('.gif'))

    def _trim_video(self, input_path, output_path, duration=6):
        """Обрезает видео до указанной длительности используя ffmpeg"""
        try:
            # Простая и быстрая команда ffmpeg - копируем видео без переквадрирования
            command = [
                'ffmpeg',
                '-i', input_path,
                '-t', str(duration),  # Обрезаем только по времени
                '-c:v', 'copy',  # КОПИРУЕМ видео без перекодирования (быстро!)
                '-c:a', 'copy',  # КОПИРУЕМ аудио без перекодирования
                '-y',  # Перезаписать выходной файл
                output_path
            ]
            
            logger.info(f"Starting FFmpeg trim: {' '.join(command)}")
            
            # Выполняем команду
            result = subprocess.run(command, capture_output=True, timeout=30)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                logger.error(f"FFmpeg error: {error_msg}")
                return False
            
            # Проверяем размер файла (<10MB)
            file_size = os.path.getsize(output_path)
            if file_size > 10 * 1024 * 1024:
                logger.warning(f"Video large: {file_size} bytes, re-encoding...")
                
                # Если файл слишком большой, пересчитываем с меньшим bitrate
                if not self._re_encode_video(output_path, duration):
                    return False
            
            logger.info(f"Video trimmed successfully: {os.path.getsize(output_path)} bytes")
            return True
            
        except FileNotFoundError:
            logger.error("FFmpeg not found")
            return False
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout during trim")
            return False
        except Exception as e:
            logger.error(f"Video trimming error: {e}")
            return False

    def _re_encode_video(self, video_path, duration=6):
        """Пересчитывает видео если оно слишком большое"""
        try:
            temp_path = video_path + ".temp.mp4"
            
            # Пересчитываем с меньшим качеством
            command = [
                'ffmpeg',
                '-i', video_path,
                '-t', str(duration),
                '-vf', 'scale=min(iw\\,720):min(ih\\,720):force_original_aspect_ratio=decrease',  # Масштабируем если нужно
                '-c:v', 'libx264',
                '-preset', 'faster',
                '-crf', '23',
                '-b:v', '800k',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                temp_path
            ]
            
            result = subprocess.run(command, capture_output=True, timeout=60)
            
            if result.returncode != 0:
                logger.error(f"Re-encode error: {result.stderr.decode()}")
                return False
            
            # Заменяем оригинальный файл
            os.replace(temp_path, video_path)
            
            file_size = os.path.getsize(video_path)
            logger.info(f"Video re-encoded: {file_size} bytes")
            return True
            
        except Exception as e:
            logger.error(f"Re-encode error: {e}")
            return False
