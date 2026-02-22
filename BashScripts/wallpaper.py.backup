#!/usr/bin/env python3
import os
import subprocess
import threading
import time
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib

class WallpaperPicker(Gtk.Window):
    def __init__(self):
        super().__init__(title="Wallpaper Browser")
        self.set_default_size(900, 600)
        self.set_border_width(12)

        # Main Layout Container
        self.overlay = Gtk.Overlay()
        self.add(self.overlay)

        # The Content Layer (Scrollable Grid)
        self.scroll = Gtk.ScrolledWindow()
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(6)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scroll.add(self.flowbox)
        self.overlay.add(self.scroll)

        # The Loading Layer (Animated Progress Bar)
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.loading_box.set_valign(Gtk.Align.CENTER)
        self.loading_box.set_halign(Gtk.Align.CENTER)
        
        self.progress = Gtk.ProgressBar()
        self.progress.set_size_request(300, 20)
        self.loading_box.pack_start(self.progress, False, False, 0)
        
        self.label = Gtk.Label(label="Scanning directory...")
        self.loading_box.pack_start(self.label, False, False, 0)
        
        self.overlay.add_overlay(self.loading_box)
        
        # Start the "Pulse" animation for the progress bar
        self.is_loading = True
        GLib.timeout_add(50, self.animate_loading)

        self.show_all()

        # Start the async background loader
        threading.Thread(target=self.load_wallpapers_async, daemon=True).start()

    def animate_loading(self):
        """Makes the progress bar block slide back and forth"""
        if self.is_loading:
            self.progress.pulse()
            return True 
        return False 

    def load_wallpapers_async(self):
        """Scans CWD and loads thumbnails efficiently"""
        cwd = os.getcwd()
        valid_exts = (".png", ".jpg", ".jpeg", ".webp")
        
        try:
            files = [f for f in os.listdir(cwd) if f.lower().endswith(valid_exts)]
        except Exception as e:
            print(f"Error reading directory: {e}")
            files = []
        
        for filename in files:
            filepath = os.path.join(cwd, filename)
            try:
                # Small sleep to keep the UI thread responsive for the animation
                time.sleep(0.01) 
                
                # OPTIMIZED: Loads directly to size for speed and low RAM usage
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filepath, 180, 110)
                
                # Push the UI update to the main thread
                GLib.idle_add(self.add_wallpaper_to_ui, filepath, filename, pixbuf)
            except Exception as e:
                print(f"Skipping {filename}: {e}")

        # Hide loading overlay when done
        GLib.idle_add(self.stop_loading)

    def add_wallpaper_to_ui(self, filepath, filename, pixbuf):
        """Creates the visual button for each image"""
        button = Gtk.Button()
        button.connect("clicked", self.on_click, filepath)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        
        # Clean up the label: truncate long names
        display_name = filename if len(filename) < 20 else filename[:17] + "..."
        label = Gtk.Label(label=display_name)
        
        box.pack_start(image, True, True, 0)
        box.pack_start(label, False, False, 0)
        
        button.add(box)
        self.flowbox.add(button)
        button.show_all()
        return False

    def stop_loading(self):
        """Removes the loading bar from view"""
        self.is_loading = False
        self.loading_box.hide()
        return False

    def on_click(self, button, filepath):
        """The command sequence you requested"""
        # pkill wbg & nohup wbg -s $wallpaper
        cmd = f"pkill wbg; nohup wbg -s '{filepath}' > /dev/null 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        print(f"Applied wallpaper: {filepath}")

if __name__ == "__main__":
    win = WallpaperPicker()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
