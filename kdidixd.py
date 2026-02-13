"""
░██████╗░██████╗░██╗░░░░░███╗░░░███╗███████╗██████╗░██████╗░
██╔════╝██╔═══██╗██║░░░░░████╗░████║██╔════╝██╔══██╗██╔══██╗
╚█████╗░██║██╗██║██║░░░░░██╔████╔██║█████╗░░██████╔╝██████╔╝
░╚═══██╗╚██████╔╝██║░░░░░██║╚██╔╝██║██╔══╝░░██╔══██╗██╔══██╗
██████╔╝░╚═██╔═╝░███████╗██║░╚═╝░██║███████╗██║░░██║██║░░██║
╚═════╝░░░░╚═╝░░░╚══════╝╚═╝░░░░░╚═╝╚══════╝╚═╝░░╚═╝╚═╝░░╚═╝
"""

# meta developer: @Dany23s
# meta icon: https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames.png?raw=true
# meta banner: https://github.com/sqlmerr/hikka_mods/blob/main/assets/banners/egsfreegames.png?raw=true

import datetime
import aiohttp
from typing import List, Dict, Optional

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class EGSFreeGames(loader.Module):
    """Следим за бесплатными играми в Epic Games Store и присылаем только новые"""

    strings = {
        "name": "EGSFreeGames",
        "game": "- <b>{title}</b>\n  <i>Статус</i>: {status}\n  <i>Начало</i>: <code>{start}</code>\n  <i>Конец</i>: <code>{end}</code>\n  <i>Ссылка</i>: {url}\n",
        "header": "🎮 <b>Новые бесплатные игры в EGS:</b>",
        "footer": "ℹ️ Статус <code>active</code> — доступна сейчас, <code>upcoming</code> — скоро.",
        "_region_cfg": "Регион проверки бесплатных игр",
        "_schedule_cfg": "Автоматически присылать новые бесплатные игры",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "region",
                default="RU",
                doc=lambda: self.strings("_region_cfg"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "schedule_checking",
                default=True,
                doc=lambda: self.strings("_schedule_cfg"),
                validator=loader.validators.Boolean(),
            ),
        )
        self.sent_games: set = set()
        self.chat = None

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        # создаём/находим чат для рассылки
        self.chat, _ = await utils.asset_channel(
            self._client,
            "EGS Free Games",
            "Здесь бот присылает новые бесплатные игры из Epic Games Store",
            avatar="https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames_chat.png?raw=true",
            invite_bot=True,
            _folder="hikka"
        )

    async def get_free_games(self, region: str = "RU") -> Optional[List[Dict]]:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        params = {"locale": "en-US", "country": region, "allowCountries": region}
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.get(url, params=params)
                resp.raise_for_status()
                data = await resp.json()
                games = []
                for game in data["data"]["Catalog"]["searchStore"]["elements"]:
                    promotions = game.get("promotions")
                    if not promotions:
                        continue

                    for promo_type, status in [
                        ("promotionalOffers", "active"),
                        ("upcomingPromotionalOffers", "upcoming")
                    ]:
                        for offer_set in promotions.get(promo_type, []):
                            for offer in offer_set.get("promotionalOffers", []):
                                if offer["discountSetting"]["discountPercentage"] == 0:
                                    slug = game.get("productSlug") or game["catalogNs"]["mappings"][0]["pageSlug"]
                                    games.append({
                                        "id": f"{game['id']}_{status}",
                                        "title": game["title"],
                                        "status": status,
                                        "start": offer["startDate"],
                                        "end": offer["endDate"],
                                        "url": f"https://store.epicgames.com/ru/p/{slug}"
                                    })
                return games
            except aiohttp.ClientError:
                return []

    def format_games(self, games: List[Dict]) -> str:
        if not games:
            return ""
        header = self.strings("header")
        text = "".join([
            self.strings("game").format(
                title=g["title"],
                status=g["status"],
                start=self.format_date(g["start"]),
                end=self.format_date(g["end"]),
                url=g["url"]
            )
            for g in games
        ])
        footer = self.strings("footer")
        return f"{header}\n\n{text}{footer}"

    @staticmethod
    def format_date(date_str: str) -> str:
        dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%d.%m.%Y %H:%M (UTC)")

    @loader.loop(interval=3600, autostart=True)
    async def loop(self):
        if not self.config["schedule_checking"]:
            return
        games = await self.get_free_games(self.config["region"])
        new_games = [g for g in games if g["id"] not in self.sent_games and g["status"] == "active"]
        if not new_games:
            return
        self.sent_games.update([g["id"] for g in new_games])
        text = self.format_games(new_games)
        if text:
            await self._client.send_message(utils.get_entity_id(self.chat), text)
