# meta developer: @Dany23s
# scope: hikka_only
# scope: hikka_min 1.6.3

import aiohttp
import random
import string
import json
from datetime import datetime
from .. import loader, utils


# ==============================
# PROVIDERS
# ==============================

class MailTM:
    name = "mailtm"
    base = "https://api.mail.tm"

    async def create(self, nick=None):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{self.base}/domains") as r:
                data = await r.json()
                domain = random.choice(data["hydra:member"])["domain"]

            if not nick:
                nick = "hikka" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

            email = f"{nick}@{domain}"
            password = "Hikka" + ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            await s.post(f"{self.base}/accounts", json={"address": email, "password": password})
            async with s.post(f"{self.base}/token", json={"address": email, "password": password}) as r:
                token = (await r.json())["token"]

        return {"email": email, "token": token}

    async def messages(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{self.base}/messages", headers=headers) as r:
                data = await r.json()
                return data.get("hydra:member", [])


class OneSecMail:
    name = "1secmail"

    async def create(self, nick=None):
        if not nick:
            nick = "hikka" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

        domains = ["1secmail.com", "1secmail.org", "1secmail.net"]
        domain = random.choice(domains)

        return {"email": f"{nick}@{domain}"}

    async def messages(self, email):
        login, domain = email.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                return await r.json()


class GuerrillaMail:
    name = "guerrillamail"

    async def create(self, nick=None):
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.guerrillamail.com/ajax.php?f=get_email_address") as r:
                data = await r.json()
                return {"email": data["email_addr"], "sid": data["sid_token"]}

    async def messages(self, sid):
        url = f"https://api.guerrillamail.com/ajax.php?f=get_email_list&sid_token={sid}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                data = await r.json()
                return data.get("list", [])


# ==============================
# MODULE
# ==============================

@loader.tds
class MultiTempMail(loader.Module):
    """Multi TempMail AutoSave"""

    strings = {"name": "MultiTempMail"}

    def __init__(self):
        self.providers = {
            "mailtm": MailTM(),
            "1secmail": OneSecMail(),
            "guerrillamail": GuerrillaMail()
        }

    def _get(self, uid):
        return self.get("data", {}).get(str(uid), [])

    def _save(self, uid, data):
        all_data = self.get("data", {})
        all_data[str(uid)] = data
        self.set("data", all_data)

    @loader.command()
    async def tempmail(self, message):
        """
        .tempmail [nick] [provider]
        """
        args = utils.get_args_raw(message).split()
        nick = args[0] if args else None
        provider_name = args[1] if len(args) > 1 else random.choice(list(self.providers.keys()))

        if provider_name not in self.providers:
            return await utils.answer(message, "❌ Провайдер не найден. Используй .tempproviders")

        provider = self.providers[provider_name]

        try:
            info = await provider.create(nick)
            rec = {
                "email": info["email"],
                "provider": provider_name,
                "meta": info,
                "created": datetime.utcnow().isoformat()
            }

            history = self._get(message.from_id)
            history.append(rec)
            self._save(message.from_id, history)

            await utils.answer(
                message,
                f"📬 <b>Создана:</b>\n<code>{info['email']}</code>\n🌍 {provider_name}"
            )
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка: {e}")

    @loader.command()
    async def tempmails(self, message):
        """
        Показать почты
        """
        history = self._get(message.from_id)
        if not history:
            return await utils.answer(message, "❌ Почт нет")

        text = "📨 <b>Твои почты:</b>\n\n"
        for rec in history:
            text += f"📧 <code>{rec['email']}</code> ({rec['provider']})\n"
        await utils.answer(message, text)

    @loader.command()
    async def tempmaildel(self, message):
        """
        .tempmaildel email
        """
        email = utils.get_args_raw(message).strip()
        history = self._get(message.from_id)
        history = [h for h in history if h["email"] != email]
        self._save(message.from_id, history)
        await utils.answer(message, "🗑 Удалено")

    @loader.command()
    async def tempproviders(self, message):
        """
        Список провайдеров
        """
        text = "🌍 <b>Доступные провайдеры:</b>\n\n"
        for p in self.providers.keys():
            text += f"• {p}\n"
        await utils.answer(message, text)
