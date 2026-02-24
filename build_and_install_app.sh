#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
APP_NAME="TikTok Upload Manager"
APP_BUNDLE="$HOME/Applications/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
EXECUTABLE_NAME="TikTokUploadManager"
PYTHON_BACKEND_DIR="$PROJECT_DIR/Python"
ICON_SOURCE="$PROJECT_DIR/Resources/app_icon.png"

mkdir -p "$BUILD_DIR"

xcrun swiftc \
  "$PROJECT_DIR/Sources/TikTokUploadManager/TikTokUploadManagerApp.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/ContentView.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/ViewModels/ClipGeneratorViewModel.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/ViewModels/FeaturesViewModel.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/Services/PythonProcessService.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/Services/TikTokFeaturesService.swift" \
  "$PROJECT_DIR/Sources/TikTokUploadManager/Models/Clip.swift" \
  -o "$BUILD_DIR/$EXECUTABLE_NAME" \
  -framework SwiftUI \
  -framework AppKit \
  -framework AVKit \
  -framework AVFoundation

rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"
cp "$BUILD_DIR/$EXECUTABLE_NAME" "$MACOS_DIR/$EXECUTABLE_NAME"
chmod +x "$MACOS_DIR/$EXECUTABLE_NAME"

if [[ -d "$PYTHON_BACKEND_DIR" ]]; then
  rm -rf "$RESOURCES_DIR/Python"
  cp -R "$PYTHON_BACKEND_DIR" "$RESOURCES_DIR/Python"
  chmod +x "$RESOURCES_DIR/Python/clip_generator_cli.py" || true
fi

# Copy the app/ backend package so clip_generator_cli.py can resolve "from app.services.*"
APP_BACKEND_DIR="$PROJECT_DIR/app"
if [[ -d "$APP_BACKEND_DIR" ]]; then
  rm -rf "$RESOURCES_DIR/app"
  cp -R "$APP_BACKEND_DIR" "$RESOURCES_DIR/app"
fi

if [[ ! -f "$ICON_SOURCE" ]]; then
  echo "Missing icon file: $ICON_SOURCE"
  exit 1
fi

ICONSET_DIR="$BUILD_DIR/AppIcon.iconset"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null

if ! xcrun iconutil --convert icns --output "$RESOURCES_DIR/AppIcon.icns" "$ICONSET_DIR" >/dev/null 2>&1; then
  echo "Warning: iconutil failed, trying Pillow fallback for AppIcon.icns."
  if ! python3 - "$ICON_SOURCE" "$RESOURCES_DIR/AppIcon.icns" <<'PY'
from pathlib import Path
import sys

from PIL import Image

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
img = Image.open(source).convert("RGBA")
img.save(
    destination,
    format="ICNS",
    sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512)],
)
PY
  then
    echo "Warning: failed to generate AppIcon.icns; using default app icon."
    rm -f "$RESOURCES_DIR/AppIcon.icns"
  fi
fi

cat > "$CONTENTS_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$EXECUTABLE_NAME</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>com.andrewpeterson.tiktokuploadmanager</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

plutil -lint "$CONTENTS_DIR/Info.plist" >/dev/null

echo "Built app: $APP_BUNDLE"
