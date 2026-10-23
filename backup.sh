#!/data/data/com.termux/files/usr/bin/bash
# ~/backup.sh — back up the Stage app + Termux setup to a GitHub repo.
# First run: creates the repo (needs `gh` authed, or set REPO_URL manually).
# Later runs: commits and pushes any changes.

set -e

# ---- CONFIG ----
REPO_NAME="daylight-stage-backup"
BACKUP_DIR="$HOME/$REPO_NAME"
HOME_DIR="$HOME"

echo "==> Backing up to $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

# ---- 1. Copy the app + server ----
echo "==> Copying app files"
cp "$HOME_DIR/stage2.html" "$BACKUP_DIR/" 2>/dev/null || echo "  (stage2.html not found)"
cp "$HOME_DIR/stage-server.py" "$BACKUP_DIR/" 2>/dev/null || echo "  (stage-server.py not found)"
cp "$HOME_DIR/stage.html" "$BACKUP_DIR/" 2>/dev/null || true  # legacy v1, if present

# ---- 2. Copy saved projects ----
echo "==> Copying saved projects"
rm -rf "$BACKUP_DIR/stage-backups"
cp -r "$HOME_DIR/stage-backups" "$BACKUP_DIR/stage-backups" 2>/dev/null || echo "  (no stage-backups dir)"

# ---- 3. Copy key configs ----
echo "==> Copying configs"
mkdir -p "$BACKUP_DIR/config"
cp "$HOME_DIR/.bashrc" "$BACKUP_DIR/config/bashrc" 2>/dev/null || true
cp "$HOME_DIR/.tmux.conf" "$BACKUP_DIR/config/tmux.conf" 2>/dev/null || true
cp "$HOME_DIR/.profile" "$BACKUP_DIR/config/profile" 2>/dev/null || true

# ---- 4. Snapshot installed packages ----
echo "==> Listing installed packages"
pkg list-installed 2>/dev/null | sed 's/\/.*//' | sort -u > "$BACKUP_DIR/config/pkg-list.txt" || true
pip freeze 2>/dev/null > "$BACKUP_DIR/config/pip-freeze.txt" || true
command -v npm >/dev/null 2>&1 && npm list -g --depth=0 2>/dev/null > "$BACKUP_DIR/config/npm-global.txt" || true

# ---- 5. Write the restore guide ----
cat > "$BACKUP_DIR/SETUP.md" << 'SETUP'
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
SETUP

# ---- 6. .gitignore ----
cat > "$BACKUP_DIR/.gitignore" << 'GIT'
c.js
node_modules/
*.log
__pycache__/
*.pyc
GIT

# ---- 7. Git init / commit / push ----
if [ ! -d "$BACKUP_DIR/.git" ]; then
  echo "==> First run: initializing git repo"
  git init
  git branch -M main
  git add -A
  git commit -m "Initial backup"

  if command -v gh >/dev/null 2>&1; then
    echo "==> Creating GitHub repo via gh"
    gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
  else
    echo ""
    echo "  >>> 'gh' CLI not found. Create the repo manually:"
    echo "  1. Make a new empty repo named '$REPO_NAME' on github.com"
    echo "  2. Run:"
    echo "       cd $BACKUP_DIR"
    echo "       git remote add origin https://github.com/YOURNAME/$REPO_NAME.git"
    echo "       git push -u origin main"
    echo ""
  fi
else
  echo "==> Committing changes"
  git add -A
  if git diff --cached --quiet; then
    echo "  Nothing changed since last backup."
  else
    git commit -m "Backup $(date '+%Y-%m-%d %H:%M')"
    git push 2>/dev/null && echo "==> Pushed!" || echo "  (push failed — check remote/auth)"
  fi
fi

echo "==> Done."
