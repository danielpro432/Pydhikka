from hikkatl.tl.types import ( Message, UpdateDeleteMessages, UpdateEditMessage, UpdateEditChannelMessage, UpdateDeleteChannelMessages ) from .. import loader, utils from ..database import Database from ..tl_cache import CustomTelegramClient

import asyncio import contextlib import datetime import io import json import logging import mimetypes import os import time import zlib from pathlib import Path from abc import ABC, abstractmethod import magic

logger = logging.getLogger(name)

version = (2, 16, 1)

ACTION_EDIT = "edit" ACTION_DELETE = "del"

------------------ UTILS ------------------

def get_size(path: Path) -> int: return sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())

def sizeof_fmt(num: int, suffix: str = "B") -> str: for unit in ["", "Ki", "Mi", "Gi", "Ti"]: if abs(num) < 1024.0: return f"{num:3.1f}{unit}{suffix}" num /= 1024.0 return f"{num:.1f}Yi{suffix}"

class RecentsItem(typing.NamedTuple): timestamp: int chat_id: int message_id: int action: str

@classmethod
def from_edit(cls, message: Message) -> "RecentsItem":
    return cls(int(time.time()), utils.get_chat_id(message), message.id, ACTION_EDIT)

@classmethod
def from_delete(cls, message_id: int, chat_id: typing.Optional[int] = None) -> "RecentsItem":
    return cls(int(time.time()), chat_id, message_id, ACTION_DELETE)

------------------ CACHE ------------------

class CacheManager(ABC): @abstractmethod def purge(self): pass

@abstractmethod
def stats(self) -> tuple: pass

@abstractmethod
def gc(self, max_age: int, max_size: int): pass

@abstractmethod
async def store_message(self, message: Message, no_repeat: bool = False): pass

@abstractmethod
async def fetch_message(self, chat_id: int, message_id: int): pass

class CacheManagerDisc(CacheManager): def init(self, client: CustomTelegramClient, db: Database): self._client = client self._db = db self._cache_dir = Path.home() / ".nekospy" self._cache_dir.mkdir(parents=True, exist_ok=True)

def purge(self):
    for f in self._cache_dir.glob('**/*'):
        if f.is_file(): f.unlink()

def stats(self):
    dirsize = sizeof_fmt(get_size(self._cache_dir))
    messages_count = len(list(self._cache_dir.glob('**/*')))
    try:
        oldest_message = datetime.datetime.fromtimestamp(
            max(map(os.path.getctime, self._cache_dir.iterdir()))
        ).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        oldest_message = "n/a"
    return dirsize, messages_count, oldest_message

def gc(self, max_age: int, max_size: int):
    for f in self._cache_dir.glob('**/*'):
        if f.is_file() and f.stat().st_mtime < time.time() - max_age:
            f.unlink()
    while get_size(self._cache_dir) > max_size:
        min(self._cache_dir.iterdir(), key=lambda x: x.stat().st_mtime).unlink()

async def store_message(self, message: Message, no_repeat: bool = False):
    _dir = self._cache_dir / str(utils.get_chat_id(message))
    _dir.mkdir(parents=True, exist_ok=True)
    _file = _dir / str(message.id)
    try:
        text = getattr(message, 'text', getattr(message, 'raw_text', ''))
    except Exception:
        text = ''
    msg_data = {
        'text': text,
        'chat_id': utils.get_chat_id(message),
        'sender_id': getattr(message.sender, 'id', None),
        'assets': {},
        'is_chat': message.is_group or message.is_channel
    }
    _file.write_bytes(zlib.compress(json.dumps(msg_data).encode('utf-8')))
    return msg_data

async def fetch_message(self, chat_id: int, message_id: int):
    _file = self._cache_dir / str(chat_id) / str(message_id)
    if not _file.exists(): return None
    data = json.loads(zlib.decompress(_file.read_bytes()).decode('utf-8'))
    return data

------------------ MODULE ------------------

@loader.tds class NekoSpy(loader.Module): strings = {'name': 'NekoSpy'}

def __init__(self):
    self.config = loader.ModuleConfig(
        loader.ConfigValue('enable_pm', True, 'Enable PM tracking', validator=loader.validators.Boolean()),
        loader.ConfigValue('enable_groups', True, 'Enable group/channel tracking', validator=loader.validators.Boolean()),
        loader.ConfigValue('blacklist', [], 'Chats/users to ignore', validator=loader.validators.Series()),
        loader.ConfigValue('max_cache_size', 1024*1024*1024, 'Maximum cache size', validator=loader.validators.Integer(minimum=0)),
        loader.ConfigValue('max_cache_age', 7*24*60*60, 'Maximum age of messages in cache', validator=loader.validators.Integer(minimum=0))
    )
    self._cacher = None
    self._queue = []
    self._channel_id = None

async def client_ready(self):
    # создаём канал, если нужно
    channel, _ = await utils.asset_channel(self._client, 'nekospy-log', 'Deleted & edited messages', silent=True, invite_bot=True)
    self._channel_id = channel.id
    self._cacher = CacheManagerDisc(self._client, self._db)
    self._gc.start()

@loader.loop(interval=15)
async def _gc(self):
    self._cacher.gc(self.config['max_cache_age'], self.config['max_cache_size'])

async def _notify(self, msg_obj, caption: str):
    await self.inline.bot.send_message(self._channel_id, caption)

@loader.raw_handler(UpdateEditMessage)
async def pm_edit_handler(self, update: UpdateEditMessage):
    msg_data = await self._cacher.fetch_message(utils.get_chat_id(update.message), update.message.id)
    if msg_data:
        await self._notify(msg_data, f"Edited message from {update.message.sender_id}: {update.message.text}")
    await self._cacher.store_message(update.message)

@loader.raw_handler(UpdateDeleteMessages)
async def pm_delete_handler(self, update: UpdateDeleteMessages):
    for msg_id in update.messages:
        msg_data = await self._cacher.fetch_message(update.peer_id, msg_id)
        if msg_data:
            await self._notify(msg_data, f"Deleted message from {msg_data.get('sender_id')}: {msg_data.get('text')}")
