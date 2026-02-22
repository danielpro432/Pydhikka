# HideOnlineStatus (Hikka module)
# Для Хероку/Termux/Linux
# Заменяет онлайн на кастомный текст

from .. import loader, utils

@loader.tds
class HideOnlineStatus(loader.Module):
    """Меняет статус пользователя на кастомный"""

    strings = {
        "name": "HideOnline",
        "status_set": "✅ Статус установлен: {}",
        "status_show": "Текущий кастомный статус: {}"
    }

    def __init__(self):
        self.name = "HideOnline"
        self.custom_status = "никогда не был в сети"

    @loader.command()
    async def setstatus(self, message):
        """Установить кастомный статус
        .setstatus [текст] — поменять на свой текст
        """
        args = utils.get_args_raw(message)
        if args:
            self.custom_status = args
            await utils.answer(message, self.strings["status_set"].format(self.custom_status))
        else:
            await utils.answer(message, self.strings["status_show"].format(self.custom_status))

    @loader.command()
    async def getstatus(self, message):
        """Показать текущий кастомный статус"""
        await utils.answer(message, self.strings["status_show"].format(self.custom_status)) 
