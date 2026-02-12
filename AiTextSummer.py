# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Semantic Summarizer
# description: Summarizes text using semantic understanding (BERT)
# meta banner: https://i.imgur.com/yourbanner.png

import asyncio
from .. import loader, utils

from transformers import pipeline

@loader.tds
class SemanticSummarizer(loader.Module):
    strings = {
        "name": "Semantic Summarizer",
        "no_text": "❌ Reply or provide text to summarize.",
        "summary": "📝 Summary:\n\n{}",
        "loading": "🔄 Loading semantic model, please wait..."
    }

    def __init__(self):
        super().__init__()
        self.summarizer = None

    async def client_ready(self, client, db):
        self._client = client
        self.summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

    @loader.command()
    async def summarize(self, message):
        """Usage: reply with .summarize or provide text"""
        text = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if reply and not text:
            text = reply.message
        if not text:
            return await utils.answer(message, self.strings["no_text"])

        await utils.answer(message, self.strings["loading"])

        try:
            summary = self.summarizer(text, max_length=150, min_length=40, do_sample=False)[0]['summary_text']
            await utils.answer(message, self.strings["summary"].format(summary))
        except Exception as e:
            await utils.answer(message, f"❌ Error during summarization:\n{e}")
