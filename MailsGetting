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

# -------------------- Base provider interface --------------------
class BaseProvider:
    name = "base"

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS_BASE)

    async def create_address(self):
        raise NotImplementedError

    async def list_messages(self, email):
        raise NotImplementedError

    async def read_message(self, email, msg_id):
        raise NotImplementedError

    async def delete_message(self, email, msg_id):
        raise NotImplementedError

    async def delete_account(self, email):
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

# -------------------- Provider implementations --------------------
# MailTmProvider, OneSecMailProvider, GetNadaProvider, MaildropProvider, MailsacProvider
# ... (код провайдеров такой же, как у тебя) ...

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

    # ---------- storage helpers ----------
    def _addr_key(self, uid):
        return f"addrs_{uid}"

    def _active_key(self, uid):
        return f"addr_{uid}"

    def _prov_key(self, uid):
        return f"prov_{uid}"

    def _lastraw_key(self, uid):
        return f"lastraw_{uid}"

    def _get_history(self, uid):
        return self.db.get(self.name, self._addr_key(uid), [])

    def _save_history(self, uid, history):
        self.db.set(self.name, self._addr_key(uid), history)

    # ---------- обновлённая функция добавления почты ----------
    def _add_record(self, uid, record):
        history = self._get_history(uid)
        history = [r for r in history if r.get("email") != record["email"]]
        history.insert(0, record)
        if len(history) > 10:
            oldest = history.pop()
            try:
                prov = self._prov_by_name(oldest.get("provider"))
                meta = oldest.get("meta", {})
                email = oldest.get("email")
                if prov:
                    if oldest.get("provider") == "mailtm":
                        token = meta.get("token")
                        if token:
                            asyncio.create_task(prov.delete_account(email, token))
                    elif oldest.get("provider") == "getnada":
                        async def delete_msgs():
                            try:
                                msgs_list = await prov.list_messages(email)
                                for m in msgs_list:
                                    mid = m.get("uid") or m.get("id")
                                    try: await prov.delete_message(email, mid)
                                    except: pass
                            except: pass
                        asyncio.create_task(delete_msgs())
            except: pass
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), record["email"])

    # ---------- команды ----------
    @loader.command()
    async def tprovider(self, message):
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(self.providers.keys())))
        p = args[0].lower()
        if p not in self.providers:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(self.providers.keys())))
        self.db.set(self.name, self._prov_key(message.from_id), p)
        return await utils.answer(message, self.strings["provider_set"].format(p))

    @loader.command()
    async def tempmail(self, message):
        args = utils.get_args_raw(message).split()
        preferred = args[0].lower() if args else None
        uid = message.from_id
        providers_try = [preferred] + [p for p in self.provider_order if p != preferred] if preferred else list(self.provider_order)
        last_err = None
        await utils.answer(message, self.strings["trying"].format(preferred or providers_try[0]))
        for p in providers_try:
            prov = self.providers.get(p)
            if not prov: continue
            try:
                info = await prov.create_address()
                email = info.get("email")
                rec = {"email": email, "provider": p, "created": datetime.utcnow().isoformat(), "meta": info}
                self._add_record(uid, rec)
                self.db.set(self.name, self._prov_key(uid), p)
                return await utils.answer(message, self.strings["created"].format(email, p))
            except Exception as e:
                last_err = str(e)[:RAW_LOG_LEN]
                self.db.set(self.name, self._lastraw_key(uid), {"provider": p, "error": last_err})
        await utils.answer(message, self.strings["api_error"].format(",".join(providers_try), last_err or "all providers failed"))

    @loader.command()
    async def delmail(self, message):
        args = utils.get_args_raw(message).split()
        uid = message.from_id
        target_email = args[0] if args else self.db.get(self.name, self._active_key(uid))
        if not target_email:
            return await utils.answer(message, self.strings["no_mail"])
        history = self._get_history(uid)
        rec = next((r for r in history if r.get("email") == target_email), None)
        if not rec:
            return await utils.answer(message, "❌ Этот адрес не найден в истории.")
        provider = rec.get("provider")
        prov = self._prov_by_name(provider)
        meta = rec.get("meta", {})
        try:
            if provider == "mailtm":
                token = meta.get("token")
                if token: await prov.delete_account(target_email, token)
            elif provider == "getnada":
                msgs = await prov.list_messages(target_email)
                for m in msgs:
                    mid = m.get("uid") or m.get("id")
                    try: await prov.delete_message(target_email, mid)
                    except: pass
            new_hist = [r for r in history if r.get("email") != target_email]
            self._save_history(uid, new_hist)
            if self.db.get(self.name, self._active_key(uid)) == target_email:
                self.db.set(self.name, self._active_key(uid), new_hist[0]["email"] if new_hist else None)
            await utils.answer(message, self.strings["deleted"].format(target_email, provider))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(provider, str(e)[:RAW_LOG_LEN]))

    # остальные команды: mymails, usemail, tinbox, tread, tinfo, tdebug — без изменений

    async def on_unload(self):
        for p in self.providers.values():
            try: await p.close()
            except: pass
