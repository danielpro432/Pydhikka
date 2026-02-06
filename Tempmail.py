# TempMail — FIXED 2026
# 1secmail anti-HTML / anti-CF

import aiohttp
import json
import logging

from .. import loader, utils

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

@loader.tds
class TempMail(loader.Module):
    """Временная почта (1secmail, fixed)"""

    strings = {
        "name": "TempMail",
        "created": "📧 <b>Email:</b>\n<code>{}</code>",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем нет</b>",
        "inbox": "📥 <b>Входящие:</b>\n{}",
        "read_usage": "❌ <code>.tread &lt;id&gt;</code>",
        "api_error": "⚠️ <b>Ошибка API (1secmail)</b>\nПопробуй позже",
    }

    async def client_ready(self, client, db):
        self.db = db

    async def _api(self, url):
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url) as resp:
                ct = resp.headers.get("Content-Type", "")
                text = await resp.text()

                if "application/json" in ct:
                    return json.loads(text)

                # fallback: HTML / Cloudflare / block
                logger.warning("1secmail returned non-JSON: %s", text[:200])
                raise ValueError("Non-JSON response")

    @loader.command()
    async def tempmail(self, message):
        """Создать временный email"""
        try:
            data = await self._api(
                "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
            )
            email = data[0]
            self.db.set(self.name, "email", email)
            await utils.answer(message, self.strings["created"].format(email))
        except Exception:
            await utils.answer(message, self.strings["api_error"])

    @loader.command()
    async def tinbox(self, message):
        """Входящие"""
        email = self.db.get(self.name, "email")
        if not email:
            return await utils.answer(message, self.strings["no_mail"])

        login, domain = email.split("@")

        try:
            msgs = await self._api(
                f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
            )
        except Exception:
            return await utils.answer(message, self.strings["api_error"])

        if not msgs:
            return await utils.answer(message, self.strings["empty"])

        text = ""
        for m in msgs:
            text += f"• <code>{m['id']}</code> | {m['from']} | {m['subject']}\n"

        await utils.answer(message, self.strings["inbox"].format(text))

    @loader.command()
    async def tread(self, message):
        """Прочитать письмо"""
        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["read_usage"])

        email = self.db.get(self.name, "email")
        if not email:
            return await utils.answer(message, self.strings["no_mail"])

        login, domain = email.split("@")
        mail_id = args[0]

        try:
            msg = await self._api(
                f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mail_id}"
            )
        except Exception:
            return await utils.answer(message, self.strings["api_error"])

        body = msg.get("textBody") or msg.get("htmlBody") or "(пусто)"

        await utils.answer(
            message,
            f"📩 <b>{msg.get('subject')}</b>\n\n{body}",
        )
