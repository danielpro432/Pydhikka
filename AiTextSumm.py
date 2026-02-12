# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: AI Text Summarizer
# description: Summarizes long messages into короткие
# meta banner: https://i.imgur.com/yourbanner.png

import asyncio
from .. import loader, utils

@loader.tds
class AISummarizer(loader.Module):
    strings = {"name": "AI Summarizer", "no_text": "❌ Reply or provide text to summarize.", "summary": "📝 Summary:\n\n{}"}

    @loader.command()
    async def summarize(self, message):
        """Usage: reply with .summarize or provide text"""
        text = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if reply and not text:
            text = reply.message
        if not text:
            return await utils.answer(message, self.strings["no_text"])

        await utils.answer(message, "🔄 Summarizing...")
        # Simple local summarization: take first 3 sentences
        summary = '. '.join(text.split('. ')[:3])
        await utils.answer(message, self.strings["summary"].format(summary))
