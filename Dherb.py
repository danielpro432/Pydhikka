#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta banner: https://github.com/sqlmerr/hikka_mods/blob/main/assets/banners/egsfreegames.png?raw=true
# meta icon: https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/egsfreegames.png?raw=true

import aiohttp
import asyncio
import datetime
import logging

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class SteamFreeGames(loader.Module):
    """Отслеживание бесплатных игр и 100%-скидок в Steam"""

    strings = {
        "name": "SteamFreeGames",
        "header": "<b>Новые бесплатные или полностью бесплатные игры в Steam:</b>",
        "no_new": "Новых игр нет",
        "status_running": "Запущен",
        "status_stopped": "Остановлен",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "CHAT_ID",
                None,
                lambda: "ID чата для отправки уведомлений",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "CHECK_INTERVAL",
                300,
                lambda: "Интервал проверки игр (секунды)",
                validator=loader.validators.Integer(),
            ),
        )
        self.running = False
        self.task = None
        self.seen_games = set()
        self._client = None
        self.chat = None

    async def client_ready(self, client, db):
        self._client = client
        self.chat = self.config["CHAT_ID"]
        if not self.chat:
            logger.warning("CHAT_ID не указан — модуль не будет отправлять игры")
        else:
            self.running = True
            self.task = asyncio.create_task(self.loop_check_games())

    async def fetch_free_games(self):
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        params = {"locale": "en-US", "country": "US", "allowCountries": "US"}
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url, params=params)
                resp.raise_for_status()
                data = await resp.json()
                games = []
                for g in data["data"]["Catalog"]["searchStore"]["elements"]:
                    promos = g.get("promotions", {})
                    active = promos.get("promotionalOffers", [])
                    upcoming = promos.get("upcomingPromotionalOffers", [])
                    for offer_list in [active, upcoming]:
                        for offer_bundle in offer_list:
                            for offer in offer_bundle.get("promotionalOffers", []):
                                discount = offer["discountSetting"]["discountPercentage"]
                                start = offer["startDate"]
                                end = offer["endDate"]
                                if discount == 100:
                                    games.append({
                                        "title": g["title"],
                                        "url": f"https://store.steampowered.com/app/{g['id']}",
                                        "start": start,
                                        "end": end
                                    })
                return games
        except Exception as e:
            logger.exception("Ошибка при fetch_free_games: %s", e)
            return []

    def format_game_text(self, game):
        start_dt = datetime.datetime.fromisoformat(game["start"].replace("Z", "+00:00"))
        end_dt = datetime.datetime.fromisoformat(game["end"].replace("Z", "+00:00"))
        return (f"- <b>{game['title']}</b>\n"
                f"  Начало: {start_dt.strftime('%d.%m.%Y %H:%M UTC')}\n"
                f"  Конец: {end_dt.strftime('%d.%m.%Y %H:%M UTC')}\n"
                f"  Ссылка: {game['url']}")

    async def loop_check_games(self):
        while self.running:
            games = await self.fetch_free_games()
            new_games = [g for g in games if g["title"] not in self.seen_games]
            if new_games and self.chat:
                text = self.strings["header"] + "\n\n" + "\n\n".join(self.format_game_text(g) for g in new_games)
                await self._client.send_message(self.chat, text)
                for g in new_games:
                    self.seen_games.add(g["title"])
            await asyncio.sleep(self.config["CHECK_INTERVAL"])

    @loader.command()
    async def steamstatus(self, message):
        """Проверить статус цикла"""
        status = self.strings["status_running"] if self.running else self.strings["status_stopped"]
        await utils.answer(message, f"<b>Цикл мониторинга Steam:</b> {status}")
