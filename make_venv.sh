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

if ! python -m pip --version >/dev/null 2>&1; then
    echo "pip not found in venv, bootstrapping via ensurepip..."
    if ! python -m ensurepip --upgrade; then
        echo ""
        echo "ERROR: Could not bootstrap pip into the virtual environment."
        echo "On Debian/Ubuntu, install the matching venv package first, e.g.:"
        echo "    sudo apt install python3-venv"
        echo "(or python3.X-venv for your specific Python version), then delete"
        echo "'${VENV_DIR}' and re-run this script."
        exit 1
    fi
fi

python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup completed."
echo "Activate with: source ${VENV_DIR}/bin/activate"
