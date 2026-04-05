# 🟦 LED Matrix Dashboard

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A modular, high-performance dashboard for RGB LED matrix panels.

Built for clarity and speed, this project displays **real-time, high-signal information** using a clean plugin system — perfect for homelabs, wall displays, or status boards.

---

## ✨ Highlights

- 🔌 **Plugin Architecture** — add new features without touching core code  
- ⚡ **Fast + Lightweight** — runs well even on Pi Zero 2 W  
- 🧠 **Signal-First Design** — prioritizes important information  
- 🖥️ **LED Optimized UI** — readable from a distance  
- 🔄 **Auto Rotation** — cycles through plugins seamlessly  

---

## 📺 Demo Layout

Each plugin uses the full display:

```
[ NEWS ]
Full-screen headline
(rotates through top stories)

[ ECONOMY ]
Stocks + macro indicators

[ CALENDAR ]
Upcoming events
```

---

## 📦 Included Plugins

### 📰 News — *World Changes*
Focuses on **what just happened**:
- War / attacks / disasters  
- Political decisions / court rulings  

Features:
- Top 4 stories  
- Full-screen display  
- US prioritized, global included  
- English-only filtering  

---

### 💰 US Economy
Snapshot of market + macro conditions:

| Stocks | Macro |
|-------|------|
| S&P 500 | CPI |
| DOW | Unemployment |
| NASDAQ | GDP |
| VIX | 10YR |

Data sources:
- Yahoo Finance  
- FRED API  

---

### 📅 Calendar (Today)
- Aggregates multiple Google Calendars  
- Smart text cleanup:
  - Removes phrases like “Return with”  
  - Abbreviates (e.g. `birthday → b'day`)  
- Clean truncation for LED display  

---

## 🧩 Plugin System

Plugins live in:

```
plugins/
```

Each plugin:
- subclasses `BasePlugin`
- implements:
  - `refresh()` → fetch data  
  - `render(width, height)` → draw frame  
- defines:
  - `refresh_seconds`  
  - `display_seconds`  

✔ Auto-discovered  
✔ No changes to `main.py` required  

---

## 🚀 Getting Started

### Run
```bash
python main.py
```

### Optional
```bash
python main.py --help
python main.py 1 3   # run selected plugins
```

---

## 🔐 Environment Variables

### News
```bash
WEBZIO_TOKEN=your_token
```

### Economy
```bash
FRED_API_KEY=your_key
```

### General
```bash
TIMEZONE=America/Los_Angeles
```

---

## 🧠 Design Philosophy

> Show the **most important information** in the **simplest possible way**

- No clutter  
- No scrolling noise  
- No wasted pixels  

Each plugin answers a clear question:

| Plugin | Question |
|-------|--------|
| 📰 News | What just changed? |
| 💰 Economy | What is the current state? |
| 📅 Calendar | What’s next? |

---

## 🔧 Future Ideas

- 🚨 Alerts plugin (only major events)  
- 📊 Micro-trends / sparklines  
- 🌦️ Weather plugin  
- ⚡ Adaptive refresh (already partially implemented)  

---

## 📜 License

MIT

---

## 🙌 Credits

Built as a homelab project focused on **clarity, usefulness, and fun**.

---

⭐ If you like this project, give it a star!
