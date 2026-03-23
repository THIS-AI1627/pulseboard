# PulseBoard — Real-Time System Monitor TUI

## Concept & Vision

PulseBoard is a visually stunning real-time terminal dashboard that makes system monitoring feel alive. Rather than displaying cold numbers, it treats system metrics as a living data visualization — with pulsing animations, gradient meters, and a dark cyberpunk aesthetic. It should feel like mission control on a spaceship.

## Design Language

### Aesthetic Direction
Dark cyberpunk command center. Inspired by sci-fi movie interfaces (TRON, Westworld terminals) meets minimalist developer tooling.

### Color Themes
| Theme | Accent 1 | Accent 2 | Accent 3 |
|-------|----------|----------|----------|
| Cyberpunk (default) | `#64ffda` cyan | `#a78bfa` violet | `#ff6b6b` coral |
| Monokai | `#f92672` pink | `#a6e22e` lime | `#fd971f` orange |
| Dracula | `#bd93f9` purple | `#ff79c6` pink | `#8be9fd` cyan |
| Nord | `#88c0d0` ice | `#bf616a` red | `#d8dee9` white |
| Solarized | `#859900` green | `#b58900` yellow | `#2aa198` teal |

### Motion Philosophy
- Meters update every 1 second
- Title pulses with accent color oscillation
- No jarring flickers — curses incremental updates

### Visual Assets
- Box-drawing: `─ │ ┌ ┐ └ ┘ ├ ┤`
- Meter fills: `█ ▓ ▒ ░`
- Network arrows: `↑ ↓`
- Status circles: `● ◉`

## Layout (80-char wide grid)

```
┌─────────────────── PulseBoard ─────────────────── 08:35:12 ─┐
│                                                                 │
│  ┌─ CPU ────────┐  ┌─ Memory ─────┐  ┌─ Temp ───────────┐     │
│  │  ████████░░  │  │ ██████░░░░░ │  │  ● Normal  62°C  │     │
│  │   47.3%      │  │   3.2/16 GB  │  │                 │     │
│  └──────────────┘  └──────────────┘  └──────────────────┘     │
│                                                                 │
│  ┌─ Disk ───────┐  ┌─ Network ↑ ──┐  ┌─ Network ↓ ──┐          │
│  │  █████░░░░░  │  │  ↑ 1.2 MB/s  │  │  ↓ 340 KB/s  │          │
│  │  256/512 GB  │  │   1.24 GB    │  │   892 MB     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌─ Top Processes ───────────────────────────────────────┐     │
│  │  PID    Name                CPU%       Memory%        │     │
│  │  1234   chrome              ████░░░░   12.3%           │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
│  [Q] Quit   [↑↓] Scroll   [R] Refresh   [T] Theme              │
└─────────────────────────────────────────────────────────────────┘
```

## Features

1. **CPU Monitor** — animated bar, shifts red under load
2. **Memory Monitor** — used/total with violet accent
3. **Temperature** — status indicator (Normal/Warning/Critical)
4. **Disk** — root partition used/total
5. **Network ↑↓** — real-time speed + cumulative total
6. **Process List** — top 8 by CPU, scrollable with ↑↓ or j/k
7. **Uptime** — system uptime displayed
8. **Live Clock** — updates every second in title bar
9. **5 Color Themes** — switchable with T key

## Technical Approach

- **Language**: Python 3
- **Framework**: `curses` (stdlib, no external deps)
- **Platform**: Linux, macOS, Windows (Git Bash/WSL)
- **Architecture**: Single file `pulseboard.py`, ~600 lines
- **Data sources**: `/proc/stat`, `/proc/meminfo`, `/proc/net/dev`, `/sys/class/thermal/`
- **Fallback**: macOS `vm_stat`/`top`, Windows `powershell`
