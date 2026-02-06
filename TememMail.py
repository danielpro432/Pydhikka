import asyncio import aiohttp import logging from .. import loader, utils

logger = logging.getLogger(name)

class BaseMailProvider: async def create_address(self): ... async def list_messages(self): ... async def read_message(self, msg_id): ... async def delete_message(self, msg_id): ... async def delete_account(self): ...

class MailTmProvider(BaseMailProvider): def init(self): self.base = "https://api.mail.tm" self.token = None self.address = None self.password = "hikka_temp_pass" self.session = aiohttp.ClientSession()

async def create_address(self):
    dom_resp = await self.session.get(f"{self.base}/domains")
    domains = (await dom_resp.json())["hydra:member"]
    domain = domains[0]["domain"]
    self.address = f"hikka_{utils.rand(6)}@{domain}"

    await self.session.post(f"{self.base}/accounts", json={
        "address": self.address,
        "password": self.password
    })
    token_resp = await self.session.post(f"{self.base}/token", json={
        "address": self.address,
        "password": self.password
    })
    self.token = (await token_resp.json())["token"]
    return self.address

async def _auth_headers(self):
    return {"Authorization": f"Bearer {self.token}"}

async def list_messages(self):
    resp = await self.session.get(f"{self.base}/messages", headers=await self._auth_headers())
    return await resp.json()

async def read_message(self, msg_id):
    resp = await self.session.get(f"{self.base}/messages/{msg_id}", headers=await self._auth_headers())
    return await resp.json()

async def delete_message(self, msg_id):
    await self.session.delete(f"{self.base}/messages/{msg_id}", headers=await self._auth_headers())

async def delete_account(self):
    await self.session.delete(f"{self.base}/me", headers=await self._auth_headers())

class GetNadaProvider(BaseMailProvider): def init(self): self.base = "https://getnada.com/api/v1" self.domains = ["getnada.com", "nada.ltd"] self.address = f"hikka_{utils.rand(6)}@{self.domains[0]}" self.session = aiohttp.ClientSession()

async def create_address(self):
    return self.address

async def list_messages(self):
    resp = await self.session.get(f"{self.base}/inboxes/{self.address}")
    return (await resp.json()).get("msgs", [])

async def read_message(self, msg_id):
    resp = await self.session.get(f"{self.base}/messages/{msg_id}")
    return await resp.json()

async def delete_message(self, msg_id):
    await self.session.delete(f"{self.base}/messages/{msg_id}")

async def delete_account(self):
    pass  # Not supported

@loader.tds class TempMailModule(loader.Module): """Модуль временной почты с несколькими провайдерами"""

strings = {"name": "TempMail"}

def __init__(self):
    self.providers = {
        "mailtm": MailTmProvider(),
        "getnada": GetNadaProvider()
    }
    self.user_data = {}

async def client_ready(self, client, db):
    self.db = db
    self._client = client

def _get_provider(self, user_id):
    prov = self.db.get(self.name, f"prov_{user_id}", "mailtm")
    return self.providers.get(prov, self.providers["mailtm"])

@loader.command()
async def tempmail(self, m):
    """Создать новый email"""
    prov = self._get_provider(m.from_id)
    addr = await prov.create_address()
    mails = self.db.get(self.name, f"addrs_{m.from_id}", [])
    mails.append(addr)
    self.db.set(self.name, f"addr_{m.from_id}", addr)
    self.db.set(self.name, f"addrs_{m.from_id}", mails)
    await utils.answer(m, f"📧 Новый email: <code>{addr}</code>")

@loader.command()
async def inbox(self, m):
    """Показать входящие письма"""
    prov = self._get_provider(m.from_id)
    try:
        msgs = await prov.list_messages()
    except:
        return await utils.answer(m, "⚠️ Не удалось получить список писем.")
    if not msgs:
        return await utils.answer(m, "📭 Нет писем")
    text = "\n".join([f"• <code>{msg['id']}</code> | {msg.get('from', msg.get('f'))} | {msg.get('subject', '')}" for msg in msgs])
    await utils.answer(m, f"📥 Входящие:\n{text}")

@loader.command()
async def read(self, m):
    """Читать письмо по ID: .read <id>"""
    args = utils.get_args(m)
    if not args:
        return await utils.answer(m, "❌ Укажи ID письма: .read <id>")
    prov = self._get_provider(m.from_id)
    try:
        msg = await prov.read_message(args[0])
    except:
        return await utils.answer(m, "⚠️ Не удалось прочитать письмо.")
    body = msg.get("text", msg.get("html", msg.get("body", "(пусто)")))
    subj = msg.get("subject", "Без темы")
    await utils.answer(m, f"📨 <b>{subj}</b>\n<code>{body}</code>")

@loader.command()
async def delmail(self, m):
    """Удалить текущий email"""
    prov = self._get_provider(m.from_id)
    try:
        await prov.delete_account()
    except:
        pass
    self.db.set(self.name, f"addr_{m.from_id}", None)
    await utils.answer(m, "🗑️ Почта удалена.")

@loader.command()
async def mymails(self, m):
    """Список всех твоих почт"""
    mails = self.db.get(self.name, f"addrs_{m.from_id}", [])
    if not mails:
        return await utils.answer(m, "📭 Нет сохранённых email.")
    await utils.answer(m, "📜 Твои адреса:\n" + "\n".join([f"• <code>{x}</code>" for x in mails]))

@loader.command()
async def usemail(self, m):
    """Сменить активную почту: .usemail <email>"""
    args = utils.get_args(m)
    if not args:
        return await utils.answer(m, "❌ Укажи email")
    mails = self.db.get(self.name, f"addrs_{m.from_id}", [])
    if args[0] not in mails:
        return await utils.answer(m, "❌ Такой почты нет в истории")
    self.db.set(self.name, f"addr_{m.from_id}", args[0])
    await utils.answer(m, f"✅ Активен: <code>{args[0]}</code>")
