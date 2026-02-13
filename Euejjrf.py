# meta developer: @Dany23s
# meta banner: https://raw.githubusercontent.com/Dany23s/assets/main/steam_banner.png

import aiohttp
import datetime
from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class SteamFreeGames(loader.Module):
    """Отслеживание бесплатных игр и скидок 100% в Steam"""

    strings = {
        "name": "SteamFreeGames",
        "game": "- <b>{title}</b>\n  <i>Discount:</i> {discount}%\n  <i>Price:</i> {price}\n  <i>Link:</i> {url}",
        "header": "🎮 Новые бесплатные или 100% скидки в Steam:",
        "_region_cfg": "Регион для Steam (например, RU)",
        "_schedule_cfg": "Отправлять автоматически новые игры в чат",
        "_cls_doc": "Модуль уведомляет о новых бесплатных играх и 100% скидках в Steam"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "region",
                default="RU",
                doc=lambda: self.strings("_region_cfg"),
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "schedule_checking",
                default=True,
                doc=lambda: self.strings("_schedule_cfg"),
                validator=loader.validators.Boolean()
            )
        )
        self.sent_games = set()
        self.chat = None

    async def client_ready(self, client, db):
        self._client = client
        # Создаем канал для уведомлений, без аватарки
        self.chat, _ = await utils.asset_channel(
            self._client,
            "Steam Free Games",
            "Будет присылать бесплатные игры и скидки 100%",
            invite_bot=True
        )

    async def fetch_free_games(self):
        url = "https://store.steampowered.com/api/featuredcategories/"
        params = {"cc": self.config["region"]}
        games = []

        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.get(url, params=params)
                data = await resp.json()
                for game in data.get("specials", {}).get("items", []):
                    if game.get("discount_percent", 0) == 100:
                        game_id = game.get("id")
                        if game_id not in self.sent_games:
                            games.append(game)
                            self.sent_games.add(game_id)
            except Exception:
                return []

        return games

    def format_games(self, games):
        text = self.strings("header") + "\n\n"
        for g in games:
            text += self.strings("game").format(
                title=g.get("name"),
                discount=g.get("discount_percent"),
                price=g.get("final_price") / 100 if g.get("final_price") else 0,
                url=f"https://store.steampowered.com/app/{g.get('id')}"
            )
            text += "\n\n"
        return text.strip()

    @loader.loop(interval=3600, autostart=True)
    async def loop_check(self, *args, **kwargs):
        if not self.config["schedule_checking"]:
            return

        games = await self.fetch_free_games()
        if not games:
            return

        text = self.format_games(games)
        chat_id = utils.get_entity_id(self.chat)
        await self.inline.bot.send_message(chat_id=chat_id, text=text)

    @loader.command(ru_doc="Проверить бесплатные игры прямо сейчас")
    async def steamfree(self, message: Message):
        """Проверка бесплатных игр и 100% скидок вручную"""
        games = await self.fetch_free_games()
        if not games:
            await utils.answer(message, "Новых бесплатных игр или 100% скидок нет.")
            return

        text = self.format_games(games)
        await utils.answer(message, text)
