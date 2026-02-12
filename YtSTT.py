# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: YouTube & Speech
# description: Search YouTube videos & convert voice messages to text
# meta banner: https://i.imgur.com/yourbanner.png

import asyncio
import logging
import yt_dlp
import os
import tempfile
from collections import defaultdict
from .. import loader, utils
from telethon.tl.types import MessageMediaDocument

# For speech recognition
import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

@loader.tds
class YouTubeSpeechModule(loader.Module):
    strings = {
        "name": "YT+Speech",
        "yt_result": "<b>🎬 YouTube Search Result:</b>\n\n{}",
        "yt_error": "❌ Could not find any video for your query.",
        "voice_error": "❌ Could not convert voice to text.",
        "voice_text": "<b>🗣 Voice message recognized:</b>\n\n{}",
    }

    def __init__(self):
        self._cache = defaultdict(list)

    @loader.command(
        ru_doc="Искать видео на YouTube по запросу",
        en_doc="Search YouTube videos by query"
    )
    async def yt(self, message):
        """Usage: .yt <query>"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "❌ Please provide a search query.")
        
        await utils.answer(message, "<b>🔎 Searching YouTube...</b>")
        try:
            ydl_opts = {
                "format": "best",
                "noplaylist": True,
                "quiet": True,
                "skip_download": True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{args}", download=False)
                videos = info.get("entries", [])
                if not videos:
                    return await utils.answer(message, self.strings["yt_error"])
                
                results = ""
                for v in videos:
                    title = v.get("title")
                    url = v.get("webpage_url")
                    duration = v.get("duration")
                    minutes, seconds = divmod(duration, 60) if duration else (0,0)
                    results += f"• <b>{title}</b> ({minutes}:{seconds:02d})\n{url}\n\n"
                
                await utils.answer(message, self.strings["yt_result"].format(results.strip()))
        except Exception as e:
            logger.error(f"YT search error: {e}")
            await utils.answer(message, self.strings["yt_error"])

    @loader.command(
        ru_doc="Конвертировать голосовое сообщение в текст",
        en_doc="Convert voice message to text"
    )
    async def v2t(self, message):
        """Usage: reply to a voice message with .v2t"""
        reply = await message.get_reply_message()
        if not reply or not getattr(reply.media, "document", None):
            return await utils.answer(message, "❌ Reply to a voice message.")
        
        await utils.answer(message, "<b>🎤 Recognizing voice...</b>")

        try:
            file_path = await self.client.download_media(reply, file=bytes)
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name

            # Convert to WAV if needed
            audio = AudioSegment.from_file(file_path)
            audio.export(tmp_wav, format="wav")

            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_wav) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)

            os.remove(tmp_wav)
            await utils.answer(message, self.strings["voice_text"].format(text))
        except Exception as e:
            logger.error(f"Voice recognition error: {e}")
            await utils.answer(message, self.strings["voice_error"])
