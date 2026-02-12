# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█
# 🔒 Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
# Name: AChange
# Description: Смена аватарки
# meta developer: @FAmods
# Попыток: 12 🤦
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
    """Смена аватарки"""

    strings = {
        "name": "AChange",
        "no_reply": "❌ Ответь на фото/видео/GIF/стикер",
        "changed": "✅ Готово! (Попыток: 12) 🤦",
        "error": "❌ Ошибка (Попыток: 12) 🤦",
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
        except:
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
                is_photo = r.photo is not None
                is_video = r.video is not None
                is_doc = r.document is not None
                
                if is_photo:
                    raw = os.path.join(tmp, "raw.jpg")
                    await message.client.download_media(r.photo, raw)
                    final = await self._to_jpeg(raw, tmp)
                    is_video_upload = False
                    
                elif is_video:
                    raw = os.path.join(tmp, "raw.mp4")
                    await message.client.download_media(r.video, raw)
                    final = await self._to_video_mp4(raw, tmp)
                    is_video_upload = True
                    
                elif is_doc:
                    raw = os.path.join(tmp, "raw.file")
                    await message.client.download_media(r.document, raw)
                    
                    doc = r.document
                    mime = getattr(doc, 'mime_type', '').lower()
                    fname = getattr(doc, 'file_name', '').lower()
                    
                    if 'gif' in mime or fname.endswith('.gif'):
                        final = await self._to_video_mp4(raw, tmp, is_gif=True)
                        is_video_upload = True
                    elif 'webp' in mime or fname.endswith('.webp'):
                        final = await self._to_video_mp4(raw, tmp)
                        is_video_upload = True
                    elif 'tgsticker' in mime or fname.endswith('.tgs'):
                        final = await self._to_video_mp4(raw, tmp)
                        is_video_upload = True
                    elif 'video' in mime or fname.endswith(('.mp4', '.webm')):
                        final = await self._to_video_mp4(raw, tmp)
                        is_video_upload = True
                    else:
                        final = await self._to_jpeg(raw, tmp)
                        is_video_upload = False
                else:
                    return await utils.answer(message, self.strings['error'])
                
                if not final or not os.path.exists(final):
                    return await utils.answer(message, self.strings['error'])
                
                uploaded = await self._client.upload_file(final)
                
                if is_video_upload:
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
            logger.error(f"Error: {e}")
            await utils.answer(message, self.strings['error'])

    async def _to_jpeg(self, file_path, tmp_dir):
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
        except:
            import shutil
            output = os.path.join(tmp_dir, "final.jpg")
            shutil.copy(file_path, output)
            return output

    async def _to_video_mp4(self, file_path, tmp_dir, is_gif=False):
        """Всё → MP4 видео"""
        try:
            output = os.path.join(tmp_dir, "final.mp4")
            
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-t', '10',
                '-vf', 'scale=trunc(min(iw\\,ih)/2)*2:trunc(min(iw\\,ih)/2)*2',
                '-c:v', 'libx264',
                '-profile:v', 'main',
                '-level', '3.1',
                '-preset', 'ultrafast',
                '-crf', '24',
                '-r', '30',
                '-b:v', '500k',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                '-y',
                output
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output):
                return output
            return None
        except:
            return None
