#!/usr/bin/env bash
# Build Pixel Art Converter as a macOS .app + DMG.
#
# Pipeline:
#   1. actool compiles docs/AppIcon.icon → build/AppIcon.icns + build/Assets.car
#      (.icns = pre-Tahoe fallback, Assets.car = Tahoe layered/styled icon)
#   2. py2app builds the .app bundle (embeds the .icns via setup.py iconfile)
#   3. Drop Assets.car into Resources and set CFBundleIconName so Tahoe loads
#      the layered icon from the asset catalog at runtime
#   4. hdiutil creates a UDZO-compressed DMG
#   5. Print the DMG SHA256 (paste into update.json + release notes)
#
# Usage:  ./build_dmg.sh

set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(grep -E '^__version__' core.py | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
echo "▶ Building Pixel Art Converter v${VERSION}"

APP_NAME="Pixel Art Converter"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="build/PixelArtConverter-${VERSION}.dmg"

# 1. Source the icon assets. Tahoe .icon → Assets.car compilation needs
#    Xcode 26 (only available on macOS 26+ runners). For portability across
#    CI macOS-15 runners and local macOS 26 boxes, prefer the pre-compiled
#    assets checked into docs/compiled-icons/. When the source .icon
#    changes, regenerate them locally via the actool command below and
#    copy the outputs into docs/compiled-icons/.
mkdir -p build
COMPILED_DIR=docs/compiled-icons
if [ -f "$COMPILED_DIR/AppIcon.icns" ] && [ -f "$COMPILED_DIR/Assets.car" ]; then
  echo "▶ Using pre-compiled icon assets from $COMPILED_DIR/"
  cp "$COMPILED_DIR/AppIcon.icns" build/AppIcon.icns
  cp "$COMPILED_DIR/Assets.car"   build/Assets.car
else
  echo "▶ Compiling docs/AppIcon.icon via actool (committed assets missing)"
  ICON_OUT=build/icon-compile
  rm -rf "$ICON_OUT" build/AppIcon.icns build/Assets.car build/icon-info.plist
  mkdir -p "$ICON_OUT"
  xcrun actool --compile "$ICON_OUT" \
    --platform macosx \
    --minimum-deployment-target 11.0 \
    --app-icon AppIcon \
    --output-partial-info-plist build/icon-info.plist \
    --output-format human-readable-text \
    --errors --warnings \
    docs/AppIcon.icon > /dev/null
  cp "$ICON_OUT/AppIcon.icns" build/AppIcon.icns
  cp "$ICON_OUT/Assets.car"   build/Assets.car
  rm -rf "$ICON_OUT"
fi

# 2. py2app
echo "▶ py2app — building .app (this can take a few minutes)…"
rm -rf "$APP_PATH" dist build/PixelArtConverter-*.dmg
python3 setup.py py2app > /dev/null
echo "  ✓ ${APP_PATH}"

# 3. Install the Tahoe layered icon: copy Assets.car and set CFBundleIconName.
#    Without Assets.car + CFBundleIconName, Tahoe falls back to the flat .icns
#    and ignores the layered/glass styling.
echo "▶ Installing Assets.car into the bundle (for Tahoe layered-icon support)"
cp build/Assets.car "${APP_PATH}/Contents/Resources/Assets.car"
plutil -replace CFBundleIconFile -string "AppIcon" "${APP_PATH}/Contents/Info.plist"
plutil -replace CFBundleIconName -string "AppIcon" "${APP_PATH}/Contents/Info.plist"

# 3c. Bundle the default rembg model so first-run users don't have to wait
#     for a 170 MB download before they can use background removal. Other
#     three models (isnet-anime, u2net, u2net_human_seg) still download
#     lazily into ~/.u2net the way they always have.
echo "▶ Bundling default rembg model (isnet-general-use)…"
python3 -c "from rembg import new_session; new_session('isnet-general-use')" > /dev/null
mkdir -p "${APP_PATH}/Contents/Resources/u2net"
cp "${HOME}/.u2net/isnet-general-use.onnx" \
   "${APP_PATH}/Contents/Resources/u2net/isnet-general-use.onnx"
echo "  ✓ isnet-general-use.onnx ($(du -h "${APP_PATH}/Contents/Resources/u2net/isnet-general-use.onnx" | awk '{print $1}'))"

# 3d. Re-sign ad-hoc. Modifying the bundle after py2app's signing invalidates
#     the original signature, which Apple Silicon enforces — the app would
#     SIGKILL on launch with "Code Signature Invalid".
echo "▶ Re-signing bundle ad-hoc"
codesign --force --deep --sign - "${APP_PATH}" > /dev/null
codesign --verify --verbose "${APP_PATH}" 2>&1 | head -2

# 4. Build the DMG
echo "▶ Creating DMG…"
hdiutil create -volname "${APP_NAME}" \
  -srcfolder "${APP_PATH}" \
  -ov -format UDZO \
  "$DMG_PATH" > /dev/null
echo "  ✓ ${DMG_PATH}"

# 5. Hash + size summary
SHA=$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')
SIZE_MB=$(du -m "$DMG_PATH" | awk '{print $1}')
echo ""
echo "▶ Build complete"
echo "  DMG:    $DMG_PATH"
echo "  Size:   ${SIZE_MB} MB"
echo "  SHA256: $SHA"
echo ""
echo "Next steps:"
echo "  1. Update update.json:  sed -i '' \"s/SHA_OLD/${SHA}/\" update.json"
echo "  2. Update README + release notes with the new SHA"
echo "  3. Upload:              gh release upload v${VERSION} ${DMG_PATH} --clobber"
