# -*- coding: utf-8 -*-
# name: WhisperLocal
# description: High quality local STT using Faster-Whisper

import os
import tempfile
from .. import loader, utils
from faster_whisper import WhisperModel

@loader.tds
class WhisperLocal(loader.Module):
    strings = {"name": "WhisperLocal"}

    async def client_ready(self, client, db):
        self.client = client
        
        # tiny = быстро
        # base = лучше
        # small = ещё лучше (но тяжелее)
        self.model = WhisperModel("base", compute_type="int8")

    @loader.command()
    async def stt(self, message):
        """Reply to voice message with .stt"""
        reply = await message.get_reply_message()
        if not reply or not reply.voice:
            return await utils.answer(message, "Ответь на голосовое.")

        await utils.answer(message, "🎤 Распознаю...")

        try:
            file_path = await self.client.download_media(reply)

            segments, info = self.model.transcribe(
                file_path,
                beam_size=5,
                language="ru"  # можно убрать для автоопределения
            )

            text = ""
            for segment in segments:
                text += segment.text

            os.remove(file_path)

            await utils.answer(
                message,
                f"<b>📝 Текст:</b>\n\n{text.strip()}"
            )

        except Exception as e:
            await utils.answer(message, f"Ошибка: {e}")
