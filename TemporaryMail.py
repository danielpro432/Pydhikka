# TempMail (multi-provider, robust v2) for Hikka — improved debug & retries
# Licensed under GNU AGPLv3

import aiohttp
import asyncio
import logging
import random
import string
import json
import urllib.parse
from .. import loader, utils

logger = logging.getLogger(__name__)

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Referer": "https://google.com/",
}

PROVIDERS = ["1secmail", "getnada"]
MAX_TRIES = 3
RAW_LOG_LEN = 600  # characters to keep of raw response for debug

@loader.tds
class TempMail(loader.Module):
    """TempMail — multi-provider, robust with debug and retries"""

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
        "debug": "🔎 Debug (provider: {})\nStatus: {}\nContent-Type: {}\nRaw ({}):\n<pre>{}</pre>",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    # low-level get with retries and headers
    async def _http_get(self, url, extra_headers=None, timeout=15):
        headers = HEADERS_BASE.copy()
        if extra_headers:
            headers.update(extra_headers)
        last_exc = None
        for attempt in range(1, MAX_TRIES + 1):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=timeout) as resp:
                        text = await resp.text(errors="ignore")
                        ct = resp.headers.get("Content-Type", "")
                        return resp.status, ct, text
            except Exception as e:
                last_exc = e
                await asyncio.sleep(0.8 * attempt)
                continue
        raise RuntimeError(f"HTTP failed after {MAX_TRIES} tries: {last_exc}")

    # ---------- 1secmail helpers (robust variants) ----------
    async def _create_1secmail(self):
        url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        status, ct, text = await self._http_get(url)
        logger.debug("1secmail create: %s %s", status, text[:200])
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        # try parse JSON-like response or fallback to csv
        try:
            data = json.loads(text)
            return {"email": data[0], "provider": "1secmail"}
        except Exception:
            # maybe returns plain string or HTML -> fail
            raise RuntimeError("1secmail: Non-JSON or unexpected response")

    async def _inbox_1secmail(self, email):
        # try several url variants (full email, urlencoded, login+domain via split)
        login, domain = email.split("@")
        variants = [
            f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}",
            f"https://www.1secmail.com/api/v1/?action=getMessages&login={urllib.parse.quote(login)}&domain={urllib.parse.quote(domain)}",
            f"https://1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        ]
        last = None
        for u in variants:
            try:
                status, ct, text = await self._http_get(u)
                logger.debug("1secmail inbox try %s -> %s %s", u, status, text[:200])
                if status != 200:
                    last = f"HTTP {status}"
                    continue
                if "application/json" in ct or text.strip().startswith("["):
                    return json.loads(text)
                last = f"Non-JSON ({ct})"
            except Exception as e:
                last = str(e)
                continue
        raise RuntimeError(f"1secmail inbox failed: {last}")

    async def _read_1secmail(self, email, mid):
        login, domain = email.split("@")
        variants = [
            f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}",
            f"https://1secmail.com/api/v1/?action=readMessage&login={urllib.parse.quote(login)}&domain={urllib.parse.quote(domain)}&id={mid}"
        ]
        last = None
        for u in variants:
            try:
                status, ct, text = await self._http_get(u)
                logger.debug("1secmail read try %s -> %s %s", u, status, text[:200])
                if status != 200:
                    last = f"HTTP {status}"
                    continue
                if "application/json" in ct or text.strip().startswith("{"):
                    return json.loads(text)
                last = f"Non-JSON ({ct})"
            except Exception as e:
                last = str(e)
                continue
        raise RuntimeError(f"1secmail read failed: {last}")

    # ---------- getnada helpers ----------
    async def _create_getnada(self):
        # pick random prefix and default domain if domains list fails
        try:
            dom_status, dom_ct, dom_text = await self._http_get("https://getnada.com/api/v1/domains")
            if dom_status != 200:
                raise RuntimeError(f"HTTP {dom_status}")
            domains = json.loads(dom_text)
            if not domains:
                raise RuntimeError("No domains from getnada")
            domain = random.choice(domains)
        except Exception as e:
            logger.debug("getnada domains failed: %s", e)
            domain = "getnada.com"

        prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{prefix}@{domain}"
        return {"email": email, "provider": "getnada"}

    async def _inbox_getnada(self, email):
        # getnada expects the inbox parameter as full email (prefix@domain)
        variants = [
            f"https://getnada.com/api/v1/inboxes/{urllib.parse.quote(email)}",
            f"https://getnada.com/api/v1/inboxes/{email}",
        ]
        last = None
        for u in variants:
            try:
                status, ct, text = await self._http_get(u)
                logger.debug("getnada inbox try %s -> %s %s", u, status, text[:200])
                if status != 200:
                    last = f"HTTP {status}"
                    continue
                data = json.loads(text)
                return data.get("msgs", [])
            except Exception as e:
                last = str(e)
                continue
        raise RuntimeError(f"getnada inbox failed: {last}")

    async def _read_getnada(self, email, mid):
        variants = [
            f"https://getnada.com/api/v1/messages/{urllib.parse.quote(mid)}",
            f"https://getnada.com/api/v1/messages/{mid}"
        ]
        last = None
        for u in variants:
            try:
                status, ct, text = await self._http_get(u)
                logger.debug("getnada read try %s -> %s %s", u, status, text[:200])
                if status != 200:
                    last = f"HTTP {status}"
                    continue
                return json.loads(text)
            except Exception as e:
                last = str(e)
                continue
        raise RuntimeError(f"getnada read failed: {last}")

    # orchestration
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
                logger.warning("Provider %s failed during create: %s", p, e)
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

    # commands
    @loader.command()
    async def tempmail(self, message):
        """Создать новый временный email. Можно: .tempmail <provider>"""
        args = utils.get_args_raw(message).split()
        preferred = args[0].lower() if args else None
        if preferred and preferred not in PROVIDERS:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(PROVIDERS)))

        await utils.answer(message, self.strings["trying"].format(preferred or PROVIDERS[0]))
        try:
            info = await self._try_create(preferred)
            email = info["email"]
            provider = info["provider"]
            self.db.set(self.name, "email", email)
            self.db.set(self.name, "provider", provider)
            # store last raw responses placeholder
            self.db.set(self.name, "last_raw", {})
            await utils.answer(message, self.strings["created"].format(email, provider))
        except Exception as e:
            logger.exception("Create email failed")
            await utils.answer(message, self.strings["api_error"].format(preferred or "all", str(e)))

    @loader.command()
    async def tprovider(self, message):
        """Принудительно выбрать провайдера: .tprovider getnada|1secmail"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, "Используй: .tprovider <provider>")
        p = args[0].lower()
        if p not in PROVIDERS:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(PROVIDERS)))
        self.db.set(self.name, "provider", p)
        await utils.answer(message, self.strings["provider_set"].format(p))

    @loader.command()
    async def tinbox(self, message):
        """Показать входящие"""
        email = self.db.get(self.name, "email")
        provider = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, self.strings["no_mail"])

        tried = []
        last_err = None
        providers = [provider] + [p for p in PROVIDERS if p != provider]
        for p in providers:
            try:
                msgs = await self._try_inbox(email, p)
                # normalize output
                text = ""
                if p == "1secmail":
                    if not msgs:
                        return await utils.answer(message, self.strings["empty"])
                    for m in msgs:
                        text += f"• <code>{m['id']}</code> | {m.get('from','?')} | {m.get('subject','(no subject)')}\n"
                else:  # getnada
                    if not msgs:
                        return await utils.answer(message, self.strings["empty"])
                    for m in msgs:
                        mid = m.get("uid") or m.get("id")
                        frm = m.get("f") or m.get("from") or "?"
                        subj = m.get("s") or m.get("subject") or "(no subject)"
                        text += f"• <code>{mid}</code> | {frm} | {subj}\n"
                await utils.answer(message, self.strings["inbox"].format(p, text))
                return
            except Exception as e:
                logger.warning("Inbox with %s failed: %s", p, e)
                # store raw error snippet for debug
                self.db.set(self.name, "last_raw", { "last_provider": p, "error": str(e)[:RAW_LOG_LEN] })
                last_err = (p, str(e))
                tried.append(p)
                continue

        await utils.answer(message, self.strings["api_error"].format(",".join(tried), str(last_err)))

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

        providers = [provider] + [p for p in PROVIDERS if p != provider]
        for p in providers:
            try:
                msg = await self._try_read(email, p, mid)
                if p == "1secmail":
                    body = msg.get("textBody") or msg.get("body") or msg.get("htmlBody") or "(пусто)"
                    frm = msg.get("from", "?")
                    subj = msg.get("subject", "(no subject)")
                else:
                    body = msg.get("text") or msg.get("html") or msg.get("body") or "(пусто)"
                    frm = msg.get("from")
                    subj = msg.get("subject") or msg.get("s") or "(no subject)"
                await utils.answer(message, self.strings["letter"].format(frm, subj, body))
                return
            except Exception as e:
                logger.warning("Read with %s failed: %s", p, e)
                self.db.set(self.name, "last_raw", { "last_provider": p, "error": str(e)[:RAW_LOG_LEN] })
                continue

        await utils.answer(message, self.strings["api_error"].format(",".join(providers), "All providers failed to read message"))

    @loader.command()
    async def tinfo(self, message):
        """Показать текущий email и provider"""
        email = self.db.get(self.name, "email")
        prov = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, "Почта не создана. Используй .tempmail")
        await utils.answer(message, self.strings["info"].format(email, prov))

    @loader.command()
    async def tdebug(self, message):
        """Тест провайдера и показать сырые данные (debug)"""
        email = self.db.get(self.name, "email")
        prov = self.db.get(self.name, "provider", PROVIDERS[0])
        if not email:
            return await utils.answer(message, "Почта не создана. Используй .tempmail")

        # Try inbox and read small sample; return status and first chars saved in db
        last = self.db.get(self.name, "last_raw", {})
        await utils.answer(message, "Запрашиваю debug... подожди секунд 1-2")
        try:
            # just call inbox to provoke response
            await self._try_inbox(email, prov)
            await utils.answer(message, "✅ Провайдер ответил нормально (inbox).")
        except Exception as e:
            raw = last.get("error", str(e))[:RAW_LOG_LEN]
            ct = "unknown"
            status = "failed"
            await utils.answer(message, self.strings["debug"].format(prov, status, ct, len(raw), raw))
