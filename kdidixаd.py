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
from typing import Dict, List, Optional
import aiohttp

from .. import utils, loader
from hikkatl.tl.patched import Message


@loader.tds
class EGSFreeGames(loader.Module):
    """Module for checking free games in Epic Games Store on Heroku userbot"""

    strings = {
        "name": "EGSFreeGames",
        "game": (
            "-  <b>Game</b>: {title}\n"
            "    <i>Status</i>: {status}\n"
            "    <i>Promotion started at</i>: <code>{start}</code>\n"
            "    <i>Promotion will end at</i>: <code>{end}</code>\n"
            "    <i>Link</i>: {url}\n"
        ),
        "header_bot": "🎮 <b>New free games in EGS:</b>",
        "footer": "<i>Only newly free games are shown.</i>",
        "_region_cfg": "Free games check region",
        "_schedule_cfg": "Automatically send new free games to chat",
        "_chat_cfg": "Chat ID or username for sending free games",
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
            loader.ConfigValue(
                "chat_id",
                default=None,
                doc=lambda: self.strings("_chat_cfg"),
                validator=loader.validators.String(),
            ),
        )
        self.sent_games: set = set()  # хранит slug отправленных игр

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
                    promotions = game.get("promotions")
                    if not promotions:
                        continue
                    promo_now = promotions.get("promotionalOffers", [])
                    promo_upcoming = promotions.get("upcomingPromotionalOffers", [])
                    for offers, status in [(promo_now, "active"), (promo_upcoming, "upcoming")]:
                        for offer_group in offers:
                            for offer in offer_group.get("promotionalOffers", []):
                                slug = game.get("productSlug") or game["catalogNs"]["mappings"][0]["pageSlug"]
                                if slug not in self.sent_games and offer["discountSetting"]["discountPercentage"] > 0:
                                    games.append({
                                        "title": game["title"],
                                        "slug": slug,
                                        "status": status,
                                        "start": offer["startDate"],
                                        "end": offer["endDate"],
                                        "url": f"https://store.epicgames.com/ru/p/{slug}"
                                    })
                return games
        except Exception:
            return []

    def gen_text(self, games: List[Dict]) -> str:
        if not games:
            return ""
        text = "".join([
            self.strings("game").format(
                title=g["title"],
                status=g["status"],
                start=g["start"],
                end=g["end"],
                url=g["url"]
            ) + "\n" for g in games
        ])
        return f"{self.strings('header_bot')}\n\n{text}{self.strings('footer')}"

    @loader.command(ru_doc="Получить новые бесплатные игры в EGS")
    async def egsgames(self, message: Message):
        """Get new free games"""
        games = await self.get_free_games(self.config["region"])
        for g in games:
            self.sent_games.add(g["slug"])
        text = self.gen_text(games)
        if text:
            await utils.answer(message, text)

    @loader.loop(interval=3600, autostart=True)
    async def loop(self, *args, **kwargs):
        if not self.config["schedule_checking"]:
            return
        chat_id = self.config["chat_id"]
        if not chat_id:
            return
        games = await self.get_free_games(self.config["region"])
        new_games = [g for g in games if g["slug"] not in self.sent_games]
        for g in new_games:
            self.sent_games.add(g["slug"])
        text = self.gen_text(new_games)
        if text:
            await self._client.send_message(chat_id, text)
