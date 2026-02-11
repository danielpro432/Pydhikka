__version__ = (2, 2, 2)

# meta developer: @mofkomodules
# name: Foundation
# meta banner: https://raw.githubusercontent.com/mofko/hass/refs/heads/main/IMG_20260128_211636_866.jpg
# meta pic: https://raw.githubusercontent.com/mofko/hass/refs/heads/main/IMG_20260128_211636_866.jpg
# description: best NSFW random module
# meta fhsdesc: hentai, 18+, random, хентай, porn, fun, mofko, хуйня, порно

import random
import logging
import asyncio
import time
import aiohttp
import ssl
from urllib.parse import quote_plus
from collections import defaultdict
from herokutl.types import Message
from .. import loader, utils
from telethon.errors import FloodWaitError
from ..inline.types import InlineCall
from cachetools import TTLCache

logger = logging.getLogger(__name__)

FOUNDATION_LINK = "https://t.me/+oScQIU-JzZhlMjAy"

@loader.tds
class Foundation(loader.Module):
    strings = {
        "name": "Foundation",
        "error": "<emoji document_id=6012681561286122335>🤤</emoji> Something went wrong, check logs",
        "not_joined": "<emoji document_id=6012681561286122335>🤤</emoji> You need to join the channel first: https://t.me/+oScQIU-JzZhlMjAy",
        "no_media": "<emoji document_id=6012681561286122335>🤤</emoji> No media found in channel",
        "no_videos": "<emoji document_id=6012681561286122335>🤤</emoji> No videos found in channel",
        "triggers_config": "⚙️ <b>Configuration of triggers for Foundation</b>\n\nChat: {} (ID: {})\n\nCurrent triggers:\n• <code>fond</code>: {}\n• <code>vfond</code>: {}",
        "select_trigger": "Select trigger to configure:",
        "enter_trigger_word": "✍️ Enter trigger word (or 'off' to disable):",
        "trigger_updated": "✅ Trigger updated!\n\n{} will now trigger .{} in chat {}",
        "trigger_disabled": "✅ Trigger disabled for .{} in chat {}",
        "no_triggers": "No triggers configured",
    }

    strings_ru = {
        "error": "<emoji document_id=6012681561286122335>🤤</emoji> Чот не то, чекай логи",
        "not_joined": "<emoji document_id=6012681561286122335>🤤</emoji> Нужно вступить в канал, ВНИМАТЕЛЬНО ЧИТАЙ ПРИ ПОДАЧЕ ЗАЯВКИ: https://t.me/+oScQIU-JzZhlMjAy",
        "no_media": "<emoji document_id=6012681561286122335>🤤</emoji> Не найдено медиа",
        "no_videos": "<emoji document_id=6012681561286122335>🤤</emoji> Не найдено видео",
        "triggers_config": "⚙️ <b>Настройка триггеров для Foundation</b>\n\nЧат: {} (ID: {})\n\nТекущие триггеры:\n• <code>fond</code>: {}\n• <code>vfond</code>: {}",
        "select_trigger": "Выберите триггер для настройки:",
        "enter_trigger_word": "✍️ Введите слово-триггер (или 'off' для отключения):",
        "trigger_updated": "✅ Триггер обновлен!\n\n{} теперь будет вызывать .{} в чате {}",
        "trigger_disabled": "✅ Триггер отключен для .{} в чате {}",
        "no_triggers": "Триггеры не настроены",
        "_cls_doc": "Случайное NSFW медиа",
    }

    # Другие языки (strings_de, strings_zh, strings_ja, strings_be, strings_fr, strings_ua, strings_kk) можно оставить без изменений, только обнови ссылки на канал как в strings_ru

    def __init__(self):
        self._media_cache = {}
        self._video_cache = {}
        self._cache_time = {}
        self.entity = None
        self._last_entity_check = 0
        self.entity_check_interval = 300
        self.cache_ttl = 1200

        self._spam_data = {
            'triggers': defaultdict(list),
            'blocked': {},
            'global_blocked': False,
            'global_block_time': 0
        }

        self._block_cache = TTLCache(maxsize=1000, ttl=15)

        self.SPAM_LIMIT = 3
        self.SPAM_WINDOW = 3
        self.BLOCK_DURATION = 15
        self.GLOBAL_LIMIT = 10
        self.GLOBAL_WINDOW = 10

        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "triggers_enabled",
                True,
                lambda: "Enable trigger watcher",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "spam_protection",
                True,
                lambda: "Enable spam protection for triggers",
                validator=loader.validators.Boolean()
            )
        )

    async def client_ready(self, client, db):
        self.client = client
        self._db = db
        self.triggers = self._db.get(__name__, "triggers", {})
        self._load_spam_data()
        await self._load_entity()
        # removed _send_fheta_like for safety

    def _load_spam_data(self):
        saved = self._db.get(__name__, "spam_protection", {})
        if saved:
            self._spam_data['triggers'] = defaultdict(list, saved.get('triggers', {}))
            self._spam_data['blocked'] = saved.get('blocked', {})
            self._spam_data['global_blocked'] = saved.get('global_blocked', False)
            self._spam_data['global_block_time'] = saved.get('global_block_time', 0)

    def _save_spam_data(self):
        triggers_dict = dict(self._spam_data['triggers'])
        data_to_save = {
            'triggers': triggers_dict,
            'blocked': self._spam_data['blocked'],
            'global_blocked': self._spam_data['global_blocked'],
            'global_block_time': self._spam_data['global_block_time']
        }
        self._db.set(__name__, "spam_protection", data_to_save)

    async def _load_entity(self):
        current_time = time.time()
        if (self.entity and 
            current_time - self._last_entity_check < self.entity_check_interval):
            return True
        try:
            self.entity = await self.client.get_entity(FOUNDATION_LINK)
            self._last_entity_check = current_time
            return True
        except Exception as e:
            logger.warning(f"Could not load foundation entity: {e}")
            self.entity = None
            return False

    async def _get_cached_media(self, media_type="any"):
        current_time = time.time()
        cache_key = media_type
        if (cache_key in self._cache_time and 
            current_time - self._cache_time[cache_key] < self.cache_ttl):
            if cache_key == "any" and cache_key in self._media_cache:
                return self._media_cache[cache_key]
            elif cache_key == "video" and cache_key in self._video_cache:
                return self._video_cache[cache_key]
        if not await self._load_entity():
            return None
        try:
            messages = await self.client.get_messages(self.entity, limit=1500)
        except FloodWaitError as e:
            logger.warning(f"FloodWait for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self._get_cached_media(media_type)
        except ValueError as e:
            if "Could not find the entity" in str(e):
                return None
            raise e
        if not messages:
            return []
        if media_type == "any":
            media_messages = [msg for msg in messages if msg.media]
            self._media_cache["any"] = media_messages
        else:
            video_messages = []
            for msg in messages:
                if msg.media and hasattr(msg.media, 'document'):
                    attr = getattr(msg.media.document, 'mime_type', '')
                    if 'video' in attr:
                        video_messages.append(msg)
            self._video_cache["video"] = video_messages
        self._cache_time[cache_key] = current_time
        return self._media_cache.get("any") if media_type == "any" else self._video_cache.get("video")

    # Остальные методы _check_global_spam, _check_user_spam, _check_spam, _send_media, команды fond/vfond и триггеры остаются без изменений
