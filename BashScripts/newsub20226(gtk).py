import sys
import threading
import time
import gi
import subprocess
import re
import os
import traceback 

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio 

# Helper class for list box rows (used for WiFi and Bluetooth dynamic lists)
class ListItemRow(Gtk.ListBoxRow):
    def __init__(self, display_text, data=None):
        super().__init__()
        self.data = data # Store the full connection/device data here
        label = Gtk.Label(label=display_text, xalign=0)
        label.set_margin_start(5)
        self.set_child(label)


class ConnectionCentreApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.connectioncentre.app", 
                         flags=0)
        # Global job tracker
        self.refresh_jobs = {}
        
        # Initialize data storage lists/variables
        self.connected_networks_data = [] # For WiFi/Ethernet connections
        self.connected_bt_data = []       # For connected Bluetooth devices
        self.bluetooth_listbox_devices = [] # For all discovered/paired BT devices
        self.device_widgets = []          # For Audio sink/source dynamic widgets
        self.app_widgets = []             # For Audio application dynamic widgets
        self.bt_adapter_mac = None        # Bluetooth adapter MAC address


    def do_activate(self):
        # --- 1. Window Setup ---
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_title("Centre")
        
        # Dynamic Sizing (Kept this, as it determines the *initial* size)
        display = Gdk.Display.get_default()
        monitor = None
        
        if display:
            try:
                # GTK 3/X11 friendly way
                monitor = display.get_primary_monitor()
            except AttributeError:
                # GTK 4/Wayland friendly way
                try:
                    monitors = display.get_monitors()
                    if monitors.get_n_items() > 0:
                        monitor = monitors.get_item(0)
                except AttributeError:
                    pass
        
        if monitor:
            geometry = monitor.get_geometry()
            # Set a size relative to the monitor, e.g., 75% of width, 80% of height
            width = int(geometry.width * 0.75)
            height = int(geometry.height * 0.8)
            self.win.set_default_size(width, height)
        else:
            # Fallback size if monitor detection fails entirely
            self.win.set_default_size(1000, 750) 
        
        
        # Connect the safe shutdown method
        self.win.connect("close-request", self.on_closing) 

        # --- 2. Styling (CSS) ---
        css_provider = Gtk.CssProvider()
        css = """
        window, box, stack, grid, listboxrow, {
            background-color: #222222B3;
            color: white;
        }
        button {
            background-color: #333333;
            color: white;
            margin: 5px;
            padding: 5px;
        }
        button:hover {
            background-color: #555555;
        }
               .yellow-text { color: yellow; }
        .lime-text { color: lime; }
        .red-text { color: red; }
        .cyan-text { color: cyan; }
        .bold { font-weight: bold; }
        .wifi-on { background-color: #004400; }
        .wifi-off { background-color: #440000; }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # --- 3. Main Layout Container ---
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_child(self.main_box)

        # --- 4. The Top Menu Bar (Buttons) ---
        self.menu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_box.append(self.menu_box)

        btn_wifi = Gtk.Button(label="WiFi")
        btn_wifi.connect("clicked", lambda x: self.show_panel("wifi"))
        self.menu_box.append(btn_wifi)

        btn_bt = Gtk.Button(label="Bluetooth")
        btn_bt.connect("clicked", lambda x: self.show_panel("bluetooth"))
        self.menu_box.append(btn_bt)

        btn_audio = Gtk.Button(label="Audio")
        btn_audio.connect("clicked", lambda x: self.show_panel("audio"))
        self.menu_box.append(btn_audio)

        # --- 5. The Content Stack (Replaces Frames) ---
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)
        self.main_box.append(self.stack)

        # --- 6. Initialize Pages (The Frames) ---
        
        # WIFI PANEL UI INJECTION
        self.wifi_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.stack.add_named(self.wifi_page, "wifi")
        self._setup_wifi_ui() # Setup method below
        
        # BLUETOOTH PANEL UI INJECTION
        self.bluetooth_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.stack.add_named(self.bluetooth_page, "bluetooth")
        self._setup_bluetooth_ui() # Setup method below

        # AUDIO PANEL UI INJECTION
        self.audio_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.stack.add_named(self.audio_page, "audio")
        self._setup_audio_ui() # Setup method below

        # Show the window
        self.win.present()
        
        # Initialize default view
        self.show_panel("wifi")


    # --- General Utilities ---
    
    def _log_error_to_ui(self, message, panel_name):
        """Logs an error message to the correct panel's log area."""
        
        def update():
            # Check if the UI element exists before trying to update it
            if panel_name == "wifi" and hasattr(self, 'status_text_view'):
                # Also log to console for debugging
                print(f"THREAD ERROR LOG (WIFI): {message}") 
                self._update_status_text(f"❌ THREAD ERROR: {message.splitlines()[0]}", clear=False)
            elif panel_name == "bluetooth" and hasattr(self, 'bt_status_listbox'):
                print(f"THREAD ERROR LOG (BLUETOOTH): {message}")
                self._update_bt_log(f"❌ THREAD ERROR: {message.splitlines()[0]}")
            else:
                 print(f"THREAD ERROR LOG (AUDIO/GLOBAL): {message}")
                 
        GLib.idle_add(update)
        
    def _safe_thread_start(self, target, args=(), kwargs={}, panel_name="wifi"):
        """Wraps a target function with exception handling before running it in a thread."""
        
        def safe_wrapper():
            try:
                # The target function is called here
                target(*args, **kwargs)
            except Exception as e:
                # Log the error and traceback to prevent application crash
                error_msg = f"Uncaught exception in background thread '{target.__name__}': {e}\n{traceback.format_exc()}"
                self._log_error_to_ui(error_msg, panel_name)

        # CRITICAL: Use the safe wrapper to start the thread
        threading.Thread(target=safe_wrapper, daemon=True).start()
    
    def on_closing(self, win):
        """Safely shuts down the application by canceling all GLib jobs."""
        print("Shutting down... canceling background jobs.")
        self.stop_refresh_jobs()
        # Returning False allows the window to close normally after cleanup.
        return False 
        
    def stop_refresh_jobs(self):
        """Cancels all active GLib timeouts."""
        for key, source_id in list(self.refresh_jobs.items()):
            print(f"Stopping job: {key}") # Debug
            GLib.source_remove(source_id)
            del self.refresh_jobs[key]

    def show_panel(self, panel_name):
        """Handles switching panels and stopping old jobs."""
        print(f"Switching to {panel_name} panel.")
        self.stop_refresh_jobs()
        self.stack.set_visible_child_name(panel_name)

        if panel_name == "wifi":
            # Start status refresh loop
            self.refresh_status() 
        elif panel_name == "bluetooth":
            # Start status refresh loop
            self.refresh_bt_status()
        elif panel_name == "audio":
            # Start initial data load in a thread
            self._safe_thread_start(target=self._load_audio_panel_thread, panel_name="audio")
            
    def _run_subprocess(self, command, timeout=10):
        """Helper to safely run subprocess commands."""
        try:
            result = subprocess.run(
                command,
                capture_output=True, text=True, check=True, timeout=timeout
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.CalledProcessError as e:
            return "", e.stderr.strip(), e.returncode
        except FileNotFoundError:
            return "", f"{command[0]} command not found.", 127
        except subprocess.TimeoutExpired:
            return "", f"{command[0]} command timed out after {timeout} seconds.", 1
        except Exception as e:
            return "", str(e), 1
            
    def _update_status_text(self, text, clear=False):
        """Helper to safely update the WiFi status Gtk.TextView."""
        buffer = self.status_text_view.get_buffer()
        
        def update():
            if clear:
                buffer.set_text("")
            # Get the end of the current content
            end_iter = buffer.get_end_iter()
            # Append the new text
            buffer.insert(end_iter, text + "\n")
            # Optionally scroll to the end
            
        # Ensure GUI update is on the main thread
        GLib.idle_add(update)
            
    def _update_bt_log(self, text):
        """Helper to add a new message to the Bluetooth Gtk.ListBox log."""
        def update():
            row = ListItemRow(text)
            self.bt_status_listbox.append(row)
            # Limit log size
            if self.bt_status_listbox.get_row_at_index(50):
                self.bt_status_listbox.remove(self.bt_status_listbox.get_row_at_index(0))
        GLib.idle_add(update)

    # --- WIFI Backend Methods (nmcli) ---
    
    def get_wifi_radio_status(self):
        """Checks the global Wi-Fi radio state (enabled/disabled)."""
        stdout, _, _ = self._run_subprocess(["nmcli", "radio", "wifi"], timeout=3)
        return stdout.lower() == "enabled"

    def toggle_wifi_radio(self):
        """Toggles the global Wi-Fi radio."""
        is_enabled = self.get_wifi_radio_status()
        action = "off" if is_enabled else "on"
        
        stdout, stderr, returncode = self._run_subprocess(["nmcli", "radio", "wifi", action], timeout=5)

        if returncode == 0:
            new_state = "DISABLED" if action == "off" else "ENABLED"
            self._update_status_text(f"📶 Wi-Fi radio successfully set to {new_state}.")
        else:
            self._update_status_text(f"❌ Failed to toggle Wi-Fi: {stderr}")
            
        # Always refresh the UI after a toggle attempt
        self.refresh_wifi_ui_on_toggle(do_scan=True)

    def refresh_wifi_ui_on_toggle(self, do_scan=True):
        """Updates the toggle button and the network listbox state."""
        is_enabled = self.get_wifi_radio_status()
        
        def update_gui():
            if is_enabled:
                self.wifi_toggle_button.set_label("Wi-Fi: ON")
                self.wifi_toggle_button.set_css_classes(['wifi-on'])
                self.wifi_networks_listbox.set_sensitive(True)
            else:
                self.wifi_toggle_button.set_label("Wi-Fi: OFF")
                self.wifi_toggle_button.set_css_classes(['wifi-off'])
                
                # Clear and disable listbox when radio is off
                self._clear_container(self.wifi_networks_listbox)
                self._add_listbox_item(self.wifi_networks_listbox, "Wi-Fi radio is OFF. Toggle ON to scan.")
                self.wifi_networks_listbox.set_sensitive(False) 
                
            # Only initiate a full scan if it's ON and explicitly requested
            if is_enabled and do_scan:
                self.perform_wifi_scan()

        GLib.idle_add(update_gui)


    def get_active_wifi_connections(self):
        """Uses nmcli to find ALL active connections."""
        stdout, _, _ = self._run_subprocess(
            ["nmcli", "-t", "-f", "TYPE,DEVICE,NAME,UUID", "connection", "show", "--active"],
            timeout=5
        )
        connections = []
        for line in stdout.split("\n"):
            if line:
                parts = line.split(":")
                if len(parts) >= 4:
                    connections.append({
                        "type": parts[0], 
                        "device": parts[1], 
                        "name": parts[2], 
                        "uuid": parts[3]
                    })
        return connections


    def do_disconnect_wifi(self, connection_name, uuid):
        """Disconnects a specific Wi-Fi connection by its UUID."""
        stdout, stderr, returncode = self._run_subprocess(
            ["nmcli", "connection", "down", uuid], timeout=10
        )
        if returncode == 0:
            self._update_status_text(f"✅ Disconnected from {connection_name}")
        else:
            self._update_status_text(f"❌ Failed to disconnect: {stderr}")
        self.refresh_status() 

    def do_forget_wifi(self, connection_name, uuid):
        """Deletes (forgets) a saved connection profile by its UUID."""
        # Ensure it's down first, then delete
        self.do_disconnect_wifi(connection_name, uuid)
        
        stdout, stderr, returncode = self._run_subprocess(
            ["nmcli", "connection", "delete", uuid], timeout=10
        )
        
        if returncode == 0:
            self._update_status_text(f"✅ Forgotten network profile: {connection_name}")
        else:
            self._update_status_text(f"❌ Failed to forget: {stderr}")
        
        self.refresh_status() 

    def _clear_container(self, container):
        """
        Removes all children from a Gtk.ListBox or Gtk.Box.
        """
        # Gtk.ListBox case (uses rows)
        if isinstance(container, Gtk.ListBox):
            while True:
                # Use get_row_at_index(0) and remove() for ListBox
                row = container.get_row_at_index(0)
                if row:
                    container.remove(row)
                else:
                    break
        
        # Gtk.Box or other generic container case
        else:
            # Use get_first_child() and remove() for Gtk.Box
            while True:
                child = container.get_first_child()
                if child:
                    container.remove(child)
                else:
                    break
            
    def _add_listbox_item(self, listbox, text, data=None):
        """Adds a new ListItemRow to a Gtk.ListBox."""
        row = ListItemRow(text, data)
        listbox.append(row)

    def refresh_status(self):
        """Updates the primary status text and the connected networks listbox."""
        
        # 1. Update primary status text (Runs on main thread for quick update)
        stdout, _, _ = self._run_subprocess(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], timeout=3
        )
        lines = []
        for line in stdout.split("\n"):
            if line:
                parts = line.split(":")
                device, dev_type, state, connection = (parts + [""] * 4)[:4]
                if state.lower() == "connected":
                    lines.append(f"✅ {device} ({dev_type}) connected to {connection}")
                elif dev_type in ("wifi", "ethernet"):
                    lines.append(f"❌ {device} ({dev_type}) not connected (State: {state})")

        self._update_status_text("\n".join(lines) if lines else "No network information available.", clear=True)
        self.refresh_wifi_ui_on_toggle(do_scan=False) # Update toggle button

        # 2. Update the connected networks listbox
        active_connections = self.get_active_wifi_connections()
        self.connected_networks_data = active_connections # Store data

        self._clear_container(self.connected_networks_listbox)
        
        if not active_connections:
            self._add_listbox_item(self.connected_networks_listbox, "No active connections.")
        else:
            for conn in active_connections:
                display = f"{conn['type'].capitalize()}: {conn['name']}"
                self._add_listbox_item(self.connected_networks_listbox, display, conn)

        # Enable/disable buttons based on if there are ANY active connections
        has_active_connections = bool(active_connections)
        self.disconnect_button.set_sensitive(has_active_connections)
        self.forget_button.set_sensitive(has_active_connections)
        
        # 3. Schedule next refresh
        # Only schedule if the speedtest job hasn't stopped it
        if 'wifi_status' in self.refresh_jobs:
            GLib.source_remove(self.refresh_jobs['wifi_status'])
        
        # Schedule the next refresh in 5 seconds
        self.refresh_jobs['wifi_status'] = GLib.timeout_add_seconds(5, self.refresh_status)
        return GLib.SOURCE_CONTINUE


    def scan_wifi_networks(self):
        stdout, _, _ = self._run_subprocess(
            ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"], timeout=10
        )
        networks = []
        known_ssids = set()
        for line in stdout.split("\n"):
            if line:
                # Use regex to find the signal percentage at the end
                match = re.search(r':(\d+)$', line)
                if match:
                    signal = match.group(1)
                    # FIX: Robustly determine the SSID by taking the substring before the signal percentage match
                    # This prevents SSIDs with colons from breaking the parsing
                    ssid = line[:match.start()].strip()
                    
                    ssid = ssid if ssid else "<Hidden Network>"
                    
                    # Only add if we haven't seen this SSID before in this scan
                    if ssid not in known_ssids:
                        networks.append((f"{ssid} ({signal}%)", ssid))
                        known_ssids.add(ssid)
        return networks

    def perform_wifi_scan(self):
        """Starts a background thread to scan networks and updates the listbox."""
        self._clear_container(self.wifi_networks_listbox)
        self._add_listbox_item(self.wifi_networks_listbox, "Scanning for networks... Please wait.")
        
        self._safe_thread_start(target=self._update_wifi_scan_results_thread, panel_name="wifi")

    def _update_wifi_scan_results_thread(self):
        """The function that runs in the thread to get scan results."""
        networks = self.scan_wifi_networks()
        # Schedule the GUI update back on the main thread
        GLib.idle_add(lambda: self._update_wifi_scan_results_gui(networks))

    def _update_wifi_scan_results_gui(self, networks):
        """Updates the Listbox on the main GUI thread."""
        self._clear_container(self.wifi_networks_listbox)
        if not networks:
            self._add_listbox_item(self.wifi_networks_listbox, "No WiFi networks found.")
        else:
            for display, ssid in networks:
                # The data stored here is just the raw SSID needed for connection
                self._add_listbox_item(self.wifi_networks_listbox, display, ssid)


    def do_connect(self):
        selected_row = self.wifi_networks_listbox.get_selected_row()
        if not selected_row:
            self._update_status_text("Select a network first.")
            return

        # The raw SSID is stored in the data attribute of the ListItemRow
        ssid = selected_row.data
        password = self.password_entry.get_text()

        if not password:
            self._update_status_text(f"⚠️ Enter a password for {ssid}.")
            return

        self._clear_container(self.wifi_networks_listbox)
        self._add_listbox_item(self.wifi_networks_listbox, f"Connecting to {ssid}...")
        
        self._safe_thread_start(target=self._connect_thread, args=(ssid, password), panel_name="wifi")

    def _connect_thread(self, ssid, password):
        """Performs the connection in a background thread."""
        
        # 1. Find the Wi-Fi interface name
        iface_stdout, _, _ = self._run_subprocess(
            ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], timeout=3
        )
        wifi_iface = next((line.split(":")[0] for line in iface_stdout.split("\n") if ":wifi" in line), None)
        
        if not wifi_iface:
            GLib.idle_add(lambda: self._update_wifi_scan_results_gui([])) # Clear list
            self._update_status_text("❌ No Wi-Fi interface found.")
            return

        # 2. Try to delete old connection profile with the same name first
        # FIX: Use the internal wrapper for consistency and timeout control
        self._run_subprocess(["nmcli", "connection", "delete", ssid], timeout=5)
        
        # 3. Create new connection profile and connect
        create_cmd = ["nmcli", "connection", "add", "type", "wifi", "ifname", wifi_iface,
                      "con-name", ssid, "ssid", ssid, "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
        
        _, create__stderr, create_returncode = self._run_subprocess(create_cmd, timeout=10)

        if create_returncode != 0:
            self._update_status_text(f"❌ Failed to create profile: {create__stderr}")
            GLib.idle_add(self.perform_wifi_scan) # Re-scan
            return
            
        connect_cmd = ["nmcli", "connection", "up", ssid]
        connect_stdout, connect_stderr, connect_returncode = self._run_subprocess(connect_cmd, timeout=20)
        
        # 4. Update UI with results
        if connect_returncode == 0:
            self._update_status_text(f"✅ Successfully connected to {ssid}", clear=True)
            # Re-scan to show connection status
            GLib.idle_add(self.perform_wifi_scan) 
        else:
            self._update_status_text(f"❌ Failed to connect: {connect_stderr}", clear=True)
            GLib.idle_add(self.perform_wifi_scan) # Re-scan
            
        # 5. Refresh general status
        GLib.idle_add(self.refresh_status)


    def disconnect_selected_wifi(self):
        selected_row = self.connected_networks_listbox.get_selected_row()
        if not selected_row:
            self._update_status_text("⚠️ Select a connection to disconnect.")
            return

        conn_data = selected_row.data
        self.do_disconnect_wifi(conn_data["name"], conn_data["uuid"])
        
    def forget_selected_connection(self):
        selected_row = self.connected_networks_listbox.get_selected_row()
        if not selected_row:
            self._update_status_text("⚠️ Select a connection to forget.")
            return

        conn_data = selected_row.data
        self.do_forget_wifi(conn_data["name"], conn_data["uuid"])

    def run_speedtest_thread(self):
        """Initiates the speedtest in a separate thread to prevent GUI freeze."""
        
        # FIX: CRITICAL - Stop the continuous refresh job before starting the speedtest
        if 'wifi_status' in self.refresh_jobs:
            GLib.source_remove(self.refresh_jobs['wifi_status'])
            del self.refresh_jobs['wifi_status']
        
        self._update_status_text("Running speedtest... This may take a minute.", clear=True)
        self.speedtest_button.set_sensitive(False)
        self.speedtest_button.set_label("Testing...")
        
        # CRITICAL FIX: Use the safe wrapper here
        self._safe_thread_start(target=self._speedtest_target, panel_name="wifi")

    def _speedtest_target(self):
        """The actual speedtest logic running in a background thread."""
        # Use a longer timeout for speedtest-cli
        output, error, return_code = self._run_subprocess(
            ["speedtest-cli", "--simple"], timeout=60
        )
        
        GLib.idle_add(lambda: self._update_speedtest_results(output, error, return_code))

    def _update_speedtest_results(self, output, error, return_code):
        """Updates the status text area with speedtest results (on main thread)."""
        
        self._update_status_text("", clear=True) # Clear existing text (the "Running speedtest..." message)

        if return_code == 0:
            self._update_status_text("✅ Speedtest Results:\n\n" + output)
        else:
            if return_code == 127:
                 self._update_status_text("❌ Speedtest Failed:\n\nError: speedtest-cli not found. Install it (e.g., 'pip install speedtest-cli').")
            elif error:
                 self._update_status_text("❌ Speedtest Failed (Check Connection):\n\n" + error)
            else:
                 self._update_status_text("❌ Speedtest Failed (Unknown Error).\n" + output)

        self.speedtest_button.set_sensitive(True)
        self.speedtest_button.set_label("Run Speedtest")
        
        # FIX: CRITICAL - Schedule the return to normal status refresh after a long delay (60s)
        def restart_status_refresh():
            # Clear the speedtest results
            self._update_status_text("\n\n--- Speedtest results expired. Resuming status updates. ---", clear=True)
            # Calling refresh_status() triggers the first status update and re-schedules the recurring job.
            self.refresh_status() 
            return GLib.SOURCE_REMOVE # This is a one-time job

        # Schedule the status refresh to remain paused for 60 seconds to allow reading
        GLib.timeout_add_seconds(60, restart_status_refresh)
        
        
    # --- BLUETOOTH Backend Methods (bluetoothctl) ---

    def _run_bluetoothctl_command(self, commands):
        """Pipes commands to the interactive bluetoothctl shell."""
        try:
            # FIX: Increased timeout from 5s to 15s for reliable pairing/connection
            p = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # Communicate sends the commands and waits for output
            stdout, stderr = p.communicate(input=commands, timeout=15) 
            return stdout, stderr, p.returncode
        except FileNotFoundError:
            return "", "bluetoothctl command not found. Is bluez-utils installed?", 127
        except subprocess.TimeoutExpired:
            p.kill()
            return "", "bluetoothctl command timed out.", 1
        except Exception as e:
            return "", str(e), 1

    def get_adapter_mac(self):
        if self.bt_adapter_mac: return self.bt_adapter_mac
        
        stdout, _, _ = self._run_bluetoothctl_command("show\nexit\n")
        mac_match = re.search(r'Controller\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', stdout, re.I)
        
        if mac_match:
            self.bt_adapter_mac = mac_match.group(1)
            return self.bt_adapter_mac
        return None

    def get_adapter_powered(self):
        stdout, _, _ = self._run_bluetoothctl_command("show\nexit\n")
        powered = re.search(r"Powered:\s*(yes|no)", stdout)
        return powered.group(1).lower() == "yes" if powered else False

    def toggle_adapter(self):
        mac = self.get_adapter_mac()
        if not mac:
            self._update_bt_log("❌ No Bluetooth adapter found.")
            return
        
        powered = self.get_adapter_powered()
        command = "power off\n" if powered else "power on\n"
        
        stdout, stderr, _ = self._run_bluetoothctl_command(command + "exit\n")
        
        if stderr and not re.search("Changing power is only allowed when on a primary controller", stderr):
            self._update_bt_log(f"❌ Failed to toggle: {stderr.strip()}")
        else:
            self.refresh_bt_status()

    def get_device_info(self, mac):
        """Gets detailed info for a single MAC."""
        info_stdout, _, _ = self._run_bluetoothctl_command(f"info {mac}\nexit\n")
        
        connected_match = re.search(r"Connected:\s*(yes)", info_stdout)
        paired_match = re.search(r"Paired:\s*(yes)", info_stdout)
        trusted_match = re.search(r"Trusted:\s*(yes)", info_stdout)
        
        name_match = re.search(r"Alias:\s*(.+)", info_stdout)
        name = name_match.group(1).strip() if name_match else mac
        
        return {
            "name": name,
            "mac": mac,
            "connected": bool(connected_match),
            "paired": bool(paired_match),
            "trusted": bool(trusted_match)
        }

    def _scan_devices_thread(self):
        """Runs the scanning logic in a separate thread."""
        
        # 1. Start Discovery (non-blocking in the interactive shell)
        self._update_bt_log("Starting discovery (8 seconds)...")
        self._run_bluetoothctl_command("scan on\n")
        # FIX: Increased sleep from 5s to 8s for more reliable discovery
        time.sleep(8) 
        self._run_bluetoothctl_command("scan off\n") # Stop discovery

        # 2. Get list of all known/discovered devices
        stdout, stderr, _ = self._run_bluetoothctl_command("devices\nexit\n")

        # 3. Parse MACs and get detailed info
        device_macs = set()
        for line in stdout.splitlines():
            match = re.search(r'Device\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', line, re.I)
            if match:
                device_macs.add(match.group(1))

        all_devices = [self.get_device_info(mac) for mac in device_macs]
        
        # 4. Process results on the main thread
        GLib.idle_add(lambda: self._update_bt_scan_results_gui(all_devices, stderr))


    def scan_bt_devices(self):
        mac = self.get_adapter_mac()
        if not mac: return
        
        self._clear_container(self.bt_status_listbox)
        self._update_bt_log("Starting background scan... Please wait.")
        self._clear_container(self.bluetooth_listbox)

        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")


    def _update_bt_scan_results_gui(self, all_devices, stderr):
        """Updates the Bluetooth device list and log on the main thread."""
        
        self.bluetooth_listbox_devices = [] # Clear stored data
        self._clear_container(self.bluetooth_listbox)
        
        if "bluetoothctl command not found" in stderr:
            self._update_bt_log("❌ bluetoothctl not found. Please install bluez-utils.")
            return
        
        if stderr and not re.search("No Controllers available", stderr):
            self._update_bt_log(f"❌ Scan failed: {stderr.strip()}")
            return

        available_devices = []
        for dev in all_devices:
            status_icon = " [Connected]" if dev['connected'] else " [Trusted]" if dev['trusted'] else " [Paired]" if dev['paired'] else ""
            display_name = f"{dev['name']}{status_icon} ({dev['mac']})"
            available_devices.append(dev) # Store full device data
            self._add_listbox_item(self.bluetooth_listbox, display_name, dev)
        
        self.bluetooth_listbox_devices = available_devices

        if not available_devices:
            self._add_listbox_item(self.bluetooth_listbox, "No Bluetooth devices found/known.")
            
        self._update_bt_log("Scan complete.")
        
        # Update connected list
        self._update_connected_bt_list_gui(all_devices)

    def _update_connected_bt_list_thread(self):
        """Runs quick device check in a thread if needed."""
        stdout, _, _ = self._run_bluetoothctl_command("devices\nexit\n")
        macs = re.findall(r'Device\s+([0-9A-F]{2}(:[0-9A-F]{2}){5})', stdout, re.I)
        all_devices = [self.get_device_info(mac[0]) for mac in set(macs)]
        GLib.idle_add(lambda: self._update_connected_bt_list_gui(all_devices))


    def _update_connected_bt_list_gui(self, all_devices):
        """Updates the list of currently connected devices on the main thread."""
        self._clear_container(self.connected_bt_listbox)
        connected_devices = []
        
        for dev in all_devices:
            if dev.get('connected'):
                display_name = f"🎧 {dev['name']} ({dev['mac']})"
                self._add_listbox_item(self.connected_bt_listbox, display_name, dev)
                connected_devices.append(dev)

        if not connected_devices:
            self._add_listbox_item(self.connected_bt_listbox, "No devices connected.")
            
        self.connected_bt_data = connected_devices # Store data

    def _get_selected_device_data(self, listbox):
        """Retrieves data for the selected device from the specified listbox."""
        selected_row = listbox.get_selected_row()
        if not selected_row:
            self._update_bt_log("⚠️ Select a device first.")
            return None, None
        return selected_row.data, selected_row.data['mac']


    def pair_bt_device(self):
        selected_device, mac = self._get_selected_device_data(self.bluetooth_listbox)
        if not mac: return
        name = selected_device['name']

        self._clear_container(self.bt_status_listbox)
        self._update_bt_log(f"Attempting **Pair** with {name}...")
        
        self._safe_thread_start(target=self._pair_bt_device_thread, args=(mac, name), panel_name="bluetooth")

    def _pair_bt_device_thread(self, mac, name):
        commands = f"pair {mac}\nexit\n"
        # Uses the increased 15s timeout from _run_bluetoothctl_command
        stdout, stderr, returncode = self._run_bluetoothctl_command(commands)

        if "Pairing successful" in stdout:
            self._update_bt_log(f"✅ Successfully paired with {name}.")
        elif "Already Paired" in stdout:
            self._update_bt_log(f"ℹ️ {name} is already paired.")
        else:
            self._update_bt_log(f"❌ Pairing failed. Error: {stderr.strip() or stdout.strip()}")

        # Re-scan to update paired status
        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")


    def connect_bt_device(self):
        selected_device, mac = self._get_selected_device_data(self.bluetooth_listbox)
        if not mac: return
        name = selected_device['name']

        self._clear_container(self.bt_status_listbox)
        self._update_bt_log(f"Attempting **Connect** with {name}...")

        self._safe_thread_start(target=self._connect_bt_device_thread, args=(mac, name), panel_name="bluetooth")

    def _connect_bt_device_thread(self, mac, name):
        commands = f"connect {mac}\nexit\n"
        # Uses the increased 15s timeout from _run_bluetoothctl_command
        stdout, stderr, returncode = self._run_bluetoothctl_command(commands)

        if returncode == 0 and ("Connection successful" in stdout or "successful" in stdout):
            self._update_bt_log(f"✅ Successfully connected to {name}.")
        else:
            self._update_bt_log(f"⚠️ Connection failed. Error: {stderr.strip() or stdout.strip()}")

        # Re-scan to update connection status
        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")

    def trust_bt_device(self):
        selected_device, mac = self._get_selected_device_data(self.bluetooth_listbox)
        if not mac: return
        name = selected_device['name']
        
        self._update_bt_log(f"Attempting to trust {name}...")
        self._safe_thread_start(target=self._trust_bt_device_thread, args=(mac, name), panel_name="bluetooth")

    def _trust_bt_device_thread(self, mac, name):
        stdout, stderr, _ = self._run_bluetoothctl_command(f"trust {mac}\nexit\n")
        
        if "Failed to set property" in stdout or stderr:
            self._update_bt_log(f"❌ Failed to trust. Pair first if necessary.")
        else:
            self._update_bt_log(f"⭐ Successfully trusted {name}. It should now auto-connect.")
            
        time.sleep(1)
        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")


    def forget_bt_device(self):
        selected_device, mac = self._get_selected_device_data(self.bluetooth_listbox)
        if not mac: return
        name = selected_device['name']

        self._update_bt_log(f"Attempting to **Forget (Remove)** {name} ({mac})...")
        self._safe_thread_start(target=self._forget_bt_device_thread, args=(mac, name), panel_name="bluetooth")

    def _forget_bt_device_thread(self, mac, name):
        commands = f"remove {mac}\nexit\n"
        stdout, stderr, returncode = self._run_bluetoothctl_command(commands)

        if "Device has been removed" in stdout or "successful" in stdout:
            self._update_bt_log(f"✅ Successfully forgotten {name}.")
        elif "not available" in stdout:
            self._update_bt_log(f"ℹ️ Device {name} was not found or already removed.")
        else:
            self._update_bt_log(f"❌ Failed to forget. Error: {stderr.strip() or stdout.strip()}")

        # Refresh the list
        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")


    def disconnect_bt_device(self):
        selected_device, mac = self._get_selected_device_data(self.connected_bt_listbox)
        if not mac: return
        name = selected_device['name']
        
        self._clear_container(self.bt_status_listbox)
        self._update_bt_log(f"Attempting to disconnect {name}...")

        self._safe_thread_start(target=self._disconnect_bt_device_thread, args=(mac, name), panel_name="bluetooth")

    def _disconnect_bt_device_thread(self, mac, name):
        commands = f"disconnect {mac}\nexit\n"
        stdout, stderr, returncode = self._run_bluetoothctl_command(commands)

        if returncode == 0 and "successful" in stdout:
            self._update_bt_log(f"Successfully disconnected from {name}.")
        else:
            self._update_bt_log(f"Disconnect failed. Error: {stderr.strip() or stdout.strip()}")

        # Re-scan to update connection status
        self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")


    def refresh_bt_status(self):
        """Refreshes the Bluetooth adapter status and connected devices."""
        
        # 1. Update adapter status
        is_powered = self.get_adapter_powered()
        
        def update_gui():
            status_msg = f"Adapter Status: {'ON' if is_powered else 'OFF'}"
            self.bt_status_label.set_label(status_msg)
            self.bt_status_label.set_css_classes(['bold', 'lime-text'] if is_powered else ['bold', 'red-text'])
            self.toggle_bt_button.set_label("Turn Off" if is_powered else "Turn On")
            
        GLib.idle_add(update_gui)

        # 2. Update the connected devices list and scan if powered
        if is_powered:
            # Perform a quick update on connected devices
            self._safe_thread_start(target=self._update_connected_bt_list_thread, panel_name="bluetooth")
            # Initial scan if the list is empty (avoids re-scanning every 5s)
            if not self.bluetooth_listbox_devices:
                self._safe_thread_start(target=self._scan_devices_thread, panel_name="bluetooth")

        # 3. Schedule the next refresh
        if 'bluetooth_status' in self.refresh_jobs:
            GLib.source_remove(self.refresh_jobs['bluetooth_status'])
            
        self.refresh_jobs['bluetooth_status'] = GLib.timeout_add_seconds(5, self.refresh_bt_status)    
        return GLib.SOURCE_CONTINUE

    # --- AUDIO Backend Methods (pactl) ---
    
    def has_pactl(self):
        return os.path.exists("/usr/bin/pactl") or self._run_subprocess(["which", "pactl"])[2] == 0

    def _run_pactl(self, args):
        """Safely run pactl command."""
        if not self.has_pactl():
            return "", "pactl command not found. Is PulseAudio/PipeWire installed?", 127
        # Note: We do NOT use safe_thread_start here as this is a sync helper used *inside* other threads.
        return self._run_subprocess(["pactl"] + args, timeout=3)

    # REVERTED: Now returns a list of dictionaries with volume and mute status
    def get_output_devices(self):
        """Gets a list of output device data (sinks)."""
        stdout, _, returncode = self._run_pactl(["list", "sinks"])
        if returncode != 0: return []
        
        devices = []
        current_device = {}
        
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("Sink #"):
                if 'name' in current_device:
                    devices.append(current_device)
                current_device = {}
                
            elif line.startswith("Name:"):
                current_device['name'] = line.split(":", 1)[1].strip()
            
            elif line.startswith("Volume:"):
                # Try to find the percentage volume, default to 0
                match = re.search(r'/\s*(\d+)%', line)
                current_device['volume'] = int(match.group(1)) if match else 0

            elif line.startswith("Mute:"):
                current_device['muted'] = line.split(":", 1)[1].strip().lower() == "yes"

        # Handle the last device
        if 'name' in current_device:
            devices.append(current_device)
            
        return devices # list of dicts: [{'name': '...', 'volume': 0, 'muted': False}, ...]

    # REVERTED: Now returns a list of dictionaries with volume and mute status
    def get_input_devices(self):
        """Gets a list of input device data (sources)."""
        stdout, _, returncode = self._run_pactl(["list", "sources"])
        if returncode != 0: return []
        
        devices = []
        current_device = {}
        
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("Source #"):
                if 'name' in current_device:
                    devices.append(current_device)
                current_device = {}
                
            elif line.startswith("Name:"):
                current_device['name'] = line.split(":", 1)[1].strip()
            
            elif line.startswith("Volume:"):
                # Try to find the percentage volume, default to 0
                match = re.search(r'/\s*(\d+)%', line)
                current_device['volume'] = int(match.group(1)) if match else 0

            elif line.startswith("Mute:"):
                current_device['muted'] = line.split(":", 1)[1].strip().lower() == "yes"

        # Handle the last device
        if 'name' in current_device:
            devices.append(current_device)
            
        return devices # list of dicts

    def get_default_output(self):
        stdout, _, returncode = self._run_pactl(["get-default-sink"])
        return stdout if returncode == 0 else None

    def get_default_input(self):
        stdout, _, returncode = self._run_pactl(["get-default-source"])
        return stdout if returncode == 0 else None

    def set_default_device(self, device_name, is_output=True):
        command = ["set-default-sink", device_name] if is_output else ["set-default-source", device_name]
        self._run_pactl(command)
        # Manually refresh the status after setting default
        self._safe_thread_start(target=self._manual_refresh_thread, panel_name="audio")

    # REVERTED: Removed debounce logic, now calls pactl in a thread directly
    def set_volume(self, scale, device_name, is_output):
        """Sets the device volume in a background thread to prevent GUI freeze."""
        value = int(scale.get_value()) 
        command = ["set-sink-volume", device_name, f"{value}%"] if is_output else ["set-source-volume", device_name, f"{value}%"]
        # Run in a thread to prevent UI freeze
        self._safe_thread_start(target=lambda: self._run_pactl(command), panel_name="audio")


    def toggle_mute(self, button, device_name, is_output, mute=True):
        command = ["set-sink-mute", device_name, "1" if mute else "0"] if is_output else ["set-source-mute", device_name, "1" if mute else "0"]
        self._safe_thread_start(target=lambda: self._run_pactl(command), panel_name="audio")
    
    # REVERTED: Accepts initial_volume and is_muted parameters, sets initial value
    def _create_device_row(self, frame_box, device_name, is_output=True, initial_volume=0, is_muted=False):
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        container.set_margin_top(2)
        container.set_margin_bottom(2)
        container.set_margin_start(5)
        container.set_margin_end(5)

        # Label (Column 0)
        display_name = device_name.split(".")[-1].capitalize()
        label = Gtk.Label(label=display_name, xalign=0)
        label.set_margin_start(5) 
        container.append(label)

        # Slider (Column 1)
        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        slider.set_hexpand(True) 
        
        # Set initial value from pactl data
        slider.set_value(initial_volume)
        
        slider.connect("value-changed", lambda s: self.set_volume(s, device_name, is_output))
        container.append(slider)

        # Mute/Unmute Buttons (Column 2/3)
        btn_mute = Gtk.Button(label="Mute")
        btn_mute.connect("clicked", lambda x: self.toggle_mute(x, device_name, is_output, True))
        container.append(btn_mute)
        
        btn_unmute = Gtk.Button(label="Unmute")
        btn_unmute.connect("clicked", lambda x: self.toggle_mute(x, device_name, is_output, False))
        container.append(btn_unmute)

        # Set Default Button (Column 4)
        btn_default = Gtk.Button(label="Set Default")
        btn_default.connect("clicked", lambda x: self.set_default_device(device_name, is_output))
        container.append(btn_default)

        frame_box.append(container)
        
        # Store initial mute status for easy refresh check. Added is_muted to the tuple.
        self.device_widgets.append((slider, label, device_name, is_output, container, is_muted))
        return container

    # REVERTED: Now returns (name, index, volume)
    def get_app_list(self):
        """Parses detailed output of pactl list sink-inputs for (name, index, volume)."""
        stdout, _, returncode = self._run_pactl(["list", "sink-inputs"])
        if returncode != 0: return []
        
        apps = []
        current_app = {}
        
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("Sink Input #"):
                # Finalize the previous app
                if 'index' in current_app:
                    name = current_app.get('name') or f"App #{current_app['index']}"
                    volume = current_app.get('volume', 0)
                    apps.append( (name, current_app['index'], volume) )
                
                # Start the new app
                current_app = {
                    'index': line.split("#")[1].strip(),
                    'name': None,
                    'volume': 0
                }
            elif line.startswith("application.name = ") and current_app.get('name') is None:
                name = line.split("=",1)[1].strip().strip('"')
                current_app['name'] = name
                
            elif line.startswith("application.process.binary = ") and current_app.get('name') is None:
                name = line.split("=",1)[1].strip().strip('"')
                current_app['name'] = name.split("/")[-1]
            
            elif line.startswith("Volume:"):
                match = re.search(r'/\s*(\d+)%', line)
                current_app['volume'] = int(match.group(1)) if match else 0
                
        # Handle the last app in the list
        if 'index' in current_app:
             name = current_app.get('name') or f"App #{current_app['index']}" 
             volume = current_app.get('volume', 0)
             apps.append( (name, current_app['index'], volume) )

        return apps # Returns list of (name, index, volume)


    # REVERTED: Accepts initial_volume parameter, sets initial value
    def _create_app_row(self, frame_box, app_name, app_index, initial_volume=0):
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        container.set_css_classes(['status-box'])
        container.set_margin_top(2)
        container.set_margin_bottom(2)
        container.set_margin_start(5)
        container.set_margin_end(5)
        
        # Label (Column 0)
        label = Gtk.Label(label=app_name, xalign=0)
        label.set_css_classes(['cyan-text'])
        container.append(label)
        
        # Slider (Column 1)
        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        slider.set_hexpand(True) 
        
        # Set initial value from pactl data
        slider.set_value(initial_volume)
        
        # Slider connects to the simple threaded method
        slider.connect("value-changed", lambda s: self._set_app_volume_in_thread(s, app_index))
        container.append(slider)
        
        # Mute/Unmute Buttons (Column 2/3)
        btn_mute = Gtk.Button(label="Mute")
        btn_mute.connect("clicked", lambda x: self._toggle_app_mute(app_index, True))
        container.append(btn_mute)
        
        btn_unmute = Gtk.Button(label="Unmute")
        btn_unmute.connect("clicked", lambda x: self._toggle_app_mute(app_index, False))
        container.append(btn_unmute)

        frame_box.append(container)
        
        self.app_widgets.append((slider, app_name, app_index, container))
        return container
    
    # REVERTED: Removed debounce logic, now calls pactl in a thread directly
    def _set_app_volume_in_thread(self, scale, app_index):
        """Sets the app volume in a background thread to prevent GUI freeze."""
        value = int(scale.get_value())
        command = ["set-sink-input-volume", app_index, f"{value}%"]
        # Run in a thread to prevent UI freeze
        self._safe_thread_start(target=lambda: self._run_pactl(command), panel_name="audio")


    def _toggle_app_mute(self, app_index, mute=True):
        action = "1" if mute else "0"
        command = ["set-sink-input-mute", app_index, action]
        self._safe_thread_start(target=lambda: self._run_pactl(command), panel_name="audio")

    def refresh_all_sliders(self):
        current_default_out = self.get_default_output()
        current_default_in = self.get_default_input()
        
        # Sinks/Sources
        # The tuple is now (slider, label, name, is_output, container, is_muted)
        for i, (slider, label, name, is_output, container, is_muted) in enumerate(self.device_widgets):
            try:
                command_prefix = "sink" if is_output else "source"
                # Use pactl get-volume and get-mute separately for simplicity
                vol_info, _, _ = self._run_pactl([f"get-{command_prefix}-volume", name])
                mute_info, _, _ = self._run_pactl([f"get-{command_prefix}-mute", name])
                current_muted = mute_info.strip().lower() == "yes"
                
                is_default = (name == current_default_out) if is_output else (name == current_default_in)
                
                # Update slider value
                match = re.search(r'/\s*(\d+)%', vol_info)
                if match:
                    percent = int(match.group(1))
                    
                    # Only update the slider if the difference is significant or mute status changed
                    if abs(slider.get_value() - percent) > 5 or current_muted != is_muted:
                        # CRITICAL: Block signal handler to prevent recursive calls
                        handler_id = slider.handler_find(self.set_volume)
                        if handler_id:
                            slider.handler_block(handler_id)
                        
                        slider.set_value(percent)

                        if handler_id:
                            slider.handler_unblock(handler_id)

                # Update label color for default and muted status
                if current_muted:
                    label.set_css_classes(['bold', 'red-text'])
                elif is_default:
                    label.set_css_classes(['bold', 'lime-text'])
                else:
                    label.set_css_classes(['bold', 'white-text'])
                    
                # Store the updated mute status in the list of widgets
                self.device_widgets[i] = (slider, label, name, is_output, container, current_muted)


            except Exception:
                # Device probably disconnected, will be cleaned up on next full refresh
                pass
        
        # Check app volumes
        for slider, name, idx, container in self.app_widgets:
            try:
                # Use the volume setting command to get current status
                vol_info, _, _ = self._run_pactl(["get-sink-input-volume", idx])
                match = re.search(r'/\s*(\d+)%', vol_info)
                if match:
                    percent = int(match.group(1))
                    if abs(slider.get_value() - percent) > 5:
                        # CRITICAL: Apply signal blocking fix here as well
                        handler_id = slider.handler_find(self._set_app_volume_in_thread)
                        if handler_id:
                            slider.handler_block(handler_id)

                        slider.set_value(percent)
                        
                        if handler_id:
                            slider.handler_unblock(handler_id)
            except Exception:
                # App probably closed, will be cleaned up on next full refresh
                pass

        # 3. Schedule the next volume check in 1 second.
        if 'audio_devices' in self.refresh_jobs:
            GLib.source_remove(self.refresh_jobs['audio_devices'])
        self.refresh_jobs['audio_devices'] = GLib.timeout_add_seconds(1, self.refresh_all_sliders)
        
        # 4. Schedule a slower check for new/closed apps
        if 'audio_apps_scan' not in self.refresh_jobs:
             self.refresh_jobs['audio_apps_scan'] = GLib.timeout_add_seconds(3, self._check_for_new_apps)
             
        return GLib.SOURCE_CONTINUE
        
    def _check_for_new_apps(self):
        """Checks for new/closed apps and updates the list if necessary."""
        self._safe_thread_start(target=self._check_for_new_apps_thread, panel_name="audio")
        return GLib.SOURCE_CONTINUE
        
    def _update_app_list_delta(self, new_apps):
        """
        Updates the app volume list by adding/removing rows to prevent GUI flicker.
        new_apps is a list of (name, index, volume).
        """
        # Map of GUI widgets by index
        gui_widgets = {idx: (slider, name, idx, container) for slider, name, idx, container in self.app_widgets}
        gui_indices = set(gui_widgets.keys())
        
        # Map of new apps by index (new_app_map = {index: (name, index, volume)})
        new_app_map = {index: (name, index, volume) for name, index, volume in new_apps}
        new_indices = set(new_app_map.keys())

        # 1. Remove closed apps
        indices_to_remove = gui_indices - new_indices
        for idx in indices_to_remove:
            # The full tuple is needed to remove it from self.app_widgets
            widget_tuple = gui_widgets[idx]
            self.app_widgets.remove(widget_tuple) # Remove from app_widgets list
            widget_tuple[3].get_parent().remove(widget_tuple[3]) # Remove container from GUI

        # 2. Add new apps
        indices_to_add = new_indices - gui_indices
        for idx in indices_to_add:
            app_tuple = new_app_map[idx]
            name, _, volume = app_tuple 
            # _create_app_row now takes name, index, and initial_volume
            self._create_app_row(self.app_device_box, name, idx, volume) 

        # 3. Handle the 'No applications playing audio' label
        # Get rid of the dummy label if there are real apps now
        if new_apps and self.app_device_box.get_first_child() and \
           isinstance(self.app_device_box.get_first_child(), Gtk.Label) and \
           self.app_device_box.get_first_child().get_label() == "No applications playing audio":
            self._clear_container(self.app_device_box)

        # Add the dummy label if no apps are found and the box is empty
        if not new_apps and not self.app_device_box.get_first_child():
            self.app_device_box.append(Gtk.Label(label="No applications playing audio", css_classes=['white-text']))

    def _check_for_new_apps_thread(self):
        apps = self.get_app_list()
        
        # Check based on index only
        current_indices = {idx for _, _, idx, _ in self.app_widgets}
        new_indices = {idx for _, idx, _ in apps} # Get indices from the new list
        
        if current_indices != new_indices:
            GLib.idle_add(lambda: self._update_app_list_delta(apps))


    def _load_audio_panel_thread(self):
        """Runs all initial slow audio data gathering and schedules GUI updates."""
        
        if not self.has_pactl():
            # Create a label for error on the main thread
            GLib.idle_add(lambda: self.audio_page.append(Gtk.Label(label="PulseAudio control (pactl) not found. Cannot manage audio.", css_classes=['red-text'])))
            return

        # Data collection (slow part)
        outputs = self.get_output_devices() # list of dicts
        inputs = self.get_input_devices()   # list of dicts
        apps = self.get_app_list()          # list of (name, index, volume)
        
        # Schedule GUI updates and start refresh loops on the main thread
        GLib.idle_add(lambda: self._initial_audio_gui_setup(outputs, inputs, apps))

    def _initial_audio_gui_setup(self, outputs, inputs, apps):
        """Updates the GUI and starts the refresh loops on the main thread."""
        
        # 1. Clear and populate output/input devices (Full rebuild is appropriate here)
        self._clear_container(self.output_device_box)
        self._clear_container(self.input_device_box)
        self.device_widgets.clear()
        
        if outputs:
            for dev in outputs:
                # Calls the reverted _create_device_row (with volume/mute args)
                self._create_device_row(
                    self.output_device_box, 
                    dev['name'], 
                    is_output=True, 
                    initial_volume=dev.get('volume', 0), 
                    is_muted=dev.get('muted', False)
                )
        else:
            self.output_device_box.append(Gtk.Label(label="No output devices found.", css_classes=['white-text']))
            
        if inputs:
            for dev in inputs:
                # Calls the reverted _create_device_row (with volume/mute args)
                self._create_device_row(
                    self.input_device_box, 
                    dev['name'], 
                    is_output=False, 
                    initial_volume=dev.get('volume', 0),
                    is_muted=dev.get('muted', False)
                )
        else:
            self.input_device_box.append(Gtk.Label(label="No input devices found.", css_classes=['white-text']))

        # 2. Clear and populate app sliders (Uses delta update now)
        self._update_app_list_delta(apps)
        
        # 3. Start the continuous refresh loops
        self.refresh_all_sliders()


    def _manual_refresh_thread(self):
        """Thread target for the manual refresh button."""
        
        # 1. Gather all data (SLOW, runs in the background thread)
        outputs = self.get_output_devices()
        inputs = self.get_input_devices()
        apps = self.get_app_list()
        
        # 2. Schedule the GUI rebuild (FAST) on the main thread
        GLib.idle_add(lambda: self._initial_audio_gui_setup(outputs, inputs, apps))


    # --- UI Setup Methods ---

    def _setup_wifi_ui(self):
        """Sets up the WiFi Panel UI (with shrink fix)."""
        # 1. Available Networks Label
        label_networks = Gtk.Label(label="Available Networks:", xalign=0)
        label_networks.set_margin_start(20)
        label_networks.set_margin_bottom(5)
        self.wifi_page.append(label_networks)

        # 2. Network Listbox (Main expanding area)
        self.networks_scrolled_window = Gtk.ScrolledWindow()
        self.networks_scrolled_window.set_vexpand(True) # Stays True
        self.networks_scrolled_window.set_has_frame(True)
        self.networks_scrolled_window.set_margin_start(20)
        self.networks_scrolled_window.set_margin_end(20)

        self.wifi_networks_listbox = Gtk.ListBox()
        self.wifi_networks_listbox.set_css_classes(['network-list'])
        self.wifi_networks_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.networks_scrolled_window.set_child(self.wifi_networks_listbox)
        self.wifi_page.append(self.networks_scrolled_window)

        # 3. Password/Connect Row
        password_grid = Gtk.Grid()
        # FIX: Ensure the Grid doesn't take extra vertical space
        password_grid.set_vexpand(False) 
        password_grid.set_column_spacing(10)
        password_grid.set_margin_top(10)
        password_grid.set_margin_start(20)
        password_grid.set_margin_end(20)
        password_grid.set_hexpand(True)

        label_password = Gtk.Label(label="Password:", xalign=0)
        password_grid.attach(label_password, 0, 0, 1, 1)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.password_entry.set_css_classes(['entry-dark'])
        password_grid.attach(self.password_entry, 1, 0, 8, 1)

        btn_connect = Gtk.Button(label="Connect")
        btn_connect.connect("clicked", lambda x: self.do_connect()) 
        password_grid.attach(btn_connect, 9, 0, 1, 1)

        self.wifi_page.append(password_grid)

        # 4. Connected Networks Section
        label_connected = Gtk.Label(label="Active Connections (Select to Disconnect/Forget):", xalign=0)
        label_connected.set_margin_top(10)
        label_connected.set_margin_start(20)
        self.wifi_page.append(label_connected)

        connected_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # FIX: Ensure connected_box does not expand vertically
        connected_box.set_vexpand(False) 
        connected_box.set_margin_top(5)
        connected_box.set_margin_bottom(5)
        connected_box.set_margin_start(20)
        connected_box.set_margin_end(20)

        self.connected_networks_listbox = Gtk.ListBox()
        self.connected_networks_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Give it a minimal size hint to prevent it from collapsing entirely
        self.connected_networks_listbox.set_size_request(-1, 30) 
        self.connected_networks_listbox.set_hexpand(True)
        connected_box.append(self.connected_networks_listbox)

        self.disconnect_button = Gtk.Button(label="Disconnect")
        self.disconnect_button.set_sensitive(False)
        self.disconnect_button.connect("clicked", lambda x: self.disconnect_selected_wifi())
        connected_box.append(self.disconnect_button)

        self.forget_button = Gtk.Button(label="Forget")
        self.forget_button.set_sensitive(False)
        self.forget_button.connect("clicked", lambda x: self.forget_selected_connection())
        connected_box.append(self.forget_button)

        self.wifi_page.append(connected_box)

        # 5. Status Box (SPEEDTEST LOG)
        label_status = Gtk.Label(label="General Device Status / Speedtest Log:", xalign=0)
        label_status.set_margin_top(10)
        label_status.set_margin_start(20)
        self.wifi_page.append(label_status)

        status_scroll_win = Gtk.ScrolledWindow()
        # FIX: Explicitly set to not expand vertically
        status_scroll_win.set_vexpand(False) 
        # ✅ TALLER LOG BOX: 120 pixels confirmed
        status_scroll_win.set_size_request(-1, 120) 
        status_scroll_win.set_margin_top(5)
        status_scroll_win.set_margin_bottom(10)
        status_scroll_win.set_margin_start(20)
        status_scroll_win.set_margin_end(20)
        status_scroll_win.set_css_classes(['status-box'])

        self.status_text_view = Gtk.TextView()
        self.status_text_view.set_editable(False)
        self.status_text_view.get_buffer().set_text("Initial status message...")
        status_scroll_win.set_child(self.status_text_view)

        self.wifi_page.append(status_scroll_win)

        # 6. Bottom Button Row
        button_box_bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        # FIX: Ensure this bottom row doesn't expand vertically
        button_box_bottom.set_vexpand(False) 
        button_box_bottom.set_margin_start(20)
        button_box_bottom.set_margin_end(20)
        button_box_bottom.set_margin_bottom(20)

        self.wifi_toggle_button = Gtk.Button(label="Wi-Fi: ...")
        self.wifi_toggle_button.set_hexpand(True)
        self.wifi_toggle_button.connect("clicked", lambda x: self.toggle_wifi_radio()) 
        button_box_bottom.append(self.wifi_toggle_button)

        btn_scan = Gtk.Button(label="Scan for Networks")
        btn_scan.set_hexpand(True)
        btn_scan.connect("clicked", lambda x: self.perform_wifi_scan())
        button_box_bottom.append(btn_scan)

        btn_refresh = Gtk.Button(label="Refresh Status")
        btn_refresh.set_hexpand(True)
        btn_refresh.connect("clicked", lambda x: self.refresh_status())
        button_box_bottom.append(btn_refresh)

        self.speedtest_button = Gtk.Button(label="Run Speedtest")
        self.speedtest_button.set_hexpand(True)
        # This calls the method that uses the safe wrapper
        self.speedtest_button.connect("clicked", lambda x: self.run_speedtest_thread()) 
        button_box_bottom.append(self.speedtest_button)

        self.wifi_page.append(button_box_bottom)

    def _setup_bluetooth_ui(self):
        """Sets up the Bluetooth Panel UI (with shrink fix)."""
        # 1. Top Status (ON/OFF)
        bt_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # FIX: Ensure this status box does not expand vertically
        bt_status_box.set_vexpand(False) 
        bt_status_box.set_margin_top(10)
        bt_status_box.set_margin_start(20)
        bt_status_box.set_margin_end(20)
        self.bluetooth_page.append(bt_status_box)

        self.bt_status_label = Gtk.Label(label="Adapter Status: Checking...", xalign=0)
        self.bt_status_label.set_css_classes(['bold', 'yellow-text'])
        self.bt_status_label.set_hexpand(True)
        bt_status_box.append(self.bt_status_label)

        self.toggle_bt_button = Gtk.Button(label="Toggle")
        self.toggle_bt_button.connect("clicked", lambda x: self.toggle_adapter())
        self.toggle_bt_button.set_size_request(100, -1)
        bt_status_box.append(self.toggle_bt_button)

        # 2. Connected Devices List
        label_connected = Gtk.Label(label="Currently Connected Devices:", xalign=0)
        label_connected.set_margin_top(10)
        label_connected.set_margin_start(20)
        self.bluetooth_page.append(label_connected)

        connected_bt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # FIX: Ensure connected_bt_box does not expand vertically
        connected_bt_box.set_vexpand(False) 
        connected_bt_box.set_margin_top(5)
        connected_bt_box.set_margin_bottom(5)
        connected_bt_box.set_margin_start(20)
        connected_bt_box.set_margin_end(20)
        self.bluetooth_page.append(connected_bt_box)

        self.connected_bt_listbox = Gtk.ListBox()
        self.connected_bt_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.connected_bt_listbox.set_size_request(-1, 60) 
        self.connected_bt_listbox.set_hexpand(True) 
        connected_bt_box.append(self.connected_bt_listbox)

        btn_disconnect_bt = Gtk.Button(label="Disconnect Selected")
        btn_disconnect_bt.connect("clicked", lambda x: self.disconnect_bt_device())
        connected_bt_box.append(btn_disconnect_bt)

        # 3. Discovered/Paired Devices List (Main expanding area)
        label_discovered = Gtk.Label(label="Available/Paired Devices (Click 'Scan Devices' below to discover):", xalign=0)
        label_discovered.set_margin_top(10)
        label_discovered.set_margin_start(20)
        self.bluetooth_page.append(label_discovered)

        bt_scroll_container = Gtk.ScrolledWindow()
        bt_scroll_container.set_vexpand(True) # Stays True
        bt_scroll_container.set_has_frame(True)
        bt_scroll_container.set_margin_start(20)
        bt_scroll_container.set_margin_end(20)
        self.bluetooth_page.append(bt_scroll_container)

        self.bluetooth_listbox = Gtk.ListBox()
        self.bluetooth_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        bt_scroll_container.set_child(self.bluetooth_listbox)

        # 4. Action Buttons Row
        bt_button_frame = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # FIX: Ensure this button row does not expand vertically
        bt_button_frame.set_vexpand(False) 
        bt_button_frame.set_margin_top(10)
        bt_button_frame.set_margin_start(20)
        bt_button_frame.set_margin_end(20)
        self.bluetooth_page.append(bt_button_frame)

        def add_bt_button(label, command):
            btn = Gtk.Button(label=label)
            btn.set_hexpand(True)
            btn.connect("clicked", command)
            bt_button_frame.append(btn)

        add_bt_button("Pair Selected", lambda x: self.pair_bt_device())
        add_bt_button("Connect Selected", lambda x: self.connect_bt_device())
        add_bt_button("Trust Selected", lambda x: self.trust_bt_device())
        add_bt_button("Forget Selected", lambda x: self.forget_bt_device())
        add_bt_button("Scan Devices", lambda x: self.scan_bt_devices())
        add_bt_button("Refresh Status", lambda x: self.refresh_bt_status())

        # 5. Bluetooth status log
        label_log = Gtk.Label(label="Bluetooth Log/Errors:", xalign=0)
        label_log.set_margin_top(10)
        label_log.set_margin_start(20)
        self.bluetooth_page.append(label_log)

        bt_log_scroll = Gtk.ScrolledWindow()
        # FIX: Explicitly set to not expand vertically
        bt_log_scroll.set_vexpand(False) 
        bt_log_scroll.set_size_request(-1, 80) 
        bt_log_scroll.set_margin_top(5)
        bt_log_scroll.set_margin_bottom(20)
        bt_log_scroll.set_margin_start(20)
        bt_log_scroll.set_margin_end(20)
        self.bluetooth_page.append(bt_log_scroll)

        self.bt_status_listbox = Gtk.ListBox()
        self.bt_status_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        bt_log_scroll.set_child(self.bt_status_listbox)
    
    def _setup_audio_ui(self):
        """Sets up the Audio Panel UI (with devices non-scrolling fix)."""

        # --- 1. Output Devices (Sinks) ---
        label_output = Gtk.Label(label="Output Devices (Sinks):", xalign=0)
        label_output.set_margin_top(10)
        label_output.set_margin_start(20)
        self.audio_page.append(label_output)

        # NEW: Container for Output Devices (replaces the scrolled window)
        output_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        output_container.set_vexpand(False) # CRITICAL: Only takes natural height
        output_container.set_css_classes(['status-box']) # Add a border/frame look
        output_container.set_margin_start(20)
        output_container.set_margin_end(20)
        output_container.set_margin_bottom(5)
        
        # This Gtk.Box receives the dynamic row widgets
        self.output_device_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.output_device_box.set_margin_top(5) # Add padding inside the box
        self.output_device_box.set_margin_bottom(5)
        
        output_container.append(self.output_device_box)
        self.audio_page.append(output_container)


        # --- 2. Input Devices (Sources) ---
        label_input = Gtk.Label(label="Input Devices (Sources):", xalign=0)
        label_input.set_margin_top(10)
        label_input.set_margin_start(20)
        self.audio_page.append(label_input)

        # NEW: Container for Input Devices (replaces the scrolled window)
        input_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        input_container.set_vexpand(False) # CRITICAL: Only takes natural height
        input_container.set_css_classes(['status-box']) 
        input_container.set_margin_start(20)
        input_container.set_margin_end(20)
        input_container.set_margin_bottom(5)

        # This Gtk.Box receives the dynamic row widgets
        self.input_device_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.input_device_box.set_margin_top(5) # Add padding inside the box
        self.input_device_box.set_margin_bottom(5)
        
        input_container.append(self.input_device_box)
        self.audio_page.append(input_container)

        # --- 3. Application Volumes (Main expanding area) ---
        label_app = Gtk.Label(label="Application Volumes:", xalign=0)
        label_app.set_margin_top(10)
        label_app.set_margin_start(20)
        self.audio_page.append(label_app)

        app_scroll_win = Gtk.ScrolledWindow()
        app_scroll_win.set_vexpand(True) # This is crucial: Takes up all *remaining* vertical space
        app_scroll_win.set_margin_start(20)
        app_scroll_win.set_margin_end(20)
        app_scroll_win.set_margin_bottom(5)
        self.audio_page.append(app_scroll_win)

        # This Gtk.Box is the target where dynamic app widgets will be added
        self.app_device_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        app_scroll_win.set_child(self.app_device_box)

        # --- 4. Refresh Button ---
        btn_refresh_audio = Gtk.Button(label="Refresh Devices & Apps")
        btn_refresh_audio.set_margin_top(5)
        btn_refresh_audio.set_margin_bottom(10)
        btn_refresh_audio.set_halign(Gtk.Align.CENTER) # Centers the button
        # NOTE: The command is adapted to start a thread inside the class instance
        btn_refresh_audio.connect(
            "clicked", 
            lambda x: self._safe_thread_start(target=self._manual_refresh_thread, panel_name="audio")
        )
        self.audio_page.append(btn_refresh_audio)
        
# --- Application Start ---
if __name__ == "__main__":
    # If using the GTK 4 approach, the final line to run the app is simpler
    app = ConnectionCentreApp()
    # Sys.exit ensures the process returns the application's exit code
    sys.exit(app.run(sys.argv))
