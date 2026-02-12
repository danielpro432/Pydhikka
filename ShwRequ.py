# ---------------------------------------------------------------------------------
# Name: ShowDeps
# Description: Показывает зависимости модулей (meta requires)
# ---------------------------------------------------------------------------------

import inspect
import sys
import importlib.metadata

from .. import loader, utils


@loader.tds
class ShowDeps(loader.Module):
    strings = {"name": "ShowDeps"}

    @loader.command()
    async def deps(self, message):
        result = "<b>📦 Зависимости модулей:</b>\n\n"
        found_any = False

        for mod in self.allmodules.modules:
            try:
                module_obj = sys.modules.get(mod.__class__.__module__)
                if not module_obj:
                    continue

                source = inspect.getsource(module_obj)
            except Exception:
                continue

            deps = []
            for line in source.split("\n"):
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

        if not found_any:
            result += "Зависимости не найдены."

        await utils.answer(message, result)
