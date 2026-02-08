# meta developer: @you
# meta name: CountSpamSafe
# meta description: Безопасный счётчик сообщений с антифлудом и остановкой

import asyncio
from telethon.errors import FloodWaitError
from .. import loader, utils

@loader.tds
class CountSpamSafe(loader.Module):
    """Максимально безопасный счётчик"""

    strings = {"name": "CountSpamSafe"}

    def __init__(self):
        self.running = False

    async def countsafecmd(self, message):
        """
        .countsafe <число> <текст>
        Пример: .countsafe 100 кукуруза
        """
        if self.running:
            await utils.answer(message, "⚠️ Уже выполняется счёт")
            return

        args = utils.get_args(message)
        if len(args) < 2:
            await utils.answer(
                message,
                "❌ Используй: <code>.countsafe 100 кукуруза</code>"
            )
            return

        try:
            count = int(args[0])
        except ValueError:
            await utils.answer(message, "❌ Первым аргументом должно быть число")
            return

        if count < 1:
            return

        if count > 1000:
            count = 1000  # безопасный предел

        text = " ".join(args[1:])
        self.running = True

        status = await utils.answer(
            message, f"🟢 Начинаю: 0 / {count}"
        )

        sent = 0

        for i in range(1, count + 1):
            if not self.running:
                break

            try:
                await message.respond(f"{i} {text}")
                sent += 1
                await status.edit(f"🟡 Отправлено: {sent} / {count}")
                await asyncio.sleep(1)

            except FloodWaitError as e:
                await status.edit(f"⏳ FloodWait {e.seconds} сек…")
                await asyncio.sleep(e.seconds)

        self.running = False
        await status.edit(f"✅ Готово: {sent} сообщений")

    async def stopcountcmd(self, message):
        """Остановить счёт"""
        self.running = False
        await utils.answer(message, "⛔️ Остановлено")
