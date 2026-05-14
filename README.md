# Game Fence

🌍 **Languages**

- 🇸🇦 [العربية](README.ar.md)
- 🇬🇧 **English** _(this file)_
- 🇫🇷 [Français](README.fr.md)

---

**Windows** tool to **limit or block program launches** using a **weekly schedule** (per executable). Useful for screen-time or gaming boundaries; it runs in the background and matching processes can be closed automatically outside allowed windows.

## Features

- Rules per **executable** (e.g. `steam.exe`) with per-day modes: blocked all day, allowed only between times, etc.
- **Tkinter** UI: French, English, Arabic (RTL).
- Reference time: **NTP** when the network allows, otherwise fallback to the system clock; configurable **UTC±N** offset.
- **Global shortcut** `Ctrl+Shift+G` to show the window (requires the `keyboard` module).
- Persistent JSON configuration file.

## Requirements

- **Windows 10/11** (64-bit).
- **Python 3.10+** (when running from source).

## Download (pre-built)

**End users** (no Python needed):

- **Direct download :** [GameFence APP](https://github.com/lebbar/game-fence/releases/latest/download/GameFence.exe)  
  

- **Releases:** [https://github.com/lebbar/game-fence/releases](https://github.com/lebbar/game-fence/releases)

### Publishing a release (maintainers)

**Option A — CI (recommended)**  
Push a version tag; GitHub Actions (`.github/workflows/release.yml`) builds on Windows and uploads **`GameFence.exe`** to the release for that tag:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

**Option B — manual**  
Build with `.\build.ps1` → `dist\GameFence.exe`, then on GitHub: **Releases** → **Draft a new release** → tag (e.g. `v1.0.0`) → attach **`GameFence.exe`** → **Publish release**.

## Development install

```powershell
git clone <your-git-url>
cd game-fence
python -m pip install -r requirements.txt
```

For the global keyboard shortcut:

```text
pip install keyboard
```

(already listed in `requirements.txt`.)

## Run

```powershell
python main.py
```

On first run the app may stay hidden: press **`Ctrl+Shift+G`** to open the window.

## Configuration

Path: `%LOCALAPPDATA%\GameFence\config.json`

- Rules, polling interval, UI language, time-zone offset (UTC±N), etc.

## Build — standalone executable

With **PyInstaller** (see `requirements-build.txt`):

```powershell
.\build.ps1
```

Output: `dist\GameFence.exe` (windowed, no console).

### Windows installer (optional)

1. Build the EXE with `build.ps1`.
2. Open `installer.iss` in **[Inno Setup](https://jrsoftware.org/isinfo.php)** and compile.

Output: `installer_output\` folder.

## Repository layout

| Item | Role |
|------|------|
| `main.py` | GUI |
| `core.py` | Scheduling, config, process termination |
| `clock_sync.py` | NTP sync / reference time |
| `i18n.py` | Strings and fonts per locale |
| `locales/` | `fr.json`, `en.json`, `ar.json` translations |
| `GameFence.spec` | PyInstaller spec |
| `build.ps1` | Install deps + build EXE |

## Main dependencies

- `keyboard` — keyboard hook for the global shortcut.
- `ntplib` — NTP requests.

## Security & limits

- Control applies on the computer where the tool runs; a user with administrator rights can disable the tool.
- Combine with appropriate Windows accounts for serious "parental control"–style use.
- This tool does not replace physical supervision or the presence of an adult.
- Someone with technical skills can often find a loophole or workaround—do not treat the protection as absolute.

---

*Personal project — issues and contributions welcome.*
