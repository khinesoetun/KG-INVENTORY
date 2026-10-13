import os
import sys


if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS
    dll_dir = bundle_dir
    fontconfig_file = os.path.join(
        bundle_dir,
        "etc",
        "fonts",
        "fonts.conf",
    )
    fontconfig_path = os.path.join(
        bundle_dir,
        "etc",
        "fonts",
    )
else:
    dll_dir = r"C:\msys64\ucrt64\bin"
    fontconfig_file = os.path.join(
        dll_dir,
        "..",
        "etc",
        "fonts",
        "fonts.conf",
    )
    fontconfig_path = os.path.join(
        dll_dir,
        "..",
        "etc",
        "fonts",
    )


if os.path.isdir(dll_dir):
    os.environ["WEASYPRINT_DLL_DIRECTORIES"] = dll_dir

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(dll_dir)

if os.path.isfile(fontconfig_file):
    os.environ["FONTCONFIG_FILE"] = fontconfig_file

if os.path.isdir(fontconfig_path):
    os.environ["FONTCONFIG_PATH"] = fontconfig_path


from weasyprint import HTML
