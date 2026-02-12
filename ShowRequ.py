# ---------------------------------------------------------------------------------
# Name: ShowDeps
# Description: Показывает зависимости модулей (meta requires)
# ---------------------------------------------------------------------------------

import os
import importlib.metadata

from .. import loader, utils


@loader.tds
class ShowDeps(loader.Module):
    """Показывает зависимости всех модулей"""

    strings = {"name": "ShowDeps"}

    @loader.command()
    async def deps(self, message):
        """Показать зависимости модулей"""

        result = "<b>📦 Зависимости модулей:</b>\n\n"
        found_any = False

        for mod in self.allmodules.modules:
            try:
                file_path = mod.__class__.__module__.replace(".", "/") + ".py"
                file_path = os.path.join(os.getcwd(), file_path)

                if not os.path.exists(file_path):
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.readlines()

                deps = []
                for line in content:
                    if line.strip().lower().startswith("# requires:"):
                        deps_line = line.split(":", 1)[1].strip()
                        deps = [x.strip() for x in deps_line.split(",") if x.strip()]
                        break

                if not deps:
                    continue

                found_any = True
                result += f"<b>{mod.__class__.__name__}</b>\n"

                for dep in deps:
                    pkg = dep.split("[")[0]

                    try:
                        version = importlib.metadata.version(pkg)
                        result += f"  ✅ {pkg} ({version})\n"
                    except importlib.metadata.PackageNotFoundError:
                        result += f"  ❌ {pkg} (не установлен)\n"

                result += "\n"

            except Exception:
                continue

        if not found_any:
            result += "Зависимости не найдены."

        await utils.answer(message, result)
