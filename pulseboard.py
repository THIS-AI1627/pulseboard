#!/usr/bin/env python3
"""
PulseBoard — Real-Time System Monitor TUI
A beautiful, animated terminal dashboard for system monitoring.
Single file, zero dependencies (stdlib only), cross-platform.

Run:  python pulseboard.py
Exit: Q / Esc  |  Theme: T  |  Refresh: R  |  Scroll: ↑↓ or J/K
"""

import sys
import os
import time
import signal
import curses
import threading
import queue
from datetime import datetime
from collections import defaultdict

# ─── Platform Detection ───────────────────────────────────────────────────────

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS   = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

# ─── Theme Definitions ─────────────────────────────────────────────────────────

class Theme:
    def __init__(self, name, bg, panel, border, text, dim,
                 cpu, mem, disk, net_up, net_dn, temp, alert, accent):
        self.name   = name
        self.bg     = bg      # curses color number
        self.panel  = panel
        self.border = border
        self.text   = text
        self.dim    = dim
        self.cpu    = cpu
        self.mem    = mem
        self.disk   = disk
        self.net_up = net_up
        self.net_dn = net_dn
        self.temp   = temp
        self.alert  = alert
        self.accent = accent

THEMES = [
    Theme("Cyberpunk",  # cyan + violet cyberpunk
          0, 236, 235, 250, 245, 51, 183, 226, 82, 45, 208, 203, 51),
    Theme("Monokai",    # monokai pink + green + orange
          0, 234, 240, 223, 245, 211, 166, 76, 79, 139, 208, 203, 197),
    Theme("Dracula",    # dracula purple + pink + cyan
          0, 52, 54, 250, 117, 198, 140, 211, 40, 50, 208, 203, 212),
    Theme("Nord",       # nord cool blue + white
          0, 58, 59, 231, 145, 38, 140, 146, 72, 146, 139, 203, 68),
    Theme("Solarized",  # solarized dark green + yellow
          0, 234, 240, 244, 136, 44, 133, 181, 147, 37, 181, 160, 133),
]

# ─── Color-pair registry ──────────────────────────────────────────────────────
# Color pair layout:
#   0          = default (white on black)
#   1          = panel background
#   2          = gauge green  (0-49%)
#   3          = gauge yellow (50-74%)
#   4          = gauge red    (75-100%)
#   5/6/7/8/9  = cpu/mem/disk/net_up/net_dn
#   10         = temp
#   11         = alert
#   12         = accent
#   13         = dim text
_color_pairs = {}   # {(fg,bg): pair_index}


def _mk_color(fg, bg):
    """Return or create a curses color pair for (fg, bg)."""
    key = (fg, bg)
    if key not in _color_pairs:
        n = len(_color_pairs) + 1
        curses.init_pair(n, fg, bg)
        _color_pairs[key] = n
    return curses.color_pair(_color_pairs[key])


def _pct_attrs(pct):
    """Return attrs for a gauge color based on percentage."""
    if pct < 50:
        return _mk_color(THEME.cpu, THEME.bg) if False else _mk_color(51, 0)
    elif pct < 75:
        return _mk_color(220, 0)
    else:
        return _mk_color(196, 0)


THEME = THEMES[0]   # default theme; updated by _apply_theme


def _apply_theme(t):
    """Apply a Theme's curses color palette."""
    global THEME
    THEME = t
    try:
        curses.init_color(0, 0, 0, 0)          # black
        curses.init_color(51, 0, 255, 218)    # cyan  (#00ffdA)
        curses.init_color(183, 167, 139, 250)  # violet
        curses.init_color(226, 255, 187, 71)   # amber
        curses.init_color(82, 52, 211, 153)    # green
        curses.init_color(45, 96, 165, 250)    # blue
        curses.init_color(208, 251, 146, 60)  # orange
        curses.init_color(203, 255, 107, 107)  # red
        curses.init_color(51, 0, 255, 218)     # accent = cyan
        curses.init_color(235, 39, 46, 50)     # panel dark
        curses.init_color(236, 22, 30, 40)     # border dark
        curses.init_color(250, 179, 194, 212)  # text
        curses.init_color(245, 92, 111, 130)  # dim
        curses.init_color(197, 203, 212, 197)  # light panel
    except curses.error:
        pass   # terminal may not support custom colors — fall back gracefully

# ─── Formatting helpers ───────────────────────────────────────────────────────

def _fmt_bytes(b):
    if b is None or b < 0:
        return "N/A"
    for unit, label in [(1024**4, "TB"), (1024**3, "GB"), (1024**2, "MB"), (1024, "KB")]:
        if b >= unit:
            return f"{b / unit:.1f} {label}"
    return f"{b} B"


def _fmt_speed(bps):
    if bps is None or bps <= 0:
        return "0 B/s"
    for unit, label in [(1024**2, "MB/s"), (1024, "KB/s")]:
        if bps >= unit:
            return f"{bps / unit:.1f} {label}"
    return f"{bps:.0f} B/s"


def _bar(pct, width=20):
    """Return a text gauge bar string (█ ▓ ▒ ░)."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * width))
    empty = width - filled
    # Use smooth gradient blocks
    bar = "█" * filled
    if empty > 0:
        bar += "░" * empty
    return bar


def _trunc(s, width):
    s = str(s)
    return s[:width].ljust(width)


# ─── Process list (psutil-free) ──────────────────────────────────────────────

def _read_processes():
    """Return list of (pid, name, cpu_pct, mem_pct) for top processes."""
    processes = []

    if IS_LINUX:
        # /proc/[pid]/stat  — field 14 = utime, 15 = stime
        # /proc/[pid]/cmdline — process name
        # /proc/stat         — total CPU time for percentage calculation
        try:
            with open("/proc/stat") as f:
                total_line = f.readline()
            total_fields = total_line.split()
            # user(1) nice(2) system(3) idle(4) iowait(5) irq(6) softirq(7) steal(8)
            # guest(9) guest_nice(10) — may not be present
            n = len(total_fields)
            total_tick = sum(int(total_fields[i]) for i in range(1, min(n, 8)))
            prev_idle = int(total_fields[3]) + int(total_fields[4])

            # Simple: sample processes twice, 0.2s apart
            time.sleep(0.2)

            with open("/proc/stat") as f:
                total_line2 = f.readline()
            total_fields2 = total_line2.split()
            n2 = len(total_fields2)
            total_tick2 = sum(int(total_fields2[i]) for i in range(1, min(n2, 8)))
            prev_idle2 = int(total_fields2[3]) + int(total_fields2[4])

            delta_total = total_tick2 - total_tick
            delta_idle  = prev_idle2 - prev_idle
            cpu_count = os.cpu_count() or 1
            overall_pct = (delta_total - delta_idle) / delta_total * 100 if delta_total > 0 else 0

            for pid_dir in os.listdir("/proc"):
                if not pid_dir.isdigit():
                    continue
                pid = int(pid_dir)
                try:
                    # cmdline
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        raw = f.read(256)
                    cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
                    name = cmdline.split("/")[-1].split()[0] if cmdline else "(kernel)"
                    name = _trunc(name, 18)

                    # stat
                    with open(f"/proc/{pid}/stat") as f:
                        stat = f.read().split()
                    utime = int(stat[13])
                    stime = int(stat[14])
                    proc_tick = utime + stime

                    # cpu %
                    cpu_pct = (proc_tick / (delta_total * cpu_count)) * 100 if delta_total > 0 else 0
                    cpu_pct = min(cpu_pct, 100)

                    # memory (RSS)
                    with open(f"/proc/{pid}/status") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                mem_kb = int(line.split()[1])
                                mem_pct = mem_kb / 1024 / 1024   # fraction of 1 GB (used as indicator)
                                break
                        else:
                            mem_pct = 0
                except (PermissionError, FileNotFoundError, ProcessLookupError, IndexError):
                    continue

                processes.append((pid, name, cpu_pct, mem_pct))
        except Exception:
            pass

    elif IS_MACOS:
        import subprocess
        try:
            out = subprocess.check_output(
                ["ps", "-Ao", "pid=,pcpu=,rss=,comm="],
                text=True, timeout=3
            )
            total_mem = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            for line in out.splitlines():
                parts = line.strip().split(None, 3)
                if len(parts) < 4:
                    continue
                try:
                    pid = int(parts[0])
                    cpu_pct = float(parts[1])
                    rss_kb  = int(parts[2])
                    name    = _trunc(parts[3].split("/")[-1], 18)
                    mem_pct = rss_kb / 1024 / 1024   # fraction of 1 GB indicator
                    processes.append((pid, name, cpu_pct, mem_pct))
                except (ValueError, IndexError):
                    continue
        except Exception:
            pass

    elif IS_WINDOWS:
        import subprocess
        try:
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-Process | Sort-Object -Property CPU -Descending | "
                 "Select-Object -First 20 Id, ProcessName, "
                 "@{N='CPU';E={$_.CPU}}, "
                 "@{N='WS';E={$_.WorkingSet64}} | "
                 "Format-Table -HideTableHeaders | Out-String -Width 200"],
                text=True, timeout=5
            )
            for line in out.splitlines():
                parts = line.strip().split(None, 4)
                if len(parts) < 4 or not parts[0].isdigit():
                    continue
                try:
                    pid = int(parts[0])
                    name = _trunc(parts[1], 18)
                    cpu_pct = float(parts[2]) if parts[2] != "" else 0.0
                    mem_mb = int(parts[3]) / 1024 / 1024
                    processes.append((pid, name, cpu_pct, mem_mb))
                except (ValueError, IndexError):
                    continue
        except Exception:
            pass

    # Sort by CPU desc, keep top 10
    processes.sort(key=lambda x: x[2], reverse=True)
    return processes[:10]


# ─── CPU ──────────────────────────────────────────────────────────────────────

_cpu_prev = None

def get_cpu_percent():
    """Return overall CPU usage 0-100 (delta between two reads)."""
    global _cpu_prev
    try:
        if IS_LINUX:
            with open("/proc/stat") as f:
                line = f.readline()
            fields = line.split()
            idle1   = int(fields[4])
            total1  = sum(int(x) for x in fields[1:8])
            time.sleep(0.1)
            with open("/proc/stat") as f:
                line = f.readline()
            fields = line.split()
            idle2  = int(fields[4])
            total2 = sum(int(x) for x in fields[1:8])
            d_idle  = idle2  - idle1
            d_total = total2 - total1
            return max(0.0, min(100.0, (1 - d_idle / d_total) * 100)) if d_total else 0.0

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(
                ["ps", "-Ao", "pcpu="], text=True, timeout=2
            )
            total = 0.0
            for line in out.splitlines():
                line = line.strip()
                if line:
                    try:
                        total += float(line)
                    except ValueError:
                        pass
            return min(total, 100.0)

        elif IS_WINDOWS:
            import subprocess
            try:
                out = subprocess.check_output(
                    ["powershell", "-Command",
                     "(Get-Counter '\\Processor(_Total)\\% Processor Time' "
                     "-ErrorAction SilentlyContinue).CounterSamples.CookedValue"],
                    text=True, timeout=3
                )
                return max(0.0, min(100.0, float(out.strip())))
            except Exception:
                pass
    except Exception:
        pass
    return 0.0


# ─── Memory ───────────────────────────────────────────────────────────────────

def get_memory():
    """Return {total, used, free, available, percent}."""
    try:
        if IS_LINUX:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            used  = total - avail
            return {
                "total": total, "used": used,
                "free": mem.get("MemFree", 0),
                "available": avail,
                "percent": (used / total * 100) if total else 0.0
            }

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(["vm_stat"], text=True)
            stats = {}
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip().replace(" ", "_").lower()
                    try:
                        stats[key] = int(parts[1].strip().rstrip("."))
                    except ValueError:
                        pass
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = os.sysconf("SC_PHYS_PAGES") * page_size
            free  = stats.get("pages_free", 0) * page_size
            inactive = stats.get("pages_inactive", 0) * page_size
            wired    = stats.get("pages_wired_down", 0) * page_size
            active   = stats.get("pages_active", 0) * page_size
            used = active + wired
            return {
                "total": total, "used": used, "free": free,
                "available": free + inactive,
                "percent": (used / total * 100) if total else 0.0
            }

        elif IS_WINDOWS:
            import subprocess
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem | "
                 "ForEach-Object { $_.TotalVisibleMemorySize*1024 + ',' + "
                 "$_.FreePhysicalMemory*1024 })"],
                text=True, timeout=5
            )
            parts = out.strip().split(",")
            total = int(parts[0])
            free  = int(parts[1])
            return {
                "total": total, "used": total - free,
                "free": free, "available": free,
                "percent": ((total - free) / total * 100) if total else 0.0
            }
    except Exception:
        pass
    return {"total": 0, "used": 0, "free": 0, "available": 0, "percent": 0.0}


# ─── Disk ─────────────────────────────────────────────────────────────────────

def get_disk(path="/"):
    """Return {total, used, free, percent} for the volume containing path."""
    try:
        if IS_LINUX:
            import subprocess
            out = subprocess.check_output(
                ["df", "-B1", path], text=True, timeout=3
            )
            lines = out.strip().splitlines()
            if len(lines) < 2:
                return {"total": 0, "used": 0, "free": 0, "percent": 0.0}
            fields = lines[-1].split()
            if len(fields) < 4:
                return {"total": 0, "used": 0, "free": 0, "percent": 0.0}
            total = int(fields[1])
            used  = int(fields[2])
            free  = int(fields[3])
            return {
                "total": total, "used": used, "free": free,
                "percent": (used / total * 100) if total else 0.0
            }

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(
                ["df", "-B1", path], text=True, timeout=3
            )
            lines = out.strip().splitlines()
            if len(lines) < 2:
                return {"total": 0, "used": 0, "free": 0, "percent": 0.0}
            fields = lines[-1].split()
            if len(fields) < 4:
                return {"total": 0, "used": 0, "free": 0, "percent": 0.0}
            total = int(fields[1])
            used  = int(fields[2])
            free  = int(fields[3])
            return {
                "total": total, "used": used, "free": free,
                "percent": (used / total * 100) if total else 0.0
            }

        elif IS_WINDOWS:
            import subprocess
            drive = os.path.splitdrive(os.path.abspath(path))[0] or "C:"
            out = subprocess.check_output(
                ["powershell", "-Command",
                 f"(Get-PSDrive -Name {drive[0]}).Used,"
                 f"((Get-PSDrive -Name {drive[0]}).Used+(Get-PSDrive -Name {drive[0]}).Free)"],
                text=True, timeout=5
            )
            parts = out.strip().splitlines()
            if len(parts) >= 1:
                try:
                    used = int(parts[0].strip())
                    total = int(parts[1].strip()) if len(parts) > 1 else used
                    free = total - used
                    return {
                        "total": total, "used": used, "free": free,
                        "percent": (used / total * 100) if total else 0.0
                    }
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return {"total": 0, "used": 0, "free": 0, "percent": 0.0}


# ─── Network ───────────────────────────────────────────────────────────────────

_net_prev = None
_net_prev_time = None

def get_network():
    """Return (bytes_up, bytes_down, speed_up, speed_down) counters."""
    global _net_prev, _net_prev_time
    now = time.time()
    try:
        if IS_LINUX:
            with open("/proc/net/dev") as f:
                lines = f.readlines()
            rx, tx = 0, 0
            for line in lines[2:]:
                fields = line.split()
                if len(fields) < 10:
                    continue
                iface = fields[0].rstrip(":")
                if iface in ("lo",):
                    continue
                rx += int(fields[1])
                tx += int(fields[9])
            prev = _net_prev
            pt   = _net_prev_time
            _net_prev      = (rx, tx)
            _net_prev_time = now
            if prev is None or pt is None:
                return rx, tx, 0.0, 0.0
            dt = max(now - pt, 0.001)
            return (rx, tx,
                    (tx - prev[1]) / dt,
                    (rx - prev[0]) / dt)

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(
                ["netstat", "-ib"], text=True, timeout=3
            )
            rx, tx = 0, 0
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) < 10:
                    continue
                try:
                    rx += int(parts[6])   # Ibytes
                    tx += int(parts[9])   # Obytes
                except (ValueError, IndexError):
                    continue
            prev = _net_prev
            pt   = _net_prev_time
            _net_prev      = (rx, tx)
            _net_prev_time = now
            if prev is None or pt is None:
                return rx, tx, 0.0, 0.0
            dt = max(now - pt, 0.001)
            return (rx, tx,
                    (tx - prev[1]) / dt,
                    (rx - prev[0]) / dt)

        elif IS_WINDOWS:
            import subprocess
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-NetAdapterStatistics | "
                 "Select-Object -ExpandProperty ReceivedBytes, SentBytes"],
                text=True, timeout=5
            )
            parts = out.strip().split()
            if len(parts) >= 2:
                rx = int(parts[0])
                tx = int(parts[1])
            else:
                rx, tx = 0, 0
            prev = _net_prev
            pt   = _net_prev_time
            _net_prev      = (rx, tx)
            _net_prev_time = now
            if prev is None or pt is None:
                return rx, tx, 0.0, 0.0
            dt = max(now - pt, 0.001)
            return (rx, tx,
                    (tx - prev[1]) / dt,
                    (rx - prev[0]) / dt)

    except Exception:
        pass
    _net_prev      = None
    _net_prev_time = None
    return 0, 0, 0.0, 0.0


# ─── Temperature ───────────────────────────────────────────────────────────────

def get_temperature():
    """Return CPU temperature in °C, or None if unavailable."""
    try:
        if IS_LINUX:
            # Try hwmon
            for hwmon_path in [f"/sys/class/hwmon/hwmon{i}" for i in range(10)]:
                if not os.path.exists(hwmon_path):
                    continue
                name_file = os.path.join(hwmon_path, "name")
                if os.path.exists(name_file):
                    with open(name_file) as f:
                        name = f.read().strip()
                    if name in ("k10temp", "coretemp", "cpu_thermal", "acpitz"):
                        for sensor_file in [f"{hwmon_path}/temp1_input",
                                            f"{hwmon_path}/temp2_input"]:
                            if os.path.exists(sensor_file):
                                with open(sensor_file) as f:
                                    millideg = int(f.read().strip())
                                return millideg / 1000.0
            # Fallback: thermal_zone
            for zone in [f"/sys/class/thermal/thermal_zone{i}" for i in range(10)]:
                trip = os.path.join(zone, "trip_point_0_temp")
                if os.path.exists(trip):
                    with open(os.path.join(zone, "temp")) as f:
                        return int(f.read().strip()) / 1000.0

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(
                ["osx-cpu-temp"], text=True, timeout=3
            ).strip()
            # "78.0°C" format
            import re
            m = re.search(r"([0-9.]+)", out)
            if m:
                return float(m.group(1))

        elif IS_WINDOWS:
            import subprocess
            try:
                out = subprocess.check_output(
                    ["powershell", "-Command",
                     "Add-Type -AssemblyName System.Runtime.InteropServices;"
                     "[System.Runtime.InteropServices.Marshal]::"
                     "SizeOf([Type]::GetType('System.IntPtr'))"],
                    text=True, timeout=3
                )
            except Exception:
                pass
            # Simpler: use OpenHardwareMonitor output if available
            # For now, return None (temperature often requires 3rd-party tool on Windows)
    except Exception:
        pass
    return None


# ─── System Uptime ─────────────────────────────────────────────────────────────

def get_uptime():
    """Return uptime string and load averages (1, 5, 15 min)."""
    try:
        if IS_LINUX:
            with open("/proc/uptime") as f:
                uptime_sec = float(f.read().split()[0])
            days  = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
            mins  = int((uptime_sec % 3600) // 60)
            if days > 0:
                uptime_str = f"{days}d {hours}h {mins}m"
            elif hours > 0:
                uptime_str = f"{hours}h {mins}m"
            else:
                uptime_str = f"{mins}m"

            with open("/proc/loadavg") as f:
                load = f.read().split()[:3]
            return uptime_str, [float(x) for x in load]

        elif IS_MACOS:
            import subprocess
            out = subprocess.check_output(["uptime"], text=True).strip()
            # "12:34  up  3:15, 2 users, load averages: 1.23 2.40 3.00"
            import re
            m = re.search(r"up ([0-9]+ day[^,]*, )?([0-9]+):([0-9]+),", out)
            if m:
                days = int(m.group(1).split()[0]) if m.group(1) else 0
                hours, mins = int(m.group(2)), int(m.group(3))
                if days > 0:
                    uptime_str = f"{days}d {hours}h {mins}m"
                else:
                    uptime_str = f"{hours}h {mins}m"
            else:
                uptime_str = "N/A"
            load_m = re.findall(r"load averages: ([0-9.]+) ([0-9.]+) ([0-9.]+)", out)
            if load_m:
                load = [float(x) for x in load_m[0]]
            else:
                load = [0.0, 0.0, 0.0]
            return uptime_str, load

        elif IS_WINDOWS:
            import subprocess
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
                 "ForEach-Object { $_.Days, $_.Hours, $_.Minutes }"],
                text=True, timeout=5
            ).strip()
            parts = out.split()
            if len(parts) >= 3:
                uptime_str = f"{parts[0]}d {parts[1]}h {parts[2]}m"
            else:
                uptime_str = "N/A"
            # Load average not easily available on Windows via stdlib
            return uptime_str, [0.0, 0.0, 0.0]

    except Exception:
        pass
    return "N/A", [0.0, 0.0, 0.0]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _gauge_bar(pct, width=20):
    """Unicode block-element bar. Filled=dark, empty=dim."""
    pct  = max(0.0, min(100.0, pct))
    fill = int(round(pct / 100 * width))
    full = "█" * fill
    empt = "░" * (width - fill)
    return full + empt


def _pct_color(pct, high=curses.A_BOLD):
    """Return (text_attr, dim_attr) for a gauge showing pct."""
    if pct < 50:
        attr = curses.color_pair(2)   # green
    elif pct < 75:
        attr = curses.color_pair(3)   # yellow
    else:
        attr = curses.color_pair(4) | high  # red
    return attr


def _a(s):
    """Shortcut for THEME.accent color pair."""
    return curses.color_pair(12)


def _d(s):
    """Shortcut for THEME.dim color pair."""
    return curses.color_pair(13)


def _t(s):
    """Shortcut for THEME.text color pair."""
    return curses.color_pair(5)


def _box_border(win, h, w, tl, tr, bl, br, hor, ver):
    """Draw a double-line box with unicode corners."""
    win.attrset(curses.color_pair(6))
    win.border(hor=curses.ACS_HLINE, ver=curses.ACS_VLINE,
               ul=curses.ACS_ULCORNER, ur=curses.ACS_URCORNER,
               ll=curses.ACS_LLCORNER, lr=curses.ACS_LRCORNER)


# ─── PulseBoard ────────────────────────────────────────────────────────────────

class PulseBoard:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.theme_idx  = 0
        self.scroll_off = 0
        self.frame      = 0
        self._metrics   = {}          # cached metric values
        self._lock      = threading.Lock()
        self._data_q    = queue.Queue(maxsize=1)
        self._refresh_e = threading.Event()
        self._worker_alive = True

        curses.curs_set(0)
        curses.noecho(); curses.echo(0)
        stdscr.nodelay(True)
        stdscr.timeout(1000)
        curses.use_default_colors()

        # Map theme colors → curses pairs
        self._apply_theme(THEMES[0])
        self._start_worker()

    def _apply_theme(self, theme):
        """Initialise curses colors for a Theme."""
        try:
            curses.start_color()
            curses.use_default_colors()
            # Define 256-color palette entries (approximate to theme hex)
            def c256(r, g, b):
                # Find closes color number available (curses can use #0-255)
                return curses.COLOR_PAIRS  # placeholder; init_color used below
            pass
        except curses.error:
            pass

        # Map: custom color index → (r,g,b)  (0-1000 scale for init_color)
        PALETTE = {
            # name  : (r,   g,    b)
            0:      (0,    0,    0),    # black
            51:     (0,    255,  218),  # cyan    #00ffdA
            183:    (167,  139,  250),  # violet  #a78bfa
            226:    (255,  187,  71),   # amber   #fbbf24
            82:     (52,   211,  153),  # green   #34d399
            45:     (96,   165,  250),  # blue    #60a5fa
            208:    (251,  146,  60),   # orange  #fb923c
            203:    (255,  107,  107),  # red     #ff6b6b
            197:    (255,  107,  107),  # alert red
            68:     (40,   200,  180),  # nord accent
            211:    (180,  100,  255),  # purple
            133:    (133,  153,  0),    # solarized green
            160:    (238,  153,  0),    # solarized yellow
            139:    (0,    209,  30),   # monokai green
            197:    (249,  38,   114),  # monokai pink
            76:     (166,  226,  44),   # monokai green2
            166:    (230,  130,  100),   # monokai orange
        }

        for idx, (r, g    """Return {total, used, free, percent}