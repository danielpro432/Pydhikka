import aiohttp, asyncio, json, random, string
from datetime import datetime
from .. import loader, utils

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux)",
    "Accept": "application/json",
}

MAX_ADDRESSES = 10

class MailTmProvider:
    """Простейший провайдер mail.tm"""
    base = "https://api.mail.tm"

    async def create_address(self):
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            r = await s.get(f"{self.base}/domains")
            data = await r.json()
            domain = random.choice(data.get("hydra:member", [{"domain": "mail.tm"}]))["domain"]
            login = "hikka" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            address = f"{login}@{domain}"
            password = "HikkaPass" + "".join(random.choices(string.digits, k=4))
            await s.post(f"{self.base}/accounts", json={"address": address, "password": password})
            tok_r = await s.post(f"{self.base}/token", json={"address": address, "password": password})
            token = (await tok_r.json()).get("token")
            return {"email": address, "provider": "mailtm", "token": token, "password": password}

    async def list_messages(self, token):
        headers = {**HEADERS, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession(headers=headers) as s:
            r = await s.get(f"{self.base}/messages")
            return (await r.json()).get("hydra:member", [])

    async def read_message(self, token, msg_id):
        headers = {**HEADERS, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession(headers=headers) as s:
            r = await s.get(f"{self.base}/messages/{msg_id}")
            return await r.json()

@loader.tds
class TempMail(loader.Module):
    """Удобные команды для TempMail (mail.tm)"""

    strings = {
        "name": "TempMail",
        "created": "📧 Создан адрес:\n<code>{}</code>",
        "mails_list": "📜 Твои адреса:\n{}",
        "no_mail": "❌ У тебя нет созданных адресов",
        "set_active": "✅ Активный адрес: <code>{}</code>",
        "inbox_empty": "📭 Входящие пусты",
        "letter": "📩 Письмо от <code>{}</code>\n<b>Тема:</b> {title}\n\n{body}",
        "deleted": "🗑️ Удалён адрес: <code>{}</code>",
    }

    def __init__(self):
        self.name = "TempMail"
        self.provider = MailTmProvider()

    # ------------------- Commands -------------------
    @loader.command()
    async def tempmail(self, message):
        """Создать новый email"""
        uid = message.from_id
        info = await self.provider.create_address()
        history = self._get_history(uid)
        if len(history) >= MAX_ADDRESSES:
            history.pop(-1)
        history.insert(0, info)
        self.db.set(self.name, f"addrs_{uid}", history)
        self.db.set(self.name, f"active_{uid}", info["email"])
        await utils.answer(message, self.strings["created"].format(info["email"]))

    @loader.command()
    async def mymails(self, message):
        """Показать все созданные адреса"""
        uid = message.from_id
        history = self._get_history(uid)
        if not history: return await utils.answer(message, self.strings["no_mail"])
        text = ""
        active = self.db.get(self.name, f"active_{uid}", "")
        for r in history:
            act = " (active)" if r["email"] == active else ""
            text += f"• <code>{r['email']}</code>{act}\n"
        await utils.answer(message, self.strings["mails_list"].format(text))

    @loader.command()
    async def setmail(self, message):
        """Сделать активным адрес: .setmail <email>"""
        uid = message.from_id
        args = utils.get_args_raw(message)
        if not args: return await utils.answer(message, "❌ Укажи email")
        history = self._get_history(uid)
        if any(r["email"] == args for r in history):
            self.db.set(self.name, f"active_{uid}", args)
            await utils.answer(message, self.strings["set_active"].format(args))
        else:
            await utils.answer(message, "❌ Email не найден в истории")

    @loader.command()
    async def inbox(self, message):
        """Посмотреть письма активной почты"""
        uid = message.from_id
        active = self.db.get(self.name, f"active_{uid}")
        if not active: return await utils.answer(message, self.strings["no_mail"])
        token = self._get_token(uid, active)
        msgs = await self.provider.list_messages(token)
        if not msgs: return await utils.answer(message, self.strings["inbox_empty"])
        text = ""
        for m in msgs:
            text += f"• <code>{m['id']}</code> | {m.get('from', {}).get('address','?')} | {m.get('subject','(без темы)')}\n"
        await utils.answer(message, f"📥 Входящие:\n{text}")

    @loader.command()
    async def readmail(self, message):
        """Прочитать письмо: .readmail <id>"""
        uid = message.from_id
        args = utils.get_args_raw(message)
        if not args: return await utils.answer(message, "❌ Укажи ID письма")
        active = self.db.get(self.name, f"active_{uid}")
        if not active: return await utils.answer(message, self.strings["no_mail"])
        token = self._get_token(uid, active)
        msg = await self.provider.read_message(token, args)
        body = msg.get("text", msg.get("html",""))
        await utils.answer(message, self.strings["letter"].format(msg.get("from",{}).get("address","?"), title=msg.get("subject","(без темы)"), body=body))

    @loader.command()
    async def delmail(self, message):
        """Удалить email: .delmail <email>"""
        uid = message.from_id
        args = utils.get_args_raw(message)
        if not args: return await utils.answer(message, "❌ Укажи email")
        history = self._get_history(uid)
        history = [r for r in history if r["email"] != args]
        self.db.set(self.name, f"addrs_{uid}", history)
        active = self.db.get(self.name, f"active_{uid}")
        if active == args and history:
            self.db.set(self.name, f"active_{uid}", history[0]["email"])
        elif not history:
            self.db.set(self.name, f"active_{uid}", None)
        await utils.answer(message, self.strings["deleted"].format(args))

    # ------------------- Helpers -------------------
    def _get_history(self, uid):
        return self.db.get(self.name, f"addrs_{uid}", [])

    def _get_token(self, uid, email):
        history = self._get_history(uid)
        for r in history:
            if r["email"] == email:
                return r.get("token")
        return None
