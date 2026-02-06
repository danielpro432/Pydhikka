from .. import loader, utils
from telethon.tl.types import Message

@loader.tds
class MyEcho(loader.Module):
    """Echo сообщений одной командой"""

    strings = {
        "name": "MyEcho",
        "on": "✅ Echo включён",
        "off": "❌ Echo выключен",
        "no_text": "⚠️ Только текстовые сообщения повторяются."
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            "enabled", False,  # echo по умолчанию выключен
        )

    async def echcmd(self, message: Message):
        """
        Команда .ech — включает или выключает echo
        """
        self.config["enabled"] = not self.config["enabled"]
        text = self.strings["on"] if self.config["enabled"] else self.strings["off"]
        await utils.answer(message, text)

    async def watcher(self, message: Message):
        """
        Наблюдатель сообщений.
        Повторяет текстовые сообщения других пользователей, если echo включён
        """
        if not self.config["enabled"]:
            return  # если echo выключен — не реагируем
        if message.out:
            return  # свои сообщения не повторяем
        if not message.text:
            return  # если нет текста, не повторяем
        await message.respond(message.text)  # повторяем сообщение
