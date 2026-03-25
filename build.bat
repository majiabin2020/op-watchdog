@echo off
echo Generating icon...
python -c "from assets.icon import create_icon; img = create_icon(256); img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(64,64),(32,32),(16,16)])"
if %errorlevel% neq 0 (
    echo ERROR: Icon generation failed
    pause
    exit /b 1
)

echo Building 老马OpenClaw小龙虾看门狗...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --icon=assets/icon.ico ^
  --name="老马OpenClaw小龙虾看门狗" ^
  --clean ^
  main.py
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)

echo.
echo Build complete! Executable is in dist\
pause
