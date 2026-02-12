# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Module Ping Profiler
# description: Measure command execution time per module
# meta banner: https://i.imgur.com/yourbanner.png

import time
import asyncio
from .. import loader, utils

@loader.tds
class ModulePingProfiler(loader.Module):
    strings = {
        "name": "ModulePingProfiler",
        "start": "<b>🕵️ Profiling modules...</b>",
        "result": "<b>📊 Top slow modules:</b>\n\n{}",
        "no_cmds": "❌ No commands found to test"
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    @loader.command()
    async def checkload(self, message):
        """Usage: .checkload - find modules causing high ping"""
        await utils.answer(message, self.strings["start"])

        if not hasattr(self.client, "commands"):
            return await utils.answer(message, self.strings["no_cmds"])

        results = []
        # проходим по всем зарегистрированным командам
        for cmd_name, cmd_func in self.client.commands.items():
            start = time.time()
            try:
                # вызываем команду безопасно, без аргументов
                coro = cmd_func(message)
                if asyncio.iscoroutine(coro):
                    await asyncio.wait_for(coro, timeout=3)
            except Exception:
                pass
            end = time.time()
            delta = round((end - start) * 1000)
            results.append((cmd_name, delta))

        # сортировка и топ 5
        results.sort(key=lambda x: x[1], reverse=True)
        output = "\n".join(f"{i+1}. {name} — {delta}ms" for i, (name, delta) in enumerate(results[:5]))
        await utils.answer(message, self.strings["result"].format(output or "No data"))
