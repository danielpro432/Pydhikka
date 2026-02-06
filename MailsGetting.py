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
MAX_HISTORY = 10  # максимум почт на пользователя

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
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        status, ct, text = await self._get(f"{self.base}/domains")
        if status != 200:
            raise RuntimeError(f"mail.tm domains HTTP {status}")
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "hydra:member" in data:
                domains = data["hydra:member"]
                domain = random.choice(domains)["domain"]
            elif isinstance(data, list):
                domain = random.choice(data)["domain"]
            else:
                raise RuntimeError("mail.tm domains parsing failed")
        except Exception as e:
            raise RuntimeError(f"mail.tm domains parse: {e}")

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

    async def delete_message(self, email, token, msg_id):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.delete(f"{self.base}/messages/{msg_id}") as resp:
                if resp.status not in (200,204):
                    raise RuntimeError(f"mail.tm delete HTTP {resp.status}")

    async def delete_account(self, email, token):
        headers = await self._auth_headers(token)
        async with aiohttp.ClientSession(headers={**HEADERS_BASE, **headers}) as s:
            async with s.delete(f"{self.base}/me") as resp:
                if resp.status in (200,204):
                    return
        raise RuntimeError("mail.tm delete failed")

# 1secmail provider
class OneSecMailProvider(BaseProvider):
    name = "1secmail"
    base = "https://www.1secmail.com/api/v1/"

    async def create_address(self):
        stat, ct, text = await self._get(self.base + "?action=genRandomMailbox&count=1")
        if stat != 200:
            raise RuntimeError(f"1secmail create HTTP {stat}")
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

    async def delete_message(self, email, msg_id):
        raise NotImplementedError

    async def delete_account(self, email):
        raise NotImplementedError

# GetNada provider
class GetNadaProvider(BaseProvider):
    name = "getnada"
    base = "https://getnada.com/api/v1"

    async def create_address(self):
        try:
            stat, ct, text = await self._get(self.base + "/domains")
            domains = json.loads(text) if stat == 200 else ["getnada.com"]
            domain = random.choice(domains)
        except:
            domain = "getnada.com"
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@{domain}", "provider": self.name}

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
            if resp.status not in (200,204):
                raise RuntimeError(f"getnada delete HTTP {resp.status}")

    async def delete_account(self, email):
        raise NotImplementedError

# Maildrop provider
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

    async def delete_message(self, email, msg_id):
        mailbox = email.split("@")[0]
        mutation = {"query": f'mutation{{delete(mailbox:\"{mailbox}\",id:\"{msg_id}\")}}'}
        stat, ct, text = await self._post(self.base, json_data=mutation)
        if stat != 200:
            raise RuntimeError(f"maildrop delete HTTP {stat}")

    async def delete_account(self, email):
        raise NotImplementedError

# Mailsac provider
class MailsacProvider(BaseProvider):
    name = "mailsac"
    base = "https://mailsac.com/api"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@mailsac.com", "provider": self.name}

    async def list_messages(self, email):
        url = f"{self.base}/addresses/{email}/messages"
        stat, ct, text = await self._get(url)
        return json.loads(text)

    async def read_message(self, email, msg_id):
        url = f"{self.base}/text/{email}/{msg_id}"
        stat, ct, text = await self._get(url)
        return {"body": text}

    async def delete_message(self, email, msg_id):
        raise NotImplementedError

    async def delete_account(self, email):
        raise NotImplementedError

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
        self.db.set(self.name, self._addr_key(uid), history[:MAX_HISTORY])  # keep max 10

    def _get_active_record(self, uid):
        active = self.db.get(self.name, self._active_key(uid))
        if not active:
            return None
        history = self._get_history(uid)
        for rec in history:
            if rec.get("email") == active:
                return rec
        return None

    def _add_record(self, uid, record):
        history = self._get_history(uid)
        history.insert(0, record)
        if len(history) > MAX_HISTORY:
            history = history[:MAX_HISTORY]
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), record["email"])

    def _prov_by_name(self, name):
        return self.providers.get(name)

    def _get_user_provider_name(self, uid):
        return self.db.get(self.name, self._prov_key(uid), self.provider_order[0])

    def _format_inbox_items(self, provider_name, raw_items):
        out = []
        for r in raw_items:
            out.append({
                "id": r.get("id") or r.get("uid") or r.get("_id"),
                "from": r.get("from") or r.get("f") or r.get("mailfrom"),
                "subject": r.get("subject") or r.get("s") or "(no subject)"
            })
        return out

    # ---------------- Commands ----------------
    @loader.command()
    async def tprovider(self, message):
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(self.providers.keys())))
        p = args[0].lower()
        if p not in self.providers:
            return await utils.answer(message, self.strings["unknown_provider"].format(", ".join(self.providers.keys())))
        self.db.set(self.name, self._prov_key(message.from_id), p)
        await utils.answer(message, self.strings["provider_set"].format(p))

    @loader.command()
    async def tempmail(self, message):
        args = utils.get_args_raw(message).split()
        preferred = args[0].lower() if args else None
        uid = message.from_id
        providers_try = [preferred] + [p for p in self.provider_order if p != preferred] if preferred else list(self.provider_order)
        last_err = None
        await utils.answer(message, self.strings["trying"].format(preferred or providers_try[0]))
        for p in providers_try:
            prov = self._prov_by_name(p)
            if not prov:
                continue
            try:
                info = await prov.create_address()
                rec = {
                    "email": info.get("email"),
                    "provider": p,
                    "created": datetime.utcnow().isoformat(),
                    "meta": info
                }
                self._add_record(uid, rec)
                self.db.set(self.name, self._prov_key(uid), p)
                return await utils.answer(message, self.strings["created"].format(info.get("email"), p))
            except Exception as e:
                last_err = str(e)[:RAW_LOG_LEN]
                self.db.set(self.name, self._lastraw_key(uid), {"provider": p, "error": last_err})
                continue
        await utils.answer(message, self.strings["api_error"].format(",".join(providers_try), last_err or "all providers failed"))

    # остальные команды: .mymails, .usemail, .tinbox, .tread, .delmail, .tinfo, .tdebug
    @loader.command()
    async def mymails(self, message):
        """📜 Список твоих почт"""
        uid = message.from_id
        history = self._get_history(uid)
        if not history:
            return await utils.answer(message, self.strings["no_mail"])
        out = []
        active = self.db.get(self.name, self._active_key(uid))
        for r in history:
            prefix = "✅" if r["email"] == active else "•"
            out.append(f"{prefix} <code>{r['email']}</code> ({r['provider']})")
        await utils.answer(message, self.strings["mails_list"].format("\n".join(out)))

    @loader.command()
    async def usemail(self, message):
        """✅ Сделать почту активной"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["no_mail"])
        uid = message.from_id
        target = args[0]
        history = self._get_history(uid)
        for r in history:
            if r["email"] == target:
                self.db.set(self.name, self._active_key(uid), target)
                return await utils.answer(message, self.strings["set_active"].format(target))
        await utils.answer(message, self.strings["no_mail"])

@loader.command()
async def tinbox(self, message):
    """📥 Показать входящие письма"""
    uid = message.from_id
    record = self._get_active_record(uid)
    if not record:
        return await utils.answer(message, self.strings["no_mail"])
    
    prov = self._prov_by_name(record["provider"])
    try:
        if record["provider"] == "mailtm":
            # mail.tm требует token
            items = await prov.list_messages(email=record["email"], token=record["meta"]["token"])
        else:
            items = await prov.list_messages(record["email"])

        inbox = self._format_inbox_items(record["provider"], items)
        if not inbox:
            return await utils.answer(message, self.strings["empty"])

        out = "\n".join(f'<b>{i["id"]}</b> | {i["from"]} | {i["subject"]}' for i in inbox)
        await utils.answer(message, self.strings["inbox"].format(len(inbox), out))

    except Exception as e:
        await utils.answer(message, self.strings["api_error"].format(record["provider"], str(e)[:RAW_LOG_LEN]))
    @loader.command()
    async def tread(self, message):
        """📩 Прочитать письмо: .tread <id> [email]"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["read_usage"])
        msg_id = args[0]
        uid = message.from_id
        email = args[1] if len(args) > 1 else None
        record = None
        if email:
            history = self._get_history(uid)
            for r in history:
                if r["email"] == email:
                    record = r
                    break
        else:
            record = self._get_active_record(uid)
        if not record:
            return await utils.answer(message, self.strings["no_mail"])
        prov = self._prov_by_name(record["provider"])
        try:
            msg = await prov.read_message(record["email"], msg_id, **record.get("meta", {}))
            body = msg.get("text") or msg.get("body") or msg.get("data") or "(no content)"
            await utils.answer(message, self.strings["letter"].format(msg.get("from") or "unknown", msg.get("subject") or "(no subject)", body))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(record["provider"], str(e)[:RAW_LOG_LEN]))

    @loader.command()
    async def delmail(self, message):
        """🗑️ Удалить почту"""
        uid = message.from_id
        record = self._get_active_record(uid)
        if not record:
            return await utils.answer(message, self.strings["no_mail"])
        prov = self._prov_by_name(record["provider"])
        try:
            await prov.delete_account(record["email"], **record.get("meta", {}))
        except:
            pass  # игнорируем если нельзя удалить
        history = self._get_history(uid)
        history = [r for r in history if r["email"] != record["email"]]
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), history[0]["email"] if history else None)
        await utils.answer(message, self.strings["deleted"].format(record["email"], record["provider"]))

    @loader.command()
    async def tinfo(self, message):
        """📌 Информация о текущей почте"""
        uid = message.from_id
        record = self._get_active_record(uid)
        if not record:
            return await utils.answer(message, self.strings["no_mail"])
        await utils.answer(message, self.strings["info"].format(record["email"], record["provider"]))

    @loader.command()
async def tdebug(self, message):
    """🔎 Debug провайдера"""
    uid = message.from_id
    record = self._get_active_record(uid)
    if not record:
        return await utils.answer(message, self.strings["no_mail"])
    
    prov = self._prov_by_name(record["provider"])
    try:
        if record["provider"] == "mailtm":
            items = await prov.list_messages(email=record["email"], token=record["meta"]["token"])
        else:
            items = await prov.list_messages(record["email"])

        await utils.answer(message, self.strings["debug"].format(record["provider"], json.dumps(items, indent=2)))

    except Exception as e:
        await utils.answer(message, self.strings["api_error"].format(record["provider"], str(e)[:RAW_LOG_LEN]))
