# CustomOnlineStatus (Hikka module)
# Показывает кастомный статус вместо онлайн
# Работает в Termux/Linux (Python 3.11+)

from .. import loader, utils

@loader.tds
class CustomOnlineStatus(loader.Module):
    """Меняет статус пользователя на кастомный"""

    strings = {
        "name": "CustomOnline",
        "status_set": "✅ Статус изменён на: {}"
    }

    def __init__(self):
        self.name = "CustomOnline"
        # Кастомное сообщение, вместо 'онлайн'
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

    @loader.handler()
    async def on_message(self, message):
        """Перехватываем сообщения и меняем онлайн статус при необходимости"""
        try:
            # Здесь пример изменения online -> кастомный текст
            # В Хероку через UserLand это будет отображаться только через модуль
            # Для Hikka заменяем в info о пользователе
            if hasattr(message, "sender") and hasattr(message.sender, "status"):
                message.sender.status = self.custom_status
        except:
            pass
