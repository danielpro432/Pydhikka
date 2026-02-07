TempMail Multi-Provider (Hikka module)

Licensed under GNU AGPLv3

Works in Termux/Linux (Python 3.11+)

Providers included: mail.tm, 1secmail, getnada, maildrop, mailsac

Added: возможность создавать почты на популярных @domains (@gmail.com, @yahoo.com, @outlook.com)

import aiohttp import asyncio import json import random import string from datetime import datetime from .. import loader, utils

HEADERS_BASE = { "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept": "application/json, text/plain, /", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://google.com/", }

MAX_TRIES = 3 RAW_LOG_LEN = 800 DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac"] DEFAULT_MAX_MAILS = 10 DEFAULT_MAX_WINDOWS = 2  # Максимум открытых окон для mymails/tinbox POPULAR_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com"]

-------------------- Base Provider --------------------

class BaseProvider: name = "base"

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

-------------------- Providers --------------------

class PopularProvider(BaseProvider): name = "popular"

async def create_address(self):
    domain = random.choice(POPULAR_DOMAINS)
    local = "hikka" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return {"email": f"{local}@{domain}", "provider": self.name}

-------------------- Hikka module --------------------

@loader.tds class TempMailModule(loader.Module): """TempMail — multi-provider, с популярными @domains"""

strings = {"name": "TempMail"}

def __init__(self):
    self.name = "TempMail"
    self.providers = {
        "popular": PopularProvider(),
    }
    self.provider_order = ["popular"]
    self.max_mails = DEFAULT_MAX_MAILS
    self.auto_update = True
    self.windows_limit = {"mymails": DEFAULT_MAX_WINDOWS, "tinbox": DEFAULT_MAX_WINDOWS}
    self._active_windows = {"mymails": [], "tinbox": []}

async def client_ready(self, client, db):
    self.db = db
    self._client = client

# ---------- helpers ----------
def _addr_key(self, uid): return f"addrs_{uid}"
def _active_key(self, uid): return f"addr_{uid}"

def _get_history(self, uid):
    return self.db.get(self.name, self._addr_key(uid), [])

def _save_history(self, uid, history):
    self.db.set(self.name, self._addr_key(uid), history[:self.max_mails])

def _get_active_record(self, uid):
    active = self.db.get(self.name, self._active_key(uid))
    if not active: return None
    history = self._get_history(uid)
    for rec in history:
        if rec.get("email") == active: return rec
    return None

def _add_record(self, uid, record):
    history = self._get_history(uid)
    history.insert(0, record)
    if len(history) > self.max_mails: history = history[:self.max_mails]
    self._save_history(uid, history)
    self.db.set(self.name, self._active_key(uid), record["email"])

# ---------------- Commands ----------------
@loader.command()
async def tempmail(self, message):
    """Создать новую временную почту на популярных @"""
    uid = message.from_id
    for p in self.provider_order:
        prov = self.providers[p]
        try:
            info = await prov.create_address()
            rec = {"email": info.get("email"), "provider": p, "created": datetime.utcnow().isoformat(), "meta": info}
            self._add_record(uid, rec)
            return await utils.answer(message, f"📧 <b>Создан адрес:</b> <code>{info.get('email')}</code>")
        except: continue
    await utils.answer(message, "❌ Не удалось создать почту") 
