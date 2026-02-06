# TempMail Multi-Provider (Hikka module) — исправленная версия
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

# General HTTP settings
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}

MAX_TRIES = 3
RAW_LOG_LEN = 800

# Provider names order for fallback
DEFAULT_PROVIDERS = ["mailtm", "1secmail", "getnada", "maildrop", "mailsac"]

# -------------------- Base provider interface --------------------
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
        # not all providers support deleting account/address
        raise NotImplementedError

    async def close(self):
        try:
            await self.session.close()
        except Exception:
            pass

    # helper
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

# 1) mail.tm - requires create account + token
class MailTmProvider(BaseProvider):
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create_address(self):
        # get domains
        status, ct, text = await self._get(f"{self.base}/domains")
        if status != 200:
            raise RuntimeError(f"mail.tm domains HTTP {status}")
        try:
            data = json.loads(text)
            # domains may be hydra:member or list
            if isinstance(data, dict) and "hydra:member" in data:
                domains = data["hydra:member"]
                domain = random.choice(domains).get("domain")
            elif isinstance(data, list):
                if data and isinstance(data[0], dict):
                    domain = random.choice(data).get("domain")
                else:
                    domain = random.choice(data)
            else:
                raise RuntimeError("mail.tm domains parsing failed")
        except Exception as e:
            raise RuntimeError(f"mail.tm domains parse: {e}")

        login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        address = f"{login}@{domain}"
        password = "HikkaTempPass!" + "".join(random.choices(string.digits, k=4))

        # create account
        stat, ct, t = await self._post(f"{self.base}/accounts", json_data={"address": address, "password": password})
        if stat not in (200, 201):
            # maybe account exists; log but continue to token request (service may return 422/etc)
            logger.debug("mail.tm create returned: %s %s", stat, t[:200])

        # get token
        stat, ct, t = await self._post(f"{self.base}/token", json_data={"address": address, "password": password})
        if stat != 200:
            raise RuntimeError(f"mail.tm token HTTP {stat}: {t[:200]}")
        tok = json.loads(t).get("token")
        if not tok:
            raise RuntimeError("mail.tm token missing")
        # store minimal meta
        return {"email": address, "provider": self.name, "token": tok, "password": password}

    def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    async def list_messages(self, email, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token to list messages")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages") as resp:
                t = await resp.text(errors="ignore")
                if resp.status != 200:
                    raise RuntimeError(f"mail.tm inbox HTTP {resp.status}: {t[:200]}")
                data = json.loads(t)
                return data.get("hydra:member", data)

    async def read_message(self, email, msg_id, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token to read message")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"{self.base}/messages/{msg_id}") as resp:
                t = await resp.text(errors="ignore")
                if resp.status != 200:
                    raise RuntimeError(f"mail.tm read HTTP {resp.status}: {t[:200]}")
                return json.loads(t)

    async def delete_message(self, email, msg_id, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token to delete message")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.delete(f"{self.base}/messages/{msg_id}") as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(f"mail.tm delete HTTP {resp.status}")

    async def delete_account(self, email, token=None):
        if not token:
            raise RuntimeError("mail.tm requires token to delete account")
        headers = {**HEADERS_BASE, **self._auth_headers(token)}
        async with aiohttp.ClientSession(headers=headers) as s:
            # try /me
            async with s.delete(f"{self.base}/me") as resp:
                if resp.status in (200, 204):
                    return
            # fallback: try accounts search
            async with s.get(f"{self.base}/accounts") as resp2:
                txt = await resp2.text(errors="ignore")
                if resp2.status == 200:
                    try:
                        data = json.loads(txt)
                        members = data.get("hydra:member", data)
                        for acc in members:
                            if acc.get("address") == email:
                                aid = acc.get("id")
                                if aid:
                                    async with s.delete(f"{self.base}/accounts/{aid}") as r3:
                                        if r3.status in (200, 204):
                                            return
                    except Exception:
                        pass
        raise RuntimeError("mail.tm delete failed")

# 2) 1secmail
class OneSecMailProvider(BaseProvider):
    name = "1secmail"
    base = "https://www.1secmail.com/api/v1/"

    async def create_address(self):
        # 1secmail provides random mailbox
        stat, ct, text = await self._get(self.base + "?action=genRandomMailbox&count=1")
        if stat != 200:
            raise RuntimeError(f"1secmail create HTTP {stat}")
        try:
            data = json.loads(text)
            return {"email": data[0], "provider": self.name}
        except Exception:
            raise RuntimeError("1secmail parse failed")

    async def list_messages(self, email, token=None):
        login, domain = email.split("@")
        url = f"{self.base}?action=getMessages&login={urllib.parse.quote(login)}&domain={urllib.parse.quote(domain)}"
        stat, ct, text = await self._get(url)
        if stat != 200:
            raise RuntimeError(f"1secmail inbox HTTP {stat}")
        try:
            return json.loads(text)
        except Exception:
            raise RuntimeError("1secmail inbox parse failed")

    async def read_message(self, email, msg_id, token=None):
        login, domain = email.split("@")
        url = f"{self.base}?action=readMessage&login={urllib.parse.quote(login)}&domain={urllib.parse.quote(domain)}&id={urllib.parse.quote(str(msg_id))}"
        stat, ct, text = await self._get(url)
        if stat != 200:
            raise RuntimeError(f"1secmail read HTTP {stat}")
        try:
            return json.loads(text)
        except Exception:
            raise RuntimeError("1secmail read parse failed")

    async def delete_message(self, email, msg_id, token=None):
        # 1secmail doesn't support delete message via API in all cases -> noop
        raise NotImplementedError

    async def delete_account(self, email, token=None):
        # not supported
        raise NotImplementedError

# 3) GetNada
class GetNadaProvider(BaseProvider):
    name = "getnada"
    base = "https://getnada.com/api/v1"

    async def create_address(self):
        # pick domain from /domains if possible
        domain = "getnada.com"
        try:
            stat, ct, text = await self._get(self.base + "/domains")
            if stat == 200:
                domains = json.loads(text)
                # domains could be list of strings or list of objects
                if isinstance(domains, list) and domains:
                    sample = random.choice(domains)
                    if isinstance(sample, dict):
                        domain = sample.get("domain", domain)
                    elif isinstance(sample, str):
                        domain = sample
            else:
                domain = "getnada.com"
        except Exception:
            domain = "getnada.com"
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@{domain}", "provider": self.name}

    async def list_messages(self, email, token=None):
        url = f"{self.base}/inboxes/{urllib.parse.quote(email)}"
        stat, ct, text = await self._get(url)
        if stat != 200:
            raise RuntimeError(f"getnada inbox HTTP {stat}")
        try:
            data = json.loads(text)
            return data.get("msgs", [])
        except Exception:
            raise RuntimeError("getnada parse failed")

    async def read_message(self, email, msg_id, token=None):
        url = f"{self.base}/messages/{urllib.parse.quote(str(msg_id))}"
        stat, ct, text = await self._get(url)
        if stat != 200:
            raise RuntimeError(f"getnada read HTTP {stat}")
        try:
            return json.loads(text)
        except Exception:
            raise RuntimeError("getnada read parse failed")

    async def delete_message(self, email, msg_id, token=None):
        url = f"{self.base}/messages/{urllib.parse.quote(str(msg_id))}"
        # getnada supports DELETE
        async with self.session.delete(url) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"getnada delete HTTP {resp.status}")

    async def delete_account(self, email, token=None):
        # not supported
        raise NotImplementedError

# 4) Maildrop (GraphQL)
class MaildropProvider(BaseProvider):
    name = "maildrop"
    base = "https://api.maildrop.cc/graphql"

    async def create_address(self):
        # maildrop uses mailbox name without creation
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@maildrop.cc", "provider": self.name}

    async def list_messages(self, email, token=None):
        mailbox = email.split("@")[0]
        query = {"query": f'query{{inbox(mailbox:\"{mailbox}\"){{id mailfrom subject}}}}'}
        stat, ct, text = await self._post(self.base, json_data=query)
        if stat != 200:
            raise RuntimeError(f"maildrop inbox HTTP {stat}")
        data = json.loads(text)
        return data.get("data", {}).get("inbox", [])

    async def read_message(self, email, msg_id, token=None):
        mailbox = email.split("@")[0]
        query = {"query": f'query{{message(mailbox:\"{mailbox}\",id:\"{msg_id}\"){{id headerfrom subject data html}}}}'}
        stat, ct, text = await self._post(self.base, json_data=query)
        if stat != 200:
            raise RuntimeError(f"maildrop read HTTP {stat}")
        data = json.loads(text)
        return data.get("data", {}).get("message", {})

    async def delete_message(self, email, msg_id, token=None):
        mailbox = email.split("@")[0]
        mutation = {"query": f'mutation{{delete(mailbox:\"{mailbox}\",id:\"{msg_id}\")}}'}
        stat, ct, text = await self._post(self.base, json_data=mutation)
        if stat != 200:
            raise RuntimeError(f"maildrop delete HTTP {stat}")

    async def delete_account(self, email, token=None):
        # not supported
        raise NotImplementedError

# 5) Mailsac (public endpoints)
class MailsacProvider(BaseProvider):
    name = "mailsac"
    base = "https://mailsac.com/api"

    async def create_address(self):
        prefix = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {"email": f"{prefix}@mailsac.com", "provider": self.name}

    async def list_messages(self, email, token=None):
        url = f"https://mailsac.com/api/addresses/{urllib.parse.quote(email)}/messages"
        stat, ct, text = await self._get(url)
        if stat != 200:
            raise RuntimeError(f"mailsac inbox HTTP {stat}")
        return json.loads(text)

    async def read_message(self, email, msg_id, token=None):
        # some mailsac endpoints expose raw text; this attempts a common pattern
        url = f"https://mailsac.com/api/text/{urllib.parse.quote(email)}/{urllib.parse.quote(msg_id)}"
        stat, ct, text = await self._get(url)
        if stat != 200:
            # fallback: try message JSON endpoint
            url2 = f"https://mailsac.com/api/addresses/{urllib.parse.quote(email)}/messages/{urllib.parse.quote(msg_id)}"
            stat2, ct2, text2 = await self._get(url2)
            if stat2 != 200:
                raise RuntimeError(f"mailsac read HTTP {stat}/{stat2}")
            try:
                return json.loads(text2)
            except Exception:
                return {"body": text2}
        return {"body": text}

    async def delete_message(self, email, msg_id, token=None):
        # public delete may require key; skip
        raise NotImplementedError

    async def delete_account(self, email, token=None):
        # not supported
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
        # instantiate providers
        self.providers = {
            "mailtm": MailTmProvider(),
            "1secmail": OneSecMailProvider(),
            "getnada": GetNadaProvider(),
            "maildrop": MaildropProvider(),
            "mailsac": MailsacProvider(),
        }
        self.provider_order = list(DEFAULT_PROVIDERS)

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

    # Normalize message list for presentation
    def _format_inbox_items(self, provider_name, raw_items):
        out = []
        if not raw_items:
            return out
        if provider_name == "mailtm":
            for r in raw_items:
                out.append({"id": r.get("id"), "from": r.get("from"), "subject": r.get("subject")})
        elif provider_name == "1secmail":
            for r in raw_items:
                out.append({"id": r.get("id"), "from": r.get("from"), "subject": r.get("subject")})
        elif provider_name == "getnada":
            for r in raw_items:
                out.append({"id": r.get("uid") or r.get("id"), "from": r.get("f") or r.get("from"), "subject": r.get("s") or r.get("subject")})
        elif provider_name == "maildrop":
            for r in raw_items:
                out.append({"id": r.get("id"), "from": r.get("mailfrom") or r.get("headerfrom"), "subject": r.get("subject")})
        elif provider_name == "mailsac":
            for r in raw_items:
                out.append({"id": r.get("_id") or r.get("id") or r.get("msgid"), "from": r.get("from"), "subject": r.get("subject") or r.get("sub")})
        else:
            # try generic
            for r in raw_items:
                out.append({"id": r.get("id") or r.get("uid") or r.get("_id"), "from": r.get("from") or r.get("f"), "subject": r.get("subject") or r.get("s")})
        return out

    # get provider instance by name
    def _prov_by_name(self, name):
        return self.providers.get(name)

    # get preferred provider for user
    def _get_user_provider_name(self, uid):
        return self.db.get(self.name, self._prov_key(uid), self.provider_order[0])

    # return active email record (dict) or None
    def _get_active_record(self, uid):
        active = self.db.get(self.name, self._active_key(uid))
        if not active:
            return None
        history = self._get_history(uid)
        for rec in history:
            if rec.get("email") == active:
                return rec
        return None

    # add new record to history
    def _add_record(self, uid, record):
        history = self._get_history(uid)
        # store record keys: email, provider, created, meta(dict)
        history.insert(0, record)
        self._save_history(uid, history)
        self.db.set(self.name, self._active_key(uid), record["email"])

    # ------------- commands -------------
    @loader.command()
    async def tprovider(self, message):
        """Установить провайдера: .tprovider mailtm|1secmail|getnada|maildrop|mailsac"""
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
        """Создать новый временный email: .tempmail [provider]"""
        args = utils.get_args_raw(message).split()
        preferred = args[0].lower() if args else None
        uid = message.from_id
        providers_try = [preferred] + [p for p in self.provider_order if p != preferred] if preferred else list(self.provider_order)
        tried = []
        last_err = None

        await utils.answer(message, self.strings["trying"].format(preferred or providers_try[0]))

        for p in providers_try:
            prov = self._prov_by_name(p)
            if not prov:
                continue
            try:
                info = await prov.create_address()
                # info expected: dict with email, provider, optional token/meta
                email = info.get("email")
                rec = {
                    "email": email,
                    "provider": p,
                    "created": datetime.utcnow().isoformat(),
                    "meta": info
                }
                self._add_record(uid, rec)
                self.db.set(self.name, self._prov_key(uid), p)
                return await utils.answer(message, self.strings["created"].format(email, p))
            except Exception as e:
                logger.warning("Provider %s create failed: %s", p, e)
                tried.append(p)
                last_err = str(e)[:RAW_LOG_LEN]
                # store last raw for debug
                self.db.set(self.name, self._lastraw_key(uid), {"provider": p, "error": last_err})
                continue

        await utils.answer(message, self.strings["api_error"].format(",".join(tried), last_err or "all providers failed"))

    @loader.command()
    async def mymails(self, message):
        """Показать все созданные тобой адреса"""
        uid = message.from_id
        history = self._get_history(uid)
        if not history:
            return await utils.answer(message, "📭 У тебя нет сохранённых адресов.")
        text = ""
        for rec in history:
            act = " (active)" if rec.get("email") == self.db.get(self.name, self._active_key(uid)) else ""
            text += f"• <code>{rec.get('email')}</code> | {rec.get('provider')} | {rec.get('created')}{act}\n"
        return await utils.answer(message, self.strings["mails_list"].format(text))

    @loader.command()
    async def usemail(self, message):
        """Сделать адрес активным: .usemail <email>"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, "❌ Укажи email: .usemail <email>")
        uid = message.from_id
        email = args[0]
        history = self._get_history(uid)
        if not any(r.get("email") == email for r in history):
            return await utils.answer(message, "❌ Такой адрес не найден в истории.")
        self.db.set(self.name, self._active_key(uid), email)
        return await utils.answer(message, self.strings["set_active"].format(email))

    @loader.command()
    async def tinbox(self, message):
        """Показать входящие: .tinbox [email]"""
        args = utils.get_args_raw(message).split()
        uid = message.from_id
        target_email = args[0] if args else self.db.get(self.name, self._active_key(uid))
        if not target_email:
            return await utils.answer(message, self.strings["no_mail"])
        # find provider metadata
        history = self._get_history(uid)
        rec = next((r for r in history if r.get("email") == target_email), None)
        if not rec:
            return await utils.answer(message, "❌ Этот адрес не из твоей истории.")
        provider = rec.get("provider")
        last_err = None
        tried = []
        # some providers require token in meta (mail.tm)
        meta = rec.get("meta", {})
        for p in [provider] + [x for x in self.provider_order if x != provider]:
            prov_try = self._prov_by_name(p)
            if not prov_try:
                continue
            try:
                if p == "mailtm":
                    token = meta.get("token")
                    msgs = await prov_try.list_messages(target_email, token)
                    norm = self._format_inbox_items(p, msgs)
                else:
                    msgs = await prov_try.list_messages(target_email)
                    norm = self._format_inbox_items(p, msgs)
                if not norm:
                    return await utils.answer(message, self.strings["empty"])
                text = ""
                for m in norm:
                    text += f"• <code>{m.get('id')}</code> | {m.get('from','?')} | {m.get('subject','(no subject)')}\n"
                return await utils.answer(message, self.strings["inbox"].format(p, text))
            except Exception as e:
                logger.warning("tinbox %s failed for %s: %s", p, target_email, e)
                tried.append(p)
                last_err = str(e)[:RAW_LOG_LEN]
                self.db.set(self.name, self._lastraw_key(uid), {"provider": p, "error": last_err})
                continue
        await utils.answer(message, self.strings["api_error"].format(",".join(tried), last_err or "no provider succeeded"))

    @loader.command()
    async def tread(self, message):
        """Прочитать письмо: .tread <id> [email]"""
        args = utils.get_args_raw(message).split()
        if not args:
            return await utils.answer(message, self.strings["read_usage"])
        mid = args[0]
        uid = message.from_id
        target_email = args[1] if len(args) > 1 else self.db.get(self.name, self._active_key(uid))
        if not target_email:
            return await utils.answer(message, self.strings["no_mail"])
        history = self._get_history(uid)
        rec = next((r for r in history if r.get("email") == target_email), None)
        if not rec:
            return await utils.answer(message, "❌ Этот адрес не из твоей истории.")
        provider = rec.get("provider")
        meta = rec.get("meta", {})
        tried = []
        last_err = None
        for p in [provider] + [x for x in self.provider_order if x != provider]:
            prov_try = self._prov_by_name(p)
            if not prov_try:
                continue
            try:
                if p == "mailtm":
                    token = meta.get("token")
                    msg = await prov_try.read_message(target_email, mid, token)
                    frm = msg.get("from")
                    subj = msg.get("subject")
                    body = msg.get("text") or msg.get("html") or msg.get("body") or "(пусто)"
                elif p == "1secmail":
                    msg = await prov_try.read_message(target_email, mid)
                    frm = msg.get("from")
                    subj = msg.get("subject")
                    body = msg.get("textBody") or msg.get("body") or msg.get("htmlBody") or "(пусто)"
                elif p == "getnada":
                    msg = await prov_try.read_message(target_email, mid)
                    frm = msg.get("from") or msg.get("f")
                    subj = msg.get("subject") or msg.get("s")
                    body = msg.get("text") or msg.get("html") or "(пусто)"
                elif p == "maildrop":
                    msg = await prov_try.read_message(target_email, mid)
                    frm = msg.get("headerfrom") or msg.get("mailfrom")
                    subj = msg.get("subject")
                    body = msg.get("data") or msg.get("html") or "(пусто)"
                elif p == "mailsac":
                    msg = await prov_try.read_message(target_email, mid)
                    if isinstance(msg, dict):
                        frm = msg.get("from") or "?"
                        subj = msg.get("subject") or "(no subject)"
                        body = msg.get("body") or msg.get("text") or "(пусто)"
                    else:
                        frm = "?"
                        subj = "(no subject)"
                        body = str(msg)
                else:
                    raise RuntimeError("unknown provider")
                await utils.answer(message, self.strings["letter"].format(frm, subj, body))
                return
            except Exception as e:
                logger.warning("tread with %s failed: %s", p, e)
                tried.append(p)
                last_err = str(e)[:RAW_LOG_LEN]
                self.db.set(self.name, self._lastraw_key(uid), {"provider": p, "error": last_err})
                continue
        await utils.answer(message, self.strings["api_error"].format(",".join(tried), last_err or "all providers failed"))

    @loader.command()
    async def delmail(self, message):
        """Удалить адрес: .delmail [email] (удалит аккаунт, если провайдер позволяет)"""
        args = utils.get_args_raw(message).split()
        uid = message.from_id
        target_email = args[0] if args else self.db.get(self.name, self._active_key(uid))
        if not target_email:
            return await utils.answer(message, self.strings["no_mail"])
        history = self._get_history(uid)
        rec = next((r for r in history if r.get("email") == target_email), None)
        if not rec:
            return await utils.answer(message, "❌ Этот адрес не из твоей истории.")
        provider = rec.get("provider")
        prov = self._prov_by_name(provider)
        meta = rec.get("meta", {})
        try:
            if provider == "mailtm":
                token = meta.get("token")
                await prov.delete_account(target_email, token)
            else:
                # providers often don't support account deletion; attempt message deletion for some providers then remove locally
                try:
                    msgs = []
                    if provider == "getnada":
                        msgs = await prov.list_messages(target_email)
                        for m in msgs:
                            mid = m.get("uid") or m.get("id")
                            try:
                                await prov.delete_message(target_email, mid)
                            except Exception:
                                pass
                except Exception:
                    pass
            # remove from history
            new_hist = [r for r in history if r.get("email") != target_email]
            self._save_history(uid, new_hist)
            if self.db.get(self.name, self._active_key(uid)) == target_email:
                self.db.set(self.name, self._active_key(uid), new_hist[0]["email"] if new_hist else None)
            await utils.answer(message, self.strings["deleted"].format(target_email, provider))
        except Exception as e:
            logger.exception("delmail failed")
            await utils.answer(message, self.strings["api_error"].format(provider, str(e)[:RAW_LOG_LEN]))

    @loader.command()
    async def tinfo(self, message):
        """Показать активный email и провайдера"""
        uid = message.from_id
        active = self.db.get(self.name, self._active_key(uid))
        prov = self._get_user_provider_name(uid)
        if not active:
            return await utils.answer(message, "Почта не создана. Используй .tempmail")
        return await utils.answer(message, self.strings["info"].format(active, prov))

    @loader.command()
    async def tdebug(self, message):
        """Debug: показать последний raw response и статус провайдера"""
        uid = message.from_id
        last = self.db.get(self.name, self._lastraw_key(uid), {})
        provider = last.get("provider", self._get_user_provider_name(uid))
        raw = last.get("error", "Нет последних записей")
        await utils.answer(message, self.strings["debug"].format(provider, raw))

    # optional: cleanup on unload
    async def on_unload(self):
        for p in self.providers.values():
            try:
                await p.close()
            except Exception:
                pass
