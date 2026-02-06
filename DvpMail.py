# meta developer: @you
# meta name: TempMail
# meta desc: Временная почта (1secmail, GetNada) для Hikka
# meta version: 1.2

import aiohttp
import asyncio
import logging
import random
import string
import json

from .. import loader, utils

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

PROVIDERS = ["1secmail", "getnada"]

@loader.tds
class TempMail(loader.Module):
    """Временная почта — исправленный модуль с fallback (1secmail, GetNada)"""

    strings = {
        "name": "TempMail",
        "created": "📧 <b>Создан email</b>\n<code>{}</code>\n<b>Провайдер:</b> {}",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Входящие пусты</b>",
        "inbox": "📥 <b>Входящие ({})</b>:\n{}",
        "read_usage": "❌ <b>Используй:</b> <code>.tread &lt;id&gt;</code>",
        "letter": "📩 <b>Письмо</b>\n\n<b>От:</b> <code>{}</code>\n<b>Тема:</b> <code>{}</code>\n\n{}",
        "api_error": "⚠️ <b>Ошибка API (provider: {})</b>\nПричина: {}",
        "trying": "⏳ Пробую провайдера: {}...",
        "provider_set": "✅ <b>Провайдер установлен:</b> {}",
        "info": "📌 <b>Email:</b> <code>{}</code>\n<b>Provider:</b> {}",
        "unknown_provider": "❌ <b>Неизвестный провайдер.</b> Доступные: {}",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    async def _http_get(self, url, headers=None, timeout=15):
        headers = headers or HEADERS
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=timeout) as resp:
                text = await resp.text()
                ct = resp.headers.get("Content-Type", "")
                return resp.status, ct, text

    # ---------- 1secmail ----------
    async def _create_1secmail(self):
        url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        status, ct, text = await self._http_get(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        data = json.loads(text)
        return {"email": data[0], "provider": "1secmail"}

    async def _inbox_1secmail(self, email):
        login, domain = email.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        status, ct, text = await self._http_get(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        msgs = json.loads(text)
        return msgs if msgs else []

    async def _read_1secmail(self, email, mid):
        login, domain = email.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}"
        status, ct, text = await self._http_get(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return json.loads(text)

    # ---------- GetNada ----------
    async def _create_getnada(self):
        try:
            status, ct, text = await self._http_get("https://getnada.com/api/v1/domains")
            domains = json.loads(text)
            domain = random.choice(domains) if domains else "getnada.com"
        except:
            domain = "getnada.com"
        prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        return {"email": f"{prefix}@{domain}", "provider": "getnada"}

    async def _inbox_getnada(self, email):
        url = f"https://getnada.com/api/v1/inboxes/{email}"
        status, ct, text = await self._http_get(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        data = json.loads(text)
        return data.get("messages", [])

    async def _read_getnada(self, email, mid):
        url = f"https://getnada.com/api/v1/messages/{mid}"
        status, ct, text = await self._http_get(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return json.loads(text)

    # ---------- orchestration ----------
    async def _try_create(self, preferred=None):
        providers = PROVIDERS[:] if preferred is None else [preferred] + [p for p in PROVIDERS if p != preferred]
        last_err = None
        for p in providers:
            try:
                if p == "1secmail":
                    return await self._create_1secmail()
                if p == "getnada":
                    return await self._create_getnada()
            except Exception as e:
                last_err = (p, str(e))
                continue
        raise RuntimeError(f"All providers failed: {last_err}")

    async def _try_inbox(self, email, provider):
        if provider == "1secmail":
            return await self._inbox_1secmail(email)
        if provider == "getnada":
            return await self._inbox_getnada(email)
        raise RuntimeError("Unknown provider")

    async def _try_read(self, email, provider, mid):
        if provider == "1secmail":
            return await self._read_1secmail(email, mid)
        if provider == "getnada":
            return await self._read_getnada(email, mid)
        raise RuntimeError("Unknown provider")

    # ---------- commands ----------
    @loader.command()
    async def tempmail(self, message):
        """Создать новый временный email (.tempmail <provider>)"""
        args = utils.get_args_raw(message).split()
        preferred = args[0].lower() if args else None
        if preferred and preferred not in PROVIDERS:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(PROVIDERS)))
        await utils.answer(message, self.strings["trying"].format(preferred or PROVIDERS[0]))
        try:
            info = await self._try_create(preferred)
            email, provider = info["email"], info["provider"]
            self.db.set(self.name, "email", email)
            self.db.set(self.name, "provider", provider)
            await utils.answer(message, self.strings["created"].format(email, provider))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(preferred or "all", str(e)))

    @loader.command()
    async def tinbox(self, message):
        """Показать входящие"""
        email = self.db.get(self.name, "email")
        provider = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, self.strings["no_mail"])
        try:
            msgs = await self._try_inbox(email, provider)
            if not msgs:
                return await utils.answer(message, self.strings["empty"])
            text = ""
            for m in msgs:
                if provider == "1secmail":
                    text += f"• <code>{m['id']}</code> | {m.get('from','?')} | {m.get('subject','(no subject)')}\n"
                else:
                    mid = m.get("uid") or m.get("id")
                    frm = m.get("f") or m.get("from") or "?"
                    subj = m.get("s") or m.get("subject") or "(no subject)"
                    text += f"• <code>{mid}</code> | {frm} | {subj}\n"
            await utils.answer(message, self.strings["inbox"].format(provider, text))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(provider, str(e)))

    @loader.command()
    async def tread(self, message):
        """Прочитать письмо: .tread <id>"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["read_usage"])
        mid = args[0]
        email = self.db.get(self.name, "email")
        provider = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, self.strings["no_mail"])
        try:
            msg = await self._try_read(email, provider, mid)
            if provider == "1secmail":
                body = msg.get("textBody") or msg.get("body") or msg.get("htmlBody") or "(пусто)"
                frm = msg.get("from", "?")
                subj = msg.get("subject", "(no subject)")
            else:
                body = msg.get("text") or msg.get("html") or msg.get("body") or "(пусто)"
                frm = msg.get("from")
                subj = msg.get("subject") or msg.get("s") or "(no subject)"
            await utils.answer(message, self.strings["letter"].format(frm, subj, body))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(provider, str(e)))

    @loader.command()
    async def tinfo(self, message):
        """Показать текущий email и provider"""
        email = self.db.get(self.name, "email")
        provider = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, "Почта не создана. Используй .tempmail")
        await utils.answer(message, self.strings["info"].format(email, provider))
