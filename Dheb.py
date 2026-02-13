# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

# meta developer: @Dany23s
# meta name: SteamFreeGames
# meta banner: https://raw.githubusercontent.com/Dany23s/steamfreegames/main/banner.png

import asyncio
import aiohttp
from datetime import datetime
from .. import loader, utils

@loader.tds
class SteamFreeGames(loader.Module):
    """Отслеживание бесплатных игр, 100% скидок и Free Weekends в Steam"""

    strings = {
        "name": "SteamFreeGames",
        "no_games": "<b>Новых бесплатных игр или скидок нет</b>",
        "new_game": "🎮 <b>{title}</b>\nСтатус: {status}\nЦена: {price}\nСсылка: {url}\nДоступно до: {end_date}",
        "loop_started": "<b>Цикл мониторинга Steam запущен</b>",
        "loop_stopped": "<b>Цикл мониторинга Steam остановлен</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "CHECK_INTERVAL",
                300,
                lambda: "Интервал проверки акций (сек)",
                validator=loader.validators.Integer()
            ),
        )
        self._client = None
        self.db = None
        self.channel = None
        self.running = False
        self.seen_games = set()
        self.task = None

    async def client_ready(self, client, db):
        self._client = client
        self.db = db
        self.channel, _ = await utils.asset_channel(
            client,
            "Steam Free Games",
            "Канал с новыми бесплатными играми и скидками 100%",
            invite_bot=True,
            _folder="hikka"
        )
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self.loop())

    async def fetch_steam_free(self):
        url = "https://store.steampowered.com/api/featuredcategories/"
        params = {"cc": "US"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                free_games = []

                # Полностью бесплатные
                for g in data.get("featured_win", []):
                    if g.get("discount_percent") == 100 or g.get("is_free") or g.get("free_weekend"):
                        free_games.append(g)
                return free_games

    def format_game(self, g):
        price = "Free" if g.get("is_free") or g.get("discount_percent") == 100 else f"${g.get('final_price')/100:.2f}"
        status = "Free Weekend" if g.get("free_weekend") else ("100% скидка" if g.get("discount_percent") == 100 else "Free")
        end_ts = g.get("end_time")
        end_date = datetime.utcfromtimestamp(end_ts).strftime("%d.%m.%Y %H:%M UTC") if end_ts else "∞"
        return self.strings["new_game"].format(
            title=g.get("name"),
            status=status,
            price=price,
            url=f"https://store.steampowered.com/app/{g.get('id')}/",
            end_date=end_date
        )

    async def send_new_games(self, games):
        for g in games:
            if g["id"] in self.seen_games:
                continue
            self.seen_games.add(g["id"])
            await self._client.send_message(self.channel, self.format_game(g))
            await asyncio.sleep(2)  # антиспам

    async def loop(self):
        await utils.answer(self.channel, self.strings["loop_started"])
        while True:
            try:
                games = await self.fetch_steam_free()
                if games:
                    await self.send_new_games(games)
            except Exception as e:
                # лог ошибок, но цикл продолжается
                utils.logger.error(f"SteamFreeGames loop error: {e}")
            await asyncio.sleep(self.config["CHECK_INTERVAL"])

    @loader.command()
    async def steamcheck(self, message):
        """Ручная проверка новых бесплатных игр"""
        games = await self.fetch_steam_free()
        if not games:
            await utils.answer(message, self.strings["no_games"])
            return
        await self.send_new_games(games)

    @loader.command()
    async def steamstatus(self, message):
        """Проверить статус цикла"""
        status = "Запущен" if self.running else "Остановлен"
        await utils.answer(message, f"<b>Цикл мониторинга Steam:</b> {status}")
