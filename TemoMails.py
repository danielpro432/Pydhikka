# TempMail — multi-provider, interactive + auto-rotation
# Works in Termux/Linux (Python 3.11+)
# Providers: mail.tm, 1secmail, getnada, maildrop, mailsac

import aiohttp, asyncio, json, logging, random, string, urllib.parse
from datetime import datetime
from .. import loader, utils
from telethon import Button

logger = logging.getLogger(__name__)

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, /",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}

MAX_TRIES = 3
RAW_LOG_LEN = 800
MAX_ADDRESSES = 10  # keep max addresses per user
DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac"]

# ---------------- Base provider -----------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS_BASE)

    async def create_address(self): raise NotImplementedError
    async def list_messages(self, email, token=None): raise NotImplementedError
    async def read_message(self, email, msg_id, token=None): raise NotImplementedError
    async def delete_message(self, email, msg_id, token=None): raise NotImplementedError
    async def delete_account(self, email, token=None): raise NotImplementedError
    async def close(self):
        try: await self.session.close()
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

# ---------------- Providers (simplified) -----------------
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        status, _, text = await self._get(f"{self.base}/domains")
        data = json.loads(text)
        if isinstance(data, dict) and "hydra:member" in data: domain = random.choice(data["hydra:member"])["domain"]
        elif isinstance(data, list): domain = random.choice(data)["domain"] if isinstance(data[0], dict) else random.choice(data)
        login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        address = f"{login}@{domain}"
        password = "HikkaTempPass!" + "".join(random.choices(string.digits, k=4))
        stat, _, t = await self._post(f"{self.base}/accounts", json_data={"address": address, "password": password})
        stat, _, t = await self._post(f"{self.base}/token", json_data={"address": address, "password": password})
        tok = json.loads(t).get("token")
        return {"email": address, "provider": self.name, "token": tok, "password": password}

    def _auth_headers(self, token): return {"Authorization": f"Bearer {token}"}

    async def list_messages(self, email, token=None):
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages") as resp:
                data = json.loads(await resp.text(errors="ignore"))
                return data.get("hydra:member", data)

    async def read_message(self, email, msg_id, token=None):
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages/{msg_id}") as resp:
                return json.loads(await resp.text(errors="ignore"))

    async def delete_account(self, email, token=None):
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.delete(f"{self.base}/me") as resp:
                if resp.status not in (200, 204): raise RuntimeError("mail.tm delete failed")

# ---------------- Module -----------------
@loader.tds
class TempMailModule(loader.Module):
    """TempMail — multi-provider, interactive, auto-rotation"""

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
        "deleted": "🗑️ Почта удалена: {} (провайдер: {})",
    }

    def __init__(self):
        self.name = "TempMail"
        self.providers = {"mailtm": MailTmProvider()}  # можно добавить остальные
        self.provider_order = list(DEFAULT_PROVIDERS)

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    # ---------------- Commands -----------------
    @loader.command()
    async def tempmail(self, message):
        """Создать новый временный email: .tempmail"""
        uid = message.from_id
        provider = self.provider_order[0]
        info = await self.providers[provider].create_address()
        rec = {"email": info["email"], "provider": provider, "meta": info, "created": datetime.utcnow().isoformat()}
        await self._add_record(uid, rec)
        await utils.answer(message, self.strings["created"].format(info["email"], provider))

    @loader.command()
    async def mymails(self, message):
        """Показать все созданные адреса"""
        uid = message.from_id
        history = self._get_history(uid)
        if not history: return await utils.answer(message, "📭 У тебя нет адресов.")
        text = ""
        for r in history:
            act = " (active)" if r.get("email") == self.db.get(self.name, f"addr_{uid}") else ""
            text += f"• <code>{r.get('email')}</code> | {r.get('provider')} | {r.get('created')}{act}\n"
        await utils.answer(message, self.strings["mails_list"].format(text))

    # ---------------- History helpers -----------------
    def _addr_key(self, uid): return f"addrs_{uid}"
    def _active_key(self, uid): return f"addr_{uid}"

    def _get_history(self, uid):
        return self.db.get(self.name, self._addr_key(uid), [])

    async def _add_record(self, uid, record):
        history = self._get_history(uid)
        if len(history) >= MAX_ADDRESSES:
            oldest = history.pop(-1)
            prov = self.providers.get(oldest["provider"])
            meta = oldest.get("meta", {})
            if prov and oldest["provider"] == "mailtm":
                token = meta.get("token")
                try: await prov.delete_account(oldest["email"], token)
                except Exception as e: logger.warning("Auto-delete failed %s: %s", oldest["email"], e)
        history.insert(0, record)
        self.db.set(self.name, self._addr_key(uid), history)
        self.db.set(self.name, self._active_key(uid), record["email"])
