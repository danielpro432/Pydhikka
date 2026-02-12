# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: NetworkProfiler
# description: Show top resource-consuming modules/processes
# meta banner: https://i.imgur.com/yourbanner.png

import asyncio
import logging
import psutil
from collections import defaultdict
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class NetworkProfiler(loader.Module):
    strings = {
        "name": "NetworkProfiler",
        "no_data": "❌ No data collected yet.",
        "top_usage": "<b>📊 Top Resource Consumers:</b>\n\n{}",
    }

    def __init__(self):
        # Храним данные о CPU/RAM/Net для модулей
        self._usage_data = defaultdict(lambda: {"cpu": 0.0, "ram": 0.0, "net": 0.0})

    async def client_ready(self, client, db):
        try:
            # Heroku loader использует Modules, а не _modules
            modules_list = getattr(loader, "Modules", [])
            if not modules_list:
                logger.warning("No modules found in loader.Modules")
        except Exception as e:
            logger.error(f"Error fetching modules: {e}")

    @loader.command(
        ru_doc="Показать топ 5 модулей по загрузке CPU/RAM/Net",
        en_doc="Show top 5 modules by CPU/RAM/Net usage"
    )
    async def profiler(self, message):
        """Usage: .profiler"""
        try:
            # Собираем все процессы Python
            processes = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "io_counters"]):
                try:
                    processes.append(p.info)
                except Exception:
                    continue

            if not processes:
                return await utils.answer(message, self.strings["no_data"])

            # Сортируем по CPU
            top_cpu = sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)[:5]
            top_ram = sorted(processes, key=lambda x: x["memory_info"].rss if x["memory_info"] else 0, reverse=True)[:5]

            results = "<b>🔥 Top CPU usage:</b>\n"
            for p in top_cpu:
                results += f"• {p['name']} (PID {p['pid']}): {p['cpu_percent']}%\n"

            results += "\n<b>💾 Top RAM usage:</b>\n"
            for p in top_ram:
                ram_mb = (p["memory_info"].rss if p["memory_info"] else 0) / 1024 / 1024
                results += f"• {p['name']} (PID {p['pid']}): {ram_mb:.2f} MB\n"

            await utils.answer(message, self.strings["top_usage"].format(results))
        except Exception as e:
            logger.error(f"Profiler error: {e}")
            await utils.answer(message, f"❌ Error: {e}")
