# █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
# █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

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
        "no_games": "Новых бесплатных игр или скидок нет",
        "new_game": "🎮 {title}\nСтатус: {status}\nЦена: {price}\nСсылка: {url}\nДоступно до: {end_date}",
        "loop_started": "Цикл мониторинга Steam запущен",
        "loop_stopped": "Цикл мониторинга Steam остановлен",
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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    data = await resp.json()
                    free_games = []

                    for g in data.get("featured_win", []):
                        if g.get("discount_percent") == 100 or g.get("is_free") or g.get("free_weekend"):
                            free_games.append(g)
                    return free_games
        except Exception as e:
            utils.logger.error(f"Steam API error: {e}")
            return []

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
            if g.get("id") in self.seen_games:
                continue
            self.seen_games.add(g.get("id"))
            try:
                await self._client.send_message(self.channel, self.format_game(g))
                await asyncio.sleep(2)
            except Exception as e:
                utils.logger.error(f"Send message error: {e}")

    async def loop(self):
        try:
            await self._client.send_message(self.channel, self.strings["loop_started"])
        except:
            pass
        
        while self.running:
            try:
                games = await self.fetch_steam_free()
                if games:
                    await self.send_new_games(games)
            except Exception as e:
                utils.logger.error(f"SteamFreeGames loop error: {e}")
            
            await asyncio.sleep(self.config["CHECK_INTERVAL"])

    @loader.command()
    async def steamcheck(self, message):
        """Ручная проверка новых бесплатных игр"""
        await utils.answer(message, "⏳ Проверка Steam...")
        games = await self.fetch_steam_free()
        if not games:
            await utils.answer(message, self.strings["no_games"])
            return
        
        for g in games[:5]:
            await utils.answer(message, self.format_game(g))
            await asyncio.sleep(1)

    @loader.command()
    async def steamstop(self, message):
        """Остановить мониторинг"""
        self.running = False
        if self.task:
            self.task.cancel()
        await utils.answer(message, self.strings["loop_stopped"])

    @loader.command()
    async def steamstart(self, message):
        """Запустить мониторинг"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self.loop())
            await utils.answer(message, self.strings["loop_started"])
        else:
            await utils.answer(message, "✅ Мониторинг уже запущен")
