@echo off
setlocal

echo Setting up Python virtual environment...

if not exist astro_env (
	py -3 -m venv astro_env
)

call astro_env\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Setup completed.
echo Activate with: astro_env\Scripts\activate.bat

endlocal