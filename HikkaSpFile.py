__version__ = (2, 16, 1)  # ©️ Dan Gazizullin, 2021-2023

"""
NekoSpy for Hikka Userbot
Tracks edited and deleted messages
"""

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

# -------------------- утилиты --------------------

def get_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

def sizeof_fmt(num: int, suffix: str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

# -------------------- recents --------------------

class RecentsItem(typing.NamedTuple):
    timestamp: int
    chat_id: int
    message_id: int
    action: str

    @classmethod
    def from_edit(cls, message: Message) -> "RecentsItem":
        return cls(int(time.time()), utils.get_chat_id(message), message.id, ACTION_EDIT)

    @classmethod
    def from_delete(cls, message_id: int, chat_id: typing.Optional[int] = None) -> "RecentsItem":
        return cls(int(time.time()), chat_id, message_id, ACTION_DELETE)

ACTION_EDIT = "edit"
ACTION_DELETE = "del"

# -------------------- CacheManager --------------------

class CacheManager(ABC):
    @abstractmethod
    def purge(self): ...
    @abstractmethod
    def stats(self) -> tuple: ...
    @abstractmethod
    def gc(self, max_age: int, max_size: int) -> None: ...
    @abstractmethod
    async def store_message(self, message: Message, no_repeat: bool = False) -> typing.Optional[dict]: ...
    @abstractmethod
    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int) -> typing.Optional[dict]: ...

class CacheManagerDisc(CacheManager):
    def __init__(self, client: CustomTelegramClient, db: Database):
        self._client = client
        self._db = db
        self._cache_dir = Path.home() / ".nekospy"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def purge(self):
        for _file in self._cache_dir.iterdir():
            if _file.is_dir():
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
                    if _child.stat().st_mtime < time.time() - max_age:
                        _child.unlink()
        while get_size(self._cache_dir) > max_size:
            min(self._cache_dir.iterdir(), key=lambda x: x.stat().st_mtime).unlink()

    async def store_message(self, message: Message, no_repeat: bool = False) -> typing.Optional[dict]:
        if not hasattr(message, "id"):
            return None
        _dir = self._cache_dir / str(utils.get_chat_id(message))
        _dir.mkdir(parents=True, exist_ok=True)
        _file = _dir / str(message.id)

        try:
            text = message.text if hasattr(message, "text") else message.raw_text
        except Exception:
            text = ""

        message_data = {
            "text": text,
            "chat_id": utils.get_chat_id(message),
            "sender_id": getattr(message.sender, "id", None),
        }
        _file.write_bytes(zlib.compress(json.dumps(message_data).encode("utf-8")))
        return message_data

    async def fetch_message(self, chat_id: typing.Optional[int], message_id: int) -> typing.Optional[dict]:
        _file = None
        if chat_id:
            _file = self._cache_dir / str(chat_id) / str(message_id)
        else:
            for _dir in self._cache_dir.iterdir():
                _file = _dir / str(message_id)
                if _file.exists():
                    break
            else:
                return None
        if not _file.exists():
            return None
        return json.loads(zlib.decompress(_file.read_bytes()).decode("utf-8"))

# -------------------- основной модуль --------------------

@loader.tds
class NekoSpy(loader.Module):
    """Tracks edited and deleted messages"""
    strings = {"name": "NekoSpy"}

    async def client_ready(self):
        self._cacher = CacheManagerDisc(self._client, self._db)
        self._recent: PointerList = self.pointer("recent_msgs", [], item_type=RecentsItem)

    @loader.command()
    async def stat(self, message: Message):
        dirsize, messages_count, oldest_message = self._cacher.stats()
        await utils.answer(message, f"Cache size: {dirsize}\nMessages: {messages_count}\nOldest: {oldest_message}") 
