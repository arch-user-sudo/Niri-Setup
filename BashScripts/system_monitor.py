#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import subprocess
import re
import psutil
import threading

class Gauge(Gtk.DrawingArea):
    def __init__(self, label="", size=120):
        super().__init__()
        self.label = label
        self.percentage = 0
        self.size = size
        self.set_size_request(size, size)
        self.set_draw_func(self.draw)
        
    def draw(self, area, cr, width, height):
        # Center coordinates
        cx, cy = width // 2, height // 2
        radius = min(width, height) // 2 - 10
        
        # Background circle
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.arc(cx, cy, radius, 0, 2 * 3.14159)
        cr.set_line_width(8)
        cr.stroke()
        
        # Progress arc (from bottom to current percentage)
        start_angle = 0.75 * 2 * 3.14159  # Start at bottom
        end_angle = start_angle + (self.percentage / 100) * 1.5 * 2 * 3.14159
        
        # Color based on percentage
        if self.percentage < 50:
            cr.set_source_rgb(0.2, 0.8, 0.2)  # Green
        elif self.percentage < 80:
            cr.set_source_rgb(0.8, 0.8, 0.2)  # Yellow
        else:
            cr.set_source_rgb(0.8, 0.2, 0.2)  # Red
            
        cr.arc(cx, cy, radius, start_angle, end_angle)
        cr.set_line_width(8)
        cr.stroke()
        
        # Center text
        cr.set_source_rgb(1, 1, 1)
        text = f"{self.percentage:.0f}%"
        cr.select_font_face("Arial")
        cr.set_font_size(14)
        text_extents = cr.text_extents(text)
        cr.move_to(cx - text_extents.width // 2, cy + 5)
        cr.show_text(text)
        
        # Label text
        if self.label:
            cr.set_font_size(10)
            label_extents = cr.text_extents(self.label)
            cr.move_to(cx - label_extents.width // 2, cy + 20)
            cr.show_text(self.label)
    
    def update_percentage(self, value):
        self.percentage = max(0, min(100, value))
        self.queue_draw()

class SystemMonitor(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("System Monitor")
        self.set_default_size(800, 400)
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        self.set_content(main_box)
        
        # GPU Row
        gpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        gpu_box.set_hexpand(True)
        gpu_box.set_vexpand(True)
        
        self.gpu_temp_gauge = Gauge("GPU Temp", 120)
        self.gpu_clock_gauge = Gauge("GPU Clock", 120)
        self.gpu_ram_gauge = Gauge("GPU RAM", 120)
        
        for gauge in [self.gpu_temp_gauge, self.gpu_clock_gauge, self.gpu_ram_gauge]:
            gauge.set_hexpand(True)
            gauge.set_vexpand(True)
            gpu_box.append(gauge)
        
        # CPU Row
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        cpu_box.set_hexpand(True)
        cpu_box.set_vexpand(True)
        
        self.cpu_temp_gauge = Gauge("CPU Temp", 120)
        self.cpu_clock_gauge = Gauge("CPU Clock", 120)
        self.sys_ram_gauge = Gauge("System RAM", 120)
        
        for gauge in [self.cpu_temp_gauge, self.cpu_clock_gauge, self.sys_ram_gauge]:
            gauge.set_hexpand(True)
            gauge.set_vexpand(True)
            cpu_box.append(gauge)
        
        # Add rows to main box
        main_box.append(gpu_box)
        main_box.append(cpu_box)
        
        # Start monitoring
        self.update_stats()
        
    def get_gpu_stats(self):
        try:
            # Try nvidia-smi first
            result = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu,clock.sm,memory.used,memory.total', 
                                   '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                parts = result.stdout.strip().split(', ')
                temp = float(parts[0])
                clock = float(parts[1]) / 2000  # Normalize to percentage (assuming max 2000MHz)
                mem_used = float(parts[2])
                mem_total = float(parts[3])
                ram_percent = (mem_used / mem_total) * 100
                return temp, clock, ram_percent
        except:
            pass
            
        return 0, 0, 0
    
    def get_cpu_stats(self):
        try:
            # CPU temperature
            temp = 0
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if 'core' in name.lower() or 'cpu' in name.lower():
                            if entries:
                                temp = entries[0].current
                                break
            except:
                temp = 0
            
            # CPU clock (approximate based on load)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            clock = cpu_percent  # Use CPU usage as proxy for clock speed percentage
            
            # System RAM
            memory = psutil.virtual_memory()
            ram_percent = memory.percent
            
            return temp, clock, ram_percent
        except:
            return 0, 0, 0
    
    def update_stats(self):
        def update():
            while True:
                try:
                    # Get stats
                    gpu_temp, gpu_clock, gpu_ram = self.get_gpu_stats()
                    cpu_temp, cpu_clock, sys_ram = self.get_cpu_stats()
                    
                    # Update gauges
                    GLib.idle_add(self.gpu_temp_gauge.update_percentage, gpu_temp)
                    GLib.idle_add(self.gpu_clock_gauge.update_percentage, gpu_clock)
                    GLib.idle_add(self.gpu_ram_gauge.update_percentage, gpu_ram)
                    
                    GLib.idle_add(self.cpu_temp_gauge.update_percentage, cpu_temp)
                    GLib.idle_add(self.cpu_clock_gauge.update_percentage, cpu_clock)
                    GLib.idle_add(self.sys_ram_gauge.update_percentage, sys_ram)
                    
                except Exception as e:
                    print(f"Update error: {e}")
                
                threading.Event().wait(2)  # Update every 2 seconds
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()

class MyApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.systemmonitor')
        
    def do_activate(self):
        win = SystemMonitor(application=self)
        win.present()

if __name__ == '__main__':
    app = MyApp()
    app.run()