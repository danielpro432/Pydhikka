# CustomStatus (Hikka module)
# Licensed under GNU AGPLv3
# Works in Termux/Linux/Heroku (Python 3.11+)
# Показывает кастомный статус вместо онлайн через команду

from .. import loader, utils

@loader.tds
class CustomStatusMod(loader.Module):
    """Кастомный статус вместо онлайн"""

    strings = {
        "name": "CustomStatus",
        "status_set": "✅ Статус установлен: <b>{}</b>",
        "status_show": "ℹ️ Текущий статус: <b>{}</b>",
        "status_none": "❌ Статус пока не установлен"
    }

    def __init__(self):
        self.name = "CustomStatus"
        self._status_db_key = "custom_status"

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    @loader.command()
    async def setstatus(self, message):
        """Установить кастомный статус вместо онлайн
        .setstatus текст"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "❌ Укажи текст статуса")
        self.db.set(self.name, self._status_db_key, args)
        await utils.answer(message, self.strings["status_set"].format(args))

    @loader.command()
    async def showstatus(self, message):
        """Показать текущий кастомный статус"""
        status = self.db.get(self.name, self._status_db_key)
        if not status:
            return await utils.answer(message, self.strings["status_none"])
        await utils.answer(message, self.strings["status_show"].format(status))

    @loader.command()
    async def resetstatus(self, message):
        """Сбросить кастомный статус"""
        self.db.set(self.name, self._status_db_key, None)
        await utils.answer(message, "♻️ Статус сброшен")
