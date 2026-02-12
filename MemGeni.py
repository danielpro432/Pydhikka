# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: URL Preview
# description: Shows URL title and description
# meta banner: https://i.imgur.com/yourbanner.png

import aiohttp
from bs4 import BeautifulSoup
from .. import loader, utils

@loader.tds
class URLPreview(loader.Module):
    strings = {"name": "URL Preview", "no_url": "❌ Provide a valid URL", "preview": "🌐 Preview:\nTitle: {}\nDescription: {}"}

    @loader.command()
    async def preview(self, message):
        url = utils.get_args_raw(message)
        if not url.startswith("http"):
            return await utils.answer(message, self.strings["no_url"])
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else "N/A"
        desc = soup.find("meta", {"name":"description"})
        desc = desc["content"] if desc else "N/A"
        await utils.answer(message, self.strings["preview"].format(title, desc))
