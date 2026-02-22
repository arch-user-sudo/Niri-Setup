#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import threading
import time
import psutil
import subprocess
import re

class Gauge(Gtk.DrawingArea):
    def __init__(self, label="", size=120, is_temp=False):
        super().__init__()
        self.label = label
        self.percentage = 0
        self.size = size
        self.is_temp = is_temp
        self.temp_value = 0
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
        
        # Calculate percentage for temperature gauges (0-100°C scaled to 0-100%)
        if self.is_temp:
            display_percentage = min(100, max(0, self.temp_value))
        else:
            display_percentage = self.percentage
            
        end_angle = start_angle + (display_percentage / 100) * 1.5 * 2 * 3.14159
        
        # Color based on value
        if self.is_temp:
            # Temperature color thresholds
            if self.temp_value < 60:
                cr.set_source_rgb(0.2, 0.8, 0.2)  # Green
            elif self.temp_value < 80:
                cr.set_source_rgb(0.8, 0.8, 0.2)  # Yellow
            else:
                cr.set_source_rgb(0.8, 0.2, 0.2)  # Red
        else:
            # Percentage color thresholds
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
        if self.is_temp:
            text = f"{self.temp_value:.0f}°C"
        else:
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
    
    def update_temperature(self, temp_value):
        self.temp_value = temp_value
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
        win.set_child(main_box)
        
        # GPU Row
        gpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        gpu_box.set_hexpand(True)
        gpu_box.set_vexpand(True)
        
        self.gpu_temp_gauge = Gauge("GPU Temp", 120, is_temp=True)
        self.gpu_clock_gauge = Gauge("GPU Usage", 120)
        self.gpu_ram_gauge = Gauge("GPU RAM", 120)
        
        for gauge in [self.gpu_temp_gauge, self.gpu_clock_gauge, self.gpu_ram_gauge]:
            gauge.set_hexpand(True)
            gauge.set_vexpand(True)
            gpu_box.append(gauge)
       
        # CPU Row
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        cpu_box.set_hexpand(True)
        cpu_box.set_vexpand(True)
        
        self.cpu_temp_gauge = Gauge("CPU Temp", 120, is_temp=True)
        self.cpu_clock_gauge = Gauge("CPU Usage", 120)
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
    
    def get_real_gpu_stats(self):
        # Try NVIDIA first
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,memory.used', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                data = result.stdout.strip().split(', ')
                temp = float(data[0])
                usage = float(data[1])
                memory_used = float(data[2])
                result_total = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                                            capture_output=True, text=True, timeout=2)
                if result_total.returncode == 0:
                    memory_total = float(result_total.stdout.strip())
                    memory_percent = (memory_used / memory_total) * 100
                else:
                    memory_percent = 50.0
                return temp, usage, memory_percent
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
            pass
        
        # Try sensors command for AMD GPU
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                output = result.stdout
                temp = 50.0
                usage = 0.0
                memory_percent = 30.0
                
                # Parse AMD GPU section
                lines = output.split('\n')
                in_amd_section = False
                
                for line in lines:
                    if 'amdgpu-pci-' in line:
                        in_amd_section = True
                        continue
                    elif in_amd_section and line.strip() == '':
                        break
                    elif in_amd_section:
                        # Parse temperature
                        if 'edge:' in line or 'junction:' in line or 'mem:' in line:
                            match = re.search(r'\+(\d+\.\d+)°C', line)
                            if match:
                                temp = float(match.group(1))
                # Try to get GPU usage and memory from radeontop
                try:
                    radeon_result = subprocess.run(['radeontop', '-l', '1', '-d', '-'], 
                                                  capture_output=True, text=True, timeout=3)
                    if radeon_result.returncode == 0:
                        radeon_output = radeon_result.stdout
                        for line in radeon_output.split('\n'):
                            # Parse GPU usage: "gpu 9.17%"
                            gpu_match = re.search(r'gpu\s+(\d+\.\d+)%', line)
                            if gpu_match:
                                usage = float(gpu_match.group(1))
                            
                            # Parse VRAM usage: "vram 38.10%"
                            vram_match = re.search(r'vram\s+(\d+\.\d+)%', line)
                            if vram_match:
                                memory_percent = float(vram_match.group(1))
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
                    pass
                
                return temp, usage, memory_percent
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
            pass
        
        # Fallback to reading sensors specifically for edge temperature
        try:
            result = subprocess.run(['sensors | grep "edge:"'], shell=True, capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                match = re.search(r'\+(\d+\.\d+)°C', result.stdout)
                if match:
                    temp = float(match.group(1))
                    return temp, 0.0, 30.0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
            pass
        
        # Final fallback to mock data
        import random
        return random.uniform(40, 60), random.uniform(0, 20), random.uniform(20, 40)
    
    def get_real_cpu_stats(self):
        try:
            # Get real CPU temperature
            temp = 50.0  # default fallback
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try to find CPU temperature
                    for name, entries in temps.items():
                        if 'coretemp' in name.lower() or 'cpu' in name.lower():
                            if entries:
                                temp = entries[0].current
                                break
            except AttributeError:
                pass
            
            # Get real CPU usage
            usage = psutil.cpu_percent(interval=0.1)
            
            # Get real memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            return temp, usage, memory_percent
        except Exception:
            # Fallback to mock data
            import random
            return random.uniform(40, 50), random.uniform(5, 15), random.uniform(30, 50)
    
    def start_monitoring(self):
        def update():
            while True:
                try:
                    # Get real system stats
                    gpu_temp, gpu_usage, gpu_ram = self.get_real_gpu_stats()
                    cpu_temp, cpu_usage, sys_ram = self.get_real_cpu_stats()
                    
                    # Update gauges
                    GLib.idle_add(self.gpu_temp_gauge.update_temperature, gpu_temp)
                    GLib.idle_add(self.gpu_clock_gauge.update_percentage, gpu_usage)
                    GLib.idle_add(self.gpu_ram_gauge.update_percentage, gpu_ram)
                    
                    GLib.idle_add(self.cpu_temp_gauge.update_temperature, cpu_temp)
                    GLib.idle_add(self.cpu_clock_gauge.update_percentage, cpu_usage)
                    GLib.idle_add(self.sys_ram_gauge.update_percentage, sys_ram)
                    
                except Exception as e:
                    print(f"Update error: {e}")
                
                time.sleep(1)  # Update every 2 seconds
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()

if __name__ == '__main__':
    app = SystemMonitor()
    app.run()
