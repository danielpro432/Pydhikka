███████╗███╗   ███╗ █████╗ ██╗██╗

██╔════╝████╗ ████║██╔══██╗██║██║

█████╗  ██╔████╔██║███████║██║██║

██╔══╝  ██║╚██╔╝██║██╔══██║██║██║

███████╗██║ ╚═╝ ██║██║  ██║██║███████╗

╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝



Name: EmailGen

Description: Генератор временной почты (mail.tm + maildrop)

Author: ChatGPT (for Hikka 2026)



Команды:

.emailgen        — создать почту

.emailbox        — входящие

.emailread <id>  — читать письмо

.emaildel        — удалить почту

.emaillist       — список созданных почт

.emailuse <id>   — выбрать активную

import aiohttp import asyncio import random import string import logging

from .. import loader, utils

logger = logging.getLogger(name)

================= PROVIDERS =================

class MailTM: BASE = "https://api.mail.tm"

def __init__(self):
    self.address = None
    self.password = "hikka"
    self.token = None
    self.session = aiohttp.ClientSession()

async def create(self):
    r = await self.session.get(f"{self.BASE}/domains")
    domains = (await r.json())["hydra:member"]
    domain = random.choice(domains)["domain"]
    name = "hikka" + ''.join(random.choices(string.ascii_lowercase, k=6))
    self.address = f"{name}@{domain}"

    await self.session.post(f"{self.BASE}/accounts", json={
        "address": self.address,
        "password": self.password
    })
    r = await self.session.post(f"{self.BASE}/token", json={
        "address": self.address,
        "password": self.password
    })
    self.token = (await r.json())["token"]
    return self.address

def headers(self):
    return {"Authorization": f"Bearer {self.token}"}

async def inbox(self):
    r = await self.session.get(f"{self.BASE}/messages", headers=self.headers())
    return (await r.json())["hydra:member"]

async def read(self, mid):
    r = await self.session.get(f"{self.BASE}/messages/{mid}", headers=self.headers())
    return await r.json()

async def delete(self):
    await self.session.delete(f"{self.BASE}/me", headers=self.headers())

class MailDrop: BASE = "https://api.maildrop.cc/graphql"

def __init__(self):
    self.box = None
    self.session = aiohttp.ClientSession()

async def create(self):
    self.box = "hikka" + ''.join(random.choices(string.ascii_lowercase, k=6))
    return f"{self.box}@maildrop.cc"

async def inbox(self):
    q = {
        "query": f"query{{inbox(mailbox:\"{self.box}\"){{id subject mailfrom}}}}"
    }
    r = await self.session.post(self.BASE, json=q)
    return (await r.json())["data"]["inbox"]

async def read(self, mid):
    q = {
        "query": f"query{{message(mailbox:\"{self.box}\",id:\"{mid}\"){{subject data}}}}"
    }
    r = await self.session.post(self.BASE, json=q)
    return (await r.json())["data"]["message"]

async def delete(self):
    self.box = None

================= MODULE =================

@loader.tds class EmailGen(loader.Module): """Генератор временных email (mail.tm + maildrop)"""

strings = {"name": "EmailGen"}

async def client_ready(self, client, db):
    self.db = db
    self.client = client
    self.providers = {
        "mailtm": MailTM(),
        "maildrop": MailDrop()
    }

def _prov(self, uid):
    name = self.db.get(self.name, f"prov_{uid}", "mailtm")
    return self.providers[name]

@loader.command()
async def emailgen(self, m):
    p = self._prov(m.from_id)
    addr = await p.create()
    lst = self.db.get(self.name, f"list_{m.from_id}", [])
    lst.append(addr)
    self.db.set(self.name, f"list_{m.from_id}", lst)
    self.db.set(self.name, f"active_{m.from_id}", addr)
    await utils.answer(m, f"📧 <b>Email создан:</b> <code>{addr}</code>")

@loader.command()
async def emailbox(self, m):
    p = self._prov(m.from_id)
    msgs = await p.inbox()
    if not msgs:
        return await utils.answer(m, "📭 Писем нет")
    txt = "\n".join([f"• <code>{x['id']}</code> | {x.get('subject','')[:30]}" for x in msgs])
    await utils.answer(m, f"📥 Входящие:\n{txt}")

@loader.command()
async def emailread(self, m):
    args = utils.get_args(m)
    if not args:
        return await utils.answer(m, "ID письма?")
    p = self._prov(m.from_id)
    msg = await p.read(args[0])
    await utils.answer(m, f"📨 <b>{msg.get('subject')}</b>\n<code>{msg.get('data')}</code>")

@loader.command()
async def emaildel(self, m):
    p = self._prov(m.from_id)
    await p.delete()
    await utils.answer(m, "🗑️ Почта удалена")

@loader.command()
async def emaillist(self, m):
    lst = self.db.get(self.name, f"list_{m.from_id}", [])
    if not lst:
        return await utils.answer(m, "Нет почт")
    await utils.answer(m, "📜 Твои почты:\n" + "\n".join([f"• <code>{x}</code>" for x in lst]))
