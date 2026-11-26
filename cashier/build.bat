@echo off
REM يبني ملف EXE واحد يشتغل على ويندوز 7/8/10/11 (32 و 64 بت)
REM لازم Python 3.8 نسخة 32-bit (آخر نسخة بتشتغل على ويندوز 7): https://www.python.org/downloads/release/python-3810/
chcp 65001 >nul
py -3.8-32 -m pip install -r requirements.txt || goto :err
py -3.8-32 -m PyInstaller --onefile --noconsole --clean --name CashierPro ^
  --hidden-import serial --hidden-import win32print --hidden-import win32ui --hidden-import win32con --hidden-import win32timezone app.py || goto :err
echo.
echo تم! الملف: dist\CashierPro.exe
exit /b 0
:err
echo فشل البناء - راجع الرسائل فوق
exit /b 1
