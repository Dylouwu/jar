# JAR - Just Another RAT

## Description

JAR is a Python-based Remote Access Trojan (RAT) that uses Discord as its Command and Control (C2) intermediary. This allows for potentially stealthier communication as traffic is directed to Discord's legitimate domains. The client can execute commands, provide shell access, and attempts persistence on Windows. Communication between the server and client payloads is encrypted.

## Features

* **Discord C2:** Uses Discord messages for sending commands and receiving output.
* **Command Execution:** Execute arbitrary shell commands on the client.
* **Interactive Shell:** "Lock" onto a specific client for an interactive shell-like session.
* **Encrypted Communication:** Commands and output payloads are encrypted using AES (Fernet).
* **Client Persistence (Windows Example):** Client attempts to set a Registry Run key for persistence on Windows.
* **Client Builder:** `build.sh` script to configure, obfuscate (with PyArmor), and bundle the client (with PyInstaller).
* **Server Control:**
    * Console-based interface on the server.
    * Discord Slash Commands (`/jar ...`) for interacting with implants.

## ⚠️ Disclaimer

**This software is intended for educational and authorized security testing purposes ONLY.** Using this tool (or any similar tool) on systems without explicit, informed consent from the owner is illegal and unethical. The author is not responsible for any misuse or damage caused by this program. Always respect privacy and legal boundaries.

## Prerequisites

- For any linux distros :

**General:**
* Python 3.8+
* `pip` (Python package installer)

**For the Server (`server.py`):**
* A Discord account.
* Ability to create a Discord Bot and invite it to a server you control.
* Python libraries: `discord.py`, `python-dotenv`, `colorama`, `cryptography`.

**For the Client Builder (`build.sh`):**
* A Linux-like environment (Bash shell).
* Standard command-line utilities: `find`, `sed`.
* `patchelf` (if you intend to use the NixOS patching feature).

- For NixOS :
**Just run `nix-shell` :3**

## Setup Instructions

### 1. Discord Bot & Server Setup

1.  **Create a Discord Application and Bot:**
    * Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    * Click "New Application", give it a name (e.g., "JAR C2 Controller"), and click "Create".
    * Navigate to the "Bot" tab on the left sidebar.
    * Click "Add Bot" and confirm.
    * **Copy the Bot Token:** Under the bot's username, find "TOKEN". Click "Reset Token" (if needed) then "Copy". **Store this token securely; it's like a password.**
    * **Enable Privileged Gateway Intents:** Scroll down to "Privileged Gateway Intents" and **enable "MESSAGE CONTENT INTENT"**. This is crucial for the bot to read commands/output. You might also need "SERVER MEMBERS INTENT" depending on future features.

2.  **Create a Discord Server (Guild):**
    * In your Discord client, create a new, private server. This will be your C2 control server.

3.  **Invite Your Bot to Your Server:**
    * In the Developer Portal, go to "OAuth2" -> "URL Generator".
    * Under "SCOPES", select `bot` AND `application.commands`.
    * Under "BOT PERMISSIONS", select at least:
        * `Send Messages`
        * `Read Message History`
        * `Manage Webhooks`
    * Copy the "GENERATED URL" at the bottom. Paste it into your browser.
    * Select the server you created in step 2 and click "Authorize".

4.  **Get Your C2 Channel ID:**
    * In your Discord server, create a new text channel (e.g., `#jar`). This channel will be used for commands and output.
    * Enable Developer Mode in Discord: User Settings -> App Settings -> Advanced -> Developer Mode (toggle ON).
    * Right-click on your new C2 channel and select "Copy ID". This is your **Channel ID**.

5.  **Create a Webhook for Client Output:**
    * In your C2 channel (#jar), click the gear icon (Edit Channel) -> Integrations -> Webhooks -> "New Webhook".
    * Give it a name (e.g., "Implant Reports").
    * Ensure it posts to your C2 channel.
    * Click "Copy Webhook URL". This URL will be used by clients to send their output.

6.  **(Optional) Get Your Guild ID (for faster slash command updates):**
    * With Developer Mode still enabled, right-click on your server's icon in the server list and select "Copy ID". This is your **Guild ID**.

### 2. Project Files & Configuration (`.env`)

1.  Clone this repository
2.  Rename `.env.example` to `.env` in the project's root directory.
3.  **Edit the `.env` file with your Discord details**

### 3. Server Setup (`server.py`)

1.  **Install Dependencies:**
    It's recommended to use a virtual environment or to run `nix-shell` on a NixOS device.
    ```bash
    python3 -m venv server_env
    source server_env/bin/activate  # On Windows: server_env\Scripts\activate
    pip install discord.py python-dotenv colorama cryptography
    ```
    (You can create a `requirements_server.txt` with these and use `pip install -r requirements_server.txt`)

2.  **Ensure `.env` is in the project root** (where `server.py` is).

3.  **Run the Server:**
    ```bash
    python server.py
    ```
    The server will start, connect to Discord, and print its status. Slash commands might take up to an hour to appear globally if you haven't specified `MY_DISCORD_GUILD_ID` for faster syncing.

### 4. Client Builder (`build.sh`)

This script compiles `client.py` into a standalone executable.

1.  **Make `build.sh` executable:**
    ```bash
    chmod +x build.sh
    ```
2.  **Run the Builder:**
    ```bash
    ./build.sh
    ```
    * The script will first try to load Discord configuration values from your `.env` file as defaults.
    * It will then prompt you to confirm or enter:
        * Discord Webhook URL (for client output)
        * Discord C2 Channel ID (for client polling)
        * Discord Bot Token (for client polling - **with security warning**)
        * RAT Encryption Key
    * It will also ask for the desired output executable name.
3.  **Output:**
    * The final executable will be in the `dist/` directory (e.g., `dist/client_discord_obf`).
4.  **NixOS Patching (Optional):**
    * The script will ask if you want to patch the executable for NixOS. This is only relevant if you are building *on* NixOS and intend to run the client on your NixOS system.

## Usage

1.  **Start the Server:** Run `python server.py` or execute `dist/server` on your machine (to get an headless version).
2.  **Deploy and Run the Client:** Transfer the client executable (e.g., `dist/client_discord_obf`) to the target machine and run it.
    * It will send an initial "CHECKIN" message to your Discord C2 channel via the configured webhook.
3.  **Control via Server Console:**
    * The `server.py` console will show a `JAR >` prompt.
    * Type `list` (or `help`, `?`) to see available implants and operations.
    * Select implants by number to send single commands or enter interactive mode (e.g., `1` for single command to implant 1, `1i` for interactive).
    * Type `0` to broadcast a command.
4.  **Control via Discord Slash Commands:**
    * In any channel your bot can see (ideally your private C2 server), type `/jar`.
    * Available commands:
        * `/jar list_implants`: Shows active implants.
        * `/jar cmd <target> <instruction>`: Sends a command. `target` can be the implant's number (from `list_implants`) or its full UUID.
        * `/jar broadcast <instruction>`: Sends a command to all active implants.
    * Output from commands sent via slash commands will be posted as a new message in the C2 channel.

## Further Development Ideas

* Implement more robust key exchange or per-client encryption keys.
* Add more persistence methods for different OS.
* File upload/download capabilities.
* Screenshotting, keylogging.
* More sophisticated client check-in and tasking.
* Alternative C2 channels (e.g., server-side command relay instead of client polling Discord directly).
