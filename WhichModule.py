# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: ModuleTop
# description: Shows top 5 most resource-heavy modules

import time
import functools
from collections import defaultdict
from .. import loader, utils

@loader.tds
class ModuleTop(loader.Module):
    strings = {"name": "ModuleTop"}

    def __init__(self):
        self.stats = defaultdict(lambda: {
            "calls": 0,
            "total_time": 0.0
        })

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

        # Оборачиваем все команды для замера времени
        for module in self.allmodules.modules:
            for attr in dir(module):
                func = getattr(module, attr)
                if callable(func) and hasattr(func, "__loader_command__"):
                    wrapped = self.wrap_command(func, module.__class__.__name__)
                    setattr(module, attr, wrapped)

    def wrap_command(self, func, module_name):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                self.stats[module_name]["calls"] += 1
                self.stats[module_name]["total_time"] += duration
        return wrapper

    @loader.command()
    async def modtop(self, message):
        """Show top 5 most heavy modules"""

        if not self.stats:
            return await utils.answer(message, "Нет данных пока.")

        data = []

        for mod, info in self.stats.items():
            avg = info["total_time"] / info["calls"] if info["calls"] else 0
            data.append((mod, info["calls"], info["total_time"], avg))

        # сортировка по суммарному времени
        data.sort(key=lambda x: x[2], reverse=True)

        text = "<b>🔥 Top 5 самых нагружающих модулей:</b>\n\n"

        for i, (mod, calls, total, avg) in enumerate(data[:5], 1):
            text += (
                f"{i}. <b>{mod}</b>\n"
                f"   📊 Вызовов: {calls}\n"
                f"   ⏱ Общее время: {total:.2f}s\n"
                f"   ⚡ Среднее: {avg:.3f}s\n\n"
            )

        await utils.answer(message, text) 
