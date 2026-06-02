# Daylight Stage — Restore Guide

How to get this running on a fresh Daylight tablet (Termux).

## 1. Install Termux packages
```bash
pkg update && pkg upgrade
pkg install python nodejs git termux-api
# See config/pkg-list.txt for the full list that was installed.
```

## 2. Restore configs
```bash
cp config/bashrc ~/.bashrc
cp config/tmux.conf ~/.tmux.conf
source ~/.bashrc
```

## 3. Put the app in place
```bash
cp stage2.html ~/
cp stage-server.py ~/
cp -r stage-backups ~/
```

## 4. Start the server
The `.bashrc` auto-starts it, or run manually:
```bash
python ~/stage-server.py &
```
Then open http://localhost:8765/2 in Brave.

## 5. Python packages (if any)
```bash
pip install -r config/pip-freeze.txt
```

## Notes
- The Stage app is a single HTML file (`stage2.html`) + a tiny Python server.
- Projects live in `stage-backups/projects/<name>/latest.json`.
- Claude Code in Termux must be pinned to a pre-binary version (auto-update breaks it).
- `/tmp` fix: `export TMPDIR=$PREFIX/tmp` in `.bashrc`.
