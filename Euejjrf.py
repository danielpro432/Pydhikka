#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# 🔒 Licensed under GNU AGPLv3
# meta developer: @Dany23s
# meta banner: https://raw.githubusercontent.com/Dany23s/assets/main/steamfreegames_banner.png

import asyncio
import aiohttp
import datetime
import logging
from typing import Dict, List, Optional

from .. import loader, utils
from hikkatl.tl.patched import Message

logger = logging.getLogger(__name__)

@loader.tds
class SteamFreeGames(loader.Module):
    """Отслеживание бесплатных игр и 100% скидок в Steam с уведомлением в отдельный чат"""

    strings = {
        "name": "SteamFreeGames",
        "game": (
            "- <b>{title}</b>\n"
            "    <i>Status</i>: {status}\n"
            "    <i>Price</i>: {price}\n"
            "    <i>Start</i>: <code>{start}</code>\n"
            "    <i>End</i>: <code>{end}</code>\n"
            "    <i>Link</i>: {url}\n"
        ),
        "header": "<emoji document_id=5472282432436708545>🎮</emoji> <b>New Steam deals:</b>",
        "no_new": "Нет новых бесплатных игр или скидок 100%",
        "_chat_id": "ID чата для уведомлений",
        "_schedule_checking_cfg": "Автоматически проверять новые игры и скидки",
    }

    strings_ru = {
        "game": (
            "- <b>{title}</b>\n"
            "    <i>Статус</i>: {status}\n"
            "    <i>Цена</i>: {price}\n"
            "    <i>Начало</i>: <code>{start}</code>\n"
            "    <i>Окончание</i>: <code>{end}</code>\n"
            "    <i>Ссылка</i>: {url}\n"
        ),
        "header": "<emoji document_id=5472282432436708545>🎮</emoji> <b>Новые предложения в Steam:</b>",
        "no_new": "Новых бесплатных игр или скидок 100% нет",
        "_chat_id": "ID чата для уведомлений",
        "_schedule_checking_cfg": "Автоматически проверять новые игры и скидки",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "chat_id",
                None,
                lambda: self.strings("_chat_id"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "schedule_checking",
                default=True,
                doc=lambda: self.strings("_schedule_checking_cfg"),
                validator=loader.validators.Boolean(),
            ),
        )
        self.seen_games = set()
        self._client = None
        self.chat = None

    async def client_ready(self, client, db):
        self._client = client
        # Попытка создать чат если не указан
        if not self.config["chat_id"]:
            self.chat, _ = await utils.asset_channel(
                self._client,
                "Steam Free Games",
                "Чат для уведомлений о новых бесплатных играх и 100% скидках в Steam",
                avatar="https://raw.githubusercontent.com/Dany23s/assets/main/steam_icon.png",
                invite_bot=True,
                _folder="steam",
            )
            self.config["chat_id"] = utils.get_entity_id(self.chat)

    async def fetch_deals(self) -> Optional[List[Dict]]:
        url = "https://store.steampowered.com/api/featuredcategories"
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url)
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch Steam deals: {e}")
            return []

        games = []
        for deal in data.get("specials", {}).get("items", []):
            # Проверяем только бесплатные или 100% скидку
            discount = deal.get("discount_percent", 0)
            is_free = deal.get("price", {}).get("final", 1) == 0
            if is_free or discount == 100:
                games.append({
                    "title": deal.get("name"),
                    "status": "Free" if is_free else f"{discount}% off",
                    "price": "Free" if is_free else deal.get("price", {}).get("final_formatted", ""),
                    "start": datetime.datetime.utcfromtimestamp(deal.get("start_timestamp", 0)).strftime("%d.%m.%Y %H:%M UTC"),
                    "end": datetime.datetime.utcfromtimestamp(deal.get("end_timestamp", 0)).strftime("%d.%m.%Y %H:%M UTC"),
                    "url": f"https://store.steampowered.com/app/{deal.get('id')}",
                })
        return games

    def gen_text(self, games: List[Dict]) -> str:
        text = "".join([self.strings("game").format(**g) + "\n" for g in games])
        return f"{self.strings('header')}\n\n{text}" if text else ""

    @loader.loop(interval=3600, autostart=True)
    async def loop(self):
        if not self.config["schedule_checking"]:
            return
        games = await self.fetch_deals()
        new_games = [g for g in games if g["title"] not in self.seen_games]
        if not new_games:
            return
        self.seen_games.update([g["title"] for g in new_games])
        chat_id = self.config["chat_id"] or utils.get_entity_id(self.chat)
        await self._client.send_message(chat_id, self.gen_text(new_games))
