# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Lite AI Chat
# description: Simple local AI chat
# meta banner: https://i.imgur.com/yourbanner.png

from .. import loader, utils
import random

@loader.tds
class LiteAIChat(loader.Module):
    strings = {"name": "Lite AI Chat", "reply": ["Hello!", "How are you?", "Interesting...", "Tell me more!"]}

    @loader.command()
    async def litechat(self, message):
        text = utils.get_args_raw(message)
        if not text:
            return await utils.answer(message, "❌ Provide a message")
        response = random.choice(self.strings["reply"])
        await utils.answer(message, response)
