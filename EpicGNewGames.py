# meta developer: @sqlmerr_m
# meta icon: https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames.png?raw=true
# meta banner: https://github.com/sqlmerr/hikka_mods/blob/main/assets/banners/egsfreegames.png?raw=true

import logging
from typing import Dict, List, Optional
import datetime
import aiohttp
from .. import utils, loader
from hikkatl.tl.patched import Message

@loader.tds
class EGSFreeGames(loader.Module):
    """Module for checking free games in Epic Games Store. Sends notifications only for new free games."""

    strings = {
        "name": "EGSFreeGames",
        "game": "🎮 <b>{title}</b>\n<i>Status</i>: {status}\n🕒 {start} - {end}\n🔗 <a href='{url}'>Link</a>\n",
        "header": "🆓 <b>Free games in Epic Games Store:</b>",
        "header_bot": "🆓 <b>Today's new free games:</b>",
        "footer": "ℹ️ <i>Active = available now | Upcoming = available soon</i>",
        "_region_cfg": "Region for checking free games",
        "_schedule_checking_cfg": "Automatically notify new free games",
    }

    strings_ru = {
        "game": "🎮 <b>{title}</b>\n<i>Статус</i>: {status}\n🕒 {start} - {end}\n🔗 <a href='{url}'>Ссылка</a>\n",
        "header": "🆓 <b>Бесплатные игры в EGS:</b>",
        "header_bot": "🆓 <b>Сегодняшние новые бесплатные игры:</b>",
        "footer": "ℹ️ <i>Active = доступно сейчас | Upcoming = скоро</i>",
        "_region_cfg": "Регион проверки бесплатных игр",
        "_schedule_checking_cfg": "Автоматически уведомлять о новых бесплатных играх",
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
                doc=lambda: self.strings("_schedule_checking_cfg"),
                validator=loader.validators.Boolean(),
            ),
        )
        self.sent_games: set = set()  # Храним уже отправленные игры

    async def client_ready(self):
        self.chat, _ = await utils.asset_channel(
            self._client,
            "EGS Free Games",
            "Channel for daily Epic Games free games",
            avatar="https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames_chat.png?raw=true",
            invite_bot=True,
            _folder="hikka",
        )

    async def get_free_games(self, region: str = "RU") -> Optional[List[Dict]]:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        params = {"locale": "en-US", "country": region, "allowCountries": region}
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(url, params=params)
                response.raise_for_status()
                data = await response.json()
                games = []
                for game in data["data"]["Catalog"]["searchStore"]["elements"]:
                    if not game.get("promotions"):
                        continue
                    promotions = game["promotions"]
                    promo = promotions.get("promotionalOffers", [])
                    upcoming = promotions.get("upcomingPromotionalOffers", [])
                    games.extend(self.process_offers(game, promo, "active"))
                    games.extend(self.process_offers(game, upcoming, "upcoming"))
                return games
        except aiohttp.ClientResponseError:
            return []

    def process_offers(self, game: Dict, offers: List, status: str) -> List[Dict]:
        games_list = []
        for offer_batch in offers:
            for offer in offer_batch.get("promotionalOffers", []):
                games_list.append({
                    "title": game["title"],
                    "status": status,
                    "start_date": offer["startDate"],
                    "end_date": offer["endDate"],
                    "url": f"https://store.epicgames.com/ru/p/{game['productSlug'] or game['catalogNs']['mappings'][0]['pageSlug']}"
                })
        return games_list

    def format_games(self, games: List[Dict], bot: bool = False) -> str:
        header = self.strings("header") if not bot else self.strings("header_bot")
        body = ""
        for g in games:
            slug = g["url"].split("/")[-1]
            if bot and slug in self.sent_games:
                continue  # пропускаем уже отправленные игры
            if bot:
                self.sent_games.add(slug)
            body += self.strings("game").format(
                title=g["title"],
                status=g["status"],
                start=self.format_time(g["start_date"]),
                end=self.format_time(g["end_date"]),
                url=g["url"]
            )
        footer = self.strings("footer") if not bot else ""
        return f"{header}\n\n{body}{footer}"

    def format_time(self, iso_date: str) -> str:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M (UTC)")

    @loader.command()
    async def egsgames(self, message: Message):
        """Get free games"""
        games = await self.get_free_games(self.config["region"])
        text = self.format_games(games)
        await utils.answer(message, text)

    @loader.loop(interval=3600, autostart=True)
    async def notify_new_games(self):
        """Send only newly added free games"""
        if not self.config["schedule_checking"]:
            return
        games = await self.get_free_games(self.config["region"])
        text = self.format_games(games, bot=True)
        if text.strip():  # только если есть новые игры
            chat_id = utils.get_entity_id(self.chat)
            await self.inline.bot.send_message(chat_id=chat_id, text=text, parse_mode="html")
