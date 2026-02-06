__version__ = (2, 16, 1)
# ©️ Dan Gazizullin, 2021-2026
# This file is a part of Hikka Userbot
# Code is licensed under CC-BY-NC-ND 4.0 unless otherwise specified.

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

import magic
from hikkatl.tl.types import (
    Message,
    UpdateDeleteMessages,
    UpdateEditMessage,
    UpdateEditChannelMessage,
    UpdateDeleteChannelMessages,
)
from .. import loader, utils
from ..database import Database
from ..tl_cache import CustomTelegramClient

logger = logging.getLogger(__name__)

# -----------------------------
# Cache helpers
# -----------------------------
def get_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

def sizeof_fmt(num: int, suffix: str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

# -----------------------------
# Recents
# -----------------------------
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

# -----------------------------
# Cache manager
# -----------------------------
class CacheManager(ABC):
    @abstractmethod
    def purge(self): ...

    @abstractmethod
    def stats(self) -> tuple: ...

    @abstractmethod
    def gc(self, max_age: int, max_size: int) -> None: ...

    @abstractmethod
    async def store_message(self, message: Message, no_repeat: bool = False) -> typing.Union[bool, dict]: ...

    @abstractmethod
    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int) -> typing.Optional[dict]: ...

class CacheManagerDisc(CacheManager):
    def __init__(self, client: CustomTelegramClient, db: Database):
        self._client = client
        self._db = db
        self._cache_dir = Path.home() / ".nekospy"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def purge(self):
        for f in self._cache_dir.iterdir():
            if f.is_dir():
                for child in f.iterdir():
                    child.unlink()
                f.rmdir()

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
        for f in self._cache_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < time.time() - max_age:
                f.unlink()
            elif f.is_dir():
                for child in f.iterdir():
                    if child.is_file() and child.stat().st_mtime < time.time() - max_age:
                        child.unlink()

        while get_size(self._cache_dir) > max_size:
            min(
                self._cache_dir.iterdir(),
                key=lambda x: x.stat().st_mtime,
            ).unlink()

    async def store_message(self, message: Message, no_repeat: bool = False) -> typing.Union[bool, dict]:
        if not hasattr(message, "id"):
            return False
        chat_id = utils.get_chat_id(message)
        _dir = self._cache_dir / str(chat_id)
        _dir.mkdir(parents=True, exist_ok=True)
        _file = _dir / str(message.id)

        sender = None
        try:
            if message.sender_id is not None:
                sender = await message.get_sender()
        except Exception:
            sender = None

        try:
            text = message.text
        except AttributeError:
            text = getattr(message, "raw_text", "")

        message_data = {
            "url": await utils.get_message_link(message),
            "text": text,
            "sender_id": getattr(sender, "id", None),
            "sender_bot": getattr(sender, "bot", False),
            "sender_name": utils.escape_html(getattr(sender, "first_name", "Unknown")),
            "chat_id": chat_id,
            "is_chat": message.is_group or message.is_channel,
        }

        _file.write_bytes(zlib.compress(json.dumps(message_data).encode("utf-8")))
        return message_data

    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int) -> typing.Optional[dict]:
        _dir = self._cache_dir / str(chat_id) if chat_id else None
        _file = _dir / str(message_id) if _dir else None
        if not _file or not _file.exists():
            return None
        data = json.loads(zlib.decompress(_file.read_bytes()).decode("utf-8"))
        data["chat_id"] = data.get("chat_id") or int(_dir.name if _dir else 0)
        return data

# -----------------------------
# Module
# -----------------------------
@loader.tds
class HikkaSpy(loader.Module):
    """Sends deleted and edited messages to a private channel"""

    strings = {"name": "HikkaSpy"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("enable_pm", True, "Enable PM capture", validator=loader.validators.Boolean()),
            loader.ConfigValue("enable_groups", True, "Enable group capture", validator=loader.validators.Boolean()),
            loader.ConfigValue("blacklist", [], "Blacklist users/chats", validator=loader.validators.Hidden(loader.validators.Series())),
            loader.ConfigValue("max_cache_size", 1024 * 1024 * 1024, "Max cache size in bytes", validator=loader.validators.Integer(minimum=0)),
            loader.ConfigValue("max_cache_age", 7 * 24 * 60 * 60, "Max cache age in seconds", validator=loader.validators.Integer(minimum=0)),
        )
        self._queue: typing.List[asyncio.coroutine] = []
        self._next: int = 0
        self._recent: typing.List[RecentsItem] = []
        self._cacher: CacheManager = None
        self._channel: int = None

    async def client_ready(self):
        # Создаём канал для пересылки
        channel, _ = await utils.asset_channel(
            self._client,
            "hikka-spy-channel",
            "Deleted and edited messages will appear here",
            silent=True,
            invite_bot=True,
        )
        self._channel = int(f"-100{channel.id}")
        self._cacher = CacheManagerDisc(self._client, self._db)
        self._gc_loop.start()

    @loader.loop(interval=15)
    async def _gc_loop(self):
        self._cacher.gc(self.config["max_cache_age"], self.config["max_cache_size"])
        self._recent = [item for item in self._recent if item.timestamp + self.config.get("recent_maximum", 3600) > time.time()]

    async def _notify(self, msg_obj: dict, caption: str):
        # Просто пересылаем текст и/или media
        caption = utils.escape_html(caption)
        await self.inline.bot.send_message(self._channel, caption, parse_mode="html")

    @loader.raw_handler(UpdateEditMessage)
    async def pm_edit_handler(self, update: UpdateEditMessage):
        self._recent.append(RecentsItem.from_edit(update.message))
        if not self.config["enable_pm"]:
            return
        msg_obj = await self._cacher.fetch_message(utils.get_chat_id(update.message), update.message.id)
        if msg_obj:
            await self._notify(msg_obj, f"Edited PM: {msg_obj['text']}")
        await self._cacher.store_message(update.message)

    @loader.raw_handler(UpdateDeleteMessages)
    async def pm_delete_handler(self, update: UpdateDeleteMessages):
        for msg_id in update.messages:
            self._recent.append(RecentsItem.from_delete(msg_id))
            msg_obj = await self._cacher.fetch_message(None, msg_id)
            if msg_obj:
                await self._notify(msg_obj, f"Deleted PM: {msg_obj['text']}")

    @loader.raw_handler(UpdateEditChannelMessage)
    async def channel_edit_handler(self, update: UpdateEditChannelMessage):
        self._recent.append(RecentsItem.from_edit(update.message))
        if not self.config["enable_groups"]:
            return
        msg_obj = await self._cacher.fetch_message(utils.get_chat_id(update.message), update.message.id)
        if msg_obj:
            await self._notify(msg_obj, f"Edited chat: {msg_obj['text']}")
        await self._cacher.store_message(update.message)

    @loader.raw_handler(UpdateDeleteChannelMessages)
    async def channel_delete_handler(self, update: UpdateDeleteChannelMessages):
        for msg_id in update.messages:
            self._recent.append(RecentsItem.from_delete(msg_id, update.channel_id))
            msg_obj = await self._cacher.fetch_message(update.channel_id, msg_id)
            if msg_obj:
                await self._notify(msg_obj, f"Deleted chat: {msg_obj['text']}")
