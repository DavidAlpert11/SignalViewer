# PyInstaller hook for numpy
# Fixes compatibility issues with numpy 1.26.x

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = collect_all('numpy')
hiddenimports += collect_submodules('numpy')
