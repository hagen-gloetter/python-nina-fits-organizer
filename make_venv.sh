#!/usr/bin/env bash
set -e

case "$(uname -s)" in
    Darwin) VENV_DIR="astro_env_mac" ;;
    *)      VENV_DIR="astro_env_linux" ;;
esac

echo "Setting up Python virtual environment in '${VENV_DIR}'..."

if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup completed."
echo "Activate with: source ${VENV_DIR}/bin/activate"
