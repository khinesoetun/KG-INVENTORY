# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


MSYS2_BIN = Path(r"C:\msys64\ucrt64\bin")

if not MSYS2_BIN.exists():
    raise FileNotFoundError(
        f"MSYS2 DLL folder not found: {MSYS2_BIN}"
    )


# MSYS2 ရှိ DLL အားလုံးကို bundle ထဲထည့်မယ်
binaries = [
    (str(dll_path), ".")
    for dll_path in MSYS2_BIN.glob("*.dll")
]


datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("schema.sql", "."),
    (r"C:\msys64\ucrt64\etc\fonts", "etc/fonts"),
]


hiddenimports = [
    "inventory",
    "weasyprint",
    "pydyf",
    "tinycss2",
    "cssselect2",
    "fontTools",
]

hiddenimports += collect_submodules("inventory")


# WeasyPrint နှင့် dependency package များ၏ data/binary/hidden imports စုမယ်
for package_name in [
    "weasyprint",
    "pydyf",
    "tinycss2",
    "cssselect2",
    "fontTools",
]:
    package_datas, package_binaries, package_hiddenimports = (
        collect_all(package_name)
    )

    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports


a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(a.pure)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KGInventory",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KGInventory",
)
