#!/data/data/com.termux/files/usr/bin/bash
# Two commands for rolling versions of stage2.html:
#   checkpoint  -> save current stage2.html onto the stack (keeps last 5)
#   goback      -> restore the most recent checkpoint (and pop it off)
#
# Install: source this from .bashrc, or copy the two functions in.

STAGE_FILE="$HOME/stage2.html"
CKPT_DIR="$HOME/.stage-versions"
MAX_KEEP=5

checkpoint() {
  mkdir -p "$CKPT_DIR"
  local ts
  ts=$(date +%Y%m%d-%H%M%S)
  cp "$STAGE_FILE" "$CKPT_DIR/stage2-$ts.html"
  echo "checkpoint saved: stage2-$ts.html"
  # Trim to the newest $MAX_KEEP
  local count
  count=$(ls -1 "$CKPT_DIR"/stage2-*.html 2>/dev/null | wc -l)
  if [ "$count" -gt "$MAX_KEEP" ]; then
    ls -1t "$CKPT_DIR"/stage2-*.html | tail -n +$((MAX_KEEP+1)) | while read -r f; do
      rm -f "$f"
    done
  fi
}

goback() {
  local latest
  latest=$(ls -1t "$CKPT_DIR"/stage2-*.html 2>/dev/null | head -n 1)
  if [ -z "$latest" ]; then
    echo "no checkpoints to go back to."
    return 1
  fi
  # Safety: stash the CURRENT file first, so goback is itself undoable once
  cp "$STAGE_FILE" "$CKPT_DIR/.before-goback.html"
  cp "$latest" "$STAGE_FILE"
  echo "restored: $(basename "$latest")"
  rm -f "$latest"   # pop it so repeated goback steps further back
  echo "(reload the page with a new ?v= to see it)"
}
