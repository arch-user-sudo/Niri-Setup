import tkinter as tk
from tkinter import ttk
import subprocess
import re
import os 
import threading 
import time

# --- Global Tracking for Recursive After Calls ---
refresh_jobs = {} 

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

# --- Tkinter Setup and Style ---
def configure_styles():
    style = ttk.Style()
    style.theme_use('clam')
    
    style.configure("TScrollbar", troughcolor="#111111", background="#444444", 
                    gripcount=0, bordercolor="#111111", darkcolor="#222222", 
                    lightcolor="#666666", arrowcolor="white")
    style.map("TScrollbar", background=[('active', '#666666')])
    
root = tk.Tk()
root.title("My App - WiFi, Bluetooth & Audio")
root.geometry("900x650") 
root.configure(bg="#111111")
root.attributes("-alpha", 0.98) 
configure_styles() 

###########################################
# ---------- TOP MENU ---------------------
###########################################
def show_wifi_panel(): 
    stop_refresh_jobs()
    for frame in (bluetooth_frame, audio_frame):
        frame.pack_forget()
    wifi_connect_frame.pack(fill="both", expand=True, padx=20, pady=20)
    perform_wifi_scan() 
    refresh_status() # Initial connection status update

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

def stop_refresh_jobs():
    """Cancels all active root.after jobs."""
    global refresh_jobs
    for key, job_id in list(refresh_jobs.items()):
        try:
            root.after_cancel(job_id)
            del refresh_jobs[key]
        except ValueError:
            pass

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
# ---------- WIFI FUNCTIONS ----------------
###########################################
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
        wifi_networks_listbox.insert(tk.END, f"✅ Disconnected from {connection_name}")
    else:
        wifi_networks_listbox.insert(tk.END, f"❌ Failed to disconnect: {disconnect_result.stderr.strip()}")
    refresh_status() # Update all status boxes

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

    # 2. Update the connected networks listbox
    connected_networks_listbox.delete(0, tk.END)
    active_connections = get_active_wifi_connections()
    
    if not active_connections:
        connected_networks_listbox.insert(tk.END, "No active connections.")
    else:
        for conn in active_connections:
            # Display the type to clarify (e.g., "Ethernet: Wired connection 1")
            display = f"{conn['type'].capitalize()}: {conn['name']}"
            connected_networks_listbox.insert(tk.END, display)

        # Store data needed for disconnect
        connected_networks_listbox.connections_data = active_connections
    
    # Enable/disable button based on if there are ANY active connections
    disconnect_button.config(state=tk.NORMAL if active_connections else tk.DISABLED)


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
            networks.append(f"{ssid} ({signal}%)")
    return networks

def perform_wifi_scan():
    wifi_networks_listbox.delete(0, tk.END)
    wifi_networks_listbox.insert(tk.END, "Scanning...")
    root.after(100, update_wifi_scan_results)

def update_wifi_scan_results():
    wifi_networks_listbox.delete(0, tk.END)
    networks = scan_wifi_networks()
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

    subprocess.run(["nmcli", "connection", "delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        connected_networks_listbox.insert(tk.END, "Select a connection to disconnect.")
    except AttributeError:
        # Should not happen if button is disabled correctly
        pass 
        
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
    
    def set_app_volume(value):
        try:
            run_pactl(["set-sink-input-volume", app_index, f"{value}%"])
        except:
            pass
            
    slider.config(command=set_app_volume)
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
    
    # Refresh app list periodically in case new apps start
    populate_app_sliders() 
    
    for slider, name, idx in app_widgets:
        try:
            vol_info = run_pactl(["list", "sink-inputs"]).stdout
            block_start = vol_info.find(f"Sink Input #{idx}")
            if block_start != -1:
                block_end = vol_info.find("Sink Input #", block_start + 1)
                block = vol_info[block_start:] if block_end == -1 else vol_info[block_start:block_end]
                
                vol_line = [l for l in block.splitlines() if "Volume:" in l]
                if vol_line:
                    match = re.search(r'/\s*(\d+)%', vol_line[0])
                    if match:
                        percent = int(match.group(1))
                        if abs(slider.get() - percent) > 5:
                            slider.set(percent)
        except Exception:
            pass
            
    refresh_jobs['audio_apps'] = audio_frame.after(1000, refresh_app_sliders)


###########################################
# ---------- AUDIO PANEL UI ----------------
###########################################
tk.Label(audio_frame, text="🎶 Output Devices (Sinks) 🎧", fg="lightcoral", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
output_container = tk.Frame(audio_frame, bg="#111111", height=150)
output_container.pack(fill="x", expand=False, padx=20, pady=5) 
output_scroll_frame = create_scrollable_frame(output_container)

tk.Label(audio_frame, text="🎤 Input Devices (Sources) 🎙️", fg="lightgreen", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
input_container = tk.Frame(audio_frame, bg="#111111", height=120)
input_container.pack(fill="x", expand=False, padx=20, pady=5) 
input_scroll_frame = create_scrollable_frame(input_container)

tk.Label(audio_frame, text="🔊 Application Volumes 🎮", fg="lightblue", bg="#111111", font=("Arial", 12, "bold")).pack(pady=(10,5), fill="x")
app_container = tk.Frame(audio_frame, bg="#111111")
app_container.pack(fill="both", expand=True, padx=20, pady=5) 
app_scroll_frame = create_scrollable_frame(app_container)

tk.Button(audio_frame, text="Refresh Devices & Apps", command=lambda: [populate_devices(), populate_app_sliders()], bg="#444444", fg="white").pack(pady=10)

###########################################
# ---------- WIFI CONNECT PANEL UI --------
###########################################
tk.Label(wifi_connect_frame, text="🌐 WiFi Connection Manager 📡", fg="white", bg="#111111", font=("Arial", 14, "bold")).pack(pady=20)
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
tk.Label(wifi_connect_frame, text="Active Connections (All Types):", fg="yellow", bg="#111111").pack(pady=(10,5), anchor="w", padx=20)
connected_frame = tk.Frame(wifi_connect_frame, bg="#111111")
connected_frame.pack(pady=5, fill="x", padx=20)

connected_networks_listbox = tk.Listbox(connected_frame, height=2, bg="#222222", fg="lime", selectbackground="#003300", selectforeground="white")
connected_networks_listbox.pack(side="left", fill="x", expand=True)
connected_networks_listbox.connections_data = [] # To store UUIDs

disconnect_button = tk.Button(connected_frame, text="Disconnect", command=disconnect_selected_wifi, bg="#440000", fg="white", state=tk.DISABLED)
disconnect_button.pack(side="right", padx=(10,0))

# --- Original Status Box ---
status_frame = tk.Frame(wifi_connect_frame, bg="#111111")
status_frame.pack(pady=10, fill="x", padx=20)
tk.Label(status_frame, text="General Device Status:", fg="white", bg="#111111").pack(anchor="w")
status_text = tk.Text(status_frame, height=4, bg="#222222", fg="white", state="disabled")
status_text.pack(fill="x", pady=5)

button_frame_bottom = tk.Frame(wifi_connect_frame, bg="#111111")
button_frame_bottom.pack(pady=5, padx=20, fill="x")

tk.Button(button_frame_bottom, text="Scan for Networks", command=perform_wifi_scan, bg="#444444", fg="white").pack(side="left", padx=(0, 5), expand=True, fill="x")
tk.Button(button_frame_bottom, text="Refresh Status", command=refresh_status, bg="#444444", fg="white").pack(side="left", padx=(5, 0), expand=True, fill="x")


###########################################
# ---------- BLUETOOTH FUNCTIONS (using bluetoothctl) ----------
###########################################
bt_adapter_mac = None

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
    
    # Simple check for successful retrieval of info
    name_match = re.search(r"Alias:\s*(.+)", info_stdout)
    name = name_match.group(1).strip() if name_match else mac
    
    return {
        "name": name,
        "mac": mac,
        "connected": bool(connected_match),
        "paired": bool(paired_match)
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
        status_icon = "🟢" if dev['connected'] else "🔵" if dev['paired'] else "⚪"
        display_name = f"{status_icon} {dev['name']}"
        available_devices.append((display_name, dev['mac']))
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
        if dev['connected']:
            connected_devices.append(dev)
            connected_bt_listbox.insert(tk.END, f"🔗 {dev['name']}")

    connected_bt_listbox.devices_data = connected_devices
    bt_disconnect_button.config(state=tk.NORMAL if connected_devices else tk.DISABLED)


def get_selected_device():
    try:
        selected_index = bluetooth_listbox.curselection()[0]
        display_name, mac = getattr(bluetooth_listbox, "devices", [])[selected_index] 
        # Clean up alias from icon and space
        alias = re.sub(r'^\s*[⚪🔵🟢]\s*', '', display_name)
        return alias, mac 
    except (tk.TclError, IndexError, AttributeError):
        bt_status_listbox.insert(tk.END, "⚠️ Select a device first from the Available list.")
        return None, None

def connect_bt_device():
    alias, mac = get_selected_device()
    if not mac: return
    
    bt_status_listbox.insert(tk.END, f"Attempting connect/pair to {alias}...")
    # Attempt to pair and then connect
    stdout, stderr, _ = run_bluetoothctl_command(f"pair {mac}\nconnect {mac}\nexit\n")

    if "Failed to pair" in stdout or "Failed to connect" in stdout or stderr:
        bt_status_listbox.insert(tk.END, f"❌ Connection failed. Check if device is discoverable/already connected.")
    else:
        bt_status_listbox.insert(tk.END, f"✅ Connection successful (or requested).")
    
    root.after(1000, scan_bt_devices) # Refresh list status

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


def disconnect_selected_bt():
    try:
        selection_index = connected_bt_listbox.curselection()[0]
        dev_data = connected_bt_listbox.devices_data[selection_index]
        do_disconnect_bt(dev_data['mac'])
    except IndexError:
        connected_bt_listbox.insert(tk.END, "Select a connected device to disconnect.")
    except AttributeError:
        pass # Button should be disabled


def refresh_bt_status():
    bt_status_listbox.delete(0, tk.END)
    mac = get_adapter_mac()
    
    if not mac:
        bt_status_listbox.insert(tk.END, "❌ Bluetooth adapter not found.")
        bluetooth_listbox.delete(0, tk.END)
        return

    powered = get_adapter_powered()
    status_msg = f"Adapter ({mac}) powered: {'✅ ON' if powered else '❌ OFF'}"
    bt_status_listbox.insert(tk.END, status_msg)
    
    if powered:
        scan_bt_devices()
    else:
        bluetooth_listbox.delete(0, tk.END)
        bluetooth_listbox.insert(tk.END, "Adapter is OFF. Toggle ON to scan.")
        update_connected_bt_list([]) # Clear connected list if off

###########################################
# ---------- BLUETOOTH PANEL UI -----------
###########################################
tk.Label(bluetooth_frame, text="🟦 Bluetooth Manager 🎧", fg="white", bg="#111111", font=("Arial", 14, "bold")).pack(pady=20)

# --- NEW: Connected Bluetooth Box ---
tk.Label(bluetooth_frame, text="Active Connections:", fg="yellow", bg="#111111").pack(pady=(0,5), anchor="w", padx=20)
bt_connected_frame = tk.Frame(bluetooth_frame, bg="#111111")
bt_connected_frame.pack(pady=5, fill="x", padx=20)

connected_bt_listbox = tk.Listbox(bt_connected_frame, height=2, bg="#222222", fg="lime", selectbackground="#003300", selectforeground="white")
connected_bt_listbox.pack(side="left", fill="x", expand=True)
connected_bt_listbox.devices_data = [] 

bt_disconnect_button = tk.Button(bt_connected_frame, text="Disconnect", command=disconnect_selected_bt, bg="#440000", fg="white", state=tk.DISABLED)
bt_disconnect_button.pack(side="right", padx=(10,0))


tk.Label(bluetooth_frame, text="Available / Known Devices:", fg="white", bg="#111111").pack(pady=(10,5), anchor="w", padx=20)
bluetooth_listbox = tk.Listbox(bluetooth_frame, bg="#222222", fg="white", selectbackground="#444444", selectforeground="white", height=10)
bluetooth_listbox.pack(padx=20, pady=10, fill="both", expand=True)
bluetooth_listbox.devices = [] 

bt_button_frame = tk.Frame(bluetooth_frame, bg="#111111")
bt_button_frame.pack(pady=10)

tk.Button(bt_button_frame, text="Toggle Adapter", command=toggle_adapter, bg="#444400", fg="white").pack(side="left", padx=5)
tk.Button(bt_button_frame, text="Scan Devices", command=scan_bt_devices, bg="#004444", fg="white").pack(side="left", padx=5)
tk.Button(bt_button_frame, text="Connect", command=connect_bt_device, bg="#004400", fg="white").pack(side="left", padx=5)
tk.Button(bt_button_frame, text="Refresh Status", command=refresh_bt_status, bg="#444444", fg="white").pack(side="left", padx=5)

tk.Label(bluetooth_frame, text="Status Log:", fg="white", bg="#111111").pack(pady=(10,5), anchor="w", padx=20)
bt_status_listbox = tk.Listbox(bluetooth_frame, bg="#222222", fg="white", height=5)
bt_status_listbox.pack(padx=20, pady=10, fill="x", expand=False)


###########################################
# ---------- START APPLICATION ------------
###########################################
# Show the WiFi panel on start up
show_wifi_panel() 

root.mainloop()