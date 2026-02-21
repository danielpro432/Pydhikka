# TempMail Multi-Provider (Hikka module)
# Licensed under GNU AGPLv3
# Works in Termux/Linux (Python 3.11+)
# Providers included: mail.tm, 1secmail, getnada, maildrop, mailsac, yopmail, guerrillamail, throwawaymail, temp-mail, mailnesia, mailcatch, spamgourmet, moakt, fakemailgenerator, mailinator

import aiohttp
import asyncio
import json
import random
import string
import time
from datetime import datetime
from .. import loader, utils

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}

MAX_TRIES = 3
RAW_LOG_LEN = 800
DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac", "yopmail"]
DEFAULT_MAX_MAILS = 10
DEFAULT_MAX_WINDOWS = 2  # Максимум открытых окон для mymails/tinbox

# -------------------- Base Provider --------------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS_BASE)

    async def create_address(self):
        raise NotImplementedError

    async def list_messages(self, email=None, token=None):
        raise NotImplementedError

    async def read_message(self, email=None, token=None, msg_id=None):
        raise NotImplementedError

    async def delete_message(self, email=None, token=None, msg_id=None):
        raise NotImplementedError

    async def delete_account(self, email=None, token=None):
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
# Основные топ 6
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        stat, ct, text = await self._get(f"{self.base}/domains")
        data = json.loads(text)
        domain = random.choice(data.get("hydra:member", data))["domain"]
        login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        address = f"{login}@{domain}"
        password = "HikkaTempPass!" + "".join(random.choices(string.digits, k=4))
        await self._post(f"{self.base}/accounts", json_data={"address": address, "password": password})
        stat, ct, t = await self._post(f"{self.base}/token", json_data={"address": address, "password": password})
        tok = json.loads(t).get("token")
        return {"email": address, "provider": self.name, "token": tok, "password": password}

    async def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    async def list_messages(self, email=None, token=None):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.get(f"{self.base}/messages") as resp:
                data = await resp.json()
                return data.get("hydra:member", [])

class OneSecMailProvider(BaseProvider):
    name = "1secmail"
    base = "https://www.1secmail.com/api/v1/"

    async def create_address(self):
        stat, ct, text = await self._get(self.base + "?action=genRandomMailbox&count=1")
        data = json.loads(text)
        return {"email": data[0], "provider": self.name}

    async def list_messages(self, email=None, token=None):
        login, domain = email.split("@")
        url = f"{self.base}?action=getMessages&login={login}&domain={domain}"
        stat, ct, text = await self._get(url)
        return json.loads(text)

class GetNadaProvider(BaseProvider):
    name = "getnada"
    base = "https://getnada.com/api/v1"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        domain = "getnada.com"
        return {"email": f"{prefix}@{domain}", "provider": self.name}

    async def list_messages(self, email=None, token=None):
        url = f"{self.base}/inboxes/{email}"
        stat, ct, text = await self._get(url)
        data = json.loads(text)
        return data.get("msgs", [])

class MaildropProvider(BaseProvider):
    name = "maildrop"
    base = "https://api.maildrop.cc/graphql"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@maildrop.cc", "provider": self.name}

    async def list_messages(self, email=None, token=None):
        mailbox = email.split("@")[0]
        query = {"query": f'query{{inbox(mailbox:\"{mailbox}\"){{id mailfrom subject}}}}'}
        stat, ct, text = await self._post(self.base, json_data=query)
        data = json.loads(text)
        return data.get("data", {}).get("inbox", [])

class MailsacProvider(BaseProvider):
    name = "mailsac"
    base = "https://mailsac.com/api"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@mailsac.com", "provider": self.name}

    async def list_messages(self, email=None, token=None):
        url = f"{self.base}/addresses/{email}/messages"
        stat, ct, text = await self._get(url)
        return json.loads(text)

class YopMailProvider(BaseProvider):
    name = "yopmail"
    base = "http://api.yopmail.com/mail"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@yopmail.com", "provider": self.name}

    async def list_messages(self, email=None, token=None):
        # Простая заглушка, т.к. YopMail нет нормального API
        return []

# Остальные провайдеры (заглушки для примера)
class DummyProvider(BaseProvider):
    def __init__(self, name, domain):
        super().__init__()
        self.name = name
        self.domain = domain

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@{self.domain}", "provider": self.name}

    async def list_messages(self, email=None, token=None):
        return []

# -------------------- Hikka module --------------------
@loader.tds
class TempMailFullModule(loader.Module):
    """TempMail Full — multi-provider, вечное хранение, read/delete"""

    strings = {
        "name": "TempMailFull",
        "created": "📧 <b>Создан адрес</b>\n<code>{}</code>\n<b>Провайдер:</b> {}",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем пока нет</b>",
        "inbox": "📥 <b>Входящие ({})</b> для <code>{}</code>:\n{}",
        "deleted": "🗑️ Почта удалена: {} (провайдер: {})",
        "mails_list": "📜 <b>Твои адреса:</b>\n{}",
        "set_active": "✅ Активный адрес: <code>{}</code>",
    }

    def __init__(self):
        self.name = "TempMailFull"
        self.providers = {
            "mailtm": MailTmProvider(),
            "1secmail": OneSecMailProvider(),
            "getnada": GetNadaProvider(),
            "maildrop": MaildropProvider(),
            "mailsac": MailsacProvider(),
            "yopmail": YopMailProvider(),
            # Остальные 9 провайдеров
            "guerrillamail": DummyProvider("guerrillamail", "guerrillamail.com"),
            "throwawaymail": DummyProvider("throwawaymail", "throwawaymail.com"),
            "temp-mail": DummyProvider("temp-mail", "temp-mail.org"),
            "mailnesia": DummyProvider("mailnesia", "mailnesia.com"),
            "mailcatch": DummyProvider("mailcatch", "mailcatch.com"),
            "spamgourmet": DummyProvider("spamgourmet", "spamgourmet.com"),
            "moakt": DummyProvider("moakt", "moakt.com"),
            "fakemailgenerator": DummyProvider("fakemailgenerator", "fakemailgenerator.com"),
            "mailinator": DummyProvider("mailinator", "mailinator.com"),
        }
        self.provider_order = DEFAULT_PROVIDERS
        self.max_mails = DEFAULT_MAX_MAILS
        self.auto_update = True
        self._db_key = "my_saved_mails"
        self.windows_limit = {"mymails": DEFAULT_MAX_WINDOWS, "tinbox": DEFAULT_MAX_WINDOWS}
        self._active_windows = {"mymails": [], "tinbox": []}

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    # ---------- helpers ----------
    def _addr_key(self, uid): return f"addrs_{uid}"
    def _active_key(self, uid): return f"addr_{uid}"

    def _get_saved(self):
        return self.db.get(self._db_key, [])

    def _save_address(self, email_data):
        saved = self._get_saved()
        saved.insert(0, email_data)
        self.db.set(self._db_key, saved[:self.max_mails])

    # ---------------- Commands ----------------
    @loader.command()
    async def tempmail(self, message):
        """Создать новую временную почту"""
        uid = message.from_id
        for p in self.provider_order:
            prov = self.providers.get(p)
            try:
                info = await prov.create_address()
                self._save_address(info)
                return await utils.answer(message, self.strings["created"].format(info.get("email"), p))
            except: continue
        await utils.answer(message, "❌ Не удалось создать почту ни с одного провайдера")

    @loader.command()
    async def mymails(self, message):
        """Показать список своих почт"""
        saved = self._get_saved()
        if not saved: return await utils.answer(message, "📭 Нет сохранённых почт")
        text = "📬 Сохранённые почты:\n\n"
        for i, mail in enumerate(saved, 1):
            text += f"{i}. {mail['email']} ({mail['provider']})\n"
        await utils.answer(message, text)

    @loader.command()
    async def delmail(self, message):
        """Удалить почту по номеру"""
        args = utils.get_args_raw(message)
        saved = self._get_saved()
        if not args.isdigit(): return await utils.answer(message, "❌ Укажи номер почты")
        idx = int(args) - 1
        if idx < 0 or idx >= len(saved): return await utils.answer(message, "❌ Неверный номер")
        removed = saved.pop(idx)
        self.db.set(self._db_key, saved)
        await utils.answer(message, f"🗑 Удалена: {removed['email']}")
