# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Meme Generator
# description: Create memes from text
# meta banner: https://i.imgur.com/yourbanner.png

import io
from PIL import Image, ImageDraw, ImageFont
from .. import loader, utils

@loader.tds
class MemeGenerator(loader.Module):
    strings = {"name": "Meme Generator", "usage": "Usage: .meme top_text | bottom_text"}

    @loader.command()
    async def meme(self, message):
        args = utils.get_args_raw(message)
        if "|" not in args:
            return await utils.answer(message, self.strings["usage"])
        top, bottom = [x.strip() for x in args.split("|", 1)]
        img = Image.new("RGB", (500, 500), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 10), top, font=font, fill="black")
        draw.text((10, 460), bottom, font=font, fill="black")
        with io.BytesIO() as bio:
            img.save(bio, "PNG")
            bio.seek(0)
            await message.client.send_file(message.chat_id, bio, reply_to=message)
