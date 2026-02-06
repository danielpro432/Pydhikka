# meta developer: @yourname
# meta name: MailGenFull
# meta desc: Генератор временных email с чтением писем и сохранением

from .. import loader, utils
import random
import string
import requests
import json
import os

DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
SAVE_FILE = "mailgen_saved.json"

@loader.tds
class MailGenFull(loader.Module):
    """Генератор временных email с сохранением и чтением писем"""

    strings = {
        "name": "MailGenFull",
        "generated": "📧 Сгенерированные почты:\n{}",
        "limit": "❌ Максимум 10 почт",
        "deleted": "🗑 Почта удалена: {}",
        "empty": "📭 Почт нет",
        "cleared": "🧹 Все почты удалены",
        "noemails": "📭 Нет писем в этом ящике",
        "emails": "📬 Письма для {}:\n{}",
        "notfound": "❌ Почта не найдена"
    }

    def __init__(self):
        self.mails = []
        self.load_mails()

    # =================== Сохранение / Загрузка ===================
    def save_mails(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(self.mails, f)
        except Exception as e:
            print(f"[MailGenFull] Ошибка сохранения: {e}")

    def load_mails(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    self.mails = json.load(f)
            except Exception as e:
                print(f"[MailGenFull] Ошибка загрузки: {e}")
                self.mails = []

    # =================== Генерация ===================
    def random_login(self, length=10):
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

    @loader.command()
    async def genmail(self, message):
        """Сгенерировать email (.genmail 5)"""
        args = utils.get_args_raw(message)
        count = int(args) if args.isdigit() else 1

        if count + len(self.mails) > 10:
            await utils.answer(message, self.strings["limit"])
            return

        new_mails = []
        for _ in range(count):
            login = self.random_login()
            domain = random.choice(DOMAINS)
            email = f"{login}@{domain}"
            self.mails.append(email)
            new_mails.append(email)

        self.save_mails()
        await utils.answer(message, self.strings["generated"].format("\n".join(new_mails)))

    # =================== Просмотр почт ===================
    @loader.command()
    async def mails(self, message):
        """Показать все почты"""
        if not self.mails:
            await utils.answer(message, self.strings["empty"])
            return
        await utils.answer(message, "📬 Почты:\n" + "\n".join(self.mails))

    # =================== Удаление ===================
    @loader.command()
    async def delmail(self, message):
        """Удалить почту (.delmail email)"""
        email = utils.get_args_raw(message)
        if email in self.mails:
            self.mails.remove(email)
            self.save_mails()
            await utils.answer(message, self.strings["deleted"].format(email))
        else:
            await utils.answer(message, self.strings["notfound"])

    @loader.command()
    async def clearmails(self, message):
        """Удалить все почты"""
        self.mails.clear()
        self.save_mails()
        await utils.answer(message, self.strings["cleared"])

    # =================== Чтение писем ===================
    @loader.command()
    async def getmails(self, message):
        """Получить письма для конкретной почты (.getmails email)"""
        email = utils.get_args_raw(message)
        if email not in self.mails:
            await utils.answer(message, self.strings["notfound"])
            return

        login, domain = email.split("@")
        try:
            r = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}")
            data = r.json()
            if not data:
                await utils.answer(message, self.strings["noemails"])
                return

            output = []
            for mail in data:
                output.append(f"📌 ID: {mail['id']} | От: {mail['from']} | Тема: {mail['subject']}")

            await utils.answer(message, self.strings["emails"].format(email, "\n".join(output)))
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка при получении писем: {e}")

    @loader.command()
    async def readmail(self, message):
        """Прочитать письмо по ID (.readmail email id)"""
        args = utils.get_args_raw(message).split()
        if len(args) != 2:
            await utils.answer(message, "Использование: .readmail email id")
            return

        email, mail_id = args
        if email not in self.mails:
            await utils.answer(message, self.strings["notfound"])
            return

        login, domain = email.split("@")
        try:
            r = requests.get(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mail_id}")
            mail = r.json()
            text = mail.get("textBody") or mail.get("htmlBody") or "Нет текста"
            await utils.answer(message, f"📨 Письмо ID {mail_id}:\nОт: {mail['from']}\nТема: {mail['subject']}\n\n{text}")
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка при чтении письма: {e}")
