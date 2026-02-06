__version__ = (2, 16, 1)  # ©️ Dan Gazizullin, 2021-2026
# NekoSpy: отслеживание удалённых и отредактированных сообщений
# https://github.com/hikariatama/Hikka

import asyncio
import contextlib
import datetime
import io
import json
import logging
import mimetypes
import os
import time
import typing
import zlib
from abc import ABC, abstractmethod
from pathlib import Path

import filetype  # вместо python-magic

from hikkatl.tl.types import (
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    Message,
    UpdateDeleteChannelMessages,
    UpdateDeleteMessages,
    UpdateEditChannelMessage,
    UpdateEditMessage,
)
from hikkatl.utils import get_display_name

from .. import loader, utils
from ..database import Database
from ..pointers import PointerList
from ..tl_cache import CustomTelegramClient

logger = logging.getLogger(__name__)

# -----------------------
# Вспомогательные функции
# -----------------------

def get_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

def sizeof_fmt(num: int, suffix: str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

# -----------------------
# Классы кеша
# -----------------------

class RecentsItem(typing.NamedTuple):
    timestamp: int
    chat_id: int
    message_id: int
    action: str

    @classmethod
    def from_edit(cls, message: Message) -> "RecentsItem":
        return cls(
            timestamp=int(time.time()),
            chat_id=utils.get_chat_id(message),
            message_id=message.id,
            action="edit",
        )

    @classmethod
    def from_delete(cls, message_id: int, chat_id: typing.Optional[int] = None) -> "RecentsItem":
        return cls(
            timestamp=int(time.time()),
            chat_id=chat_id,
            message_id=message_id,
            action="del",
        )

class CacheManager(ABC):
    @abstractmethod
    def purge(self): ...

    @abstractmethod
    def stats(self) -> tuple: ...

    @abstractmethod
    def gc(self, max_age: int, max_size: int) -> None: ...

    @abstractmethod
    async def store_message(self, message: Message, no_repeat: bool = False):
        ...

    @abstractmethod
    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int):
        ...

class CacheManagerDisc(CacheManager):
    def __init__(self, client: CustomTelegramClient, db: Database):
        self._client = client
        self._db = db
        self._cache_dir = Path.home() / ".nekospy"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def purge(self):
        for _file in self._cache_dir.iterdir():
            if _file.is_file():
                _file.unlink()
            else:
                for _child in _file.iterdir():
                    _child.unlink()
                _file.rmdir()

    def stats(self) -> tuple:
        dirsize = sizeof_fmt(get_size(self._cache_dir))
        messages_count = len(list(self._cache_dir.glob("**/*")))
        try:
            oldest_message = datetime.datetime.fromtimestamp(
                max(map(os.path.getctime, self._cache_dir.iterdir()))
            ).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            oldest_message = "n/a"
        return dirsize, messages_count, oldest_message

    def gc(self, max_age: int, max_size: int) -> None:
        for _file in self._cache_dir.iterdir():
            if _file.is_file() and _file.stat().st_mtime < time.time() - max_age:
                _file.unlink()
            elif _file.is_dir():
                for _child in _file.iterdir():
                    if _child.is_file() and _child.stat().st_mtime < time.time() - max_age:
                        _child.unlink()

        while get_size(self._cache_dir) > max_size:
            min(self._cache_dir.iterdir(), key=lambda x: x.stat().st_mtime).unlink()

    async def store_message(self, message: Message, no_repeat: bool = False):
        if not hasattr(message, "id"):
            return False

        _dir = self._cache_dir / str(utils.get_chat_id(message))
        _dir.mkdir(parents=True, exist_ok=True)
        _file = _dir / str(message.id)

        sender = getattr(message, "sender", None)
        try:
            if message.sender_id is not None and sender is None:
                sender = await message.get_sender()
            chat = await message.get_chat()
            if message.sender_id is None:
                sender = chat
        except Exception:
            if no_repeat:
                return False
            await asyncio.sleep(1)
            return await self.store_message(message, True)

        try:
            text = message.text
        except AttributeError:
            text = getattr(message, "raw_text", "")

        is_chat: bool = message.is_group or message.is_channel
        message_data = {
            "url": await utils.get_message_link(message),
            "text": text,
            "sender_id": getattr(sender, "id", None),
            "sender_bot": getattr(sender, "bot", False),
            "sender_name": utils.escape_html(get_display_name(sender)),
            "sender_url": utils.get_entity_url(sender),
            "chat_id": chat.id,
            **({"chat_name": utils.escape_html(get_display_name(chat)),
                "chat_url": utils.get_entity_url(chat)} if is_chat else {}),
            "assets": await self._extract_assets(message),
            "is_chat": is_chat,
            "via_bot_id": bool(getattr(message, "via_bot_id", False)),
        }

        _file.write_bytes(zlib.compress(json.dumps(message_data).encode("utf-8")))
        return message_data

    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int):
        _dir = self._cache_dir / str(chat_id) if chat_id else None
        _file = (_dir / str(message_id)) if _dir else None
        if not _file or not _file.exists():
            # ищем в любых чатах
            for _dir in self._cache_dir.iterdir():
                _file = _dir / str(message_id)
                if _file.exists():
                    break
            else:
                return None
        data = json.loads(zlib.decompress(_file.read_bytes()).decode("utf-8"))
        data["chat_id"] = data.get("chat_id") or int(_dir.name if _dir else 0)
        return data

    async def _extract_assets(self, message: Message):
        return {}  # упрощённо, можно добавить фото/видео/документы

# -----------------------
# Основной модуль
# -----------------------

@loader.tds
class NekoSpy(loader.Module):
    """Отслеживание удалённых и отредактированных сообщений"""

    strings = {"name": "NekoSpy"}

    async def client_ready(self):
        # канал куда пересылать
        channel, _ = await utils.asset_channel(
            self._client, "hikka-nekospy",
            "Deleted and edited messages will appear there",
            silent=True, invite_bot=True)
        self._channel = int(f"-100{channel.id}")
        self._cacher = CacheManagerDisc(self._client, self._db)
        self._recent: PointerList = self.pointer("recent_msgs", [], item_type=RecentsItem)
        self._gc.start()

    @loader.loop(interval=15)
    async def _gc(self):
        self._cacher.gc(7*24*3600, 1024*1024*1024)
        for item in self._recent:
            if item.timestamp + 3600 < time.time():
                self._recent.remove(item)

    @loader.raw_handler(UpdateDeleteMessages)
    async def pm_delete_handler(self, update: UpdateDeleteMessages):
        for msg_id in update.messages:
            self._recent.append(RecentsItem.from_delete(msg_id))
            msg_obj = await self._cacher.fetch_message(None, msg_id)
            if msg_obj:
                await self.inline.bot.send_message(self._channel, f"Deleted PM: {msg_obj['text']}")

    @loader.raw_handler(UpdateEditMessage)
    async def pm_edit_handler(self, update: UpdateEditMessage):
        self._recent.append(RecentsItem.from_edit(update.message))
        msg_obj = await self._cacher.fetch_message(utils.get_chat_id(update.message), update.message.id)
        if msg_obj and update.message.raw_text != msg_obj["text"]:
            await self.inline.bot.send_message(self._channel, f"Edited PM: {msg_obj['text']}")
