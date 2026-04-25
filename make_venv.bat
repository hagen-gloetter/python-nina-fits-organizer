@echo off
setlocal

echo Setting up Python virtual environment...

if not exist astro_env_win\Scripts\python.exe (
    py -3.13 -m venv astro_env_win
)

astro_env_win\Scripts\python.exe -m ensurepip --upgrade
astro_env_win\Scripts\python.exe -m pip install --upgrade pip
astro_env_win\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Setup completed.
echo Activate with: astro_env_win\Scripts\activate.bat

endlocal