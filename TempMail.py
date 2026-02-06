# tempmail.py
from .. import loader, utils
import aiohttp
import asyncio

@loader.tds
class TempMailMod(loader.Module):
    """TempMail через 1secmail API"""

    strings = {"name": "TempMail"}

    async def tempmailcmd(self, message):
        """.tempmail — создать новый временный email"""
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1") as resp:
                emails = await resp.json()
                self.email = emails[0]
        await message.edit(f"📧 Ваш временный email:\n{self.email}")

    async def inboxcmd(self, message):
        """.inbox — показать список писем"""
        if not hasattr(self, "email"):
            await message.edit("❌ Сначала создайте email через .tempmail")
            return
        login, domain = self.email.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                msgs = await resp.json()
        if not msgs:
            await message.edit("📭 Входящие пусты")
            return
        text = ""
        for m in msgs:
            text += f"ID: {m['id']} | От: {m['from']} | Тема: {m['subject']}\n"
        await message.edit(f"📥 Входящие:\n{text}")

    async def readcmd(self, message):
        """.read <id> — прочитать письмо"""
        if not hasattr(self, "email"):
            await message.edit("❌ Сначала создайте email через .tempmail")
            return
        args = utils.get_args(message)
        if not args:
            await message.edit("❌ Укажите ID письма: .read <id>")
            return
        email_id = args[0]
        login, domain = self.email.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={email_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                msg = await resp.json()
        body = msg.get("body", "(нет текста)")
        await message.edit(f"📩 От: {msg.get('from')}\nТема: {msg.get('subject')}\n\n{body}")
