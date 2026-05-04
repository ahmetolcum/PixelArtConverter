#!/usr/bin/env bash
# Build Pixel Art Converter as a macOS .app + DMG.
#
# Pipeline:
#   1. Generate AppIcon.icns from docs/icon.png (for pre-Tahoe macOS)
#   2. py2app builds the .app bundle (embeds the .icns)
#   3. Copy docs/AppIcon.icon (the Tahoe layered icon) into the bundle
#   4. hdiutil creates a UDZO-compressed DMG
#   5. Print the DMG SHA256 (paste into update.json + release notes)
#
# Usage:  ./build_dmg.sh

set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(grep -E '^__version__' pixel_art_converter.py | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
echo "▶ Building Pixel Art Converter v${VERSION}"

APP_NAME="Pixel Art Converter"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="build/PixelArtConverter-${VERSION}.dmg"

# 1. Build AppIcon.icns from docs/icon.png
echo "▶ Generating AppIcon.icns from docs/icon.png"
ICONSET=build/AppIcon.iconset
rm -rf "$ICONSET" build/AppIcon.icns
mkdir -p "$ICONSET"
for size in 16 32 64 128 256 512 1024; do
  sips -z $size $size docs/icon.png --out "$ICONSET/icon_${size}x${size}.png" > /dev/null
done
cp "$ICONSET/icon_32x32.png"     "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"     "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png"   "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png"   "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
rm -f "$ICONSET/icon_64x64.png" "$ICONSET/icon_1024x1024.png"
iconutil -c icns "$ICONSET" -o build/AppIcon.icns
rm -rf "$ICONSET"

# 2. py2app
echo "▶ py2app — building .app (this can take a few minutes)…"
rm -rf "$APP_PATH" dist build/PixelArtConverter-*.dmg
python3 setup.py py2app > /dev/null
echo "  ✓ ${APP_PATH}"

# 3. Copy the Tahoe layered .icon into Resources
echo "▶ Copying docs/AppIcon.icon into the bundle (for Tahoe icon-style support)"
cp -R docs/AppIcon.icon "${APP_PATH}/Contents/Resources/AppIcon.icon"

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
