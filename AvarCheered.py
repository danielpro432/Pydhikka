from .. import loader, utils
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
import tempfile
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

MAX_DURATION = 7


@loader.tds
class AvCh(loader.Module):
    """Фото / GIF / Видео → авто 7 сек"""

    strings = {
        "name": "AvCh",
        "no_reply": "❌ Ответь на фото, GIF или видео",
        "changed": "✅ Аватарка обновлена!",
        "error": "❌ Ошибка при смене аватарки",
    }

    async def client_ready(self, client, db):
        self._client = client
        self.added = []

    @loader.command()
    async def AvCh(self, message):
        reply = await message.get_reply_message()

        if not reply or not reply.media:
            return await utils.answer(message, self.strings["no_reply"])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                input_path = os.path.join(tmp, "input")
                output_path = os.path.join(tmp, "output.mp4")

                await message.client.download_media(reply.media, input_path)

                if reply.photo:
                    uploaded = await self._client.upload_file(input_path)
                    result = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )
                else:
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-i", input_path,
                        "-t", str(MAX_DURATION),
                        "-vf", "crop='min(iw,ih)':'min(iw,ih)'",
                        "-an",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-pix_fmt", "yuv420p",
                        output_path
                    ]

                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    uploaded = await self._client.upload_file(output_path)
                    result = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )

                self.added.append(result.photo)
                if len(self.added) > 1:
                    await self._client(DeletePhotosRequest(self.added[:-1]))
                    self.added = self.added[-1:]

                await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(f"AvCh error: {e}")
            await utils.answer(message, self.strings["error"])
