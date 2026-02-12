# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Module Profiler
# description: Shows top 5 heaviest modules by time and memory
# meta banner: https://i.imgur.com/yourbanner.png

import time
import psutil
import os
from collections import defaultdict
from .. import loader, utils

@loader.tds
class ModuleProfiler(loader.Module):
    strings = {"name": "ModuleProfiler", "no_data": "📊 Нет данных для отображения."}

    def __init__(self):
        self._stats = defaultdict(lambda: {"calls": 0, "time": 0, "mem": 0})

    @loader.command()
    async def profstart(self, message):
        """Начать профилирование команд"""
        self._stats.clear()
        await utils.answer(message, "✅ Профилирование включено.")

    @loader.command()
    async def profstop(self, message):
        """Показать топ 5 самых нагружающих команд"""
        if not self._stats:
            return await utils.answer(message, self.strings["no_data"])

        sorted_stats = sorted(
            self._stats.items(), key=lambda x: x[1]["time"], reverse=True
        )[:5]

        text = "<b>📊 Топ 5 нагружающих команд:</b>\n\n"
        for cmd, data in sorted_stats:
            text += (
                f"• <b>{cmd}</b>\n"
                f"   Вызовов: {data['calls']}\n"
                f"   Время: {data['time']:.2f}s\n"
                f"   Память: {data['mem']:.2f} MB\n\n"
            )
        await utils.answer(message, text)

    def wrap_command(self, func, name):
        async def wrapper(message):
            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss / 1024 / 1024
            start = time.time()
            result = await func(message)
            elapsed = time.time() - start
            mem_after = process.memory_info().rss / 1024 / 1024

            self._stats[name]["calls"] += 1
            self._stats[name]["time"] += elapsed
            self._stats[name]["mem"] += mem_after - mem_before
            return result

        return wrapper

    def client_ready(self, client, db):
        # Оборачиваем все команды текущего бота
        for mod in loader._modules.values():
            for name, func in mod.commands.items():
                mod.commands[name] = self.wrap_command(func, f"{mod.strings['name']}.{name}")
