# 🎛️ PulseBoard

> A real-time system monitor TUI with cyberpunk aesthetics. Zero dependencies — pure Python + curses.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows%20(WSL)-cyan?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Stars](https://img.shields.io/github/stars/THIS-AI1627/pulseboard?style=flat-square)
![Issues](https://img.shields.io/github/issues/THIS-AI1627/pulseboard?style=flat-square)

---

## ✨ Features

| Widget | Description |
|--------|-------------|
| 📊 **CPU** | Animated gradient bar — green → yellow → red as load increases |
| 🧠 **Memory** | Used / Total GB with gradient meter |
| 🌡️ **Temperature** | Normal (green) / Warning (yellow) / Critical (red) |
| 💾 **Disk** | Root partition usage with visual bar |
| 🌐 **Network** | Live upload/download speed + cumulative total |
| 🖥️ **Process List** | Top 8 processes by CPU usage |
| ⏰ **Live Clock** | Real-time clock, updates every second |

### 🎨 5 Built-in Color Themes

```
Cyberpunk  ·  Monokai  ·  Dracula  ·  Nord  ·  Solarized Dark
```

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/THIS-AI1627/pulseboard.git
cd pulseboard

# Run — no pip install needed!
python pulseboard.py
```

> **Windows?** Use [Git Bash](https://gitforwindows.org/), [WSL](https://aka.ms/wsl), or [Windows Terminal with WSL](https://aka.ms/wsl).

---

## 🕹️ Controls

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `↑ / ↓` or `J / K` | Navigate process list |
| `R` | Refresh data immediately |
| `T` | Cycle to next color theme |

---

## 📸 Screenshot

```
┌────────────────────── PulseBoard ────────────────────── 08:35:12 ─┐
│  ┌─ CPU ─────────┐  ┌─ Memory ──────┐  ┌─ Temp ───────────┐       │
│  │ ████████░░░░ │  │ ██████░░░░░░░ │  │  ● Normal  62°C  │       │
│  │    47.3%      │  │   3.2/16 GB   │  │                  │       │
│  └───────────────┘  └───────────────┘  └──────────────────┘       │
│                                                                      │
│  💾 Disk: ██████████░░░░  52%  (120G / 232G)                      │
│                                                                      │
│  🌐 Up:  1.23 KB/s  Down: 45.67 KB/s  │  Total: ↑ 12.3 MB  ↓ 890 MB │
│                                                                      │
│  Top Processes (CPU%)                                               │
│   1. python3      ██████████  12.4%                                │
│   2. chrome       ████████░░   9.1%                                 │
│   3. firefox      ██████░░░░   6.3%                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Requirements

- **Python 3.8+**
- `curses` — stdlib on Linux/macOS; on Windows use WSL or Git Bash

No `pip install`. No external packages. Just Python.

---

## 📦 Alternative Install Methods

```bash
# Download directly
curl -fsSL https://raw.githubusercontent.com/THIS-AI1627/pulseboard/main/pulseboard.py -o pulseboard.py
python pulseboard.py

# pip (coming soon)
pip install pulseboard-tui
```

---

## 🤝 Contributing

Contributions welcome! Open an issue or submit a PR.

---

## 📄 License

MIT License — free to use, modify, and distribute.
