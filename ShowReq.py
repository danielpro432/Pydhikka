# ---------------------------------------------------------------------------------
# Name: ShowDeps
# Description: Показывает зависимости установленных модулей
# meta developer: @Dany23s
# ---------------------------------------------------------------------------------

import importlib
import importlib.metadata

from .. import loader, utils


@loader.tds
class ShowDeps(loader.Module):
    """Показывает зависимости всех модулей"""

    strings = {
        "name": "ShowDeps",
    }

    @loader.command()
    async def deps(self, message):
        """Показать зависимости модулей"""

        result = "<b>📦 Зависимости модулей:</b>\n\n"

        for mod in self.allmodules.modules:
            name = mod.__class__.__name__

            requires = getattr(mod, "__doc__", "")
            lines = requires.split("\n")

            deps = []
            for line in lines:
                if "requires:" in line.lower():
                    deps_line = line.split("requires:")[1].strip()
                    deps = [x.strip() for x in deps_line.split(",")]

            if not deps:
                continue

            result += f"<b>{name}</b>\n"

            for dep in deps:
                pkg = dep.split("[")[0]

                try:
                    version = importlib.metadata.version(pkg)
                    result += f"  ✅ {pkg} ({version})\n"
                except importlib.metadata.PackageNotFoundError:
                    result += f"  ❌ {pkg} (не установлен)\n"

            result += "\n"

        await utils.answer(message, result)
