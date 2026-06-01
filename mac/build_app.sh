#!/usr/bin/env bash
# VTT.app をビルドして Dock/Launchpad から起動できる普通のMacアプリにする。
#
# 方式: システムの python3 を使う軽量バンドル（Pythonを丸ごと同梱しないので軽い）。
#   - mac/ の .py を VTT.app/Contents/Resources にコピー
#   - 起動スクリプトが python3 mac/gui.py を呼ぶ
#   - アイコン(icon_1024.png)を .icns に変換して同梱
#
# 使い方:
#   bash mac/build_app.sh            # ./VTT.app を作成
#   bash mac/build_app.sh --install  # 作成後 /Applications にコピー（Launchpadに出る）
#
# 完全に自己完結（Python同梱）したい場合は README の py2app 手順を参照。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/VTT.app"
RES="$APP/Contents/Resources"
MACOS="$APP/Contents/MacOS"

echo "[build] 既存バンドルを掃除"
rm -rf "$APP"
mkdir -p "$RES/mac" "$MACOS"

echo "[build] スクリプトをコピー"
cp "$ROOT/mac/gui.py" "$ROOT/mac/vtt.py" "$ROOT/mac/slides.py" "$RES/mac/"

echo "[build] Info.plist を作成"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>VTT</string>
  <key>CFBundleDisplayName</key><string>VTT</string>
  <key>CFBundleIdentifier</key><string>com.vtt.transcriber</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>VTT</string>
  <key>CFBundleIconFile</key><string>VTT.icns</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

echo "[build] 起動スクリプトを作成"
cat > "$MACOS/VTT" <<'LAUNCH'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
# ターミナル無しで起動されるので PATH に Homebrew を足す（ffmpeg/yt-dlp/buzz 用）
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# 出力はホームの VTT_output に置く（.app内に書き込めないため）
OUT="$HOME/VTT_output"; mkdir -p "$OUT"; cd "$OUT"
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  osascript -e 'display alert "VTT" message "python3 が見つかりません。Python3 をインストールしてください。"'
  exit 1
fi
exec "$PY" "$DIR/mac/gui.py"
LAUNCH
chmod +x "$MACOS/VTT"

echo "[build] アイコンを変換"
ICON_SRC="$ROOT/mac/app/icon_1024.png"
if [ -f "$ICON_SRC" ] && command -v iconutil >/dev/null 2>&1; then
  TMP="$(mktemp -d)/VTT.iconset"; mkdir -p "$TMP"
  for s in 16 32 64 128 256 512; do
    sips -z $s $s    "$ICON_SRC" --out "$TMP/icon_${s}x${s}.png"       >/dev/null
    sips -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$TMP/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$TMP" -o "$RES/VTT.icns"
  echo "[build] VTT.icns を作成"
else
  echo "[build] (iconutil/icon無し: アイコンはスキップ)"
fi

echo "[build] 完了 → $APP"

if [ "${1:-}" = "--install" ]; then
  echo "[build] /Applications にインストール"
  rm -rf "/Applications/VTT.app"
  cp -R "$APP" "/Applications/VTT.app"
  echo "[build] Launchpad/Dock から 'VTT' を起動できます"
fi
