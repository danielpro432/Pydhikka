# TempMail Multi-Provider (Hikka module)
# Licensed under GNU AGPLv3
# Works in Termux/Linux (Python 3.11+)
# Providers included: mail.tm, 1secmail, getnada, maildrop, mailsac, guerrilla

import aiohttp
import asyncio
import json
import random
import string
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
DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac", "guerrilla"]
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
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        stat, ct, text = await self._get(f"{self.base}/domains")
        data = json.loads(text)
        if isinstance(data, dict) and "hydra:member" in data:
            domain = random.choice(data["hydra:member"])["domain"]
        else:
            domain = random.choice(data)["domain"]
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

# 1secmail
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

# GetNada
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

# Maildrop
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

# Mailsac
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

# GuerrillaMail
class GuerrillaMailProvider(BaseProvider):
    name = "guerrilla"
    base = "https://api.guerrillamail.com/ajax.php"

    async def create_address(self):
        stat, ct, text = await self._get(self.base + "?f=get_email_address")
        data = json.loads(text)
        return {
            "email": data.get("email_addr"),
            "provider": self.name,
            "meta": {"sid_token": data.get("sid_token")}
        }

    async def list_messages(self, email=None, token=None):
        stat, ct, text = await self._get(self.base + "?f=get_email_list&offset=0")
        data = json.loads(text)
        return data.get("list", [])

# -------------------- Hikka module --------------------
@loader.tds
class TempMailModule(loader.Module):
    """TempMail — multi-provider, история, read/delete, delmail"""

    strings = {
        "name": "TempMail",
        "created": "📧 <b>Создан адрес</b>\n<code>{}</code>\n<b>Провайдер:</b> {}",
        "no_mail": "❌ <b>Сначала создай почту:</b> <code>.tempmail</code>",
        "empty": "📭 <b>Писем пока нет</b>",
        "inbox": "📥 <b>Входящие ({})</b> для <code>{}</code>:\n{}",
        "provider_set": "✅ <b>Провайдер установлен:</b> {}",
        "deleted": "🗑️ Почта удалена: {} (провайдер: {})",
        "mails_list": "📜 <b>Твои адреса:</b>\n{}",
        "set_active": "✅ Активный адрес: <code>{}</code>",
        "del_prompt": "📌 Выбери почту для удаления (номер или часть адреса, можно несколько через пробел):\n{}",
        "del_done": "🗑️ Удалены почты:\n{}",
        "windows_set": "⚙️ Лимит окон команды <code>{}</code> установлен: {}",
    }

    def __init__(self):
        self.name = "TempMail"
        self.providers = {
            "mailtm": MailTmProvider(),
            "1secmail": OneSecMailProvider(),
            "getnada": GetNadaProvider(),
            "maildrop": MaildropProvider(),
            "mailsac": MailsacProvider(),
            "guerrilla": GuerrillaMailProvider(),
        }
        self.provider_order = DEFAULT_PROVIDERS
        self.max_mails = DEFAULT_MAX_MAILS
        self.auto_update = False  # отключаем авто-удаление
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

    def _prov_by_name(self, name): return self.providers.get(name)

    def _format_inbox_items(self, rec):
        items = rec.get("msgs", [])
        out = []
        for r in items:
            out.append(f"{r.get('id')}: {r.get('from') or r.get('mailfrom') or r.get('f')} | {r.get('subject') or '(no subject)'}")
        return "\n".join(out)

    def _register_window(self, cmd, message):
        self._active_windows.setdefault(cmd, [])
        self._active_windows[cmd].append(message)
        while len(self._active_windows[cmd]) > self.windows_limit.get(cmd, 2):
            self._active_windows[cmd].pop(0)

    # ---------------- Commands ----------------
    @loader.command()
    async def tempmail(self, message):
        """Создать новую временную почту
        .tempmail              — авто логин
        .tempmail myname       — свой логин
        .tempmail myname mailtm — свой логин + провайдер
        """
        uid = message.from_id
        args = utils.get_args_raw(message).split()

        custom_login = None
        custom_provider = None

        if args:
            custom_login = args[0]
            if len(args) > 1:
                custom_provider = args[1]

        providers_to_try = (
            [custom_provider] if custom_provider in self.providers
            else self.provider_order
        )

        for p in providers_to_try:
            prov = self._prov_by_name(p)
            try:
                info = await prov.create_address()
                if custom_login:
                    domain = info["email"].split("@")[1]
                    info["email"] = f"{custom_login}@{domain}"
                rec = {
                    "email": info.get("email"),
                    "provider": p,
                    "created": datetime.utcnow().isoformat(),
                    "meta": info
                }
                self._add_record(uid, rec)
                return await utils.answer(
                    message,
                    self.strings["created"].format(info.get("email"), p)
                )
            except: continue

        await utils.answer(message, "❌ Не удалось создать почту")

    @loader.command()
    async def mymails(self, message):
        """Показать список своих почт"""
        self._register_window("mymails", message)
        uid = message.from_id
        history = self._get_history(uid)
        if not history: return await utils.answer(message, self.strings["no_mail"])
        out = []
        for idx, rec in enumerate(history, 1):
            active = " (active)" if rec.get("email") == self.db.get(self.name, self._active_key(uid)) else ""
            out.append(f"{idx}. {rec.get('email')} [{rec.get('provider')}] {active}")
        await utils.answer(message, self.strings["mails_list"].format("\n".join(out)))

    @loader.command()
    async def usemail(self, message):
        """Выбрать активную почту (по email или номеру)"""
        args = utils.get_args_raw(message).split()
        if not args: return await utils.answer(message, "❌ Укажи почту или номер")
        uid = message.from_id
        history = self._get_history(uid)
        target = None
        for arg in args:
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(history):
                    target = history[idx]
            else:
                for rec in history:
                    if arg in rec["email"]:
                        target = rec
        if target:
            self.db.set(self.name, self._active_key(uid), target["email"])
            return await utils.answer(message, self.strings["set_active"].format(target["email"]))
        await utils.answer(message, "❌ Почта не найдена")

    @loader.command()
    async def tinbox(self, message):
        """Показать письма активной почты"""
        self._register_window("tinbox", message)
        uid = message.from_id
        rec = self._get_active_record(uid)
        if not rec: return await utils.answer(message, self.strings["no_mail"])
        prov = self._prov_by_name(rec["provider"])
        try:
            msgs = await prov.list_messages(email=rec.get("email"), token=rec.get("meta", {}).get("token"))
            rec["msgs"] = msgs
            out = self._format_inbox_items(rec)
            if not out: out = self.strings["empty"]
            await utils.answer(message, self.strings["inbox"].format(len(msgs), rec["email"], out))
        except Exception as e:
            await utils.answer(message, f"⚠️ Ошибка API\nПровайдер: {rec['provider']}\nПричина: {str(e)[:RAW_LOG_LEN]}")

    @loader.command()
    async def delmail(self, message):
        """Удалить почту по номеру, части адреса или полному email"""
        uid = message.from_id
        history = self._get_history(uid)
        if not history:
            return await utils.answer(message, self.strings["no_mail"])
        args = utils.get_args_raw(message).split()
        if not args:
            out = []
            for idx, rec in enumerate(history, 1):
                out.append(f"{idx}. {rec['email']} [{rec['provider']}]")
            return await utils.answer(message, self.strings["del_prompt"].format("\n".join(out)))
        to_del = []
        for arg in args:
            if arg.isdigit():
                idx = int(arg)-1
                if 0 <= idx < len(history):
                    to_del.append(history[idx])
            else:
                for rec in history:
                    if arg in rec["email"]:
                        to_del.append(rec)
        removed = []
        for rec in to_del:
            if rec in history:
                history.remove(rec)
                removed.append(f"{rec['email']} [{rec['provider']}]")
        self._save_history(uid, history)
        await utils.answer(message, self.strings["del_done"].format("\n".join(removed)))

    @loader.command()
    async def setmaxwindows(self, message):
        """Настроить лимит открытых окон команды: .setmaxwindows mymails 2"""
        args = utils.get_args_raw(message).split()
        if len(args) != 2 or not args[1].isdigit():
            return await utils.answer(message, "❌ Используй: .setmaxwindows <mymails/tinbox> <число 1-10>")
        cmd, val = args
        val = max(1, min(10, int(val)))
        self.windows_limit[cmd] = val
        await utils.answer(message, self.strings["windows_set"].format(cmd, val))
