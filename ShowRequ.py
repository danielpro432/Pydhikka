# ---------------------------------------------------------------------------------
# Name: PipList
# Description: Показывает все установленные pip-пакеты
# ---------------------------------------------------------------------------------

import pkg_resources

from .. import loader, utils


@loader.tds
class PipList(loader.Module):
    """Показывает установленные pip пакеты"""

    strings = {"name": "PipList"}

    @loader.command()
    async def piplist(self, message):
        """Показать все установленные пакеты"""

        packages = sorted(
            [f"{d.project_name}=={d.version}" for d in pkg_resources.working_set],
            key=lambda x: x.lower()
        )

        text = "<b>📦 Установленные пакеты:</b>\n\n"
        text += "\n".join(packages)

        if len(text) > 4000:
            await utils.answer(message, text[:4000] + "\n\n⚠️ Слишком длинный вывод.")
        else:
            await utils.answer(message, text)
