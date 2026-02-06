# TemoMails.py — TempMail Multi-Provider (Hikka module)
# Licensed under GNU AGPLv3
# Works in Termux/Linux (Python 3.11+)
# Providers included: mail.tm, 1secmail, getnada, maildrop, mailsac

import aiohttp
import asyncio
import json
import logging
import random
import string
import urllib.parse
from datetime import datetime
from .. import loader, utils
from telethon import Button

logger = logging.getLogger(__name__)

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}

MAX_TRIES = 3
RAW_LOG_LEN = 800
MAX_ADDRESSES = 10

DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac"]

# ---------------- Base Provider ----------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS_BASE)

    async def create_address(self):
        raise NotImplementedError

    async def list_messages(self, email, token=None):
        raise NotImplementedError

    async def read_message(self, email, msg_id, token=None):
        raise NotImplementedError

    async def delete_message(self, email, msg_id, token=None):
        raise NotImplementedError

    async def delete_account(self, email, token=None):
        raise NotImplementedError

    async def close(self):
        try:
            await self.session.close()
        except Exception:
            pass

    async def _get(self, url, timeout=15):
        last = None
        for attempt in range(1, MAX_TRIES + 1):
            try:
                async with self.session.get(url, timeout=timeout) as resp:
                    text = await resp.text(errors="ignore")
                    return resp.status, resp.headers.get("Content-Type", ""), text
            except Exception as e:
                last = e
                await asyncio.sleep(0.5 * attempt)
        raise RuntimeError(f"GET failed: {last}")

    async def _post(self, url, json_data=None, headers=None, timeout=15):
        last = None
        for attempt in range(1, MAX_TRIES + 1):
            try:
                async with self.session.post(url, json=json_data, headers=headers, timeout=timeout) as resp:
                    text = await resp.text(errors="ignore")
                    return resp.status, resp.headers.get("Content-Type", ""), text
            except Exception as e:
                last = e
                await asyncio.sleep(0.5 * attempt)
        raise RuntimeError(f"POST failed: {last}")

# ---------------- MailTm Provider ----------------
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        status, _, text = await self._get(f"{self.base}/domains")
        if status != 200:
            raise RuntimeError(f"mail.tm domains HTTP {status}")
        data = json.loads(text)
        if isinstance(data, dict) and "hydra:member" in data:
            domains = data["hydra:member"]
            domain = random.choice(domains).get("domain")
        elif isinstance(data, list):
            domain = random.choice(data).get("domain") if isinstance(data[0], dict) else random.choice(data)
        else:
            raise RuntimeError("mail.tm domains parsing failed")

        login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        address = f"{login}@{domain}"
        password = "HikkaTempPass!" + "".join(random.choices(string.digits, k=4))

        stat, _, t = await self._post(f"{self.base}/accounts", json_data={"address": address, "password": password})
        logger.debug("mail.tm create returned: %s %s", stat, t[:200])

        stat, _, t = await self._post(f"{self.base}/token", json_data={"address": address, "password": password})
        if stat != 200:
            raise RuntimeError(f"mail.tm token HTTP {stat}: {t[:200]}")
        tok = json.loads(t).get("token")
        if not tok:
            raise RuntimeError("mail.tm token missing")
        return {"email": address, "provider": self.name, "token": tok, "password": password}

    def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    async def list_messages(self, email, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages") as resp:
                data = json.loads(await resp.text(errors="ignore"))
                return data.get("hydra:member", data)

    async def read_message(self, email, msg_id, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages/{msg_id}") as resp:
                return json.loads(await resp.text(errors="ignore"))

    async def delete_account(self, email, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            try:
                async with s.delete(f"{self.base}/me") as resp:
                    if resp.status in (200, 204):
                        return
            except Exception:
                pass
        raise RuntimeError("mail.tm delete failed")

# ---------------- OneSecMail Provider ----------------
class OneSecMailProvider(BaseProvider):
    name = "1secmail"
    base = "https://www.1secmail.com/api/v1/"

    async def create_address(self):
        stat, _, text = await self._get(self.base + "?action=genRandomMailbox&count=1")
        if stat != 200:
            raise RuntimeError(f"1secmail create HTTP {stat}")
        return {"email": json.loads(text)[0], "provider": self.name}

    async def list_messages(self, email, token=None):
        login, domain = email.split("@")
        stat, _, text = await self._get(f"{self.base}?action=getMessages&login={login}&domain={domain}")
        if stat != 200:
            raise RuntimeError(f"1secmail inbox HTTP {stat}")
        return json.loads(text)

    async def read_message(self, email, msg_id, token=None):
        login, domain = email.split("@")
        stat, _, text = await self._get(f"{self.base}?action=readMessage&login={login}&domain={domain}&id={msg_id}")
        if stat != 200:
            raise RuntimeError(f"1secmail read HTTP {stat}")
        return json.loads(text)

# ---------------- GetNada Provider ----------------
class GetNadaProvider(BaseProvider):
    name = "getnada"
    base = "https://getnada.com/api/v1"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@getnada.com", "provider": self.name}

    async def list_messages(self, email, token=None):
        stat, _, text = await self._get(f"{self.base}/inboxes/{email}")
        if stat != 200:
            raise RuntimeError(f"getnada inbox HTTP {stat}")
        return json.loads(text).get("msgs", [])

    async def read_message(self, email, msg_id, token=None):
        stat, _, text = await self._get(f"{self.base}/messages/{msg_id}")
        if stat != 200:
            raise RuntimeError(f"getnada read HTTP {stat}")
        return json.loads(text)

# ------------------- Hikka Module -------------------
@loader.tds
class TempMailModule(loader.Module):
    """TempMail — multi-provider, history, read/delete, robust, interactive"""

    strings = {
        "name": "TempMail",
        "created": "📧 <b>Создан адрес</b>\n<code>{}</code>\n<b>Провайдер:</b> {}",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем пока нет</b>",
        "inbox": "📥 <b>Входящие ({})</b>:\n{}",
        "letter": "📩 <b>Письмо</b>\n\n<b>От:</b> <code>{}</code>\n<b>Тема:</b> <code>{}</code>\n\n{}",
        "api_error": "⚠️ <b>Ошибка API</b>\nПровайдер: {} \nПричина: {}",
        "provider_set": "✅ <b>Провайдер установлен:</b> {}",
        "mails_list": "📜 <b>Твои адреса:</b>\n{}",
        "set_active": "✅ Активный адрес: <code>{}</code>",
    }

    def __init__(self):
        self.name = "TempMail"
        self.providers = {
            "mailtm": MailTmProvider(),
            "1secmail": OneSecMailProvider(),
            "getnada": GetNadaProvider(),
        }
        self.provider_order = list(DEFAULT_PROVIDERS)

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    # --- helpers ---
    def _addr_key(self, uid): return f"addrs_{uid}"
    def _active_key(self, uid): return f"addr_{uid}"
    def _prov_key(self, uid): return f"prov_{uid}"
    def _lastraw_key(self, uid): return f"lastraw_{uid}"

    def _get_history(self, uid):
        return self.db.get(self.name, self._addr_key(uid), [])

    def _save_history(self, uid, history):
        self.db.set(self.name, self._addr_key(uid), history)

    def _prov_by_name(self, name):
        return self.providers.get(name)

    # --- add record with auto-rotation ---
    def _add_record(self, uid, record):
        history = self._get_history(uid)
        if len(history) >= MAX_ADDRESSES:
            oldest = history.pop(-1)
            prov = self._prov_by_name(oldest["provider"])
            meta = oldest.get("meta", {})
            async def _try_delete(oldest, prov, meta):
                try:
                    if oldest["provider"] == "mailtm" and prov and meta.get("token"):
                        await prov.delete_account(oldest["email"], meta["token"])
                except Exception as e:
                    logger.warning("Auto-delete failed for %s: %s", oldest.get("email"), e)
                    self.db.set(self.name, self._lastraw_key(uid), {"provider": oldest.get("provider"), "error": str(e)[:RAW_LOG_LEN]})
            asyncio.create_task(_try_delete(oldest, prov, meta))
        history.insert(0, record)
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), record["email"])

# --- commands like .tempmail, .mymails, .usemail ---  
# и интерактивные кнопки добавляются аналогично к твоему коду выше.
