@echo off
echo Building Media Manager...

pip install -r requirements.txt --quiet

python generate_icon.py

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "MediaManager" ^
  --icon "icon.ico" ^
  --hidden-import "pycaw.pycaw" ^
  --hidden-import "comtypes.gen" ^
  --hidden-import "comtypes.gen.AudioPolicy" ^
  --hidden-import "comtypes.gen.MMDeviceAPILib" ^
  --hidden-import "pynput.keyboard._win32" ^
  --hidden-import "pystray._win32" ^
  main.py

echo.
echo Done. Executable is in the dist\ folder.
pause
