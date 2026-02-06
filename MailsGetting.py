# TempMail Multi-Provider (Hikka module)
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

logger = logging.getLogger(__name__)

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}

MAX_TRIES = 3
RAW_LOG_LEN = 800
DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac"]
MAX_HISTORY = 10  # сохранять только последние 10 адресов

# -------------------- Base provider --------------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS_BASE)

    async def create_address(self):
        raise NotImplementedError

    async def list_messages(self, *args, **kwargs):
        raise NotImplementedError

    async def read_message(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_message(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_account(self, *args, **kwargs):
        raise NotImplementedError

    async def close(self):
        try:
            await self.session.close()
        except: pass

    async def _get(self, url, timeout=15):
        last = None
        for attempt in range(1, MAX_TRIES + 1):
            try:
                async with self.session.get(url, timeout=timeout) as resp:
                    text = await resp.text(errors="ignore")
                    ct = resp.headers.get("Content-Type", "")
                    return resp.status, ct, text
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
                    ct = resp.headers.get("Content-Type", "")
                    return resp.status, ct, text
            except Exception as e:
                last = e
                await asyncio.sleep(0.5 * attempt)
        raise RuntimeError(f"POST failed: {last}")

# -------------------- Providers --------------------
# 1) mail.tm
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        status, ct, text = await self._get(f"{self.base}/domains")
        if status != 200:
            raise RuntimeError(f"mail.tm domains HTTP {status}")
        data = json.loads(text)
        if isinstance(data, dict) and "hydra:member" in data:
            domains = data["hydra:member"]
            domain = random.choice(domains)["domain"]
        elif isinstance(data, list):
            domain = random.choice(data)["domain"]
        else:
            raise RuntimeError("mail.tm domains parsing failed")

        login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        address = f"{login}@{domain}"
        password = "HikkaTempPass!" + "".join(random.choices(string.digits, k=4))

        stat, ct, t = await self._post(f"{self.base}/accounts", json_data={"address": address, "password": password})
        stat, ct, t = await self._post(f"{self.base}/token", json_data={"address": address, "password": password})
        if stat != 200:
            raise RuntimeError(f"mail.tm token HTTP {stat}")
        tok = json.loads(t).get("token")
        if not tok:
            raise RuntimeError("mail.tm token missing")
        return {"email": address, "provider": self.name, "token": tok, "password": password}

    async def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    async def list_messages(self, email, token):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.get(f"{self.base}/messages") as resp:
                t = await resp.text(errors="ignore")
                if resp.status != 200:
                    raise RuntimeError(f"mail.tm inbox HTTP {resp.status}")
                data = json.loads(t)
                return data.get("hydra:member", data)

    async def read_message(self, email, token, msg_id):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.get(f"{self.base}/messages/{msg_id}") as resp:
                t = await resp.text(errors="ignore")
                if resp.status != 200:
                    raise RuntimeError(f"mail.tm read HTTP {resp.status}")
                return json.loads(t)

    async def delete_account(self, email, token):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.delete(f"{self.base}/me") as resp:
                if resp.status in (200, 204):
                    return
        raise RuntimeError("mail.tm delete failed")

# 2) 1secmail
class OneSecMailProvider(BaseProvider):
    name = "1secmail"
    base = "https://www.1secmail.com/api/v1/"

    async def create_address(self):
        stat, ct, text = await self._get(self.base + "?action=genRandomMailbox&count=1")
        data = json.loads(text)
        return {"email": data[0], "provider": self.name}

    async def list_messages(self, email):
        login, domain = email.split("@")
        url = f"{self.base}?action=getMessages&login={login}&domain={domain}"
        stat, ct, text = await self._get(url)
        return json.loads(text)

    async def read_message(self, email, msg_id):
        login, domain = email.split("@")
        url = f"{self.base}?action=readMessage&login={login}&domain={domain}&id={msg_id}"
        stat, ct, text = await self._get(url)
        return json.loads(text)

# 3) getnada
class GetNadaProvider(BaseProvider):
    name = "getnada"
    base = "https://getnada.com/api/v1"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@getnada.com", "provider": self.name}

    async def list_messages(self, email):
        url = f"{self.base}/inboxes/{email}"
        stat, ct, text = await self._get(url)
        data = json.loads(text)
        return data.get("msgs", [])

    async def read_message(self, email, msg_id):
        url = f"{self.base}/messages/{msg_id}"
        stat, ct, text = await self._get(url)
        return json.loads(text)

    async def delete_message(self, email, msg_id):
        url = f"{self.base}/messages/{msg_id}"
        async with self.session.delete(url) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"getnada delete HTTP {resp.status}")

# 4) maildrop
class MaildropProvider(BaseProvider):
    name = "maildrop"
    base = "https://api.maildrop.cc/graphql"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@maildrop.cc", "provider": self.name}

    async def list_messages(self, email):
        mailbox = email.split("@")[0]
        query = {"query": f'query{{inbox(mailbox:\"{mailbox}\"){{id mailfrom subject}}}}'}
        stat, ct, text = await self._post(self.base, json_data=query)
        data = json.loads(text)
        return data.get("data", {}).get("inbox", [])

    async def read_message(self, email, msg_id):
        mailbox = email.split("@")[0]
        query = {"query": f'query{{message(mailbox:\"{mailbox}\",id:\"{msg_id}\"){{id headerfrom subject data html}}}}'}
        stat, ct, text = await self._post(self.base, json_data=query)
        data = json.loads(text)
        return data.get("data", {}).get("message", {})

# 5) mailsac
class MailsacProvider(BaseProvider):
    name = "mailsac"
    base = "https://mailsac.com/api"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@mailsac.com", "provider": self.name}

    async def list_messages(self, email):
        url = f"https://mailsac.com/api/addresses/{urllib.parse.quote(email)}/messages"
        stat, ct, text = await self._get(url)
        return json.loads(text)

    async def read_message(self, email, msg_id):
        url = f"https://mailsac.com/api/text/{urllib.parse.quote(email)}/{urllib.parse.quote(msg_id)}"
        stat, ct, text = await self._get(url)
        return {"body": text}

# -------------------- Hikka module --------------------
@loader.tds
class TempMailModule(loader.Module):
    """TempMail — multi-provider, history, read/delete, robust"""

    strings = {
        "name": "TempMail",
        "created": "📧 <b>Создан адрес</b>\n<code>{}</code>\n<b>Провайдер:</b> {}",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем пока нет</b>",
        "inbox": "📥 <b>Входящие ({})</b>:\n{}",
        "read_usage": "❌ <b>Используй:</b> <code>.tread &lt;id&gt; [email]</code>",
        "letter": "📩 <b>Письмо</b>\n\n<b>От:</b> <code>{}</code>\n<b>Тема:</b> <code>{}</code>\n\n{}",
        "api_error": "⚠️ <b>Ошибка API</b>\nПровайдер: {} \nПричина: {}",
        "trying": "⏳ Пробую провайдера: {}...",
        "provider_set": "✅ <b>Провайдер установлен:</b> {}",
        "info": "📌 <b>Активный Email:</b> <code>{}</code>\n<b>Провайдер:</b> {}",
        "unknown_provider": "❌ Неизвестный провайдер. Доступные: {}",
        "deleted": "🗑️ Почта удалена: {} (провайдер: {})",
        "mails_list": "📜 <b>Твои адреса:</b>\n{}",
        "set_active": "✅ Активный адрес: <code>{}</code>",
        "debug": "🔎 Debug провайдера: {}\n\n{}"
    }

    def __init__(self):
        self.name = "TempMail"
        self.providers = {
            "mailtm": MailTmProvider(),
            "1secmail": OneSecMailProvider(),
            "getnada": GetNadaProvider(),
            "maildrop": MaildropProvider(),
            "mailsac": MailsacProvider(),
        }
        self.provider_order = DEFAULT_PROVIDERS

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    # ------------- Storage helpers -------------
    def _addr_key(self, uid): return f"addrs_{uid}"
    def _active_key(self, uid): return f"addr_{uid}"
    def _prov_key(self, uid): return f"prov_{uid}"
    def _lastraw_key(self, uid): return f"lastraw_{uid}"

    def _get_history(self, uid): return self.db.get(self.name, self._addr_key(uid), [])
    def _save_history(self, uid, history): self.db.set(self.name, self._addr_key(uid), history)

    def _prov_by_name(self, name): return self.providers.get(name)
    def _get_user_provider_name(self, uid): return self.db.get(self.name, self._prov_key(uid), self.provider_order[0])

    # -------------------- Core logic --------------------
    def _add_record(self, uid, record):
        history = self._get_history(uid)
        history.insert(0, record)
        # keep only last MAX_HISTORY addresses
        if len(history) > MAX_HISTORY:
            history = history[:MAX_HISTORY]
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), record["email"])

    # ... Остальные команды такие же, как у тебя, включая tempmail, tinbox, tread, delmail, mymails, tprovider, usemail, tinfo, tdebug ...
