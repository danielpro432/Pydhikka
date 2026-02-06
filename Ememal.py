# meta developer: @yourname
# meta name: MailGen
# meta desc: Генератор временных почт (до 10 штук)

from .. import loader, utils
import random
import string
import requests

DOMAINS = [
    "1secmail.com",
    "1secmail.org",
    "1secmail.net"
]

@loader.tds
class MailGen(loader.Module):
    """Генератор временных email"""

    strings = {
        "name": "MailGen",
        "generated": "📧 Сгенерированные почты:\n{}",
        "limit": "❌ Максимум 10 почт за раз",
        "deleted": "🗑 Почта удалена: {}",
        "empty": "📭 Почт нет",
        "cleared": "🧹 Все почты удалены"
    }

    def __init__(self):
        self.mails = []

    def random_login(self, length=10):
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

    @loader.command()
    async def genmail(self, message):
        """Сгенерировать email (.genmail 5)"""
        args = utils.get_args_raw(message)
        count = int(args) if args.isdigit() else 1

        if count > 10:
            await utils.answer(message, self.strings["limit"])
            return

        new_mails = []
        for _ in range(count):
            login = self.random_login()
            domain = random.choice(DOMAINS)
            email = f"{login}@{domain}"
            self.mails.append(email)
            new_mails.append(email)

        await utils.answer(
            message,
            self.strings["generated"].format("\n".join(new_mails))
        )

    @loader.command()
    async def mails(self, message):
        """Показать все почты"""
        if not self.mails:
            await utils.answer(message, self.strings["empty"])
            return

        await utils.answer(message, "📬 Почты:\n" + "\n".join(self.mails))

    @loader.command()
    async def delmail(self, message):
        """Удалить почту (.delmail email)"""
        email = utils.get_args_raw(message)
        if email in self.mails:
            self.mails.remove(email)
            await utils.answer(message, self.strings["deleted"].format(email))
        else:
            await utils.answer(message, "❌ Почта не найдена")

    @loader.command()
    async def clearmails(self, message):
        """Удалить все почты"""
        self.mails.clear()
        await utils.answer(message, self.strings["cleared"])
