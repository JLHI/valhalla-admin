#!/bin/sh
set -eu

# Ensure base dir exists
mkdir -p /data/graphs

echo "[valhalla-toolbox] Ready. Following build logs under /data/graphs" >&2

# Track tailed files using marker files
mkdir -p /tmp/valhalla-tail

# Periodically discover new build.log files and tail them to stdout
while :; do
  # Search typical depths: /data/graphs/<graph>/build.log or nested /build/build.log
  for f in /data/graphs/*/build.log /data/graphs/*/*/build.log; do
    [ -f "$f" ] || continue
    key="/tmp/valhalla-tail/$(echo "$f" | sed 's#[^A-Za-z0-9]#_#g')"
    if [ ! -e "$key" ]; then
      echo "[valhalla-toolbox] Following $f" >&2
      : > "$key"
      # Tail in background; output goes to container stdout/stderr
      # -n 0: only new lines; -F: follow across rotations/moves
      tail -n 0 -F "$f" 2>&1 &
    fi
  done
  sleep 2
done
