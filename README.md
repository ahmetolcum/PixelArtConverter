<div align="center">

<img src="docs/logo.png" alt="Pixel Art Converter" width="256"/>

# Pixel Art Converter

### Turn AI illustrations into game-ready pixel art — single sprites or animation sheets, locally on Mac, Windows, or Linux, in seconds.

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Status](https://img.shields.io/badge/status-active-success)

**[⬇ Download Latest Release](https://github.com/ahmetolcum/PixelArtConverter/releases/latest)** — `.dmg` for macOS, `.zip` for Windows, `.tar.gz` for Linux. &nbsp;·&nbsp; [Documentation](#documentation) &nbsp;·&nbsp; [Roadmap](#roadmap)

<br/>

<img src="docs/screenshot.png" alt="App screenshot" width="900"/>

</div>

---

## What is this?

You can generate beautiful illustrations with Stable Diffusion, Midjourney, ChatGPT/DALL-E, Sora — but **game engines don't want a 1024×1024 illustration**. They want:

- **16×16 to 256×256 sprites** at exact pixel dimensions
- **Limited palettes** (8–64 colors), often a specific Lospec palette
- **Hard-edged pixels** with zero anti-aliasing
- **Clean transparent backgrounds** for compositing
- **Sprite sheets** for animation, with the **same colors across every frame** so the character doesn't flicker

Pixel Art Converter does all of that, **locally**, in seconds. Drop in your AI illustration. Get a usable game asset out.

---

## ✨ Features

### 🎨 Pixel-perfect conversion pipeline

- **Edge-preserving bilateral smoothing** — flat regions become flat without blurring shape boundaries
- **CIELAB perceptual K-means** — chosen colors look right to humans, not just statistics
- **Majority-vote downscaling** — picks the dominant palette color per source block; never blends, never produces muddy in-between pixels
- **Strict pixel-art invariants:** every pixel is fully opaque or fully transparent (no partial alpha), every RGB color is a palette-exact match

### 🌈 Lospec palette support

- **10 bundled palettes** ready to use: PICO-8, Sweetie 16, Endesga 32, Resurrect 64, AAP-64, Apollo (46), NA16, Slso8, Nyx8, Game Boy
- **Load ANY palette from Lospec** by slug (`pico-8`, `vintage-berry`) or full URL — fetched on demand and cached for the session
- **Auto K-means** mode for when you don't want to lock to a specific palette

### 🎬 Animation / sprite-sheet output

- Drop **multiple PNG frames** → get a horizontal sprite sheet
- Or drop a **single sprite sheet image** + set Rows × Cols → app splits, processes, recombines
- **Frame-coherent palette:** one shared palette across every frame, so colors don't flicker
- Filename auto-suggests `name_7frames_64x64.png` — game engines slice by reading frame size

### 🤖 AI-first workflow

- **Built-in prompt generator** with two modes (animation sprite sheet / single image) and two targets (**ChatGPT/DALL-E 3** and **Gemini/Imagen**). The Gemini variant explicitly demands iconic mascot detail, thick black outlines, gold trim, and full prop/accessory rendering — the same prompt produces noticeably plainer art on Gemini otherwise.
- **View** and **Background** dropdowns in both modes — pick from common camera angles (side, front 3/4, isometric, top-down…) and solid background colors that the converter keys out automatically.
- **Action presets** (walk, run, idle, jump, sit, sword swing, cast spell pose, hurt, death, wave) auto-fill frame-by-frame choreographies. The cast-spell preset is **pose-only with no spell visuals** — composite any spell effect in afterwards.
- **Edge-color background removal** — purpose-built for the solid-color backgrounds AI tools produce. Far more reliable than AI background removers (rembg / u2net / isnet) on stylized inputs.
- AI-failure fallbacks: if rembg can't find a subject, the app keeps the original image and warns you instead of silently deleting everything.

### 🍎 Native macOS Tahoe icon

- Ships a **layered `.icon`** (Icon Composer format) compiled into the app's `Assets.car`. macOS Tahoe (26+) renders it dynamically with light, dark, tinted, clear and glass styles — same icon, system-styled.
- Falls back to a flat `.icns` on Big Sur through Sequoia, so older Macs still get a clean app icon.

### 🔍 Pro preview

- **Pan with mouse drag** when the scaled sprite overflows the panel (open-hand cursor)
- **Nearest-neighbor zoom** at 1×, 2×, 4×, 8× — pixels stay hard-edged at every scale
- **Optional pixel grid overlay** to inspect every cell individually
- **Resizable window** — both preview panels grow with the window

### 🎛️ Fine controls

- **Brightness / Contrast / Saturation** sliders, applied pre-quantization
- **Bayer 8×8 ordered dithering** — produces handmade-looking checker patterns instead of Floyd-Steinberg noise
- **Selective outlining** — outline color is a darkened version of the adjacent material's color (in CIELAB), automatically snapped to the active palette
- **Multiple background-removal methods** — rembg AI (`isnet-general-use`, `isnet-anime`, `u2net`, `u2net_human_seg`) or color-key keying

> **Background-removal model downloads.**
> - **macOS DMG (v2.0+):** the default `isnet-general-use` model (~170 MB) is **bundled** in the app, so first-run BG removal works immediately and offline. The other three models still download lazily into `~/.u2net/` the first time you pick them.
> - **Windows / Linux:** none of the rembg models are bundled — each one downloads from GitHub the first time you select it (~170 MB per model, ~700 MB total if you try them all) and caches in `~/.u2net/` (or `%USERPROFILE%\.u2net\` on Windows). The app shows a progress dialog and you can cancel it.
> - **All platforms:** the default **Edge color (auto)** option needs no model download and works fully offline.

---

## 🚀 Quick Start

Grab the build for your OS from **[the latest release](https://github.com/ahmetolcum/PixelArtConverter/releases/latest)**, then jump to the matching section below.

### 🍎 macOS — `.dmg` (402 MB, Apple Silicon)

1. Open `PixelArtConverter-2.0.0.dmg`, drag **Pixel Art Converter** into your **Applications** folder.
2. First launch: see [Opening an unsigned macOS app](#opening-an-unsigned-macos-app--first-launch-only) below.
3. **Drop a PNG** into the app, pick your output size and palette, click **Save Pixel Art PNG**. Done.

The macOS DMG bundles the default rembg background-removal model, so BG removal works on first launch with no download.

### 🪟 Windows — `.zip` (363 MB, x64)

1. Right-click `PixelArtConverter-windows-x64.zip` → **Extract All…** (or use 7-Zip).
2. Double-click `PixelArtConverter.exe`.
3. **Windows SmartScreen** will warn that the publisher is unrecognized — click **More info** → **Run anyway**. (The exe is not yet signed; future releases may include an authenticode signature.)
4. **Drop a PNG** into the app, pick your output size and palette, click **Save**. Done.

The first time you pick an AI background-removal model (other than the default **Edge color**), it downloads ~170 MB from GitHub and caches in `%USERPROFILE%\.u2net\`. Subsequent runs are instant.

### 🐧 Linux — `.tar.gz` (426 MB, x64)

```bash
tar -xzf PixelArtConverter-linux-x64.tar.gz
chmod +x PixelArtConverter
./PixelArtConverter
```

If the binary fails with a missing-library error, install the Qt runtime libs your distro typically uses:

```bash
# Debian / Ubuntu
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 \
    libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
    libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxcb1 libfontconfig1
```

Same lazy model-download behavior as Windows: BG removal models cache in `~/.u2net/`.

### 🎬 Animation (any platform)

Drop multiple PNGs at once (or tick **Sprite Sheet** and drop one grid image), and **Save** produces a sprite sheet PNG with palette-coherent colors across every frame.

### Opening an unsigned macOS app — first launch only

The macOS build is **not yet signed** with an Apple Developer certificate (signing/notarization is on the roadmap). On first launch, macOS Gatekeeper will refuse to open the app and show one of these messages:

> *"Pixel Art Converter" cannot be opened because the developer cannot be verified.*

> *"Pixel Art Converter" is damaged and can't be opened. You should move it to the Trash.* (This appears on Sequoia/Tahoe; the app is not actually damaged — Gatekeeper marks unsigned downloads with a quarantine flag.)

You only need to do **one** of the following the **first time** you launch. After that, the app opens normally with a double-click.

**Option A — Right-click → Open (works on all macOS versions):**

1. **Right-click** (or two-finger click / Control-click) the app in Applications → choose **Open**
2. Click **Open** in the confirmation dialog
3. Done. Future launches work normally.

**Option B — System Settings (if Option A doesn't appear):**

1. Try to open the app normally; macOS will block it
2. Open **System Settings → Privacy & Security**, scroll to **Security**
3. You'll see *"'Pixel Art Converter' was blocked from use…"* — click **Open Anyway**
4. Re-launch the app, click **Open** in the confirmation

**Option C — Terminal (Sequoia / Tahoe, when the "damaged" message appears):**

If you installed to **`/Applications/`** (system-wide, the usual place from drag-to-Applications):

```bash
xattr -dr com.apple.quarantine "/Applications/Pixel Art Converter.app"
```

If you installed to **`~/Applications/`** (your user folder):

```bash
xattr -dr com.apple.quarantine ~/Applications/Pixel\ Art\ Converter.app
```

If you're not sure where it is, this finds it and clears the flag wherever it lives:

```bash
sudo xattr -dr com.apple.quarantine "$(mdfind 'kMDItemFSName == "Pixel Art Converter.app"' | head -1)"
```

Any of these removes the quarantine flag set on downloads. Then double-click the app — it opens normally.

This is **standard for unsigned indie apps**. The app does nothing it doesn't claim — all source is in this repo.

### Verify the download (optional)

To verify a downloaded build matches what's published:

```bash
# macOS
shasum -a 256 ~/Downloads/PixelArtConverter-2.0.0.dmg
# expected: 202e7b7f896597804fe685c9e9c7fbf26512c32371e67fc4dda616fb1d5a7193

# Linux
sha256sum PixelArtConverter-linux-x64.tar.gz
# expected: 724ab9d4eab972fb6a36b6e04e3abe03bb078964358b37f9b185503a2b7e757c
```

```powershell
# Windows (PowerShell)
Get-FileHash PixelArtConverter-windows-x64.zip -Algorithm SHA256
# expected: 181D5AE282A68FF1907A8937201A3CBFF24E48E57AA4134C0AA10ED1502D6E03
```

---

## 🎯 Who is this for?

| User | Why it helps |
|---|---|
| **Indie game devs** | Turn AI-generated concept art into Unity/Godot/GameMaker-ready sprite sheets without leaving the desktop. |
| **AI artists** | Finish your generations: get clean palette-quantized exports with proper transparency. |
| **Pixel artists** | Skip Photoshop's quantize dialog. Lospec palettes, dithering, and outlining built in. |
| **Asset packers** | Ship multiple resolutions and palettes from one source illustration with a couple of clicks. |
| **Hobbyists** | Experiment with retro Game Boy / NES looks on photos and modern art. |

---

## 📚 Documentation

### Two ways to provide animation frames

**A. Multiple separate PNGs**

- Drop multiple files at once, or shift-click in the open dialog to multi-select.
- Files are sorted alphabetically. Name them `walk_01.png`, `walk_02.png`, etc.
- App processes each frame and composes a horizontal sprite sheet.

**B. A single sprite-sheet image**

- Tick the **Sprite Sheet** checkbox.
- Set **Cols × Rows** to match the input grid.
- Drop a single PNG. The app splits, processes, and recomposes.

In both modes, **one shared palette** is built across all frames so colors don't flicker.

### Settings reference

| Control | Effect |
|---|---|
| **Preset / W × H** | Output sprite dimensions |
| **Lock** | Keeps W:H aspect ratio when editing |
| **Colors** | Auto-mode palette size (4–64) |
| **Palette** | Auto K-means or a Lospec palette |
| **Bright / Contr / Sat** | Pre-quantization adjustments (−100 to +100) |
| **Dithering** | 8×8 Bayer ordered dither |
| **Remove Background** | Background removal toggle |
| **Model** | rembg AI model OR Edge-color (auto) keying |
| **Selective Outline** | Hue-aware 1px outline |
| **Preview Scale / Grid** | Visual zoom + pixel grid |
| **Sprite Sheet** | Single image dropped is split by Cols × Rows |

### Mouse controls

- **Drag** preview panels to pan when content overflows
- Cursor turns into open-hand when panning is available

### Generating input with AI

The app includes an **AI Prompt Samples** button that opens a window where you can:

- Pick **Type**: animation frames sprite sheet, or a single image
- Pick **Target** model: **ChatGPT (DALL-E 3)** or **Gemini (Imagen)** — the templates differ. Gemini's variant pushes harder for iconic mascot detail, thick outlines, gold trim, and explicit accessories, since the same prompt tends to give plainer art on Gemini otherwise.
- Pick an **Action preset** (walk, run, idle, jump, sit, sword swing, cast spell pose, hurt, death, wave) for a ready-made frame-by-frame choreography
- Fill in **Subject** (the character/object that must stay identical), **View** (camera angle), and **Background** (solid color the converter keys out)
- For frames mode: **Frame count (N)** and a per-frame **Action** description

Variables are colored in blue in the live-rendered prompt so you can see at a glance what's yours vs boilerplate. Click **Copy Prompt** and paste into ChatGPT or Gemini.

---

## 👨‍💻 For developers

### Source layout

The codebase splits into one shared core and two GUIs — pick the one that fits your platform when contributing.

| File | What it is | Used by |
|---|---|---|
| `core.py` | Pure image-processing pipeline, palette tables, prompt templates, presets. No GUI imports. | both apps |
| `pixel_art_converter.py` | macOS-native GUI built on PyObjC + AppKit. | the `.dmg` build |
| `pixel_art_converter_qt.py` | Cross-platform PySide6 GUI. | the Windows `.zip` and Linux `.tar.gz` builds |
| `setup.py` | py2app config for the macOS bundle. | `build_dmg.sh` |
| `pixel_art_converter_qt.spec` | PyInstaller spec for the Qt bundle. | `.github/workflows/release.yml` |
| `requirements.txt` | Cross-platform Qt runtime deps. | Qt source-runs and PyInstaller |

PRs that change conversion behavior (palettes, smoothing, dithering, BG removal, sprite-sheet handling) land in `core.py` and benefit both apps. PRs that change UI land in the relevant `pixel_art_converter*.py` file.

### Run from source

**macOS — native AppKit GUI:**

```bash
git clone https://github.com/ahmetolcum/PixelArtConverter.git
cd PixelArtConverter
pip3 install Pillow numpy scikit-image scikit-learn scipy pyobjc "rembg[cpu]"
python3 pixel_art_converter.py
```

**Windows — PySide6 GUI** (PowerShell or `cmd`, requires Python 3.10+):

```powershell
git clone https://github.com/ahmetolcum/PixelArtConverter.git
cd PixelArtConverter
py -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe pixel_art_converter_qt.py
```

No `git`? Download the source ZIP directly and skip the `git clone` step:

```cmd
curl -L -o pac.zip https://github.com/ahmetolcum/PixelArtConverter/archive/refs/heads/main.zip
tar -xf pac.zip
cd PixelArtConverter-main
```

**Linux — PySide6 GUI:**

```bash
git clone https://github.com/ahmetolcum/PixelArtConverter.git
cd PixelArtConverter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python pixel_art_converter_qt.py
```

### Build distributable binaries

**macOS DMG** (requires Xcode command-line tools for `actool`/`codesign`/`hdiutil`):

```bash
pip3 install py2app pyobjc-core pyobjc-framework-Cocoa
./build_dmg.sh
# Output: build/PixelArtConverter-<version>.dmg
```

`build_dmg.sh` compiles the layered Tahoe icon (or uses the pre-compiled assets in `docs/compiled-icons/` if Xcode 26 isn't available), runs py2app, bundles the default `isnet-general-use` rembg model into `Resources/u2net/`, re-signs ad-hoc, and produces a UDZO DMG.

**Windows / Linux PyInstaller bundles** are produced by the GitHub Actions workflow (`.github/workflows/release.yml`) on every `vX.Y.Z` tag push. To build locally:

```bash
pip install pyinstaller
pip install -r requirements.txt
pyinstaller --noconfirm pixel_art_converter_qt.spec
# Output: dist/PixelArtConverter (or .exe on Windows)
```

### Cutting a release

1. Bump `core.__version__` (and `setup.py`'s `CFBundleVersion` / `CFBundleShortVersionString` to match).
2. Push to `main`.
3. Tag `vX.Y.Z` and push the tag — the release workflow builds Windows + Linux + macOS in parallel and creates the GitHub Release.
4. After the release goes live, pin `update.json` and the README's verify hashes to the new SHA256s so the macOS in-app updater promotes the new version to existing 1.x users.

---

## 🗺️ Roadmap

**Shipped in v2.0**
- [x] Cross-platform port — PySide6 GUI for Windows + Linux, alongside the macOS native build
- [x] Default rembg model bundled into the macOS DMG (no first-run download)
- [x] Single GitHub Actions workflow that releases all three platforms on tag push
- [x] Shared `core.py` so both GUIs use the exact same conversion pipeline

**Planned**
- [ ] Notarized & signed `.dmg` (no more Gatekeeper friction)
- [ ] Authenticode-signed `.exe` (no more SmartScreen warning)
- [ ] Animated GIF export option
- [ ] Frame-by-frame preview scrubbing with FPS slider
- [ ] Sprite sheet grid auto-detection
- [ ] Batch CLI mode for headless conversion

---

## 🛠️ Built with

[Python](https://www.python.org/) · [PyObjC](https://pyobjc.readthedocs.io/) (macOS GUI) · [PySide6 / Qt](https://doc.qt.io/qtforpython-6/) (Windows + Linux GUI) · [Pillow](https://pillow.readthedocs.io/) · [scikit-image](https://scikit-image.org/) · [scikit-learn](https://scikit-learn.org/) · [rembg](https://github.com/danielgatis/rembg) · [Lospec](https://lospec.com/) · [py2app](https://py2app.readthedocs.io/) · [PyInstaller](https://pyinstaller.org/)

---

## 🤝 Contributing

Pull requests welcome. For substantial changes, open an issue first to discuss.

The app deliberately doesn't try to do creative-judgment tasks (light source detection, "smooth jagged curves," three-colors-per-material enforcement). Those need a human in Aseprite/Krita. PRs that add such heuristics are likely to be declined unless they ship with a kill-switch and don't degrade the simple cases.

---

## 📜 License

MIT — see [LICENSE](LICENSE).

Lospec palettes are © their respective creators and are bundled here under their permitted reuse terms (most are CC0 or fair-use compatible). If you're a palette author and want yours removed, please open an issue.
