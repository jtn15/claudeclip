#!/usr/bin/env bash
# Regenerates the social share image (1200x630), favicon PNG and Apple touch icon from the logo SVGs.
# Needs a Chromium binary: set CHROME=/path/to/chrome, or it falls back to the Playwright copy.
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-$(ls -d /opt/pw-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1)}"
IMG=src/assets/img
TMP="$(mktemp -d)"
LOCKUP="$(cat $IMG/logo/lockup.svg | sed 's/currentColor/#12301F/')"
MONO="$(cat $IMG/favicon.svg)"

cat > "$TMP/og.html" <<HTML
<html><body style="margin:0;width:1200px;height:630px;background:#F3EEE4;display:flex;align-items:center;justify-content:center">
<div style="width:760px">$LOCKUP</div></body></html>
HTML
cat > "$TMP/fav.html" <<HTML
<html><body style="margin:0;width:64px;height:64px;background:transparent;display:flex;align-items:center;justify-content:center">
<div style="width:56px">$MONO</div></body></html>
HTML
cat > "$TMP/touch.html" <<HTML
<html><body style="margin:0;width:180px;height:180px;background:#F3EEE4;display:flex;align-items:center;justify-content:center">
<div style="width:120px">$MONO</div></body></html>
HTML

shot() { "$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --default-background-color=00000000 --window-size="$3,$4" --screenshot="$2" "file://$TMP/$1.html" >/dev/null 2>&1; }
shot og "$PWD/$IMG/og-image.png" 1200 630
shot fav "$PWD/$IMG/favicon-32.png" 64 64
shot touch "$PWD/$IMG/apple-touch-icon.png" 180 180
rm -rf "$TMP"
echo "Wrote og-image.png, favicon-32.png, apple-touch-icon.png"
