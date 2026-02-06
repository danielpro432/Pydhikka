#   █▀▀ ▀█▀ █▀▀ █▀▄▀█ ▄▀█ █ █░░
#   █▀░ ░█░ ██▄ █░▀░█ █▀█ █ █▄▄

#   TempMail module for Hikka
#   Temporary email via 1secmail API

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

import aiohttp
import asyncio
import logging

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class TempMail(loader.Module):
    """Временная почта (1secmail)"""

    strings = {
        "name": "TempMail",

        "created": "📧 <b>Временный email создан:</b>\n<code>{}</code>",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем пока нет</b>",
        "inbox": "📥 <b>Входящие:</b>\n{}",
        "read_usage": "❌ <b>Используй:</b> <code>.tread &lt;id&gt;</code>",
        "letter": (
            "📩 <b>Письмо</b>\n\n"
            "<b>От:</b> <code>{}</code>\n"
            "<b>Тема:</b> <code>{}</code>\n\n{}"
        ),
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    async def _api(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()

    @loader.command()
    async def tempmail(self, message):
        """Создать временный email"""

        data = await self._api(
            "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        )
        email = data[0]

        self.db.set(self.name, "email", email)

        await utils.answer(message, self.strings["created"].format(email))

    @loader.command()
    async def tinbox(self, message):
        """Показать входящие письма"""

        email = self.db.get(self.name, "email")
        if not email:
            return await utils.answer(message, self.strings["no_mail"])

        login, domain = email.split("@")
        msgs = await self._api(
            f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        )

        if not msgs:
            return await utils.answer(message, self.strings["empty"])

        text = ""
        for m in msgs:
            text += f"• <code>{m['id']}</code> | {m['from']} | {m['subject']}\n"

        await utils.answer(message, self.strings["inbox"].format(text))

    @loader.command()
    async def tread(self, message):
        """Прочитать письмо по ID"""

        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["read_usage"])

        email = self.db.get(self.name, "email")
        if not email:
            return await utils.answer(message, self.strings["no_mail"])

        login, domain = email.split("@")
        mail_id = args[0]

        msg = await self._api(
            f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mail_id}"
        )

        body = msg.get("textBody") or msg.get("htmlBody") or "(пусто)"

        await utils.answer(
            message,
            self.strings["letter"].format(
                msg.get("from"), msg.get("subject"), body
            ),
      )
