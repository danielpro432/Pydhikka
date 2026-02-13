#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

#   https://t.me/sqlmerr_m
# 🔒 Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

import logging
import datetime
from typing import Dict, List, Optional

import aiohttp
from .. import loader, utils
from hikkatl.tl.patched import Message

logger = logging.getLogger(__name__)

@loader.tds
class EGSFreeGames(loader.Module):
    """Проверка новых бесплатных игр в Epic Games Store"""

    strings = {
        "name": "EGSFreeGames",
        "game": (
            "-  <b>{title}</b>\n"
            "    <i>Статус</i>: {status}\n"
            "    <i>Начало акции</i>: <code>{start}</code>\n"
            "    <i>Конец акции</i>: <code>{end}</code>\n"
            "    <i>Ссылка</i>: {url}\n"
        ),
        "header": "<emoji document_id=5472282432436708545>🎮</emoji> <b>Новые бесплатные игры в EGS:</b>",
        "_region_cfg": "Регион проверки бесплатных игр",
        "_schedule_checking_cfg": "Отправлять новые бесплатные игры в канал автоматически",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "region", default="RU",
                doc=lambda: self.strings("_region_cfg"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "schedule_checking", default=True,
                doc=lambda: self.strings("_schedule_checking_cfg"),
                validator=loader.validators.Boolean(),
            ),
        )
        self.prev_free_games: set[str] = set()  # для хранения ранее полученных игр
        self.chat = None

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.chat, _ = await utils.asset_channel(
            client,
            "EGS Free Games",
            "Новые бесплатные игры каждый день",
            avatar="https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames_chat.png?raw=true",
            invite_bot=True,
        )

    async def get_free_games(self, region: str = "RU") -> List[Dict]:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        params = {"locale": "en-US", "country": region, "allowCountries": region}
        games = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                for game in data["data"]["Catalog"]["searchStore"]["elements"]:
                    promos = game.get("promotions")
                    if not promos:
                        continue
                    active = promos.get("promotionalOffers", [])
                    upcoming = promos.get("upcomingPromotionalOffers", [])
                    for offers, status in [(active, "active"), (upcoming, "upcoming")]:
                        for offer_set in offers:
                            for offer in offer_set.get("promotionalOffers", []):
                                if offer["discountSetting"]["discountPercentage"] == 0:
                                    slug = game.get("productSlug") or game["catalogNs"]["mappings"][0]["pageSlug"]
                                    games.append({
                                        "id": game["id"],
                                        "title": game["title"],
                                        "status": status,
                                        "start": offer["startDate"],
                                        "end": offer["endDate"],
                                        "url": f"https://store.epicgames.com/ru/p/{slug}"
                                    })
        return games

    def gen_text(self, games: List[Dict]) -> str:
        text = "".join([
            self.strings("game").format(
                title=g["title"], status=g["status"],
                start=self.format_date(g["start"]), end=self.format_date(g["end"]),
                url=g["url"]
            )
            for g in games
        ])
        return f"{self.strings('header')}\n\n{text}" if text else ""

    def format_date(self, iso_str: str) -> str:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M (UTC)")

    @loader.loop(interval=3600, autostart=True)
    async def check_new_games(self):
        if not self.config["schedule_checking"]:
            return

        current_games = await self.get_free_games(self.config["region"])
        current_ids = {g["id"] for g in current_games}

        # находим новые игры
        new_games = [g for g in current_games if g["id"] not in self.prev_free_games]

        if new_games:
            text = self.gen_text(new_games)
            if text:
                chat_id = utils.get_entity_id(self.chat)
                await self.inline.bot.send_message(chat_id, text)

        self.prev_free_games = current_ids

    @loader.command(ru_doc="Показать текущие бесплатные игры")
    async def egsgames(self, message: Message):
        games = await self.get_free_games(self.config["region"])
        text = self.gen_text(games)
        if text:
            await utils.answer(message, text)
        else:
            await utils.answer(message, "Сейчас нет бесплатных игр.")
