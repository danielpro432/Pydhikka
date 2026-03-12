from .. import loader, utils
import asyncio
import aiohttp
from dateutil import parser
from telethon.tl import functions, types


@loader.tds
class SteamFreeBio(loader.Module):
    """Steam Free Bio + уведомления обо всех новых бесплатных играх"""

    strings = {"name": "SteamFreeBio"}

    def __init__(self):
        self._task = None
        self._enabled = True           # уведомления о играх
        self._bio_enabled = False      # обновление bio по умолчанию выключено
        self._old_bio = ""
        self._last_bio = ""
        self._group_id = None
        self._sent_games = set()
        self.db = None

    async def client_ready(self, client, db):
        self._client = client
        self.db = db

        try:
            me = await self._client.get_me()
            self._old_bio = me.about or ""
            self._last_bio = me.about or ""
        except:
            self._old_bio = ""
            self._last_bio = ""

        # Загружаем group_id из базы
        self._group_id = self.db.get("SteamFreeBio", "group_id", None)

        # Проверяем, существует ли группа
        if self._group_id:
            try:
                entity = await self._client.get_entity(self._group_id)
                if not isinstance(entity, (types.Channel, types.Chat)):
                    self._group_id = None
            except Exception:
                self._group_id = None

        # Если группы нет — создаём
        if not self._group_id:
            await self.create_group()

        # Запускаем цикл обновления
        if not self._task:
            self._task = asyncio.create_task(self.auto_update_loop())

    async def create_group(self):
        try:
            result = await self._client(
                functions.channels.CreateChannelRequest(
                    title="Steam Free Bio Updates",
                    about="Уведомления о новых бесплатных играх Steam.",
                    megagroup=True
                )
            )

            self._group_id = result.chats[0].id
            self.db.set("SteamFreeBio", "group_id", self._group_id)

            await self._client.send_message(
                self._group_id,
                "👋 Группа создана. Здесь будут уведомления о новых бесплатных играх."
            )
        except Exception:
            self._group_id = None

    # ====================== Игры ======================

    async def get_free_games(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://store.steampowered.com/api/featuredcategories/",
                    timeout=10
                ) as resp:
                    data = await resp.json()
        except:
            return []

        free_ids = []
        for category in data.values():
            if isinstance(category, dict) and "items" in category:
                for item in category["items"]:
                    if item.get("final_price", 1) == 0:
                        free_ids.append(item["id"])

        games = []
        async with aiohttp.ClientSession() as session:
            for app_id in free_ids[:20]:
                try:
                    async with session.get(
                        f"https://store.steampowered.com/api/appdetails?appids={app_id}",
                        timeout=10
                    ) as resp:
                        details = await resp.json()

                    info = details[str(app_id)]["data"]
                    if info.get("type") != "game":
                        continue

                    release = info.get("release_date", {}).get("date")
                    name = info.get("name")
                    if not release or not name:
                        continue

                    parsed_date = parser.parse(release).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

                    games.append({"name": name, "date": parsed_date})
                except:
                    continue

        games.sort(key=lambda x: x["date"], reverse=True)
        return games

    # ====================== Автообновление ======================

    async def auto_update_loop(self):
        while True:
            if self._enabled or self._bio_enabled:
                await self.process_games()
            await asyncio.sleep(3600)

    async def process_games(self):
        games = await self.get_free_games()
        if not games:
            return

        newest = games[0]
        bio = f"{newest['date'].strftime('%d/%m/%Y')} {newest['name']} - free"

        # Обновляем bio только если включено
        if self._bio_enabled and bio != self._last_bio:
            try:
                await self._client(
                    functions.account.UpdateProfileRequest(about=bio)
                )
                self._last_bio = bio
            except:
                pass

        # Отправка уведомлений в группу
        if self._group_id:
            count = 0
            for game in games:
                text = f"{game['date'].strftime('%d/%m/%Y')} — {game['name']}"
                if text not in self._sent_games:
                    try:
                        await self._client.send_message(
                            self._group_id,
                            f"🎮 Новая бесплатная игра:\n{text}"
                        )
                        self._sent_games.add(text)
                        count += 1
                        await asyncio.sleep(1)
                    except:
                        break
                if count >= 5:
                    break

    # ====================== Команды ======================

    @loader.command()
    async def steamcheck(self, message):
        """Принудительная проверка новых бесплатных игр"""
        await utils.answer(message, "🔄 Проверяю новые бесплатные игры...")
        await self.process_games()
        await utils.answer(message, "✅ Проверка завершена")

    @loader.command()
    async def steamstatus(self, message):
        args = utils.get_args_raw(message).lower()
        if args not in ("on", "off"):
            return await utils.answer(message, "Используй: .steamstatus on/off")

        # Включение/выключение уведомлений и bio
        self._enabled = args == "on"
        self._bio_enabled = args == "on"  # включаем обновление bio только по команде

        if self._enabled:
            await utils.answer(message, "✅ Уведомления и обновление bio включены")
        else:
            try:
                # Восстанавливаем старый bio
                await self._client(
                    functions.account.UpdateProfileRequest(about=self._old_bio)
                )
                self._last_bio = self._old_bio
            except:
                pass
            await utils.answer(message, "🛑 Уведомления и обновление bio выключены")

    @loader.command()
    async def steamrefr(self, message):
        games = await self.get_free_games()
        if not games:
            return await utils.answer(message, "Не удалось получить игры")
        newest = games[0]
        bio = f"{newest['date'].strftime('%d/%m/%Y')} {newest['name']} - free"
        try:
            await self._client(
                functions.account.UpdateProfileRequest(about=bio)
            )
            self._last_bio = bio
            await utils.answer(message, f"Bio обновлено:\n{bio}")
        except Exception as e:
            await utils.answer(message, f"Ошибка: {str(e)}")

    @loader.command()
    async def steamgrestore(self, message):
        """Создать группу уведомлений, если её нет"""
        if self._group_id:
            try:
                await self._client.get_entity(self._group_id)
                return await utils.answer(message, "✅ Группа уже существует")
            except Exception:
                self._group_id = None
        await self.create_group()
        if self._group_id:
            await utils.answer(message, "✅ Группа создана")
        else:
            await utils.answer(message, "❌ Не удалось создать группу")
