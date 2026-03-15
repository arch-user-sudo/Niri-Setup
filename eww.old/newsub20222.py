import tkinter as tk
from tkinter import ttk
import subprocess
import re
import os 
import threading 
import time

# --- Global Tracking for Recursive After Calls ---
refresh_jobs = {} 


# --- Tkinter Setup and Style ---
def configure_styles():
    style = ttk.Style()
    style.theme_use('clam')
    
    style.configure("TScrollbar", troughcolor="#111111", background="#444444", 
                    gripcount=0, bordercolor="#111111", darkcolor="#222222", 
                    lightcolor="#666666", arrowcolor="white")
    style.map("TScrollbar", background=[('active', '#666666')])
    
root = tk.Tk()
root.title("cONNECTION Centre")
root.geometry("1000x750") 
root.configure(bg="#111111")
root.attributes("-alpha", 0.98) 
configure_styles() 

###########################################
# ---------- TOP MENU DEFINITIONS---------------------
###########################################

def show_bluetooth_panel():
    stop_refresh_jobs()
    for frame in (wifi_connect_frame, audio_frame):
        frame.pack_forget()
    bluetooth_frame.pack(fill="both", expand=True, padx=20, pady=20)
    refresh_bt_status()

def show_audio_panel():
    stop_refresh_jobs()
    for frame in (wifi_connect_frame, bluetooth_frame):
        frame.pack_forget()
    
    populate_devices()
    populate_app_sliders()
    
    audio_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    refresh_all_sliders() 
    refresh_app_sliders()


def show_wifi_panel():
    stop_refresh_jobs()
    for frame in (bluetooth_frame, audio_frame):
        frame.pack_forget()
        
    # 1. Pack the frame instantly
    wifi_connect_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    # 2. Update the button and network list state instantly (no scan yet)
    refresh_wifi_ui_on_toggle(do_scan=False)
    
    # 3. Update initial status instantly
    status_text.config(state="normal")
    status_text.delete(1.0, tk.END)
    status_text.insert(tk.END, "Loading network status in background...")
    status_text.config(state="disabled")
    
    # 4. Start slow operations in threads
    # refresh_status_thread will call refresh_status() which will NOT trigger a scan.
    threading.Thread(target=refresh_status_thread, daemon=True).start()
    
    # 5. Manually start the scan thread, which will run or do nothing based on is_enabled
    perform_wifi_scan()

#def show_audio_panel():
#    stop_refresh_jobs()
##    for frame in (wifi_connect_frame, bluetooth_frame):
#        frame.pack_forget()
        
    # 1. Pack the frame instantly
#    audio_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    # 2. Run the slow population logic in a background thread
#    threading.Thread(target=_load_audio_panel_thread, daemon=True).start()

def stop_refresh_jobs():
    """Cancels all active root.after jobs."""
    global refresh_jobs
    for key, job_id in list(refresh_jobs.items()):
        try:
            root.after_cancel(job_id)
            del refresh_jobs[key]
        except ValueError:
            pass

###########################################
# ---------- TOP MENU UI ------------------
###########################################

menu_bar = tk.Menu(root, bg="#111111", fg="white", activebackground="#444444", activeforeground="white")
root.config(menu=menu_bar)

menu_bar.add_command(label="WiFi", command=lambda: show_wifi_panel())
menu_bar.add_command(label="Bluetooth", command=lambda: show_bluetooth_panel())
menu_bar.add_command(label="Audio", command=lambda: show_audio_panel())

###########################################
# ---------- FRAMES -----------------------
###########################################
bluetooth_frame = tk.Frame(root, bg="#111111")
audio_frame = tk.Frame(root, bg="#111111")
wifi_connect_frame = tk.Frame(root, bg="#111111")

# Placeholder for scroll frames
output_scroll_frame = None
input_scroll_frame = None
app_scroll_frame = None

device_widgets = []
app_widgets = []

###########################################
# ---------- WIFI FUNCTIONS ---------------
###########################################

def get_wifi_radio_status():
    """Checks the global Wi-Fi radio state (enabled/disabled)."""
    try:
        result = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True, check=True)
        # nmcli radio wifi returns "enabled" or "disabled"
        return result.stdout.strip().lower() == "enabled"
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False

def toggle_wifi_radio():
    """Toggles the global Wi-Fi radio and updates the button text."""
    is_enabled = get_wifi_radio_status()
    action = "off" if is_enabled else "on"
    
    try:
        toggle_result = subprocess.run(
            ["nmcli", "radio", "wifi", action],
            capture_output=True, text=True, check=True
        )

        status_text.config(state="normal")
        status_text.delete(1.0, tk.END)
        
        if toggle_result.returncode == 0:
            new_state = "DISABLED" if action == "off" else "ENABLED"
            status_text.insert(tk.END, f"📶 Wi-Fi radio successfully set to {new_state}.")
        else:
            # Handle cases where the command runs but fails (e.g., no hardware)
            status_text.insert(tk.END, f"❌ Failed to toggle Wi-Fi: {toggle_result.stderr.strip()}")
            
        status_text.config(state="disabled")

    except Exception as e:
        status_text.config(state="normal")
        status_text.insert(tk.END, f"❌ Error executing nmcli: {str(e)}")
        status_text.config(state="disabled")
        
    # Always refresh the UI after a toggle attempt
    refresh_wifi_ui_on_toggle(do_scan=True)

def refresh_wifi_ui_on_toggle(do_scan=True):
    """Updates the toggle button and the network listbox state based on Wi-Fi radio status."""
    is_enabled = get_wifi_radio_status()
    
    # Update button appearance
    if is_enabled:
        wifi_toggle_button.config(text="Wi-Fi: ON", bg="#004400")
        wifi_networks_listbox.config(state=tk.NORMAL)
    else:
        wifi_toggle_button.config(text="Wi-Fi: OFF", bg="#440000")
        # Clear and disable listbox when radio is off
        wifi_networks_listbox.delete(0, tk.END)
        wifi_networks_listbox.insert(tk.END, "Wi-Fi radio is OFF. Toggle ON to scan.")
        wifi_networks_listbox.config(state=tk.DISABLED) 
        
    # Only initiate a full scan if it's ON and explicitly requested (e.g., after a manual toggle or panel load)
    if is_enabled and do_scan:
        perform_wifi_scan()

def get_active_wifi_connections():
    """Uses nmcli to find ALL active connections (not just Wi-Fi)."""
    result = subprocess.run(
        ["nmcli", "-t", "-f", "TYPE,DEVICE,NAME,UUID", "connection", "show", "--active"],
        capture_output=True, text=True
    )
    connections = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split(":")
            # TYPE, DEVICE, NAME, UUID
            if len(parts) >= 4:
                conn_type = parts[0]
                conn_name = parts[2]
                conn_device = parts[1]
                conn_uuid = parts[3]
                connections.append({
                    "name": conn_name, 
                    "device": conn_device, 
                    "uuid": conn_uuid,
                    "type": conn_type
                })
    return connections


def do_disconnect_wifi(connection_name, uuid):
    """Disconnects a specific Wi-Fi connection by its UUID."""
    disconnect_result = subprocess.run(
        ["nmcli", "connection", "down", uuid],
        capture_output=True, text=True
    )
    if disconnect_result.returncode == 0:
        status_text.config(state="normal")
        status_text.insert(tk.END, f"\n✅ Disconnected from {connection_name}")
        status_text.config(state="disabled")
    else:
        status_text.config(state="normal")
        status_text.insert(tk.END, f"\n❌ Failed to disconnect: {disconnect_result.stderr.strip()}")
        status_text.config(state="disabled")
    refresh_status() # Update all status boxes

# --- NEW FORGET FUNCTION ---
def do_forget_wifi(connection_name, uuid):
    """Deletes (forgets) a saved connection profile by its UUID."""
    # Ensure it's down first, then delete
    do_disconnect_wifi(connection_name, uuid)
    
    forget_result = subprocess.run(
        ["nmcli", "connection", "delete", uuid],
        capture_output=True, text=True
    )
    
    status_text.config(state="normal")
    if forget_result.returncode == 0:
        status_text.insert(tk.END, f"\n✅ Forgotten network profile: {connection_name}")
    else:
        status_text.insert(tk.END, f"\n❌ Failed to forget: {forget_result.stderr.strip()}")
    status_text.config(state="disabled")
    
    refresh_status() # Update listbox
# --- END NEW FORGET FUNCTION ---

def refresh_status():
    """Updates the primary status text and the connected networks listbox."""
    # 1. Update primary status text
    result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
        capture_output=True, text=True
    )
    status_text.config(state="normal")
    status_text.delete(1.0, tk.END)
    lines = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split(":")
            device, dev_type, state, connection = (parts + [""] * 4)[:4]
            # Show status for connected devices of any type (wifi, ethernet, etc.)
            if state.lower() == "connected":
                lines.append(f"✅ {device} ({dev_type}) connected to {connection}")
            elif dev_type in ("wifi", "ethernet"):
                lines.append(f"❌ {device} ({dev_type}) not connected (State: {state})")

    if not lines:
        lines.append("No network information available.")
    status_text.insert(tk.END, "\n".join(lines))
    status_text.config(state="disabled")
    refresh_wifi_ui_on_toggle(do_scan=False) # Don't rescan on every status refresh

    # 2. Update the connected networks listbox
    connected_networks_listbox.delete(0, tk.END)
    active_connections = get_active_wifi_connections()
    
    if not active_connections:
        connected_networks_listbox.insert(tk.END, "No active connections.")
        # Clear stored data
        connected_networks_listbox.connections_data = []
    else:
        for conn in active_connections:
            # Display the type to clarify (e.g., "Ethernet: Wired connection 1")
            display = f"{conn['type'].capitalize()}: {conn['name']}"
            connected_networks_listbox.insert(tk.END, display)

        # Store data needed for disconnect/forget
        connected_networks_listbox.connections_data = active_connections
    
    # Enable/disable buttons based on if there are ANY active connections
    has_active_connections = bool(active_connections)
    disconnect_button.config(state=tk.NORMAL if has_active_connections else tk.DISABLED)
    forget_button.config(state=tk.NORMAL if has_active_connections else tk.DISABLED)


def refresh_status_thread():
    """Runs the status refresh logic in a separate thread."""
    # Since refresh_status() is safe (uses root.after for final GUI updates), we can schedule it.
    root.after(0, refresh_status)    

def scan_wifi_networks():
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"],
        capture_output=True, text=True
    )
    networks = []
    for line in result.stdout.strip().split("\n"):
        if line:
            match = re.search(r':(\d+)$', line)
            if match:
                signal = match.group(1)
                ssid = line[:match.start()]
            else:
                ssid = line
                signal = "?"

            ssid = ssid if ssid else "<Hidden Network>"
            # Ensure unique SSIDs by keeping a set, but for display simplicity we just list them
            networks.append(f"{ssid} ({signal}%)")
    return networks

def perform_wifi_scan():
    """Starts a background thread to scan networks and updates the listbox."""
    wifi_networks_listbox.delete(0, tk.END)
    wifi_networks_listbox.insert(tk.END, "Scanning for networks... Please wait.")
    
    threading.Thread(target=update_wifi_scan_results_thread, daemon=True).start()

def update_wifi_scan_results_thread():
    """The function that runs in the thread to get scan results."""
    networks = scan_wifi_networks()
    # Schedule the GUI update back on the main thread
    root.after(0, lambda: update_wifi_scan_results_gui(networks))

def update_wifi_scan_results_gui(networks):
    """Updates the Listbox on the main GUI thread."""
    wifi_networks_listbox.delete(0, tk.END)
    if not networks:
        wifi_networks_listbox.insert(tk.END, "No WiFi networks found.")
    else:
        for net in networks:
            wifi_networks_listbox.insert(tk.END, net)

def do_connect():
    try:
        selection = wifi_networks_listbox.get(wifi_networks_listbox.curselection())
    except tk.TclError:
        wifi_networks_listbox.insert(tk.END, "Select a network first.")
        return

    # Extract SSID, removing the signal strength part
    ssid = selection.split(" (")[0]
    password = password_entry.get()

    if not password:
        wifi_networks_listbox.insert(tk.END, f"⚠️ Enter a password for {ssid}.")
        return

    wifi_networks_listbox.delete(0, tk.END)
    wifi_networks_listbox.insert(tk.END, f"Connecting to {ssid}...")

    iface_result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"],
        capture_output=True, text=True
    )
    wifi_iface = None
    for line in iface_result.stdout.strip().split("\n"):
        if ":wifi" in line:
            wifi_iface = line.split(":")[0]
            break
    if not wifi_iface:
        wifi_networks_listbox.insert(tk.END, "❌ No Wi-Fi interface found.")
        return

    # Try to delete old connection profile with the same name first
    subprocess.run(["nmcli", "connection", "delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Create new connection profile and connect
    create_result = subprocess.run(
        ["nmcli", "connection", "add", "type", "wifi", "ifname", wifi_iface,
         "con-name", ssid, "ssid", ssid, "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password],
        capture_output=True, text=True
    )
    if create_result.returncode != 0:
        wifi_networks_listbox.insert(tk.END, f"❌ Failed to create profile: {create_result.stderr.strip()}")
        return
        
    connect_result = subprocess.run(["nmcli", "connection", "up", ssid], capture_output=True, text=True)
    wifi_networks_listbox.delete(0, tk.END)
    if connect_result.returncode == 0:
        wifi_networks_listbox.insert(tk.END, f"✅ Successfully connected to {ssid}")
    else:
        wifi_networks_listbox.insert(tk.END, f"❌ Failed to connect: {connect_result.stderr.strip()}")
    refresh_status()

# Helper for the Disconnect button
def disconnect_selected_wifi():
    try:
        selection_index = connected_networks_listbox.curselection()[0]
        conn_data = connected_networks_listbox.connections_data[selection_index]
        do_disconnect_wifi(conn_data["name"], conn_data["uuid"])
    except IndexError:
        status_text.config(state="normal")
        status_text.insert(tk.END, "\n⚠️ Select a connection to disconnect.")
        status_text.config(state="disabled")
    except AttributeError:
        pass 
        
# Helper for the Forget button (NEW)
def forget_selected_connection():
    try:
        selection_index = connected_networks_listbox.curselection()[0]
        conn_data = connected_networks_listbox.connections_data[selection_index]
        do_forget_wifi(conn_data["name"], conn_data["uuid"])
    except IndexError:
        status_text.config(state="normal")
        status_text.insert(tk.END, "\n⚠️ Select a connection to forget.")
        status_text.config(state="disabled")
    except AttributeError:
        pass


# --- NEW SPEEDTEST FUNCTIONS ---
def run_speedtest_thread():
    """Initiates the speedtest in a separate thread to prevent GUI freeze."""
    
    # 1. Clear status and report start
    status_text.config(state="normal")
    status_text.delete(1.0, tk.END)
    status_text.insert(tk.END, "Running speedtest... This may take a minute.")
    status_text.config(state="disabled")
    speedtest_button.config(state=tk.DISABLED, text="Testing...")
    
    # 2. Define the target function for the thread
    def target():
        try:
            # Using speedtest-cli and asking for just summary results
            result = subprocess.run(
                ["speedtest-cli", "--simple"],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            # 3. Schedule the update on the main thread
            root.after(0, lambda: update_speedtest_results(output, error, result.returncode))
            
        except FileNotFoundError:
            root.after(0, lambda: update_speedtest_results("", "Error: speedtest-cli not found. Install it (e.g., 'pip install speedtest-cli').", 127))
        except subprocess.TimeoutExpired:
            root.after(0, lambda: update_speedtest_results("", "Error: Speedtest timed out after 60 seconds.", 1))
        except Exception as e:
            root.after(0, lambda: update_speedtest_results("", f"An unexpected error occurred: {str(e)}", 1))

    # 4. Start the thread
    threading.Thread(target=target, daemon=True).start()

def update_speedtest_results(output, error, return_code):
    """Updates the status text area with speedtest results."""
    status_text.config(state="normal")
    status_text.delete(1.0, tk.END)
    
    if return_code == 0:
        status_text.insert(tk.END, "✅ Speedtest Results:\n\n")
        status_text.insert(tk.END, output)
    else:
        if return_code == 127:
             status_text.insert(tk.END, "❌ Speedtest Failed:\n\n")
             status_text.insert(tk.END, error)
        elif error:
             status_text.insert(tk.END, "❌ Speedtest Failed (Check Connection):\n\n")
             status_text.insert(tk.END, error)
        else:
             status_text.insert(tk.END, "❌ Speedtest Failed (Unknown Error).\n")
             status_text.insert(tk.END, output) # Show output just in case

    status_text.config(state="disabled")
    speedtest_button.config(state=tk.NORMAL, text="Run Speedtest")
# --- END NEW SPEEDTEST FUNCTIONS ---

###########################################
# ---------- WIFI CONNECT PANEL UI --------
###########################################

tk.Label(wifi_connect_frame, text="Available Networks:", fg="white", bg="#111111").pack(pady=(0,5), anchor="w", padx=20)

listbox_frame = tk.Frame(wifi_connect_frame, bg="#111111")
listbox_frame.pack(padx=20, pady=0, fill="both", expand=True)

wifi_networks_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
wifi_networks_listbox = tk.Listbox(
    listbox_frame, bg="#222222", fg="white", selectbackground="#444444", 
    selectforeground="white", height=10,
    yscrollcommand=wifi_networks_scrollbar.set
)
wifi_networks_scrollbar.config(command=wifi_networks_listbox.yview)

wifi_networks_scrollbar.pack(side="right", fill="y")
wifi_networks_listbox.pack(side="left", fill="both", expand=True)


password_frame = tk.Frame(wifi_connect_frame, bg="#111111")
password_frame.pack(pady=10, fill="x", padx=20)
tk.Label(password_frame, text="Password:", fg="white", bg="#111111", width=10, anchor="w").pack(side="left", padx=(0,10))
password_entry = tk.Entry(password_frame, show="*", bg="#222222", fg="white", insertbackground="white")
password_entry.pack(side="left", fill="x", expand=True)
tk.Button(password_frame, text="Connect", command=do_connect, bg="#004400", fg="white", width=8).pack(side="left", padx=(10,0))

# --- NEW: Connected Wi-Fi Box ---
tk.Label(wifi_connect_frame, text="Active Connections (Select to Disconnect/Forget):", fg="yellow", bg="#111111").pack(pady=(10,5), anchor="w", padx=20)
connected_frame = tk.Frame(wifi_connect_frame, bg="#111111")
connected_frame.pack(pady=5, fill="x", padx=20)

connected_networks_listbox = tk.Listbox(connected_frame, height=2, bg="#222222", fg="lime", selectbackground="#003300", selectforeground="white")
connected_networks_listbox.pack(side="left", fill="x", expand=True)
connected_networks_listbox.connections_data = [] # To store UUIDs

# --- Disconnect Button ---
disconnect_button = tk.Button(connected_frame, text="Disconnect", command=disconnect_selected_wifi, bg="#440000", fg="white", state=tk.DISABLED)
disconnect_button.pack(side="right", padx=(10,0))

# --- Forget Button (NEW) ---
forget_button = tk.Button(connected_frame, text="Forget", command=forget_selected_connection, bg="#442200", fg="white", state=tk.DISABLED)
forget_button.pack(side="right", padx=(10,0)) # Added 10 padding to separate from the listbox


# --- Original Status Box ---
status_frame = tk.Frame(wifi_connect_frame, bg="#111111")
status_frame.pack(pady=10, fill="x", padx=20)
tk.Label(status_frame, text="General Device Status / Speedtest Log:", fg="white", bg="#111111").pack(anchor="w")
status_text = tk.Text(status_frame, height=4, bg="#222222", fg="white", state="disabled")
status_text.pack(fill="x", pady=5)

button_frame_bottom = tk.Frame(wifi_connect_frame, bg="#111111")
button_frame_bottom.pack(pady=5, padx=20, fill="x")

# Define the button globally and call the state check function on startup
global wifi_toggle_button
wifi_toggle_button = tk.Button(button_frame_bottom, text="Wi-Fi: ...", command=toggle_wifi_radio, fg="white")
# Initial state will be set by the refresh_status() call in show_wifi_panel()
wifi_toggle_button.pack(side="left", padx=(0, 5), expand=True, fill="x")

tk.Button(button_frame_bottom, text="Scan for Networks", command=perform_wifi_scan, bg="#444444", fg="white").pack(side="left", padx=(0, 5), expand=True, fill="x")
tk.Button(button_frame_bottom, text="Refresh Status", command=refresh_status, bg="#444444", fg="white").pack(side="left", padx=(5, 5), expand=True, fill="x")
# --- NEW SPEEDTEST BUTTON ---
speedtest_button = tk.Button(button_frame_bottom, text="Run Speedtest", command=run_speedtest_thread, bg="#000044", fg="white")
speedtest_button.pack(side="left", padx=(5, 0), expand=True, fill="x")
# --- END NEW SPEEDTEST BUTTON ---

###########################################
# BLUETOOTH FUNCTIONS (using bluetoothctl)
###########################################
bt_adapter_mac = None

# --- Bluetooth Utility ---
def run_bluetoothctl_command(commands):
    """Pipes commands to the interactive bluetoothctl shell."""
    try:
        # Popen starts the process
        p = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Communicate sends the commands and waits for output
        # Increased timeout for commands that might take a moment
        stdout, stderr = p.communicate(input=commands, timeout=5)
        return stdout, stderr, p.returncode
    except FileNotFoundError:
        return "", "bluetoothctl command not found. Is bluez-utils installed?", 127
    except subprocess.TimeoutExpired:
        p.kill()
        return "", "bluetoothctl command timed out.", 1
    except Exception as e:
        return "", str(e), 1

def get_adapter_mac():
    global bt_adapter_mac
    if bt_adapter_mac: return bt_adapter_mac
    
    stdout, _, _ = run_bluetoothctl_command("show\nexit\n")
    mac_match = re.search(r'Controller\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', stdout, re.I)
    
    if mac_match:
        bt_adapter_mac = mac_match.group(1)
        return bt_adapter_mac
    return None

def get_adapter_powered():
    stdout, _, _ = run_bluetoothctl_command("show\nexit\n")
    powered = re.search(r"Powered:\s*(yes|no)", stdout)
    return powered.group(1).lower() == "yes" if powered else False

def toggle_adapter():
    mac = get_adapter_mac()
    if not mac:
        bt_status_listbox.insert(tk.END, "❌ No adapter found.")
        return
    
    powered = get_adapter_powered()
    command = "power off\n" if powered else "power on\n"
    
    stdout, stderr, _ = run_bluetoothctl_command(command + "exit\n")
    
    if stderr and not re.search("Changing power is only allowed when on a primary controller", stderr):
        bt_status_listbox.insert(tk.END, f"❌ Failed to toggle: {stderr.strip()}")
    else:
        refresh_bt_status()

def get_device_info(mac):
    """Gets detailed info for a single MAC."""
    info_stdout, _, _ = run_bluetoothctl_command(f"info {mac}\nexit\n")
    
    connected_match = re.search(r"Connected:\s*(yes)", info_stdout)
    paired_match = re.search(r"Paired:\s*(yes)", info_stdout)
    trusted_match = re.search(r"Trusted:\s*(yes)", info_stdout)
    
    # Simple check for successful retrieval of info
    name_match = re.search(r"Alias:\s*(.+)", info_stdout)
    name = name_match.group(1).strip() if name_match else mac
    
    return {
        "name": name,
        "mac": mac,
        "connected": bool(connected_match),
        "paired": bool(paired_match),
        "trusted": bool(trusted_match) # <-- Added trusted status
    }

def _scan_devices_thread():
    """Runs the scanning logic in a separate thread."""
    
    # 1. Start Discovery (non-blocking in the interactive shell)
    bt_status_listbox.insert(tk.END, "Starting discovery (5 seconds)...")
    run_bluetoothctl_command("scan on\n")
    time.sleep(5)
    run_bluetoothctl_command("scan off\n") # Stop discovery

    # 2. Get list of all known/discovered devices
    stdout, stderr, _ = run_bluetoothctl_command("devices\nexit\n")

    # 3. Parse MACs and get detailed info
    device_macs = set()
    for line in stdout.splitlines():
        match = re.search(r'Device\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', line, re.I)
        if match:
            device_macs.add(match.group(1))

    all_devices = [get_device_info(mac) for mac in device_macs]
    
    # 4. Process results on the main thread (using root.after)
    root.after(0, lambda: update_bt_scan_results(all_devices, stderr))


def scan_bt_devices():
    mac = get_adapter_mac()
    if not mac: return
    
    bt_status_listbox.delete(0, tk.END)
    bt_status_listbox.insert(tk.END, "Starting background scan... Please wait.")
    bluetooth_listbox.delete(0, tk.END)

    scan_thread = threading.Thread(target=_scan_devices_thread, daemon=True)
    scan_thread.start()


def update_bt_scan_results(all_devices, stderr):
    bt_listbox = bluetooth_listbox
    bt_listbox.delete(0, tk.END)
    bt_listbox.devices = []
    
    if "bluetoothctl command not found" in stderr:
        bt_status_listbox.insert(tk.END, "❌ bluetoothctl not found. Please install bluez-utils.")
        return
    
    if stderr and not re.search("No Controllers available", stderr):
        bt_status_listbox.insert(tk.END, f"❌ Scan failed: {stderr.strip()}")
        return

    # Process scanned devices for the main list
    available_devices = []
    for dev in all_devices:
        status_icon = "[Connected] " if dev['connected'] else "[Trusted] " if dev['trusted'] else "[Paired] " if dev['paired'] else "[Connect?] "
        display_name = f"{status_icon} {dev['name']}"
        available_devices.append((display_name, dev['mac'], dev)) # Store full device data
        bt_listbox.insert(tk.END, f"{display_name} ({dev['mac']})")
    
    bt_listbox.devices = available_devices

    if not available_devices:
        bt_listbox.insert(tk.END, "No Bluetooth devices found/known.")
        
    bt_status_listbox.insert(tk.END, "Scan complete.")
    
    # Update connected list
    update_connected_bt_list(all_devices)

def update_connected_bt_list(all_devices=None):
    """Updates the list of currently connected devices."""
    connected_bt_listbox.delete(0, tk.END)
    connected_devices = []
    
    # If all_devices wasn't passed (e.g., from a quick disconnect), run a quick check
    if all_devices is None:
        stdout, _, _ = run_bluetoothctl_command("devices\nexit\n")
        macs = re.findall(r'Device\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', stdout, re.I)
        all_devices = [get_device_info(mac[0]) for mac in set(macs)]

    for dev in all_devices:
        if dev.get('connected'):
            display_name = f"🎧 {dev['name']}"
            connected_bt_listbox.insert(tk.END, f"{display_name} ({dev['mac']})")
            connected_devices.append(dev)

    if not connected_devices:
        connected_bt_listbox.insert(tk.END, "No devices connected.")
        
    connected_bt_listbox.connected_data = connected_devices


def get_selected_device():
    try:
        selected_index = bluetooth_listbox.curselection()[0]
        _, mac, dev_data = getattr(bluetooth_listbox, "devices", [])[selected_index]
        alias = dev_data['name']
        return alias, mac
    except (tk.TclError, IndexError, AttributeError):
        bt_status_listbox.insert(tk.END, "⚠️ Select a device first from the Available list.")
        return None, None

def pair_bt_device():
    """Attempts to pair with the selected Bluetooth device."""
    try:
        selection_index = bluetooth_listbox.curselection()[0]
        selected_device = bluetooth_listbox.devices[selection_index][2]
        mac = selected_device['mac']
        name = selected_device['name']
    except IndexError:
        bt_status_listbox.insert(tk.END, "Select a device to pair first.")
        return

    bt_status_listbox.delete(0, tk.END)
    bt_status_listbox.insert(tk.END, f"Attempting **Pair** with {name}...")

    commands = f"pair {mac}\nexit\n"
    stdout, stderr, returncode = run_bluetoothctl_command(commands)

    if "Pairing successful" in stdout:
        bt_status_listbox.insert(tk.END, f"✅ Successfully paired with {name}.")
    elif "Already Paired" in stdout:
        bt_status_listbox.insert(tk.END, f"ℹ️ {name} is already paired.")
    else:
        bt_status_listbox.insert(tk.END, f"❌ Pairing failed. Error: {stderr.strip() or stdout.strip()}")

    # Re-scan to update paired status
    threading.Thread(target=_scan_devices_thread, daemon=True).start()


def connect_bt_device():
    """Connects to the selected Bluetooth device."""
    try:
        selection_index = bluetooth_listbox.curselection()[0]
        # Assuming the full device data is stored in the listbox attribute
        selected_device = bluetooth_listbox.devices[selection_index][2]
        mac = selected_device['mac']
        name = selected_device['name']
    except IndexError:
        bt_status_listbox.insert(tk.END, "Select a device to connect first.")
        return

    bt_status_listbox.delete(0, tk.END)
    bt_status_listbox.insert(tk.END, f"Attempting **Connect** with {name}...")

    # Only send connect command
    commands = f"connect {mac}\nexit\n"
    stdout, stderr, returncode = run_bluetoothctl_command(commands)

    if returncode == 0 and "Connection successful" in stdout or "successful" in stdout:
        bt_status_listbox.insert(tk.END, f"✅ Successfully connected to {name}.")
    else:
        bt_status_listbox.insert(tk.END, f"⚠️ Connection failed. Error: {stderr.strip() or stdout.strip()}")

    # Re-scan to update connection status
    threading.Thread(target=_scan_devices_thread, daemon=True).start()

def trust_bt_device():
    """Trusts the selected Bluetooth device for auto-connection."""
    alias, mac = get_selected_device()
    if not mac: return

    bt_status_listbox.insert(tk.END, f"Attempting to trust {alias}...")
    
    stdout, stderr, _ = run_bluetoothctl_command(f"trust {mac}\nexit\n")
    
    if "Failed to set property" in stdout or stderr:
        bt_status_listbox.insert(tk.END, f"❌ Failed to trust. Pair first if necessary.")
    else:
        bt_status_listbox.insert(tk.END, f"⭐ Successfully trusted {alias}. It should now auto-connect.")
        
    root.after(1000, scan_bt_devices) # Refresh list status

def forget_bt_device():
    """Removes (forgets) the selected device from the system's paired list."""
    alias, mac = get_selected_device()
    if not mac: return

    # Prompt user in the log
    bt_status_listbox.insert(tk.END, f"Attempting to **Forget (Remove)** {alias} ({mac})...")

    # The 'remove' command unpairs/untrusts and removes the device entry
    commands = f"remove {mac}\nexit\n"
    stdout, stderr, returncode = run_bluetoothctl_command(commands)

    if "Device has been removed" in stdout or "successful" in stdout:
        bt_status_listbox.insert(tk.END, f"✅ Successfully forgotten {alias}.")
    elif "not available" in stdout:
        bt_status_listbox.insert(tk.END, f"ℹ️ Device {alias} was not found or already removed.")
    else:
        bt_status_listbox.insert(tk.END, f"❌ Failed to forget. Error: {stderr.strip() or stdout.strip()}")

    # Refresh the list to remove the device entry
    threading.Thread(target=_scan_devices_thread, daemon=True).start()


def do_disconnect_bt(mac):
    """Internal function to send the disconnect command."""
    stdout, stderr, _ = run_bluetoothctl_command(f"disconnect {mac}\nexit\n")
    
    if "Failed to disconnect" in stdout or stderr:
        bt_status_listbox.insert(tk.END, f"❌ Disconnect failed: {stderr.strip()}")
    else:
        bt_status_listbox.insert(tk.END, f"✅ Disconnect command sent.")
    
    # Run a quick update to refresh the connected list
    root.after(500, update_connected_bt_list)
    root.after(1000, scan_bt_devices)


def disconnect_bt_device():
    """Disconnects the selected connected Bluetooth device."""
    try:
        selection_index = connected_bt_listbox.curselection()[0]
        # Get the mac from the stored connection data
        selected_device = connected_bt_listbox.connected_data[selection_index]
        mac = selected_device['mac']
        name = selected_device['name']
    except IndexError:
        bt_status_listbox.insert(tk.END, "Select a connected device to disconnect first.")
        return

    bt_status_listbox.delete(0, tk.END)
    bt_status_listbox.insert(tk.END, f"Attempting to disconnect {name}...")

    commands = f"disconnect {mac}\nexit\n"
    stdout, stderr, returncode = run_bluetoothctl_command(commands)

    if returncode == 0 and "successful" in stdout:
        bt_status_listbox.insert(tk.END, f"Successfully disconnected from {name}.")
    else:
        bt_status_listbox.insert(tk.END, f"Disconnect failed. Error: {stderr.strip() or stdout.strip()}")

    # Re-scan to update connection status
    threading.Thread(target=_scan_devices_thread, daemon=True).start()


def refresh_bt_status():
    """Refreshes the Bluetooth adapter status and connected devices."""
    global refresh_jobs
    
    # 1. Update adapter status
    is_powered = get_adapter_powered()
    status_msg = f"Adapter Status: {'ON' if is_powered else 'OFF'}"
    bt_status_label.config(text=status_msg, fg="lime" if is_powered else "red")
    toggle_bt_button.config(text="Turn Off" if is_powered else "Turn On",
                            bg="#440000" if is_powered else "#004400")

    # 2. Update the connected devices list and scan if powered
    if is_powered:
        # Perform a quick update on connected devices
        threading.Thread(target=lambda: update_connected_bt_list(None), daemon=True).start()
        # Initial scan if the list is empty (avoids re-scanning every 5s)
        if not hasattr(bluetooth_listbox, 'devices') or not bluetooth_listbox.devices:
            threading.Thread(target=_scan_devices_thread, daemon=True).start()

    # 3. Schedule the next refresh
    # We use a try/except for robustness against multiple calls
    try:
        if 'bluetooth_status' in refresh_jobs:
             root.after_cancel(refresh_jobs['bluetooth_status'])
    except ValueError:
        pass

    refresh_jobs['bluetooth_status'] = bluetooth_frame.after(5000, refresh_bt_status)    


###########################################
# ---------- BLUETOOTH PANEL UI -----------
###########################################
# Top status (ON/OFF)

bt_status_frame = tk.Frame(bluetooth_frame, bg="#111111")
bt_status_frame.pack(pady=(0, 10), fill="x", padx=20)

bt_status_label = tk.Label(bt_status_frame, text="Adapter Status: Checking...", fg="yellow", bg="#111111", font=("Arial", 12, "bold"))
bt_status_label.pack(side="left")

toggle_bt_button = tk.Button(bt_status_frame, text="Toggle", command=toggle_adapter, bg="#444444", fg="white", width=10)
toggle_bt_button.pack(side="right")

# Connected Devices List

tk.Label(bluetooth_frame, text="Currently Connected Devices:", fg="lime", bg="#111111").pack(pady=(10, 5), anchor="w", padx=20)
connected_bt_frame = tk.Frame(bluetooth_frame, bg="#111111")
connected_bt_frame.pack(pady=5, fill="x", padx=20)

connected_bt_listbox = tk.Listbox(connected_bt_frame, height=2, bg="#222222", fg="lime", selectbackground="#003300", selectforeground="white")
connected_bt_listbox.pack(side="left", fill="x", expand=True)
connected_bt_listbox.connected_data = [] # To store full device data

tk.Button(connected_bt_frame, text="Disconnect Selected", command=disconnect_bt_device, bg="#440000", fg="white").pack(side="right", padx=(10, 0))

# Discovered/Paired Devices List
tk.Label(bluetooth_frame, text="Available/Paired Devices (Click 'Scan Devices' below to discover):", fg="white", bg="#111111").pack(pady=(10, 5), anchor="w", padx=20)

bt_listbox_container = tk.Frame(bluetooth_frame, bg="#111111")
bt_listbox_container.pack(padx=20, pady=0, fill="both", expand=True)

bt_networks_scrollbar = ttk.Scrollbar(bt_listbox_container, orient=tk.VERTICAL)
bluetooth_listbox = tk.Listbox(
    bt_listbox_container, bg="#222222", fg="white", selectbackground="#444444",
    selectforeground="white", height=10,
    yscrollcommand=bt_networks_scrollbar.set
)
bt_networks_scrollbar.config(command=bluetooth_listbox.yview)

bt_networks_scrollbar.pack(side="right", fill="y")
bluetooth_listbox.pack(side="left", fill="both", expand=True)
bluetooth_listbox.devices = [] # To store full device data (name, mac, full_data)

# Action buttons
bt_button_frame = tk.Frame(bluetooth_frame, bg="#111111")
bt_button_frame.pack(pady=10, padx=20, fill="x")

# --- Pair Button ---
tk.Button(bt_button_frame, text="Pair Selected", command=pair_bt_device, bg="#440044", fg="white").pack(side="left", padx=(0, 5), expand=True, fill="x")

# --- Connect Button ---
tk.Button(bt_button_frame, text="Connect Selected", command=connect_bt_device, bg="#000044", fg="white").pack(side="left", padx=(5, 5), expand=True, fill="x")

# --- Trust Button ---
tk.Button(bt_button_frame, text="Trust Selected", command=trust_bt_device, bg="#444400", fg="white").pack(side="left", padx=(5, 5), expand=True, fill="x")

# --- Forget Button (NEW) ---
tk.Button(bt_button_frame, text="Forget Selected", command=forget_bt_device, bg="#442200", fg="white").pack(side="left", padx=(5, 5), expand=True, fill="x")

# --- Scan and Refresh Buttons ---
tk.Button(bt_button_frame, text="Scan Devices", command=scan_bt_devices, bg="#004400", fg="white").pack(side="left", padx=(5, 5), expand=True, fill="x")
tk.Button(bt_button_frame, text="Refresh Status", command=refresh_bt_status, bg="#444444", fg="white").pack(side="left", padx=(5, 0), expand=True, fill="x")


# Bluetooth status log
tk.Label(bluetooth_frame, text="Bluetooth Log/Errors:", fg="white", bg="#111111").pack(pady=(10, 5), anchor="w", padx=20)
bt_status_listbox = tk.Listbox(bluetooth_frame, height=3, bg="#222222", fg="yellow", selectbackground="#333300", selectforeground="white")
bt_status_listbox.pack(pady=5, fill="x", padx=20)


###########################################
# ---------- AUDIO FUNCTIONS ----------------
###########################################
def create_scrollable_frame(parent):
    canvas = tk.Canvas(parent, bg="#111111", highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#111111")
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return scrollable_frame

def has_pactl():
    return os.path.exists("/usr/bin/pactl") or subprocess.run(["which", "pactl"], capture_output=True).returncode == 0

def run_pactl(args):
    """Safely run pactl command."""
    if not has_pactl():
        raise FileNotFoundError("pactl command not found. Is PulseAudio/PipeWire installed?")
    return subprocess.run(["pactl"] + args, capture_output=True, text=True, check=True)

def get_output_devices():
    try:
        result = run_pactl(["list","short","sinks"])
        return [line.split("\t")[1] for line in result.stdout.strip().split("\n") if line]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

def get_input_devices():
    try:
        result = run_pactl(["list","short","sources"])
        return [line.split("\t")[1] for line in result.stdout.strip().split("\n") if line]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

def get_default_output():
    try:
        result = run_pactl(["get-default-sink"])
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

def get_default_input():
    try:
        result = run_pactl(["get-default-source"])
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

def set_default_device(device_name, is_output=True):
    try:
        if is_output:
            run_pactl(["set-default-sink", device_name])
        else:
            run_pactl(["set-default-source", device_name])
        populate_devices()
    except:
        pass

def create_device_slider(frame, device_name, is_output=True):
    container = tk.Frame(frame, bg="#111111", bd=1, relief="ridge", padx=5, pady=5)
    container.pack(fill="x", padx=5, pady=5)
    
    default_dev = get_default_output() if is_output else get_default_input()
    title_color = "lime" if device_name == default_dev else "white"
    
    display_name = device_name.split(".")[-1] # Cleaner name
    
    tk.Label(container, text=display_name, fg=title_color, bg="#111111", width=15, anchor="w", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    
    slider = tk.Scale(container, from_=0, to=150, orient="horizontal", 
                      bg="#111111", fg="white", highlightbackground="#111111",
                      troughcolor="#222222", length=300, highlightthickness=0, bd=0)
    slider.pack(side="left", padx=10)

    def set_volume(value):
        try:
            if is_output:
                run_pactl(["set-sink-volume", device_name, f"{value}%"])
            else:
                run_pactl(["set-source-volume", device_name, f"{value}%"])
        except:
            pass
            
    slider.config(command=set_volume)

    def toggle_mute(mute=True):
        try:
            if is_output:
                run_pactl(["set-sink-mute", device_name, "1" if mute else "0"])
            else:
                run_pactl(["set-source-mute", device_name, "1" if mute else "0"])
        except:
            pass
    
    tk.Button(container, text="Mute", command=lambda: toggle_mute(True), bg="#330000", fg="white", width=5).pack(side="left", padx=2)
    tk.Button(container, text="Unmute", command=lambda: toggle_mute(False), bg="#003300", fg="white", width=5).pack(side="left", padx=2)
    tk.Button(container, text="Set Default", command=lambda: set_default_device(device_name, is_output), bg="#003344", fg="white", width=10).pack(side="left", padx=5)
    
    device_widgets.append((slider, device_name, is_output, container))

def populate_devices():
    if not has_pactl():
        tk.Label(audio_frame, text="PulseAudio control (pactl) not found. Cannot manage audio.", fg="red", bg="#111111").pack(pady=10)
        return

    for w in output_scroll_frame.winfo_children(): w.destroy()
    for w in input_scroll_frame.winfo_children(): w.destroy()
    
    global device_widgets
    device_widgets.clear()
    
    outputs = get_output_devices()
    inputs = get_input_devices()
    
    if outputs:
        for dev in outputs:
            create_device_slider(output_scroll_frame, dev, is_output=True)
    else:
        tk.Label(output_scroll_frame, text="No output devices found.", fg="white", bg="#111111").pack(pady=5)
        
    if inputs:
        for dev in inputs:
            create_device_slider(input_scroll_frame, dev, is_output=False)
    else:
        tk.Label(input_scroll_frame, text="No input devices found.", fg="white", bg="#111111").pack(pady=5)


def refresh_all_sliders():
    global refresh_jobs
    current_default_out = get_default_output()
    current_default_in = get_default_input()
    
    for slider, name, is_output, container in device_widgets:
        try:
            if is_output:
                vol_info = run_pactl(["get-sink-volume", name]).stdout
                is_default = name == current_default_out
            else:
                vol_info = run_pactl(["get-source-volume", name]).stdout
                is_default = name == current_default_in
            
            match = re.search(r'/\s*(\d+)%', vol_info)
            if match:
                 percent = int(match.group(1))
                 if abs(slider.get() - percent) > 5:
                    slider.set(percent)
            
            label = container.winfo_children()[0] 
            title_color = "lime" if is_default else "white"
            label.config(fg=title_color)

        except Exception:
            pass
            
    refresh_jobs['audio_devices'] = audio_frame.after(1000, refresh_all_sliders) 

def get_app_list():
    try:
        result = run_pactl(["list", "sink-inputs"])
        apps = []
        index = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Sink Input #"):
                index = line.split("#")[1].strip()
            elif line.startswith("application.name = ") and index:
                app_name = line.split("=",1)[1].strip().strip('"')
                apps.append( (app_name, index) )
                index = None 
        return apps
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

def create_app_slider(frame, app_name, app_index):
    container = tk.Frame(frame, bg="#111111", bd=1, relief="ridge", padx=5, pady=5)
    container.pack(fill="x", padx=5, pady=5)
    tk.Label(container, text=app_name, fg="cyan", bg="#111111", wraplength=120, width=15, anchor="w", font=("Arial", 10)).pack(side="left", padx=5)
    
    slider = tk.Scale(container, from_=0, to=150, orient="horizontal", 
                      bg="#111111", fg="white", highlightbackground="#111111",
                      troughcolor="#222222", length=300, highlightthickness=0, bd=0)
                      
    slider.pack(side="left", padx=10)
    
    # --- THREAD-SAFE VOLUME SETTER ---
    def set_app_volume_in_thread(value):
        value = int(value) # Tkinter passes the value as a string
        def target():
            try:
                run_pactl(["set-sink-input-volume", app_index, f"{value}%"])
            except:
                pass
        
        # Run the slow subprocess command in a dedicated, quick thread
        threading.Thread(target=target, daemon=True).start()
    
    # --- MUTE FUNCTION (Reused from previous) ---
    def toggle_app_mute(mute=True):
        def target():
            try:
                action = "1" if mute else "0"
                run_pactl(["set-sink-input-mute", app_index, action])
            except:
                pass
        threading.Thread(target=target, daemon=True).start()
            
    # Use the new thread-safe command
    slider.config(command=set_app_volume_in_thread)
    
    # Mute buttons (UI remains the same)
    tk.Button(container, text="Mute", command=lambda: toggle_app_mute(True), bg="#330000", fg="white", width=5).pack(side="left", padx=2)
    tk.Button(container, text="Unmute", command=lambda: toggle_app_mute(False), bg="#003300", fg="white", width=5).pack(side="left", padx=2)

    app_widgets.append((slider, app_name, app_index))

def populate_app_sliders():
    for w in app_scroll_frame.winfo_children(): w.destroy()
    
    global app_widgets
    app_widgets.clear()
    
    if not has_pactl(): return

    apps = get_app_list()
    if not apps:
        tk.Label(app_scroll_frame, text="No applications playing audio", fg="white", bg="#111111").pack(pady=5)
    else:
        for name, idx in apps:
            create_app_slider(app_scroll_frame, name, idx)

def refresh_app_sliders():
    global refresh_jobs
    
    # 1. If no app widgets exist, check for new running apps in a separate thread.
    if not app_widgets:
        threading.Thread(target=_check_for_new_apps_thread, daemon=True).start()
        
    # 2. Iterate through existing widgets and update their volume.
    for slider, name, idx in app_widgets:
        try:
            # Running pactl list sink-inputs here to get ALL info, then parsing the block is SLOW.
            # A much faster way, though still blocking, is to target just the volume for the specific index:
            vol_info = subprocess.run(
                ["pactl", "get-sink-input-volume", idx], 
                capture_output=True, text=True, check=True
            ).stdout
            
            # The output format for 'pactl get-sink-input-volume' is generally: 
            # "Volume: 1: 65536 / 100% / 0.00 dB"
            match = re.search(r'/\s*(\d+)%', vol_info)
            if match:
                percent = int(match.group(1))
                # Only update the slider if the current value differs by more than 5 
                # (to prevent visual jitters and infinite loop potential).
                if abs(slider.get() - percent) > 5:
                    slider.set(percent)
                    
        except Exception:
            # Device/app probably closed. A full refresh will clean up the old widget.
            pass
            
    # 3. Schedule the next volume check in 1 second.
    refresh_jobs['audio_apps'] = audio_frame.after(1000, refresh_app_sliders)

 # --- NEW Thread Target Function ---
def _load_audio_panel_thread():
    """Runs all initial slow audio data gathering and schedules GUI updates."""
    # Check for pactl availability first
    if not has_pactl():
        root.after(0, lambda: tk.Label(audio_frame, text="PulseAudio control (pactl) not found. Cannot manage audio.", fg="red", bg="#111111").pack(pady=10))
        return

    # Data collection (slow part)
    outputs = get_output_devices()
    inputs = get_input_devices()
    apps = get_app_list()
    
    # Schedule GUI updates and start refresh loops on the main thread
    root.after(0, lambda: _initial_audio_gui_setup(outputs, inputs, apps))

def _initial_audio_gui_setup(outputs, inputs, apps):
    """Updates the GUI and starts the refresh loops on the main thread."""
    
    # Clear and populate output/input devices
    for w in output_scroll_frame.winfo_children(): w.destroy()
    for w in input_scroll_frame.winfo_children(): w.destroy()
    global device_widgets
    device_widgets.clear()
    
    if outputs:
        for dev in outputs:
            create_device_slider(output_scroll_frame, dev, is_output=True)
    else:
        tk.Label(output_scroll_frame, text="No output devices found.", fg="white", bg="#111111").pack(pady=5)
        
    if inputs:
        for dev in inputs:
            create_device_slider(input_scroll_frame, dev, is_output=False)
    else:
        tk.Label(input_scroll_frame, text="No input devices found.", fg="white", bg="#111111").pack(pady=5)

    # Clear and populate app sliders
    for w in app_scroll_frame.winfo_children(): w.destroy()
    global app_widgets
    app_widgets.clear()

    if not apps:
        tk.Label(app_scroll_frame, text="No applications playing audio", fg="white", bg="#111111").pack(pady=5)
    else:
        for name, idx in apps:
            create_app_slider(app_scroll_frame, name, idx)
    
    # Start the continuous refresh loops
    refresh_all_sliders()
    refresh_app_sliders()   

# In your UI setup at the bottom:
tk.Button(audio_frame, text="Refresh Devices & Apps", command=lambda: threading.Thread(target=_manual_refresh_thread, daemon=True).start(), bg="#444444", fg="white").pack(pady=10)

# --- NEW Thread Target for Manual Refresh ---
def _manual_refresh_thread():
    """Thread target for the manual refresh button."""
    outputs = get_output_devices()
    inputs = get_input_devices()
    apps = get_app_list()
    root.after(0, lambda: _initial_audio_gui_setup(outputs, inputs, apps)) 
    # _initial_audio_gui_setup handles clearing/repopulating and re-starting the timers

def _check_for_new_apps_thread():
    """Checks for new apps and updates the list if necessary (runs less often)."""
    # This function is the slow one now
    apps = get_app_list()
    
    # Quick check to see if the GUI needs to be updated (new app started)
    current_indices = {idx for _, idx in apps}
    gui_indices = {idx for _, _, idx in app_widgets}
    
    if current_indices != gui_indices:
        root.after(0, lambda: _initial_audio_gui_setup(get_output_devices(), get_input_devices(), apps))    

# --- NEW Thread Target for Manual Refresh ---
def _manual_refresh_thread():
    """
    Thread target for the manual refresh button.
    Gathers all device/app data in the background.
    """
    
    # 1. Gather all data (SLOW, runs in the background thread)
    outputs = get_output_devices()
    inputs = get_input_devices()
    apps = get_app_list()
    
    # 2. Schedule the GUI rebuild (FAST) on the main thread
    # This relies on the _initial_audio_gui_setup function provided previously.
    root.after(0, lambda: _initial_audio_gui_setup(outputs, inputs, apps))

###########################################
# ---------- AUDIO PANEL UI ----------------
###########################################
# Note: Placeholder objects (audio_frame, device_widgets, app_widgets, refresh_jobs) 
# are assumed to be defined in the global scope of your main application.

# --- Output Devices (Sinks) ---
tk.Label(audio_frame, text="Output Devices (Sinks):", fg="lightcoral", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
output_container = tk.Frame(audio_frame, bg="#111111")
# FIX: Use fill="x" and expand=False here if you want these fixed-size sections to only stretch horizontally.
# If you want this to take up space too, use fill="both", expand=True. Sticking to fill="x", expand=False for a tighter top section.
output_container.pack(fill="x", expand=False, padx=20, pady=5) 
output_scroll_frame = create_scrollable_frame(output_container)

# --- Input Devices (Sources) ---
tk.Label(audio_frame, text="Input Devices (Sources):", fg="lightgreen", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
input_container = tk.Frame(audio_frame, bg="#111111")
# FIX: Use fill="x" and expand=False for this section.
input_container.pack(fill="x", expand=False, padx=20, pady=5) 
input_scroll_frame = create_scrollable_frame(input_container)

# --- Application Volumes ---
tk.Label(audio_frame, text="Application Volumes:", fg="lightblue", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
app_container = tk.Frame(audio_frame, bg="#111111")

# ✅ THE CRITICAL FIX: The application list should take up all remaining space.
app_container.pack(fill="both", expand=True, padx=20, pady=5) 
app_scroll_frame = create_scrollable_frame(app_container)

# --- Refresh Button ---
tk.Button(
    audio_frame, 
    text="Refresh Devices & Apps", 
    command=lambda: threading.Thread(target=_manual_refresh_thread, daemon=True).start(), 
    bg="#444444", 
    fg="white"
).pack(pady=10)    


###########################################
# ---------- START APPLICATION ------------
###########################################
# Show the WiFi panel on start up
show_wifi_panel() 


###########################################
# ---------- CLOSE APPLICATION ------------
###########################################
def on_closing():
    """Stops all recurring jobs and destroys the root window."""
    # 1. Cancel all recurring jobs
    stop_refresh_jobs() 
    
    # 2. Safely destroy the root window
    root.destroy()

# Override the default window close handler
root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()