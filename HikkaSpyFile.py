__version__ = (2, 16, 1)  # ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# Code is licensed under CC-BY-NC-ND 4.0 unless otherwise specified.
# 🌐 https://github.com/hikariatama/Hikka
# 🔑 https://creativecommons.org/licenses/by-nc-nd/4.0/
# meta pic: https://0x0.st/oRer.webp
# meta developer: @hikarimods
# scope: hikka_min 1.6.3
# requires: filetype
# packurl: https://gist.github.com/marat2509/38072f28bc92d209126cd59858b667e4/raw/5c8eabcbec5072fc0a5d4c823a48ae9ea77bb659/nekospy.yml

import asyncio
import contextlib
import datetime
import io
import json
import logging
import mimetypes
import os
import re
import time
import typing
import zlib
from abc import ABC, abstractmethod
from pathlib import Path

import filetype
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


def get_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())


def sizeof_fmt(num: int, suffix: str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


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
            action=ACTION_EDIT,
        )

    @classmethod
    def from_delete(
        cls,
        message_id: int,
        chat_id: typing.Optional[int] = None,
    ) -> "RecentsItem":
        return cls(
            timestamp=int(time.time()),
            chat_id=chat_id,
            message_id=message_id,
            action=ACTION_DELETE,
        )


ACTION_EDIT = "edit"
ACTION_DELETE = "del"


class CacheManager(ABC):
    @abstractmethod
    def purge(self):
        """Purge the cache"""

    @abstractmethod
    def stats(self) -> tuple:
        """Return cache statistics"""

    @abstractmethod
    def gc(self, max_age: int, max_size: int) -> None:
        """Clean the cache"""

    @abstractmethod
    async def store_message(
        self,
        message: Message,
        no_repeat: bool = False,
    ) -> typing.Union[bool, typing.Dict[str, typing.Any]]:
        """Store a message in the cache"""

    @abstractmethod
    async def fetch_message(
        self,
        chat_id: typing.Optional[int],
        message_id: int,
    ) -> typing.Optional[dict]:
        """Fetch a message from the cache"""


class CacheManagerDisc(CacheManager):
    def __init__(self, client: CustomTelegramClient, db: Database):
        self._client = client
        self._db = db
        self._cache_dir = Path.home().joinpath(".nekospy")
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
            if _file.is_file():
                if _file.stat().st_mtime < time.time() - max_age:
                    _file.unlink()
            else:
                for _child in _file.iterdir():
                    if (
                        _child.is_file()
                        and _child.stat().st_mtime < time.time() - max_age
                    ):
                        _child.unlink()

        while get_size(self._cache_dir) > max_size:
            min(
                self._cache_dir.iterdir(),
                key=lambda x: x.stat().st_mtime,
            ).unlink()

    async def store_message(
        self,
        message: Message,
        no_repeat: bool = False,
    ) -> typing.Union[bool, typing.Dict[str, typing.Any]]:
        if not hasattr(message, "id"):
            return False

        _dir = self._cache_dir.joinpath(str(utils.get_chat_id(message)))
        _dir.mkdir(parents=True, exist_ok=True)
        _file = _dir.joinpath(str(message.id))

        sender = None
        try:
            if message.sender_id is not None:
                try:
                    sender = await self._client.get_entity(message.sender_id, exp=0)
                except Exception:
                    sender = await message.get_sender()

            try:
                chat = await self._client.get_entity(utils.get_chat_id(message), exp=0)
            except Exception:
                chat = await message.get_chat()

            if message.sender_id is None:
                sender = chat
        except ValueError:
            if no_repeat:
                logger.debug("Failed to get sender/chat, skipping", exc_info=True)
                return False
            await asyncio.sleep(5)
            return await self.store_message(message, True)

        is_chat: bool = message.is_group or message.is_channel

        try:
            text: str = message.text
        except AttributeError:
            text: str = message.raw_text

        message_data = {
            "url": await utils.get_message_link(message),
            "text": text,
            "sender_id": sender.id if sender else None,
            "sender_bot": not not getattr(sender, "bot", False),
            "sender_name": utils.escape_html(get_display_name(sender)),
            "sender_url": utils.get_entity_url(sender),
            "chat_id": chat.id,
            **(
                {
                    "chat_name": utils.escape_html(get_display_name(chat)),
                    "chat_url": utils.get_entity_url(chat),
                }
                if is_chat
                else {}
            ),
            "assets": await self._extract_assets(message),
            "is_chat": is_chat,
            "via_bot_id": not not message.via_bot_id,
        }

        # ⚡ ЗАМЕНА python-magic на filetype
        for key, file in message_data["assets"].items():
            if file:
                file_bytes = await self._client.download_file(
                    InputDocumentFileLocation(**file), bytes
                )
                kind = filetype.guess(file_bytes)
                ext = f".{kind.extension}" if kind else ".bin"
                file["ext"] = ext

        _file.write_bytes(zlib.compress(json.dumps(message_data).encode("utf-8")))
        return message_data

    async def fetch_message(
        self,
        chat_id: typing.Optional[int],
        message_id: int,
    ) -> typing.Optional[dict]:
        _dir = None
        if chat_id:
            _dir = self._cache_dir.joinpath(str(chat_id))
            _file = _dir.joinpath(str(message_id))
        else:
            for _dir in self._cache_dir.iterdir():
                _file = _dir.joinpath(str(message_id))
                if _file.exists():
                    break
            else:
                _file = None

        if not _file or not _file.exists():
            return None

        data = json.loads(zlib.decompress(_file.read_bytes()).decode("utf-8"))
        data["chat_id"] = data["chat_id"] or int(_dir.name if _dir else 0)

        return data

    async def _extract_assets(self, message: Message) -> typing.Dict[str, dict]:
        return {
            attribute: value
            for attribute, value in filter(
                lambda x: x[1],
                {
                    arg: getattr(message, arg)
                    for arg in {
                        "photo",
                        "audio",
                        "document",
                        "sticker",
                        "video",
                        "voice",
                        "video_note",
                        "gif",
                    }
                }.items(),
            )
        }
