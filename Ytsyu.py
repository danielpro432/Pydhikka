# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: Network Profiler
# description: Shows top commands by internet usage
# meta banner: https://i.imgur.com/yourbanner.png

import time
import psutil
import os
from collections import defaultdict
from .. import loader, utils

try:
    import socket
except ImportError:
    socket = None

@loader.tds
class NetworkProfiler(loader.Module):
    strings = {"name": "NetProfiler", "no_data": "📊 Нет данных для отображения."}

    def __init__(self):
        self._stats = defaultdict(lambda: {"calls": 0, "time": 0, "mem": 0, "net": 0})

    @loader.command()
    async def netstart(self, message):
        """Начать сбор сетевой статистики"""
        self._stats.clear()
        await utils.answer(message, "✅ Сетевой профайлер включен.")

    @loader.command()
    async def netstop(self, message):
        """Показать топ 5 команд по сетевой нагрузке"""
        if not self._stats:
            return await utils.answer(message, self.strings["no_data"])

        sorted_stats = sorted(
            self._stats.items(), key=lambda x: x[1]["net"], reverse=True
        )[:5]

        text = "<b>🌐 Топ 5 команд по интернет нагрузке:</b>\n\n"
        for cmd, data in sorted_stats:
            text += (
                f"• <b>{cmd}</b>\n"
                f"   Вызовов: {data['calls']}\n"
                f"   Время: {data['time']:.2f}s\n"
                f"   Память: {data['mem']:.2f} MB\n"
                f"   Трафик: {data['net']:.2f} KB\n\n"
            )
        await utils.answer(message, text)

    def wrap_command(self, func, name):
        async def wrapper(message):
            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss / 1024 / 1024
            net_before = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
            start = time.time()
            result = await func(message)
            elapsed = time.time() - start
            mem_after = process.memory_info().rss / 1024 / 1024
            net_after = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv

            self._stats[name]["calls"] += 1
            self._stats[name]["time"] += elapsed
            self._stats[name]["mem"] += mem_after - mem_before
            self._stats[name]["net"] += (net_after - net_before) / 1024  # KB
            return result

        return wrapper

    def client_ready(self, client, db):
        # Оборачиваем все команды текущего бота
        for mod in loader._modules.values():
            for name, func in mod.commands.items():
                mod.commands[name] = self.wrap_command(func, f"{mod.strings['name']}.{name}")
