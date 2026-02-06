# ech.py
from hikka.modules import HikkaModule, loader
from hikka.types import ConfigValue

@loader.tds
class EchoMod(HikkaModule):
    """Простой модуль Echo"""

    strings = {"name": "Echo"}

    def __init__(self):
        # Создаём конфиг с ключом 'enabled', чтобы не было KeyError
        self.config = self.get_config()
        self.config.add(ConfigValue(
            key="enabled",
            value=True,
            label="Включить echo"
        ))

    @loader.command()
    async def echcmd(self, message):
        """Повторяет текст сообщения, если мод включен"""
        if not self.config["enabled"].value:
            await message.edit("Модуль отключен")
            return

        text = message.args  # получаем аргументы команды
        if not text:
            await message.edit("❌ Нет текста для повторения")
            return

        await message.respond(text)

    @loader.command()
    async def toggleechcmd(self, message):
        """Включает/выключает модуль Echo"""
        self.config["enabled"].value = not self.config["enabled"].value
        status = "включен" if self.config["enabled"].value else "выключен"
        await message.edit(f"✅ Echo теперь {status}")
