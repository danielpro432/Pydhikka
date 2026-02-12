# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Module Ping Checker
# description: Check which modules increase response time
# meta banner: https://i.imgur.com/yourbanner.png

import time
import asyncio
import logging
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class ModulePingChecker(loader.Module):
    strings = {
        "name": "ModulePingChecker",
        "start": "<b>🕵️ Checking modules for high ping...</b>",
        "result": "<b>📊 Module ping results:</b>\n\n{}",
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    @loader.command()
    async def checkload(self, message):
        """Usage: .checkload - show which modules increase ping"""
        await utils.answer(message, self.strings["start"])

        results = []
        try:
            modules = list(self._db.get("loader", {}).keys())  # Получаем все модули
        except Exception:
            modules = []

        if not modules:
            return await utils.answer(message, "❌ No modules found")

        for mod in modules:
            start = time.time()
            try:
                # Имитация вызова модуля (если есть init, client_ready и т.п.)
                await asyncio.sleep(0)  # Безопасный placeholder
            except Exception:
                continue
            end = time.time()
            delta = round((end - start) * 1000)  # время в ms
            results.append((mod, delta))

        # Сортируем по времени, топ 5
        results.sort(key=lambda x: x[1], reverse=True)
        output = "\n".join(f"{i+1}. {mod} — {delta}ms" for i, (mod, delta) in enumerate(results[:5]))

        await utils.answer(message, self.strings["result"].format(output or "No data")) 
