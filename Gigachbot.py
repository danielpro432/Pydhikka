#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀  
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█  

#   https://t.me/famods  

# 🔒    Licensed under the GNU AGPLv3  
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html  

# ---------------------------------------------------------------------------------  
# Name: GigaChat  
# Description: GigaChat AI. БЕЗ АПИ + AUTO MODE  
# meta developer: @FAmods  
# meta banner: https://github.com/FajoX1/FAmods/blob/main/assets/banners/gigachat.png?raw=true  
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

        "auto_on": "🟢 <b>Авто-режим GigaChat включен</b>",
        "auto_off": "🔴 <b>Авто-режим GigaChat выключен</b>",
    }  

    async def client_ready(self, client, db):  
        self.db = db  
        self._client = client  
        self.ggbot = "@GigaChat_Bot"  
        self.auto = self.db.get("GigaChat", "auto", False)

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

    # обычная команда
    @loader.command()  
    async def ggchat(self, message):  
        """Задать вопрос к GigaChat"""  
        q = utils.get_args_raw(message)  
        if not q:  
            return await utils.answer(
                message, 
                self.strings["no_args"].format(self.get_prefix(), "ggchat", "[вопрос]")
            )  

        await utils.answer(message, self.strings['asking_gg'])  

        return await utils.answer(  
            message,  
            self.strings['answer'].format(  
                question=q,   
                answer=await self._ask_ai(q))  
            )  

    # включение / выключение авто режима
    @loader.command()
    async def ggauto(self, message):
        """Включить/выключить авто режим (on/off)"""
        args = utils.get_args_raw(message).lower()

        if args not in ["on", "off"]:
            return await utils.answer(message, "<b>Используй:</b> <code>.ggauto on/off</code>")

        if args == "on":
            self.auto = True
            self.db.set("GigaChat", "auto", True)
            await utils.answer(message, self.strings["auto_on"])
        else:
            self.auto = False
            self.db.set("GigaChat", "auto", False)
            await utils.answer(message, self.strings["auto_off"])

    # авто ответчик
    async def watcher(self, message):
        if not self.auto:
            return

        if message.out:
            return

        if not message.text:
            return

        try:
            answer = await self._ask_ai(message.text)
            await message.reply(answer)
        except Exception as e:
            logger.error(f"GigaChat auto error: {e}") 
