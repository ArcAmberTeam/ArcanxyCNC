#!/usr/bin/env python3
"""Enforce QML capability imports and Python public-entry dependency graphs."""

import ast
import importlib.util
import pathlib
import re
import sys
import sysconfig

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
MODULES = ROOT / "qml" / "BetterCnc"
ALLOWED = {
    "Ui": set(),
    "Catalog": set(),
    "Manual": {"Ui", "Catalog"},
    "Toolpath": {"Ui", "Catalog"},
    "Program": {"Ui", "Catalog"},
    "Chrome": {"Ui", "Catalog", "Manual", "Toolpath"},
}
errors = []
for directory in sorted(MODULES.iterdir()):
    if not directory.is_dir():
        continue
    owner = directory.name
    if owner not in ALLOWED:
        errors.append(f"Unregistered module: {owner}")
        continue
    manifest = directory / "qmldir"
    if not manifest.exists():
        errors.append(f"Missing public manifest: {manifest}")
        continue
    declared = set(re.findall(r"\b([\w.-]+\.qml)\b", manifest.read_text()))
    for source in directory.rglob("*.qml"):
        if source.parent == directory and source.name not in declared:
            errors.append(f"Undeclared public/internal type: {source}")
        text = source.read_text()
        for imported in re.findall(r"^import\s+BetterCnc\.([\w.]+)", text, re.M):
            if imported not in ALLOWED[owner] and imported != owner:
                errors.append(f"{source}: forbidden dependency {owner} → {imported}")
        for imported in re.findall(r'^import\s+"([^"]+)"', text, re.M):
            target = (source.parent / imported).resolve()
            if not target.is_relative_to(directory.resolve()):
                errors.append(f"{source}: cross-module private import {imported}")
        for imported in re.findall(
            r'Qt\.(?:createComponent|resolvedUrl)\(\s*[\'"]([^\'"]+)[\'"]', text
        ):
            target = (source.parent / imported).resolve()
            if not target.is_relative_to(directory.resolve()):
                errors.append(f"{source}: cross-module private resource {imported}")
        if re.search(r"^import\s+(QtWebEngine|QtWebView|QtNetwork)", text, re.M):
            errors.append(f"{source}: platform access in a presentation module")
        if re.search(r"\b(XMLHttpRequest|WebSocket)\b", text):
            errors.append(f"{source}: network access in a presentation module")

for source in (ROOT / "qml").glob("*.qml"):
    if re.search(r'^import\s+".*BetterCnc/', source.read_text(), re.M):
        errors.append(f"{source}: composition must use named public modules")

# Each Python capability owns its underscore-prefixed implementation files.
# Application launchers are composition roots with one declared dependency.
PYTHON_GRAPH = {
    "bettercnc": set(),
    "bettercnc.desktop": {"bettercnc", "bettercnc.session", "bettercnc_error_records"},
    "bettercnc.session": set(),
    "betterlinuxcnc_service": {
        "bettercnc_controller",
        "bettercnc_preview",
        "bettercnc_error_records",
    },
    "bettercnc_controller": {"bettercnc_error_records"},
    "bettercnc_error_records": set(),
    "bettercnc_preview": set(),
    "desktop-launcher": {"bettercnc.desktop"},
    "service-launcher": {"betterlinuxcnc_service"},
    "bettercnc_launcher": {"bettercnc_error_records"},
    "orchestration-launcher": {"bettercnc_launcher"},
}
PYTHON_ROOTS = [
    ROOT / "python",
    REPOSITORY / "app/controller/src",
    REPOSITORY / "app/launcher/src",
    REPOSITORY / "app/platform/error-records/python/src",
]
VENDOR_MODULES = {"linuxcnc", "gcode", "hal"}
# Preview's read-only linuxcnc.stat poll initializes native tool data before
# gcode.parse. It never owns command, HAL or error-channel access.
VENDOR_OWNERS = {
    "bettercnc_controller": {"linuxcnc", "hal"},
    "bettercnc_preview": {"gcode", "linuxcnc"},
}


def owner_of(module):
    candidates = [name for name in PYTHON_GRAPH if module == name or module.startswith(name + ".")]
    return max(candidates, key=len) if candidates else None


def source_module(source, root):
    parts = list(source.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


sources = []
public_exports = {}
for python_root in PYTHON_ROOTS:
    if not python_root.is_dir():
        errors.append(f"Missing Python capability source directory: {python_root}")
        continue
    for source in sorted(python_root.rglob("*.py")):
        module = source_module(source, python_root)
        tree = ast.parse(source.read_text(), filename=str(source))
        sources.append((source, module, owner_of(module), tree))
        if source.name == "__init__.py":
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                ):
                    public_exports[module] = set(ast.literal_eval(node.value))
for source, owner in [
    (ROOT / "app/main.py", "desktop-launcher"),
    (ROOT / "app/betterlinuxcnc.in", "desktop-launcher"),
    (REPOSITORY / "app/controller/packaging/betterlinuxcnc-service.in", "service-launcher"),
    (REPOSITORY / "app/launcher/packaging/betterlinuxcnc-launch.in", "orchestration-launcher"),
]:
    sources.append((source, "", owner, ast.parse(source.read_text(), filename=str(source))))


def is_standard_library(module):
    if hasattr(sys, "stdlib_module_names"):
        return module in sys.stdlib_module_names
    # Keep the source checker usable with older host Python installations.
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        return False
    if spec.origin in {"built-in", "frozen"}:
        return True
    origin = pathlib.Path(spec.origin).resolve()
    return origin.is_relative_to(pathlib.Path(sysconfig.get_path("stdlib"))) and not any(
        part in {"site-packages", "dist-packages"} for part in origin.parts
    )


def check_import(source, owner, imported, names, line):
    prefix = imported.split(".")[0]
    label = f"{source}:{line}"
    if prefix in VENDOR_MODULES and prefix not in VENDOR_OWNERS.get(owner, set()):
        errors.append(f"{label}: vendor access forbidden in {owner}: {imported}")
    target = owner_of(imported)
    if target == owner:
        return
    if target:
        if target not in PYTHON_GRAPH[owner]:
            errors.append(f"{label}: forbidden dependency {owner} → {target}")
        elif imported != target:
            errors.append(f"{label}: cross-module private import {imported}")
        elif names and any(name not in public_exports.get(target, set()) for name in names):
            errors.append(f"{label}: import is not declared by {target}.__all__: {names}")
    elif owner in {"bettercnc.session", "bettercnc_launcher"} and not is_standard_library(prefix):
        errors.append(f"{label}: {owner} may only depend on the standard library: {imported}")


for source, module, owner, tree in sources:
    if owner is None:
        errors.append(f"{source}: unregistered Python capability {module}")
        continue
    package = module if source.name == "__init__.py" else module.rpartition(".")[0]
    importlib_names = {"importlib"}
    dynamic_names = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_names.add(alias.asname or alias.name)
                check_import(source, owner, alias.name, [], node.lineno)
        elif isinstance(node, ast.ImportFrom):
            imported = node.module or ""
            if node.level:
                imported = importlib.util.resolve_name("." * node.level + imported, package)
            if imported == "importlib":
                dynamic_names.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "import_module"
                )
            check_import(source, owner, imported, [alias.name for alias in node.names], node.lineno)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dynamic = (isinstance(node.func, ast.Name) and node.func.id in dynamic_names) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in importlib_names
            and node.func.attr == "import_module"
        )
        if dynamic:
            if (
                not node.args
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
            ):
                errors.append(
                    f"{source}:{node.lineno}: dynamic imports must name a literal public entry"
                )
                continue
            imported = node.args[0].value
            if imported.startswith("."):
                imported = importlib.util.resolve_name(imported, package)
            check_import(source, owner, imported, [], node.lineno)

if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(
    f"Module boundaries passed ({len(ALLOWED)} QML modules, "
    f"{len(PYTHON_GRAPH)} Python capabilities/launchers)."
)
