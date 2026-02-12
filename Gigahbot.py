#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

#   https://t.me/famods

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: GigaChat
# Description: GigaChat AI. БЕЗ АПИ + AUTO MODE (по чатам)
# meta developer: @FAmods
# requires: aiohttp
# ---------------------------------------------------------------------------------

import asyncio
import logging
import hikkatl

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class GigaChat(loader.Module):
    """GigaChat AI. БЕЗ АПИ + AUTO MODE"""

    strings = {
        "name": "GigaChat",

        "no_args": "<emoji document_id=5854929766146118183>❌</emoji> <b>Нужно </b><code>{}{} {}</code>",

        "asking_gg": "<emoji document_id=5325787248363314644>🔄</emoji> <b>Спрашиваю GigaChat...</b>",

        "answer": """<emoji document_id=5357555931745893459>🗿</emoji> <b>Ответ:</b> {answer}

<emoji document_id=5785419053354979106>❔</emoji> <b>Вопрос:</b> {question}""",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        self.ggbot = "@GigaChat_Bot"

        # список чатов где включён авто режим
        self.auto_chats = self.db.get("GigaChat", "auto_chats", [])

        # активация диалога
        try:
            async with self._client.conversation(self.ggbot) as conv:
                msg = await conv.send_message("/start")
                r = await conv.get_response()
                await msg.delete()
                await r.delete()
        except:
            pass

    async def _ask_ai(self, q):
        while True:
            try:
                async with self._client.conversation(self.ggbot) as conv:
                    msg = await conv.send_message(q)
                    r = await conv.get_response()
                    await msg.delete()
                    await r.delete()
                return r.text
            except hikkatl.errors.common.AlreadyInConversationError:
                await asyncio.sleep(5)

    # --------------------------------------------------
    # Обычная команда
    # --------------------------------------------------

    @loader.command()
    async def ggchat(self, message):
        """Задать вопрос к GigaChat"""
        q = utils.get_args_raw(message)
        if not q:
            return await utils.answer(
                message,
                self.strings["no_args"].format(self.get_prefix(), "ggchat", "[вопрос]")
            )

        await utils.answer(message, self.strings["asking_gg"])

        answer = await self._ask_ai(q)

        return await utils.answer(
            message,
            self.strings["answer"].format(
                question=q,
                answer=answer
            )
        )

    # --------------------------------------------------
    # Управление авто режимом
    # --------------------------------------------------

    @loader.command()
    async def ggauto(self, message):
        """
        Управление авто-режимом

        .ggauto on
        .ggauto off
        .ggauto add chat_id
        .ggauto del chat_id
        .ggauto offall
        """

        args = utils.get_args_raw(message).split()

        if not args:
            return await utils.answer(
                message,
                "<b>Используй:</b>\n"
                "<code>.ggauto on</code>\n"
                "<code>.ggauto off</code>\n"
                "<code>.ggauto add chat_id</code>\n"
                "<code>.ggauto del chat_id</code>\n"
                "<code>.ggauto offall</code>"
            )

        cmd = args[0].lower()
        chat_id = utils.get_chat_id(message)

        # включить в текущем чате
        if cmd == "on":
            if chat_id not in self.auto_chats:
                self.auto_chats.append(chat_id)
                self.db.set("GigaChat", "auto_chats", self.auto_chats)
            return await utils.answer(message, "🟢 Авто включён в этом чате")

        # выключить в текущем чате
        if cmd == "off":
            if chat_id in self.auto_chats:
                self.auto_chats.remove(chat_id)
                self.db.set("GigaChat", "auto_chats", self.auto_chats)
            return await utils.answer(message, "🔴 Авто выключен в этом чате")

        # добавить чат по ID
        if cmd == "add" and len(args) > 1:
            try:
                cid = int(args[1])
                if cid not in self.auto_chats:
                    self.auto_chats.append(cid)
                    self.db.set("GigaChat", "auto_chats", self.auto_chats)
                return await utils.answer(message, f"🟢 Добавлен чат {cid}")
            except:
                return await utils.answer(message, "❌ Неверный chat_id")

        # удалить чат по ID
        if cmd == "del" and len(args) > 1:
            try:
                cid = int(args[1])
                if cid in self.auto_chats:
                    self.auto_chats.remove(cid)
                    self.db.set("GigaChat", "auto_chats", self.auto_chats)
                return await utils.answer(message, f"🔴 Удалён чат {cid}")
            except:
                return await utils.answer(message, "❌ Неверный chat_id")

        # выключить везде
        if cmd == "offall":
            self.auto_chats = []
            self.db.set("GigaChat", "auto_chats", self.auto_chats)
            return await utils.answer(message, "⛔ Авто выключен во всех чатах")

    # --------------------------------------------------
    # Watcher (строго только активированные чаты)
    # --------------------------------------------------

    async def watcher(self, message):
        if message.out:
            return

        chat_id = utils.get_chat_id(message)

        if chat_id not in self.auto_chats:
            return

        if not message.text:
            return

        try:
            answer = await self._ask_ai(message.text)
            await message.reply(answer)
        except Exception as e:
            logger.error(f"GigaChat auto error: {e}")
