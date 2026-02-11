# -*- coding: utf-8 -*-
# meta developer: @yourname
# name: UniversalSearch
# description: Модуль для поиска аниме, игр, мультфильмов и артов по кадру. Поддержка SauceNAO и Yandex.Images.
# meta banner: https://raw.githubusercontent.com/yourname/banner/main/universal_search.jpg

import logging
import io
import aiohttp
import base64
from telethon import errors
from telethon.tl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class UniversalSearchMod(loader.Module):
    """Модуль для поиска аниме, игр, мультиков и артов по кадру."""
    strings = {
        "name": "UniversalSearch",
        "no_reply": "<b>Пожалуйста, ответьте на сообщение с картинкой.</b>",
        "searching": "<b>🔍 Ищу по кадру...</b>",
        "not_found": "<b>❌ Не удалось найти результат с достаточной точностью.</b>",
        "result": "<b>🔎 Найдено:</b>\n\n<b>Источник:</b> {source}\n<b>Название:</b> {title}\n<b>Сходство:</b> {similarity:.1f}%\n<b>Ссылка:</b> {url}"
    }

    def __init__(self):
        super().__init__()
        self.session = None
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "saucenao_api_key",
                "",
                lambda: "Ваш SauceNAO API Key",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "similarity_threshold",
                70,
                lambda: "Минимальный процент сходства для показа результата",
                validator=loader.validators.Integer(minimum=10, maximum=100)
            )
        )

    async def client_ready(self, client, db):
        self.client = client
        self.session = aiohttp.ClientSession()

    async def _search_saucenao(self, image_bytes: bytes):
        api_key = self.config["saucenao_api_key"]
        if not api_key:
            return []

        url = "https://saucenao.com/search.php"
        files = {"file": image_bytes}
        params = {"output_type": 2, "api_key": api_key}

        try:
            async with self.session.post(url, params=params, data=files) as resp:
                if resp.status != 200:
                    logger.warning(f"SauceNAO HTTP error: {resp.status}")
                    return []
                data = await resp.json()
                results = []
                for item in data.get("results", []):
                    header = item.get("header", {})
                    similarity = float(header.get("similarity", 0))
                    if similarity >= self.config["similarity_threshold"]:
                        data_item = item.get("data", {})
                        title = data_item.get("title") or data_item.get("eng_name") or "Неизвестно"
                        source = data_item.get("source") or data_item.get("ext_urls", ["Неизвестно"])[0]
                        url_result = data_item.get("ext_urls", [""])[0]
                        results.append({"title": title, "source": source, "similarity": similarity, "url": url_result})
                return results
        except Exception as e:
            logger.exception(e)
            return []

    async def _search_yandex(self, image_bytes: bytes):
        # Yandex reverse image search через URL API (можно доработать через aiohttp)
        # Возвращаем просто ссылку на поиск, чтобы пользователь сам смотрел
        encoded = base64.b64encode(image_bytes).decode()
        search_url = f"https://yandex.ru/images/search?rpt=imageview&img_url=data:image/jpeg;base64,{encoded}"
        return [{"title": "Проверить на Yandex.Images", "source": "Yandex.Images", "similarity": 100, "url": search_url}]

    @loader.command(
        ru_doc="<reply на изображение> - Поиск аниме, игр и артов по кадру",
        en_doc="<reply to image> - Search anime, games, and art by frame"
    )
    async def anisearchcmd(self, message: Message):
        reply = await message.get_reply_message()
        if not reply or not getattr(reply, "media", None):
            await utils.answer(message, self.strings("no_reply"))
            return

        status_msg = await utils.answer(message, self.strings("searching"))

        try:
            image_bytes = await self.client.download_media(reply, file=io.BytesIO())
            image_bytes.seek(0)
            img_data = image_bytes.read()

            # 1. SauceNAO
            results = await self._search_saucenao(img_data)

            # 2. Если нет результатов, даём ссылку на Yandex
            if not results:
                results = await self._search_yandex(img_data)

            if not results:
                await status_msg.edit(self.strings("not_found"))
                return

            text = ""
            for res in results[:3]:  # Показываем максимум 3 результата
                text += self.strings("result").format(
                    source=res["source"],
                    title=res["title"],
                    similarity=res["similarity"],
                    url=res["url"]
                ) + "\n\n"

            await status_msg.edit(text.strip())

        except Exception as e:
            logger.exception(e)
            await status_msg.edit("<b>❌ Произошла ошибка при поиске.</b>")

    async def client_unload(self):
        if self.session:
            await self.session.close()
