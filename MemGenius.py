# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Quick Poll
# description: Create quick poll
# meta banner: https://i.imgur.com/yourbanner.png

from .. import loader, utils

@loader.tds
class QuickPoll(loader.Module):
    strings = {"name": "Quick Poll", "usage": "Usage: .poll Question | option1 | option2 | ...", "poll_created": "✅ Poll created!"}

    @loader.command()
    async def poll(self, message):
        args = utils.get_args_raw(message)
        if "|" not in args:
            return await utils.answer(message, self.strings["usage"])
        question, *options = [x.strip() for x in args.split("|")]
        await message.client.send_message(message.chat_id, question, buttons=[[opt] for opt in options])
        await utils.answer(message, self.strings["poll_created"])
