# meta developer: @you
# meta name: CountSpamSafe
# meta description: Безопасный спамер с настраиваемой задержкой

import asyncio
from telethon.errors import FloodWaitError
from .. import loader, utils

@loader.tds
class CountSpamSafe(loader.Module):
    """Максимально безопасный спамер с настраиваемой задержкой"""

    strings = {"name": "CountSpamSafe"}

    def __init__(self):
        self.running = False

    async def countsafecmd(self, message):
        """
        .countsafe <число> <текст> [<секунды>]
        Пример: .countsafe 100 кукуруза 2
        Если <секунды> не указаны — по умолчанию 1 секунда
        """
        if self.running:
            await utils.answer(message, "⚠️ Уже выполняется счёт")
            return

        args = utils.get_args(message)
        if len(args) < 2:
            await utils.answer(
                message,
                "❌ Используй: <code>.countsafe 100 кукуруза [секунды]</code>"
            )
            return

        # Количество сообщений
        try:
            count = int(args[0])
        except ValueError:
            await utils.answer(message, "❌ Первым аргументом должно быть число")
            return

        if count < 1:
            return
        if count > 1000:
            count = 1000  # безопасный предел

        # Текст сообщения
        text = " ".join(args[1:-1]) if len(args) > 2 else args[1]

        # Интервал между сообщениями
        try:
            interval = float(args[-1]) if len(args) > 2 else 1.0
        except ValueError:
            interval = 1.0

        if interval < 0.5:
            interval = 0.5  # минимальная безопасная задержка
        elif interval > 10:
            interval = 10  # максимальная задержка

        self.running = True
        sent = 0

        for _ in range(count):
            if not self.running:
                break

            try:
                await message.respond(text)
                sent += 1
                await asyncio.sleep(interval)

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

        self.running = False

    async def stopcountcmd(self, message):
        """Остановить счёт"""
        self.running = False
        await utils.answer(message, "⛔️ Остановлено")
