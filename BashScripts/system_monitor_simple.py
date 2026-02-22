#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Cairo
import threading
import time

class Gauge(Gtk.DrawingArea):
    def __init__(self, label="", size=120):
        super().__init__()
        self.label = label
        self.percentage = 0
        self.size = size
        self.set_size_request(size, size)
        
    def do_snapshot(self, snapshot):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        ctx = snapshot.append_cairo(Cairo.Context(snapshot.get_target()))
        
        # Center coordinates
        cx, cy = width // 2, height // 2
        radius = min(width, height) // 2 - 10
        
        # Background circle
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.arc(cx, cy, radius, 0, 2 * 3.14159)
        ctx.set_line_width(8)
        ctx.stroke()
        
        # Progress arc (from bottom to current percentage)
        start_angle = 0.75 * 2 * 3.14159  # Start at bottom
        end_angle = start_angle + (self.percentage / 100) * 1.5 * 2 * 3.14159
        
        # Color based on percentage
        if self.percentage < 50:
            ctx.set_source_rgb(0.2, 0.8, 0.2)  # Green
        elif self.percentage < 80:
            ctx.set_source_rgb(0.8, 0.8, 0.2)  # Yellow
        else:
            ctx.set_source_rgb(0.8, 0.2, 0.2)  # Red
            
        ctx.arc(cx, cy, radius, start_angle, end_angle)
        ctx.set_line_width(8)
        ctx.stroke()
        
        # Center text
        ctx.set_source_rgb(1, 1, 1)
        text = f"{self.percentage:.0f}%"
        ctx.select_font_face("Arial", Cairo.FontSlant.NORMAL, Cairo.FontWeight_NORMAL)
        ctx.set_font_size(14)
        text_extents = ctx.text_extents(text)
        ctx.move_to(cx - text_extents.width // 2, cy + 5)
        ctx.show_text(text)
        
        # Label text
        if self.label:
            ctx.set_font_size(10)
            label_extents = ctx.text_extents(self.label)
            ctx.move_to(cx - label_extents.width // 2, cy + 20)
            ctx.show_text(self.label)
    
    def update_percentage(self, value):
        self.percentage = max(0, min(100, value))
        self.queue_draw()

class SystemMonitor(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.systemmonitor')
        
    def do_activate(self):
        # Create main window
        win = Gtk.ApplicationWindow(application=self)
        win.set_title("System Monitor")
        win.set_default_size(800, 400)
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        win.set_content(main_box)
        
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
        
        win.present()
        
        # Start monitoring
        self.start_monitoring()
    
    def get_mock_gpu_stats(self):
        # Mock GPU stats for testing
        import random
        return random.uniform(60, 85), random.uniform(30, 90), random.uniform(40, 80)
    
    def get_mock_cpu_stats(self):
        # Mock CPU stats for testing
        import random
        return random.uniform(45, 75), random.uniform(20, 85), random.uniform(30, 70)
    
    def start_monitoring(self):
        def update():
            while True:
                try:
                    # Get mock stats for now
                    gpu_temp, gpu_clock, gpu_ram = self.get_mock_gpu_stats()
                    cpu_temp, cpu_clock, sys_ram = self.get_mock_cpu_stats()
                    
                    # Update gauges
                    GLib.idle_add(self.gpu_temp_gauge.update_percentage, gpu_temp)
                    GLib.idle_add(self.gpu_clock_gauge.update_percentage, gpu_clock)
                    GLib.idle_add(self.gpu_ram_gauge.update_percentage, gpu_ram)
                    
                    GLib.idle_add(self.cpu_temp_gauge.update_percentage, cpu_temp)
                    GLib.idle_add(self.cpu_clock_gauge.update_percentage, cpu_clock)
                    GLib.idle_add(self.sys_ram_gauge.update_percentage, sys_ram)
                    
                except Exception as e:
                    print(f"Update error: {e}")
                
                time.sleep(2)  # Update every 2 seconds
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()

if __name__ == '__main__':
    app = SystemMonitor()
    app.run()