#!/usr/bin/env python3
"""Pixel Art Converter — transparent, outlined pixel art for 2D games."""

import io
import os
import subprocess
import tempfile
import threading
import urllib.request

import objc
import numpy as np
from AppKit import (
    NSApplication, NSApplicationActivationPolicyRegular,
    NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable, NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSView, NSButton, NSTextField, NSImageView, NSBox, NSSlider,
    NSPopUpButton, NSOpenPanel, NSSavePanel, NSPasteboard,
    NSColor, NSFont, NSBezierPath, NSRectFill, NSImage,
    NSSwitchButton, NSOnState,
    NSBezelStyleRounded,
    NSImageScaleProportionallyUpOrDown, NSImageAlignCenter,
    NSBoxSeparator, NSTextAlignmentCenter,
    NSDragOperationCopy, NSDragOperationNone, NSFilenamesPboardType,
    NSModalResponseOK,
    NSForegroundColorAttributeName, NSFontAttributeName,
    NSAppearance, NSGraphicsContext,
    NSAlert, NSAlertFirstButtonReturn,
    NSMenu, NSMenuItem,
    NSCursor,
    NSTextView, NSScrollView, NSAttributedString, NSMutableAttributedString,
    NSComboBox,
)
from Foundation import NSMakeRange
from Foundation import NSObject, NSData, NSMakeRect, NSMakePoint, NSString, NSProcessInfo
from PIL import Image


# ── Lospec palettes ───────────────────────────────────────────────────────

# Hex strings; lower-case, no '#'. Bundled directly so it works offline.
LOSPEC_PALETTES: dict = {
    "Auto (K-means)": None,

    "Game Boy (4)": ["0f380f","306230","8bac0f","9bbc0f"],

    "Slso8 (8)": ["0d2b45","203c56","544e68","8d697a",
                  "d08159","ffaa5e","ffd4a3","ffecd6"],

    "Nyx8 (8)": ["08141e","0f2a3f","20394f","f6d6bd",
                 "c3a38a","997577","816271","4e495f"],

    "PICO-8 (16)": ["000000","1d2b53","7e2553","008751",
                    "ab5236","5f574f","c2c3c7","fff1e8",
                    "ff004d","ffa300","ffec27","00e436",
                    "29adff","83769c","ff77a8","ffccaa"],

    "Sweetie 16": ["1a1c2c","5d275d","b13e53","ef7d57",
                   "ffcd75","a7f070","38b764","257179",
                   "29366f","3b5dc9","41a6f6","73eff7",
                   "f4f4f4","94b0c2","566c86","333c57"],

    "NA16": ["8c8fae","584563","3e2137","9a6348",
             "d79b7d","f5edba","c0c741","647d34",
             "e4943a","9d303b","d26471","70377f",
             "7ec4c1","34859d","17434b","1f0e1c"],

    "Endesga 32": ["be4a2f","d77643","ead4aa","e4a672",
                   "b86f50","733e39","3e2731","a22633",
                   "e43b44","f77622","feae34","fee761",
                   "63c74d","3e8948","265c42","193c3e",
                   "124e89","0099db","2ce8f5","ffffff",
                   "c0cbdc","8b9bb4","5a6988","3a4466",
                   "262b44","181425","ff0044","68386c",
                   "b55088","f6757a","e8b796","c28569"],

    "Apollo (46)": ["172038","253a5e","3c5e8b","4f8fba",
                    "73bed3","a4dddb","19332d","25562e",
                    "468232","75a743","a8ca58","d0da91",
                    "4d2b32","7a4841","ad7757","c09473",
                    "d7b594","e7d5b3","341c27","602c2c",
                    "884b2b","be772b","de9e41","e8c170",
                    "241527","411d31","752438","a53030",
                    "cf573c","da863e","1e1d39","402751",
                    "7a367b","a23e8c","c65197","df84a5",
                    "090a14","10141f","151d28","202e37",
                    "394a50","577277","819796","a8b5b2",
                    "c7cfcc","ebede9"],

    "Resurrect 64": ["2e222f","3e3546","625565","966c6c",
                     "ab947a","694f62","7f708a","9babb2",
                     "c7dcd0","ffffff","6e2727","b33831",
                     "ea4f36","f57d4a","ae2334","e83b3b",
                     "fb6b1d","f79617","f9c22b","7a3045",
                     "9e4539","cd683d","e6904e","fbb954",
                     "4c3e24","676633","a2a947","d5e04b",
                     "fbff86","165a4c","239063","1ebc73",
                     "91db69","cddf6c","313638","374e4a",
                     "547e64","92a984","b2ba90","0b5e65",
                     "0b8a8f","0eaf9b","30e1b9","8ff8e2",
                     "323353","484a77","4d65b4","4d9be6",
                     "8fd3ff","45293f","6b3e75","905ea9",
                     "a884f3","eaaded","753c54","a24b6f",
                     "cf657f","ed8099","831c5d","c32454",
                     "f04f78","f68181","fca790","fdcbb0"],

    "AAP-64": ["060608","141013","3b1725","73172d",
               "b4202a","df3e23","fa6a0a","f9a31b",
               "ffd541","fffc40","d6f264","9cdb43",
               "59c135","14a02e","1a7a3e","24523b",
               "122020","143464","285cc4","249fde",
               "20d6c7","a6fcdb","ffffff","fef3c0",
               "fad6b8","f5a097","e86a73","bc4a9b",
               "793a80","403353","242234","221c1a",
               "322b28","71413b","bb7547","dba463",
               "f4d29c","dae0ea","b3b9d1","8b93af",
               "6d758d","4a5462","333941","422433",
               "5b3138","8e5252","ba756a","e9b5a3",
               "e3e6ff","b9bffb","849be4","588dbe",
               "477d85","23674e","328464","5daf8d",
               "92dcba","cdf7e2","e4d2aa","c7b08b",
               "a08662","796755","5a4e44","423934"],
}

LOSPEC_LOAD_OPTION = "Load from Lospec…"


def _hex_to_rgb(h: str) -> tuple:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _palette_to_rgb_array(hex_list) -> np.ndarray:
    return np.array([_hex_to_rgb(h) for h in hex_list], dtype=np.uint8)


def fetch_lospec_palette(slug_or_url: str) -> tuple:
    """
    Returns (display_name, hex_list).
    Accepts either a slug ('pico-8') or a full URL
    ('https://lospec.com/palette-list/pico-8' or .../pico-8.hex).
    """
    s = slug_or_url.strip()
    if s.startswith("http"):
        url = s
        slug = url.rstrip("/").split("/")[-1].replace(".hex", "")
    else:
        slug = s.lower().strip("/")
        url = f"https://lospec.com/palette-list/{slug}.hex"
    if not url.endswith(".hex"):
        url = url.rstrip("/") + ".hex"

    req = urllib.request.Request(url, headers={"User-Agent": "PixelArtConverter/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    hex_list = []
    for line in text.splitlines():
        line = line.strip().lstrip("#")
        if len(line) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in line):
            hex_list.append(line.lower())
    if not hex_list:
        raise ValueError("No colors found in palette response")

    name = slug.replace("-", " ").title() + f" ({len(hex_list)})"
    return name, hex_list


def _quantize_to_palette_lab(img: Image.Image, palette_rgb: np.ndarray) -> Image.Image:
    """Map every pixel to the nearest palette color in CIELAB (perceptual)."""
    from skimage.color import rgb2lab
    arr   = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    h, w  = arr.shape[:2]
    pix_lab = rgb2lab(arr).reshape(-1, 3).astype(np.float32)

    pal_lab = rgb2lab(
        (palette_rgb.astype(np.float32) / 255.0).reshape(1, -1, 3)
    ).reshape(-1, 3).astype(np.float32)

    out_idx = np.zeros(len(pix_lab), dtype=np.int32)
    chunk = 100_000
    for i in range(0, len(pix_lab), chunk):
        c   = pix_lab[i:i+chunk]
        d2  = ((c[:, None, :] - pal_lab[None, :, :]) ** 2).sum(axis=-1)
        out_idx[i:i+chunk] = np.argmin(d2, axis=1)

    out_rgb = palette_rgb[out_idx].reshape(h, w, 3)
    return Image.fromarray(out_rgb, "RGB")


# ── Image processing ──────────────────────────────────────────────────────

_rembg_sessions: dict = {}
_last_rembg_status = "ok"   # "ok" | "fallback" — read by the UI thread

# ── App version + auto-update endpoint ────────────────────────────────────
# Bump __version__ on every release. The update endpoint hosts a tiny JSON
# manifest of the latest version + download URL + SHA256.
__version__ = "1.2.0"
_UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/ahmetolcum/"
    "PixelArtConverter/main/update.json"
)


def _version_tuple(v: str):
    """Parse '1.10.2' → (1, 10, 2). Trailing non-digit segments are ignored."""
    parts = []
    for seg in str(v).split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) if parts else (0,)

EDGE_COLOR_OPTION = "Edge color (auto)"


# ── Prompt templates for the AI Prompt Samples window ─────────────────────
# Variables are wrapped in {NAME} so the template can be rendered with values
# and we can color those substitutions in the in-app preview.
#
# Each (mode, target) pair has its own template. ChatGPT/DALL-E follows
# loose stylistic prose well; Gemini/Imagen tends to produce plainer, more
# generic art with the same prompt — so the Gemini variants push harder for
# iconic mascot detail, thick outlines, gold trim, and explicit accessories.

PROMPT_TEMPLATE_FRAMES_CHATGPT = """Generate a single horizontal sprite sheet image showing {N} frames of {SUBJECT} performing {ACTION}. Lay the frames left-to-right in one row, all identical in size, no labels, captions, numbers or borders between them.

HARD RULES (critical for animation consistency):
• Identical {SUBJECT} in every frame — same proportions, same outfit, same color of every part. The ONLY differences between frames are the body parts (or features) actively moving for this action.
• {VIEW} view of the subject. Identical camera angle, identical scale, identical position. The character's center point must be in the same pixel position in every frame's bounding box.
• Identical lighting direction — shadows fall the same way in every frame.
• Background: ONE uniform solid color across all frames (use {BACKGROUND}). No gradient, no scenery, no shadows on the background. The converter app keys this color out automatically.

STYLE:
• Clean cel-shaded illustration, bold outlines, flat colors with one shadow + one highlight per material. NOT pixel art. NOT photorealistic. NOT painterly.
• Limited palette: 6 to 10 distinct colors total. No gradients within shapes.

OUTPUT:
• Roughly {N}×512 wide × 512 tall ({N} square frames at 512×512 each). PNG.
• Subject centered in each frame with ~10% padding.

DO NOT include: frame numbers, text labels, watermarks, transparency, multiple rows, decorative borders."""

PROMPT_TEMPLATE_FRAMES_GEMINI = """Generate a single horizontal sprite sheet image showing {N} frames of {SUBJECT} performing {ACTION}, drawn in the iconic mascot art style of a 2D platformer game. Lay the frames left-to-right in one row, all identical in size, no labels, captions, numbers or borders between them.

ART DIRECTION (must match exactly — do not simplify):
• Bold, thick, uniform black outlines around every shape and every internal detail. Fully closed contours.
• Saturated, vivid colors. Add gold or cream-colored trim to robes, belts, hats, capes and boots when relevant for visual identity. Add brown leather for footwear and belts.
• Cel shading: ONE solid shadow tone + ONE solid highlight tone per material. No gradients, no airbrush blending.
• Iconic, recognizable, mascot-style character with strong silhouette, clear personality, and rich visual identity — NOT a plain or generic interpretation.
• Render every detail of {SUBJECT} explicitly: props, accessories, age cues (white beard, wrinkles), facial features (visible eyes), clothing trim, footwear. If the subject is a wizard, include a wooden staff with a colored orb on top.

HARD RULES (critical for animation consistency):
• Identical {SUBJECT} in every frame — same proportions, same outfit, same color of every part. The ONLY differences between frames are the body parts (or features) actively moving for this action.
• {VIEW} view of the subject. Identical camera angle, identical scale, identical position. The character's center point must be in the same pixel position in every frame's bounding box.
• Identical lighting direction — shadows fall the same way in every frame.
• Background: ONE uniform solid color across all frames (use {BACKGROUND}). No gradient, no scenery, no shadows on the background. The converter app keys this color out automatically.

OUTPUT:
• Roughly {N}×512 wide × 512 tall ({N} square frames at 512×512 each). PNG.
• Subject centered in each frame with ~10% padding.

DO NOT include: frame numbers, text labels, watermarks, transparency, multiple rows, decorative borders, plain or under-detailed characters, soft pastel coloring, sketch-style linework."""

PROMPT_DEFAULTS_FRAMES = {
    "N":          "4",
    "SUBJECT":    "a small wizard with a long blue robe and a pointed hat",
    "ACTION":     ("a walk cycle: left foot forward (frame 1), both feet together passing (frame 2), "
                   "right foot forward (frame 3), both feet together passing (frame 4)"),
    "VIEW":       "side profile (right)",
    "BACKGROUND": "dark teal #1a3a4a",
}

# Single-image mode — generate one illustration ready to be turned into a single
# pixel-art sprite. Uses the same flat-shaded / solid-background style so the
# converter's edge-color BG removal and palette quantization work cleanly.

PROMPT_TEMPLATE_SINGLE_CHATGPT = """Generate a single illustration of {SUBJECT}, designed to be converted into a pixel-art sprite by an external tool.

COMPOSITION:
• {SUBJECT} centered in the image with about 10% padding from every edge.
• {VIEW} view of the subject.
• Single subject only — no additional scenery, no other objects, no UI elements, no text.

STYLE:
• Clean cel-shaded illustration, bold outlines, flat colors with ONE shadow tone + ONE highlight tone per material. NOT pixel art. NOT photorealistic. NOT painterly.
• Limited palette: 6 to 10 distinct colors total. No gradients within shapes.

BACKGROUND:
• ONE uniform solid color across the entire background (use {BACKGROUND}).
• No gradient, no scenery, no shadows on the background — completely flat. The converter app keys this color out automatically.

OUTPUT:
• Square 1024×1024 PNG.
• {SUBJECT} occupies about 80% of the canvas.

DO NOT include: text labels, watermarks, transparency, decorative borders, frame numbers."""

PROMPT_TEMPLATE_SINGLE_GEMINI = """Generate a single illustration of {SUBJECT}, drawn in the iconic mascot art style of a 2D platformer game, designed to be converted into a pixel-art sprite by an external tool.

ART DIRECTION (must match exactly — do not simplify):
• Bold, thick, uniform black outlines around every shape and every internal detail. Fully closed contours.
• Saturated, vivid colors. Add gold or cream-colored trim to robes, belts, hats, capes and boots when relevant for visual identity. Add brown leather for footwear and belts.
• Cel shading: ONE solid shadow tone + ONE solid highlight tone per material. No gradients, no airbrush blending.
• Iconic, recognizable, mascot-style character with strong silhouette, clear personality, and rich visual identity — NOT a plain or generic interpretation.
• Render every detail of {SUBJECT} explicitly: props, accessories, age cues (white beard, wrinkles), facial features (visible eyes), clothing trim, footwear. If the subject is a wizard, include a wooden staff with a colored orb on top.

COMPOSITION:
• {SUBJECT} centered in the image with about 10% padding from every edge.
• {VIEW} view of the subject.
• Single subject only — no additional scenery, no other objects, no UI elements, no text.

BACKGROUND:
• ONE uniform solid color across the entire background (use {BACKGROUND}).
• No gradient, no scenery, no shadows on the background — completely flat. The converter app keys this color out automatically.

OUTPUT:
• Square 1024×1024 PNG.
• {SUBJECT} occupies about 80% of the canvas.

DO NOT include: text labels, watermarks, transparency, decorative borders, frame numbers, plain or under-detailed characters, soft pastel coloring, sketch-style linework."""

PROMPT_DEFAULTS_SINGLE = {
    "SUBJECT":    "a small wizard with a long blue robe and a pointed hat, holding a glowing staff",
    "VIEW":       "front-facing 3/4",
    "BACKGROUND": "dark teal #1a3a4a",
}

# (mode, target) → template. Mode is "frames" or "single"; target is "chatgpt"
# or "gemini". The default target is ChatGPT since the original templates were
# tuned for DALL-E.
PROMPT_TEMPLATES = {
    ("frames", "chatgpt"): PROMPT_TEMPLATE_FRAMES_CHATGPT,
    ("frames", "gemini"):  PROMPT_TEMPLATE_FRAMES_GEMINI,
    ("single", "chatgpt"): PROMPT_TEMPLATE_SINGLE_CHATGPT,
    ("single", "gemini"):  PROMPT_TEMPLATE_SINGLE_GEMINI,
}

# Quick-pick presets for the AI Prompt Samples window.
# View / background are NSComboBox values — users can also type custom text.
VIEW_PRESETS = [
    "front-facing 3/4",
    "straight-on front",
    "side profile (right)",
    "side profile (left)",
    "back 3/4",
    "back view",
    "top-down",
    "isometric",
    "close-up portrait",
    "low-angle hero shot",
]

BACKGROUND_PRESETS = [
    "dark teal #1a3a4a",
    "navy blue #0a2540",
    "pure black #000000",
    "pure white #ffffff",
    "warm grey #5c5c5c",
    "pastel pink #ffd1dc",
    "lime green #00ff00",
    "magenta #ff00ff",
    "deep purple #2b1a3d",
    "forest green #1f3d2b",
]

# Frame-by-frame action choreographies. Selecting one auto-fills both the
# Frame count (N) and the Action multiline. ("Custom" leaves the fields alone.)
ACTION_PRESETS = {
    "Custom — keep current values": (None, None),

    "Walk cycle (4 frames)": (4,
        "a walk cycle: left foot forward and right arm forward (frame 1); "
        "both feet together passing through neutral pose (frame 2); "
        "right foot forward and left arm forward (frame 3); "
        "both feet together passing through neutral pose (frame 4)"),

    "Run cycle (4 frames)": (4,
        "a fast running cycle, body leaned forward throughout: "
        "left foot extended forward, right foot kicking back behind, knees bent (frame 1); "
        "contact pose with left foot planted on ground, right knee high in front (frame 2); "
        "right foot extended forward, left foot kicking back behind (frame 3); "
        "contact pose with right foot planted, left knee high in front (frame 4)"),

    "Idle breathing (4 frames)": (4,
        "a subtle idle breathing animation, feet planted, arms barely moving: "
        "chest at rest, shoulders neutral (frame 1); "
        "chest expanding mid-inhale, shoulders rising slightly (frame 2); "
        "chest at peak inhale, shoulders highest (frame 3); "
        "chest deflating mid-exhale, shoulders lowering (frame 4)"),

    "Jump (4 frames)": (4,
        "a jump animation: "
        "crouching down with knees deeply bent and arms swung back, anticipation pose (frame 1); "
        "legs fully extending and arms swinging upward at takeoff, feet leaving the ground (frame 2); "
        "apex of the jump with arms held high and legs tucked underneath (frame 3); "
        "landing with knees bent absorbing the impact, arms forward for balance (frame 4)"),

    "Sitting down (4 frames)": (4,
        "a sit-down sequence: "
        "standing upright at rest (frame 1); "
        "knees beginning to bend, torso leaning forward slightly, hands moving back (frame 2); "
        "deep squat just above seat, hands reaching back for support (frame 3); "
        "fully seated with back upright and hands resting on knees (frame 4)"),

    "Sword swing attack (4 frames)": (4,
        "a sword swing attack: "
        "weapon raised overhead, body coiled with weight on back foot (frame 1); "
        "weapon coming down through mid-arc, body uncoiling, weight shifting forward (frame 2); "
        "weapon at full forward extension at the peak of the strike, weight on front foot (frame 3); "
        "follow-through with weapon held low and body recovering toward neutral (frame 4)"),

    "Cast spell — pose only, no FX (4 frames)": (4,
        "a spell-casting body motion with NO visible spell or magical effect at all — "
        "pose and body movement only, so any spell visual can be composited in afterwards: "
        "arms held forward at chest height, palms up, body relaxed and upright (frame 1); "
        "arms drawn back slightly, hands beginning to come together at the chest, body coiling, "
        "weight shifting onto the back foot (frame 2); "
        "hands close together at chest height, body fully coiled and leaning back, "
        "feet planted, gathering momentum (frame 3); "
        "arms thrust fully forward with palms facing outward, body uncoiled and leaning forward "
        "toward the imaginary target, weight on the front foot (frame 4). "
        "ABSOLUTELY NO glow, no energy ball, no orb, no particles, no aura, no light rays, "
        "no smoke, no sparkles, no swirls, no magic effects of any kind. The hands and the air "
        "around and between them must be completely empty — only the character's body is visible."),

    "Hurt / damage (2 frames)": (2,
        "a damage reaction: "
        "standing pose with body slightly recoiled and pained expression on the face (frame 1); "
        "body knocked further backward with arm raised defensively (frame 2)"),

    "Death (4 frames)": (4,
        "a death animation: "
        "standing pose with hands clutching chest, pained expression (frame 1); "
        "staggering backward with knees beginning to give way (frame 2); "
        "kneeling on the ground with head bowed, arms slack (frame 3); "
        "fallen flat to the side on the ground, completely still (frame 4)"),

    "Wave / greeting (3 frames)": (3,
        "a friendly waving gesture: "
        "right arm raised at 45° from the body, hand open (frame 1); "
        "right arm at full vertical with hand tilted to the right (frame 2); "
        "right arm still raised but hand now tilted to the left, mid-wave (frame 3)"),
}


def render_prompt(template: str, values: dict):
    """
    Substitute {VAR} placeholders with values and return the resulting string
    plus a list of (start, length) ranges for each substituted value, so the
    UI can color them differently.
    """
    out = []
    ranges = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            end = template.find("}", i)
            if end == -1:
                out.append(template[i]); i += 1; continue
            name  = template[i+1:end]
            value = str(values.get(name, ""))
            start = sum(len(s) for s in out)
            out.append(value)
            ranges.append((start, len(value)))
            i = end + 1
        else:
            out.append(template[i]); i += 1
    return "".join(out), ranges


def remove_bg_by_color(img: Image.Image, tolerance: float = 14.0,
                       border_px: int = 2) -> Image.Image:
    """
    Color-key background removal.
    Finds the dominant color in the image's border (sampled `border_px` thick
    on each side), then marks every pixel within `tolerance` ΔE in CIELAB as
    transparent. Reliable for pixel art / illustrations with a solid or
    near-solid background where rembg fails.
    """
    from skimage.color import rgb2lab
    global _last_rembg_status

    arr  = np.array(img.convert("RGBA"), dtype=np.uint8)
    h, w = arr.shape[:2]
    bp   = max(1, min(border_px, h // 4, w // 4))

    border = np.concatenate([
        arr[:bp].reshape(-1, 4),
        arr[-bp:].reshape(-1, 4),
        arr[:, :bp].reshape(-1, 4),
        arr[:, -bp:].reshape(-1, 4),
    ])

    opaque = border[border[:, 3] > 200]
    if len(opaque) == 0:
        # Whole border is already transparent — nothing to remove.
        _last_rembg_status = "fallback"
        return img.convert("RGBA")

    # Mode of border RGB after quantizing to 8 bins/channel — robust to slight
    # gradients/anti-aliasing in the border. Then refine to the mean of that bin.
    rgb     = opaque[:, :3]
    rgb_q   = (rgb >> 5) << 5
    unique_q, counts = np.unique(rgb_q, axis=0, return_counts=True)
    bg_q    = unique_q[np.argmax(counts)]
    in_bin  = (rgb_q == bg_q).all(axis=1)
    bg_color = rgb[in_bin].mean(axis=0)

    img_lab = rgb2lab(arr[:, :, :3].astype(np.float32) / 255.0)
    bg_lab  = rgb2lab((bg_color / 255.0).reshape(1, 1, 3))[0, 0]
    de      = np.sqrt(((img_lab - bg_lab) ** 2).sum(axis=-1))
    bg_mask = de < tolerance

    if bg_mask.mean() > 0.98:
        # Almost everything matched — likely a low-contrast image where the
        # subject is also near-BG color. Bail rather than nuke the image.
        _last_rembg_status = "fallback"
        return img.convert("RGBA")

    new_alpha = arr[:, :, 3].copy()
    new_alpha[bg_mask] = 0
    arr[:, :, 3] = new_alpha
    _last_rembg_status = "ok"
    return Image.fromarray(arr, "RGBA")

def do_remove_bg(img: Image.Image, model: str = "isnet-general-use",
                 dilate: int = 1) -> Image.Image:
    """
    Run rembg with adaptive thresholding. rembg models are trained on photos;
    on small or pixel-art inputs they often return very soft alpha. A single
    strict threshold (> 200) deletes the whole subject in those cases.

    Strategy: try strict first, walk down to looser thresholds if the strict
    one would leave essentially nothing. If even loose thresholds find nothing,
    pass the original image through unchanged — better than deleting it.
    """
    global _last_rembg_status
    model = str(model)
    if model == EDGE_COLOR_OPTION:
        return remove_bg_by_color(img)

    from rembg import remove, new_session
    if model not in _rembg_sessions:
        _rembg_sessions[model] = new_session(model)
    session = _rembg_sessions[model]

    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    out = Image.open(io.BytesIO(remove(buf.getvalue(), session=session))).convert("RGBA")

    arr   = np.array(out, dtype=np.uint8)
    alpha = arr[:, :, 3]
    total = alpha.size

    # (threshold, min coverage required to accept that threshold)
    # Strict thresholds only need a small mask — they're trustworthy.
    # Loose thresholds need bigger coverage before we trust them.
    mask = None
    for thr, min_cov in [(200, 0.02), (128, 0.03), (80, 0.05), (30, 0.10)]:
        m = alpha > thr
        if m.sum() / total >= min_cov:
            mask = m
            break

    if mask is None or not mask.any():
        # rembg can't find a foreground here. Pass the original through.
        _last_rembg_status = "fallback"
        return img.convert("RGBA")

    _last_rembg_status = "ok"

    # 1-pixel dilation for a smooth clean boundary
    for _ in range(dilate):
        exp = np.zeros_like(mask)
        exp[:-1, :] |= mask[1:, :];  exp[1:, :]  |= mask[:-1, :]
        exp[:, :-1] |= mask[:, 1:];  exp[:, 1:]  |= mask[:, :-1]
        mask = mask | exp

    arr[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def add_outline(img: Image.Image, palette: np.ndarray = None,
                lightness_drop: float = 0.45) -> Image.Image:
    """
    Selective silhouette outline ('selout').
    Each transparent pixel adjacent to an opaque pixel takes the color of its
    opaque neighbor with the lightness reduced in CIELAB (hue/saturation kept).
    When `palette` is provided, the darkened color is snapped to the nearest
    palette entry so the outline stays palette-exact.
    """
    from skimage.color import rgb2lab, lab2rgb

    arr    = np.array(img.convert("RGBA"), dtype=np.uint8)
    h, w   = arr.shape[:2]
    opaque = arr[:, :, 3] > 127

    # 4-directional outline mask: transparent pixel touching an opaque pixel
    exp = np.zeros_like(opaque)
    exp[:-1, :] |= opaque[1:,  :]
    exp[1:,  :] |= opaque[:-1, :]
    exp[:, :-1] |= opaque[:, 1:]
    exp[:, 1:]  |= opaque[:, :-1]
    outline_mask = exp & ~opaque
    if not outline_mask.any():
        return img.copy()

    # Average color of opaque neighbors (vectorized via padded shifts)
    rgb         = arr[:, :, :3].astype(np.int32)
    rgb_pad     = np.pad(rgb,    ((1, 1), (1, 1), (0, 0)), mode="edge")
    op_pad      = np.pad(opaque, ((1, 1), (1, 1)), mode="constant", constant_values=False)

    up_rgb,  up_op    = rgb_pad[0:h,   1:w+1], op_pad[0:h,   1:w+1]
    dn_rgb,  dn_op    = rgb_pad[2:h+2, 1:w+1], op_pad[2:h+2, 1:w+1]
    lf_rgb,  lf_op    = rgb_pad[1:h+1, 0:w  ], op_pad[1:h+1, 0:w  ]
    rt_rgb,  rt_op    = rgb_pad[1:h+1, 2:w+2], op_pad[1:h+1, 2:w+2]

    nb_sum = (up_rgb * up_op[..., None] + dn_rgb * dn_op[..., None] +
              lf_rgb * lf_op[..., None] + rt_rgb * rt_op[..., None])
    nb_cnt = (up_op.astype(np.int32) + dn_op + lf_op + rt_op)

    valid = outline_mask & (nb_cnt > 0)
    avg_color = np.zeros_like(rgb, dtype=np.uint8)
    avg_color[valid] = (nb_sum[valid] // nb_cnt[valid][:, None]).astype(np.uint8)

    # Darken in LAB: drop L, keep a/b — preserves hue, just reduces brightness.
    # (Multiplicative RGB darkening drifts dark colors toward pure black.)
    avg_norm = avg_color.astype(np.float32) / 255.0
    avg_lab  = rgb2lab(avg_norm.reshape(1, h * w, 3)).reshape(h, w, 3)
    avg_lab[..., 0] *= lightness_drop
    darkened = np.clip(
        lab2rgb(avg_lab.reshape(1, h * w, 3)).reshape(h, w, 3) * 255,
        0, 255).astype(np.uint8)

    # Snap to palette if a fixed palette is in use → palette-exact outlines
    if palette is not None and len(palette) > 0:
        d_lab   = rgb2lab((darkened.astype(np.float32) / 255.0)
                          .reshape(1, h * w, 3)).reshape(-1, 3)
        pal_lab = rgb2lab((palette.astype(np.float32) / 255.0)
                          .reshape(1, -1, 3)).reshape(-1, 3)
        d2      = ((d_lab[:, None, :] - pal_lab[None, :, :]) ** 2).sum(axis=-1)
        nearest = np.argmin(d2, axis=1)
        darkened = palette[nearest].reshape(h, w, 3).astype(np.uint8)

    res = arr.copy()
    res[valid, :3] = darkened[valid]
    res[valid,  3] = 255
    return Image.fromarray(res, "RGBA")


def _majority_downscale(img: Image.Image, tw: int, th: int,
                        alpha_arr: np.ndarray = None) -> Image.Image:
    """
    Resize by choosing the most-common color in each source block.
    alpha_arr: if provided, only opaque pixels (>127) participate in the vote,
    preventing background fringe from contaminating edge blocks.
    """
    sw, sh = img.size
    if sw == tw and sh == th:
        return img.copy()

    arr = np.array(img, dtype=np.uint32)
    packed = arr[:, :, 0] * 65536 + arr[:, :, 1] * 256 + arr[:, :, 2]

    if alpha_arr is not None:
        # Resize alpha mask to source resolution if they differ
        if alpha_arr.shape[:2] != (sh, sw):
            a_img = Image.fromarray(alpha_arr.astype(np.uint8))
            alpha_src = np.array(
                a_img.resize((sw, sh), Image.Resampling.NEAREST)) > 127
        else:
            alpha_src = alpha_arr > 127
    else:
        alpha_src = None

    out = np.zeros((th, tw), dtype=np.uint32)
    for ty in range(th):
        y0, y1 = ty * sh // th, (ty + 1) * sh // th
        if y1 <= y0: y1 = y0 + 1
        for tx in range(tw):
            x0, x1 = tx * sw // tw, (tx + 1) * sw // tw
            if x1 <= x0: x1 = x0 + 1
            block = packed[y0:y1, x0:x1].ravel()

            if alpha_src is not None:
                fg = alpha_src[y0:y1, x0:x1].ravel()
                fg_block = block[fg]
                if len(fg_block) > 0:
                    block = fg_block   # vote only among foreground pixels

            vals, cnts = np.unique(block, return_counts=True)
            out[ty, tx] = vals[cnts.argmax()]

    r_ch = ((out >> 16) & 0xFF).astype(np.uint8)
    g_ch = ((out >> 8)  & 0xFF).astype(np.uint8)
    b_ch = ( out        & 0xFF).astype(np.uint8)
    return Image.fromarray(np.stack([r_ch, g_ch, b_ch], axis=2), "RGB")


def _bayer_dither(img: Image.Image, palette: np.ndarray) -> Image.Image:
    """8×8 Bayer ordered dithering — looks more like handmade pixel art than
    Floyd-Steinberg's random-looking error diffusion."""
    BAYER_8 = np.array([
        [ 0, 32,  8, 40,  2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44,  4, 36, 14, 46,  6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [ 3, 35, 11, 43,  1, 33,  9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47,  7, 39, 13, 45,  5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ], dtype=np.float32) / 64.0
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    tiled = np.tile(BAYER_8 - 0.5, ((h+7)//8, (w+7)//8))[:h, :w]

    # Median nearest-neighbor distance in palette → dither magnitude
    pal = palette.astype(np.float32)
    if len(pal) > 1:
        lum = pal @ np.array([0.299, 0.587, 0.114])
        order = np.argsort(lum)
        steps = np.linalg.norm(np.diff(pal[order], axis=0), axis=1)
        step = float(np.median(steps)) if len(steps) else 16.0
    else:
        step = 16.0

    dithered = np.clip(arr + tiled[:, :, None] * step, 0, 255).reshape(-1, 3)
    out = np.zeros_like(dithered, dtype=np.uint8)
    chunk = 100_000
    for i in range(0, len(dithered), chunk):
        c = dithered[i:i+chunk]
        d2 = ((c[:, None, :] - pal[None, :, :]) ** 2).sum(axis=-1)
        out[i:i+chunk] = pal[np.argmin(d2, axis=1)].astype(np.uint8)
    return Image.fromarray(out.reshape(h, w, 3), "RGB")


def _run_bg(img, remove_bg, bg_model):
    """Step 0: only background removal. (Brightness/contrast/saturation moved
    to a separate, fast step applied after bilateral so slider tweaks don't
    invalidate the cached bilateral result.)"""
    img = img.convert("RGBA")
    if not remove_bg:
        return img
    if bg_model == EDGE_COLOR_OPTION:
        return do_remove_bg(img, model=bg_model)
    a_pre = np.array(img.split()[-1])
    already_alpha = (a_pre < 200).mean() > 0.05
    if not already_alpha:
        return do_remove_bg(img, model=bg_model)
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b,
                                a.point(lambda v: 255 if v > 200 else 0)))


def _apply_image_adjustments(rgb_pil, brightness, contrast, saturation):
    """Apply Brightness/Contrast/Saturation to an RGB PIL image.
    Cheap (Pillow C ops) — runs every conversion regardless of cache."""
    if not (brightness or contrast or saturation):
        return rgb_pil
    from PIL import ImageEnhance
    out = rgb_pil
    if brightness: out = ImageEnhance.Brightness(out).enhance(1 + brightness/100.0)
    if contrast:   out = ImageEnhance.Contrast(out).enhance(1 + contrast/100.0)
    if saturation: out = ImageEnhance.Color(out).enhance(1 + saturation/100.0)
    return out


# ── Bilateral cache ──────────────────────────────────────────────────────
# denoise_bilateral on a 1024² image with sigma~5 takes seconds. The same
# call with the same input produces the same output, so we cache it. Keyed
# by (image bytes hash, target w, target h) since target size affects sigma.
# Bounded FIFO so memory doesn't grow unbounded for animation sets.
_BILATERAL_CACHE_MAX = 32
_bilateral_cache: dict = {}
_bilateral_order: list = []


def _bilateral_get(key):
    return _bilateral_cache.get(key)


def _bilateral_put(key, value):
    if key in _bilateral_cache:
        _bilateral_order.remove(key)
    elif len(_bilateral_cache) >= _BILATERAL_CACHE_MAX:
        old = _bilateral_order.pop(0)
        _bilateral_cache.pop(old, None)
    _bilateral_cache[key] = value
    _bilateral_order.append(key)


def _split_and_smooth(img, w, h):
    """Step 1: pre-resize source to a sane processing size, split alpha,
    bilateral-smooth RGB (cached). Returns (smoothed PIL, smoothed_norm np,
    alpha_arr np uint8, a_bin PIL)."""
    from skimage.restoration import denoise_bilateral

    # Pre-resize source — full resolution is overkill for small target sprites.
    # Cap to 4× target, with a floor of 256 (preserve detail) and ceiling of
    # 1024 (keep bilateral fast). Target ≥256: source kept up to 1024.
    max_proc = max(min(max(w, h) * 4, 1024), 256)
    if max(img.width, img.height) > max_proc:
        scale = max_proc / max(img.width, img.height)
        img = img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
            Image.Resampling.LANCZOS)

    r, g, b, a = img.split()
    a_bin = a.point(lambda v: 255 if v > 127 else 0)
    rgb   = Image.merge("RGB", (r, g, b))
    alpha_arr = np.array(a_bin)

    ratio = max(rgb.width / max(w, 1), rgb.height / max(h, 1), 1.0)
    if ratio > 1.2:
        # Cache key: hash of the post-BG-removal RGB bytes + target size.
        # Same source + same target = cache hit, even if user is dragging
        # a B/C/S slider — those are applied AFTER bilateral now.
        cache_key = (hash(rgb.tobytes()), w, h)
        smoothed_norm = _bilateral_get(cache_key)
        if smoothed_norm is None:
            rgb_norm = np.array(rgb, dtype=np.float32) / 255.0
            sigma_s  = float(np.clip(ratio * 0.6, 1.0, 6.0))
            smoothed_norm = denoise_bilateral(
                rgb_norm, sigma_color=0.06, sigma_spatial=sigma_s, channel_axis=-1)
            _bilateral_put(cache_key, smoothed_norm)
        smoothed = Image.fromarray(np.clip(smoothed_norm * 255, 0, 255).astype(np.uint8))
    else:
        smoothed = rgb
        smoothed_norm = np.array(rgb, dtype=np.float32) / 255.0
    return smoothed, smoothed_norm, alpha_arr, a_bin


def _kmeans_palette_from_lab(visible_lab, num_colors):
    """K-means in LAB → RGB palette."""
    from sklearn.cluster import MiniBatchKMeans
    from skimage.color import lab2rgb
    if len(visible_lab) > 80_000:
        idx = np.random.default_rng(0).choice(len(visible_lab), 80_000, replace=False)
        sample = visible_lab[idx]
    else:
        sample = visible_lab
    n_colors = max(1, min(num_colors, len(visible_lab)))
    km = MiniBatchKMeans(n_clusters=n_colors, random_state=0, n_init=3)
    km.fit(sample)
    return np.clip(
        lab2rgb(km.cluster_centers_.reshape(1, -1, 3)).reshape(-1, 3) * 255,
        0, 255).astype(np.uint8)


def _finalize_frame(smoothed, alpha_arr, a_bin, palette, is_fixed, w, h, dither, outline):
    """Quantize → majority downscale → dither → compose alpha → outline → binarize."""
    if is_fixed:
        quantized_full = _quantize_to_palette_lab(smoothed, palette)
    else:
        pal_img = Image.new("P", (1, 1))
        flat_pal = np.zeros(768, dtype=np.uint8)
        for i, c in enumerate(palette):
            flat_pal[i*3:i*3+3] = c
        pal_img.putpalette(flat_pal.tolist())
        quantized_full = smoothed.quantize(
            palette=pal_img, dither=Image.Dither.NONE).convert("RGB")

    rgb_small = _majority_downscale(quantized_full, w, h, alpha_arr)
    a_small   = a_bin.resize((w, h), Image.Resampling.NEAREST)

    if dither:
        rgb_small = _bayer_dither(rgb_small, palette)

    out = rgb_small.convert("RGBA")
    out.putalpha(a_small)
    if outline:
        out = add_outline(out, palette=palette)

    final = np.array(out)
    final[..., 3] = np.where(final[..., 3] > 127, 255, 0).astype(np.uint8)
    return Image.fromarray(final, "RGBA")


def _adjust_pack(smoothed, smoothed_norm, brightness, contrast, saturation):
    """If any adjustment is non-zero, re-derive the smoothed PIL + norm array.
    Otherwise pass through. Cheap on its own; only matters that we don't have
    to re-run bilateral when sliders change."""
    if not (brightness or contrast or saturation):
        return smoothed, smoothed_norm
    smoothed = _apply_image_adjustments(smoothed, brightness, contrast, saturation)
    smoothed_norm = np.array(smoothed, dtype=np.float32) / 255.0
    return smoothed, smoothed_norm


def make_pixel_art(img, w, h, num_colors, dither, remove_bg, outline,
                   bg_model="isnet-general-use", fixed_palette=None,
                   brightness=0, contrast=0, saturation=0):
    """Single-frame pixel-art pipeline."""
    from skimage.color import rgb2lab

    # 1) BG removal (slow but rare — re-runs only when toggle/model changes)
    img = _run_bg(img, remove_bg, bg_model)
    # 2) Pre-resize + alpha split + bilateral (CACHED — repeats are free)
    smoothed, smoothed_norm, alpha_arr, a_bin = _split_and_smooth(img, w, h)
    # 3) Brightness / contrast / saturation (fast, post-bilateral)
    smoothed, smoothed_norm = _adjust_pack(
        smoothed, smoothed_norm, brightness, contrast, saturation)

    if fixed_palette is not None and len(fixed_palette) > 0:
        palette = np.asarray(fixed_palette, dtype=np.uint8)
        is_fixed = True
    else:
        lab_flat = rgb2lab(smoothed_norm).reshape(-1, 3).astype(np.float32)
        visible  = lab_flat[alpha_arr.flatten() > 127]
        if len(visible) < num_colors:
            visible = lab_flat
        palette  = _kmeans_palette_from_lab(visible, num_colors)
        is_fixed = False

    return _finalize_frame(smoothed, alpha_arr, a_bin, palette, is_fixed,
                           w, h, dither, outline)


def make_pixel_art_animation(frames, w, h, num_colors, dither, remove_bg, outline,
                             bg_model="isnet-general-use", fixed_palette=None,
                             brightness=0, contrast=0, saturation=0):
    """Multi-frame pipeline — every frame uses the SAME palette so colors don't flicker."""
    from skimage.color import rgb2lab

    # BG removal per frame (skipped/quick if input has alpha)
    pre = [_run_bg(f, remove_bg, bg_model) for f in frames]
    # Bilateral per frame, each cached independently (32-entry FIFO covers
    # typical animation sets); subsequent slider tweaks reuse all of them.
    packs = [_split_and_smooth(f, w, h) for f in pre]
    # Apply adjustments per frame (cheap)
    packs = [
        (*_adjust_pack(s, sn, brightness, contrast, saturation), aa, ab)
        for s, sn, aa, ab in packs
    ]

    if fixed_palette is not None and len(fixed_palette) > 0:
        palette = np.asarray(fixed_palette, dtype=np.uint8)
        is_fixed = True
    else:
        all_visible = []
        for _s, smoothed_norm, alpha_arr, _a in packs:
            lab_flat = rgb2lab(smoothed_norm).reshape(-1, 3).astype(np.float32)
            all_visible.append(lab_flat[alpha_arr.flatten() > 127])
        combined = np.concatenate(all_visible) if all_visible else np.zeros((0, 3), dtype=np.float32)
        if len(combined) < num_colors:
            combined = np.concatenate([
                rgb2lab(p[1]).reshape(-1, 3).astype(np.float32) for p in packs
            ]) if packs else np.zeros((0, 3), dtype=np.float32)
        palette  = _kmeans_palette_from_lab(combined, num_colors)
        is_fixed = False

    return [
        _finalize_frame(smoothed, alpha_arr, a_bin, palette, is_fixed,
                        w, h, dither, outline)
        for smoothed, _norm, alpha_arr, a_bin in packs
    ]


def split_sprite_sheet(img, cols, rows):
    """Split a sprite sheet image into a list of frames (row-major order)."""
    img = img.convert("RGBA")
    w, h = img.size
    fw, fh = w // cols, h // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            box = (c*fw, r*fh, (c+1)*fw, (r+1)*fh)
            frames.append(img.crop(box))
    return frames


def compose_sprite_sheet(frames):
    """Compose frames into one horizontal sprite sheet (always 1 row, left-to-right)."""
    if not frames:
        return None
    fw, fh = frames[0].size
    sheet = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * fw, 0))
    return sheet


def extract_palette(img):
    arr  = np.array(img.convert("RGBA"))
    mask = arr[:, :, 3] > 127
    rgb  = arr[mask, :3]
    if not len(rgb):
        return []
    unique, counts = np.unique(rgb.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-counts)
    return [(int(unique[i,0]), int(unique[i,1]), int(unique[i,2])) for i in order[:64]]


def pil_to_nsimage(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    return NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(raw, len(raw)))


# ── Pasteable text field ──────────────────────────────────────────────────
# NSAlert's accessory view doesn't get the Edit menu in its responder chain,
# so Cmd+V is silently dropped. This subclass handles the shortcuts directly.

class PasteableTextField(NSTextField):
    def performKeyEquivalent_(self, event):
        if event.modifierFlags() & (1 << 20):   # NSEventModifierFlagCommand
            chars = event.charactersIgnoringModifiers()
            ed = self.currentEditor()
            if ed is not None:
                if chars == "v": ed.paste_(self);     return True
                if chars == "c": ed.copy_(self);      return True
                if chars == "x": ed.cut_(self);       return True
                if chars == "a": ed.selectAll_(self); return True
        return objc.super(PasteableTextField, self).performKeyEquivalent_(event)


# ── Drop zone ─────────────────────────────────────────────────────────────

class DropZoneView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(DropZoneView, self).initWithFrame_(frame)
        if self is None: return None
        self.__dict__.update(on_file=None, hovered=False)
        self.registerForDraggedTypes_([NSFilenamesPboardType])
        return self

    def isOpaque(self): return False

    def drawRect_(self, rect):
        hov = self.__dict__.get("hovered", False)
        dark = _is_dark_view(self)
        b   = self.bounds()
        p   = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, 10, 10)
        if hov:
            # Same blue tint in both modes (it's the highlight, not the bg)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.45, 0.9, 0.25).setFill()
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.6, 1.0, 1.0).setStroke()
        else:
            if dark:
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.13, 0.13, 0.15, 1.0).setFill()
                NSColor.colorWithCalibratedWhite_alpha_(0.35, 1.0).setStroke()
            else:
                NSColor.colorWithCalibratedWhite_alpha_(0.94, 1.0).setFill()
                NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0).setStroke()
        p.fill(); p.setLineWidth_(1.5)
        p.setLineDash_count_phase_([7.0, 4.0], 2, 0.0); p.stroke()
        cx, cy = b.size.width/2, b.size.height/2
        self._text("Drop PNG here" if not hov else "Release to open",
                   NSMakePoint(cx, cy), 13, bold=True)
        self._text("or click to open…" if not hov else "",
                   NSMakePoint(cx, cy-20), 11, alpha=0.55)

    @objc.python_method
    def _text(self, s, pt, sz, bold=False, alpha=1.0):
        if not s: return
        font  = NSFont.boldSystemFontOfSize_(sz) if bold else NSFont.systemFontOfSize_(sz)
        # Use appearance-aware label color so text reads in both Light and Dark.
        base  = NSColor.labelColor()
        color = base.colorWithAlphaComponent_(alpha) if alpha < 1.0 else base
        attrs = {NSForegroundColorAttributeName: color, NSFontAttributeName: font}
        ns = NSString.stringWithString_(s)
        tw = ns.sizeWithAttributes_(attrs).width
        th = ns.sizeWithAttributes_(attrs).height
        ns.drawAtPoint_withAttributes_(NSMakePoint(pt.x - tw/2, pt.y - th/2), attrs)

    def mouseDown_(self, _):
        if self.__dict__.get("locked"): return
        cb = self.__dict__.get("on_file")
        if not cb: return
        p = NSOpenPanel.openPanel()
        p.setAllowedFileTypes_(["png","PNG"])
        p.setCanChooseFiles_(True); p.setCanChooseDirectories_(False)
        p.setAllowsMultipleSelection_(True)   # multi-select for animation frames
        if p.runModal() == NSModalResponseOK:
            paths = sorted(str(u.path()) for u in p.URLs())
            cb(paths)

    def draggingEntered_(self, sender):
        files = sender.draggingPasteboard().propertyListForType_(NSFilenamesPboardType)
        if files and any(str(f).lower().endswith(".png") for f in files):
            self.__dict__["hovered"] = True; self.setNeedsDisplay_(True)
            return NSDragOperationCopy
        return NSDragOperationNone

    def draggingExited_(self, sender):
        self.__dict__["hovered"] = False; self.setNeedsDisplay_(True)

    def performDragOperation_(self, sender):
        self.__dict__["hovered"] = False; self.setNeedsDisplay_(True)
        if self.__dict__.get("locked"): return False
        files = sender.draggingPasteboard().propertyListForType_(NSFilenamesPboardType)
        cb = self.__dict__.get("on_file")
        if files and cb:
            pngs = sorted(str(f) for f in files if str(f).lower().endswith(".png"))
            if pngs:
                cb(pngs); return True
        return False


# ── Palette view ──────────────────────────────────────────────────────────

class PaletteView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(PaletteView, self).initWithFrame_(frame)
        if self is None: return None
        self.__dict__["colors"] = []
        return self

    @objc.python_method
    def setColors(self, colors):
        self.__dict__["colors"] = [(int(r), int(g), int(b)) for r,g,b in colors]
        self.setNeedsDisplay_(True)

    def isOpaque(self): return False

    def drawRect_(self, rect):
        colors = self.__dict__.get("colors", [])
        # Subtle dark slot in dark mode, subtle light slot in light mode
        bg = (NSColor.colorWithCalibratedWhite_alpha_(0.12, 1.0)
              if _is_dark_view(self) else
              NSColor.colorWithCalibratedWhite_alpha_(0.88, 1.0))
        bg.setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 3, 3).fill()
        if not colors: return

        # Crisp swatches: disable antialiasing and snap each rect to integer pixel
        # boundaries so adjacent swatches abut without partial-coverage edges.
        ctx = NSGraphicsContext.currentContext()
        if ctx: ctx.setShouldAntialias_(False)

        w = float(self.bounds().size.width)
        h = float(self.bounds().size.height)
        n = len(colors)
        for i, (r, g, b) in enumerate(colors):
            x0 = int(round(i * w / n))
            x1 = int(round((i + 1) * w / n))
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                r/255.0, g/255.0, b/255.0, 1.0).setFill()
            NSRectFill(NSMakeRect(x0, 0, x1 - x0, h))


# ── Checkerboard image view — draws pixel art with nearest-neighbor ───────

class CheckerImageView(NSImageView):
    """
    Overrides drawRect_ entirely so we control interpolation.
    px_scale: each source pixel is displayed as px_scale × px_scale screen pixels.
    Aspect ratio is always preserved; if the scaled image overflows the view,
    the user can drag with the mouse to pan around.
    """

    def initWithFrame_(self, frame):
        self = objc.super(CheckerImageView, self).initWithFrame_(frame)
        if self is None: return None
        self.__dict__.update(px_scale=4, pan_x=0.0, pan_y=0.0)
        return self

    def isOpaque(self): return False

    @objc.python_method
    def _disp_size(self):
        img = self.image()
        if not img: return (0, 0)
        s   = self.__dict__.get("px_scale", 4)
        sz  = img.size()
        return (sz.width * s, sz.height * s)

    @objc.python_method
    def _max_pan(self):
        b = self.bounds()
        dw, dh = self._disp_size()
        return (max(0.0, (dw - b.size.width)  / 2),
                max(0.0, (dh - b.size.height) / 2))

    @objc.python_method
    def _clamp_pan(self):
        mx, my = self._max_pan()
        d = self.__dict__
        d["pan_x"] = max(-mx, min(mx, d.get("pan_x", 0.0)))
        d["pan_y"] = max(-my, min(my, d.get("pan_y", 0.0)))

    def drawRect_(self, rect):
        b    = self.bounds()
        bw   = int(b.size.width)
        bh   = int(b.size.height)
        tile = 8

        # Checkerboard background — subtle in both Light and Dark appearances.
        if _is_dark_view(self):
            ca, cb = 0.22, 0.16   # dark grays
        else:
            ca, cb = 0.93, 0.86   # light grays
        for row in range(0, bh, tile):
            for col in range(0, bw, tile):
                c = ca if (row//tile + col//tile) % 2 == 0 else cb
                NSColor.colorWithCalibratedWhite_alpha_(c, 1.0).setFill()
                NSRectFill(NSMakeRect(col, row, tile, tile))

        img = self.image()
        if not img: return

        # Aspect ratio is preserved — never clamp w/h independently.
        # Overflow is fine; NSView clips drawing to its bounds.
        disp_w, disp_h = self._disp_size()
        self._clamp_pan()
        pan_x = self.__dict__.get("pan_x", 0.0)
        pan_y = self.__dict__.get("pan_y", 0.0)
        # Snap drawing to integer pixels so NSImage doesn't edge-blend at
        # fractional positions — which would *look* like partial-alpha pixels.
        x = round((bw - disp_w) / 2 + pan_x)
        y = round((bh - disp_h) / 2 + pan_y)
        disp_w = int(round(disp_w))
        disp_h = int(round(disp_h))

        ctx = NSGraphicsContext.currentContext()
        if ctx:
            ctx.setImageInterpolation_(0)   # NSImageInterpolationNone
            ctx.setShouldAntialias_(False)

        img.drawInRect_(NSMakeRect(x, y, disp_w, disp_h))

        # ── Optional pixel-grid overlay
        # Lines at every actual pixel boundary, computed as round(i*disp/src).
        # This keeps the grid aligned even at fractional scales (5.7×, 11.3×…).
        scale = float(self.__dict__.get("px_scale", 4))
        if self.__dict__.get("show_grid", False) and scale >= 2.0:
            NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.40).setFill()
            sw, sh = int(isz.width), int(isz.height)
            for i in range(sw + 1):
                gx = x + int(round(i * disp_w / sw))
                NSRectFill(NSMakeRect(gx, y, 1, disp_h))
            for i in range(sh + 1):
                gy = y + int(round(i * disp_h / sh))
                NSRectFill(NSMakeRect(x, gy, disp_w, 1))

    @objc.python_method
    def setShowGrid(self, show):
        self.__dict__["show_grid"] = bool(show)
        self.setNeedsDisplay_(True)

    # ── Mouse panning ─────────────────────────────────────────────────────

    def mouseDown_(self, event):
        if not self.image(): return
        mx, my = self._max_pan()
        if mx == 0 and my == 0: return        # nothing to pan
        pt = self.convertPoint_fromView_(event.locationInWindow(), None)
        d  = self.__dict__
        d["_drag_anchor"] = (pt.x, pt.y)
        d["_pan_anchor"]  = (d.get("pan_x", 0.0), d.get("pan_y", 0.0))
        NSCursor.closedHandCursor().push()

    def mouseDragged_(self, event):
        d = self.__dict__
        if "_drag_anchor" not in d: return
        pt = self.convertPoint_fromView_(event.locationInWindow(), None)
        ax, ay = d["_drag_anchor"]
        px, py = d["_pan_anchor"]
        d["pan_x"] = px + (pt.x - ax)
        d["pan_y"] = py + (pt.y - ay)
        self._clamp_pan()
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event):
        d = self.__dict__
        if "_drag_anchor" in d:
            d.pop("_drag_anchor", None)
            d.pop("_pan_anchor",  None)
            NSCursor.pop()

    def resetCursorRects(self):
        # Open-hand cursor over the view if there's something to pan.
        mx, my = self._max_pan()
        if mx > 0 or my > 0:
            self.addCursorRect_cursor_(self.bounds(), NSCursor.openHandCursor())

    @objc.python_method
    def setPixelScale(self, scale):
        self.__dict__["px_scale"] = scale
        # New scale → re-center; previous pan offset isn't meaningful any more.
        self.__dict__["pan_x"] = 0.0
        self.__dict__["pan_y"] = 0.0
        self.window().invalidateCursorRectsForView_(self) if self.window() else None
        self.setNeedsDisplay_(True)

    # ── Scroll wheel + pinch-to-zoom ──────────────────────────────────────
    # Continuous (floating-point) zoom in [SCALE_MIN, SCALE_MAX] = [1×, 32×].
    # The Preview Scale popup snaps to the nearest discrete SCALES value, but
    # the actual zoom level can be any float in between.

    def scrollWheel_(self, event):
        if not self.image(): return
        delta = float(event.scrollingDeltaY())
        if delta == 0: return
        # Multiplicative zoom: each scroll-unit nudges by 0.5%.
        # Trackpad sends many small deltas (smooth); a real wheel sends a few
        # big ones (~10 each). Both feel right with this factor.
        cur = float(self.__dict__.get("px_scale", 4.0))
        new_scale = cur * (1.0 + delta * 0.005)
        self._apply_smooth_zoom(new_scale)

    def magnifyWithEvent_(self, event):
        if not self.image(): return
        # event.magnification() is the *delta* (~0.01–0.05 per event for pinch)
        cur = float(self.__dict__.get("px_scale", 4.0))
        new_scale = cur * (1.0 + float(event.magnification()))
        self._apply_smooth_zoom(new_scale)

    @objc.python_method
    def _apply_smooth_zoom(self, new_scale):
        new_scale = max(SCALE_MIN, min(SCALE_MAX, float(new_scale)))
        cur = float(self.__dict__.get("px_scale", 4.0))
        if abs(new_scale - cur) < 0.001: return
        # Tell the AppDelegate that THIS view zoomed. The delegate updates only
        # this view (independent zoom per panel) and syncs the popup if the
        # gesture happened on the Pixel Art preview.
        delegate = NSApplication.sharedApplication().delegate()
        if delegate is not None:
            try:
                delegate._sync_scale(new_scale, self)
                return
            except Exception:
                pass
        self.setPixelScale(new_scale)

    def setImage_(self, img):
        objc.super(CheckerImageView, self).setImage_(img)
        # New image → reset pan; cursor rect may need updating.
        self.__dict__["pan_x"] = 0.0
        self.__dict__["pan_y"] = 0.0
        if self.window(): self.window().invalidateCursorRectsForView_(self)


# ── Preset sizes ──────────────────────────────────────────────────────────

PRESETS = [
    ("16 × 16",   16, 16),  ("32 × 32",   32, 32),  ("32 × 48",   32, 48),
    ("48 × 48",   48, 48),  ("64 × 64",   64, 64),  ("64 × 96",   64, 96),
    ("96 × 96",   96, 96),  ("128 × 128", 128, 128), ("256 × 256", 256, 256),
    ("Custom…",   0,  0),
]
SCALES = [1, 2, 4, 8, 16, 32]
# Smooth zoom can go below 1× (useful for fitting a large source image into
# the Original panel). The popup stays at 1× minimum since fractional values
# clutter the dropdown — scroll/pinch beyond 1× and the popup snaps to 1×.
SCALE_MIN = 0.05
SCALE_MAX = 32.0


# ── App delegate ──────────────────────────────────────────────────────────

class AppDelegate(NSObject):

    def applicationDidFinishLaunching_(self, _):
        self.__dict__.update(
            frames=[], src_paths=[], result_img=None, result_frames=[],
            busy=False, aspect_locked=True,
            w_tag=1, h_tag=2,
        )
        self._build()
        # Re-load icon when system appearance flips (user toggles Dark mode).
        # KVO on NSApp's effectiveAppearance is the canonical hook.
        try:
            NSApplication.sharedApplication().addObserver_forKeyPath_options_context_(
                self, "effectiveAppearance", 0, None)
        except Exception:
            pass

    def observeValueForKeyPath_ofObject_change_context_(self, key, obj, change, ctx):
        if str(key) == "effectiveAppearance":
            _load_app_icon(NSApplication.sharedApplication())
            # Force every custom-drawn view to redraw with the new colors.
            d = self.__dict__
            for k in ("orig_view", "result_view", "palette",
                      "drop_zone", "prompt_view"):
                v = d.get(k)
                if v is not None and hasattr(v, "setNeedsDisplay_"):
                    v.setNeedsDisplay_(True)

    def applicationShouldTerminateAfterLastWindowClosed_(self, _): return True

    # ── Build window ──────────────────────────────────────────────────────

    @objc.python_method
    def _build(self):
        W, H = 980, 930
        self.__dict__["custom_palettes"] = {}   # display_name -> hex_list
        mask = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), mask, NSBackingStoreBuffered, False)
        win.setTitle_("Pixel Art Converter")
        win.center()
        # Inherit the system appearance (Light or Dark). Custom-drawn views
        # below detect effectiveAppearance at draw time and pick colors.
        self.__dict__["win"] = win
        cv = win.contentView()
        LP, PW = 14, 268

        # ── Drop zone
        dz = DropZoneView.alloc().initWithFrame_(NSMakeRect(LP, H-14-148, PW, 148))
        dz.__dict__["on_file"] = self._load
        cv.addSubview_(dz); self.__dict__["drop_zone"] = dz

        # ── Sprite-sheet input row (single image → split by Cols × Rows)
        y = H - 14 - 148 - 4
        ssh = NSButton.alloc().initWithFrame_(NSMakeRect(LP, y-22, 130, 22))
        ssh.setButtonType_(NSSwitchButton); ssh.setTitle_("Sprite Sheet")
        ssh.setTarget_(self); ssh.setAction_("onSheet:")
        cv.addSubview_(ssh); self.__dict__["sheet_chk"] = ssh

        cv.addSubview_(self._lbl("Cols", NSMakeRect(LP+135, y-22, 32, 22)))
        cf = self._numfield(NSMakeRect(LP+170, y-22, 36, 22), "4", tag=10)
        cv.addSubview_(cf); self.__dict__["sheet_cols"] = cf

        cv.addSubview_(self._lbl("Rows", NSMakeRect(LP+212, y-22, 34, 22)))
        rf = self._numfield(NSMakeRect(LP+248, y-22, 36, 22), "1", tag=11)
        cv.addSubview_(rf); self.__dict__["sheet_rows"] = rf

        y -= 30
        self._sep(cv, LP, y, PW)

        # ── Preset size
        y -= 36
        cv.addSubview_(self._lbl("Preset", NSMakeRect(LP, y, 55, 22)))
        pp = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(LP+58, y-2, PW-58, 26), False)
        for name, *_ in PRESETS: pp.addItemWithTitle_(name)
        pp.selectItemAtIndex_(4)
        pp.setTarget_(self); pp.setAction_("onPreset:")
        cv.addSubview_(pp); self.__dict__["preset_pop"] = pp

        # ── W × H
        y -= 36
        cv.addSubview_(self._lbl("W", NSMakeRect(LP, y, 18, 22)))
        wf = self._numfield(NSMakeRect(LP+20, y, 64, 22), "64", tag=1)
        cv.addSubview_(wf); self.__dict__["w_field"] = wf

        cv.addSubview_(self._lbl("×", NSMakeRect(LP+91, y, 14, 22)))
        cv.addSubview_(self._lbl("H", NSMakeRect(LP+111, y, 18, 22)))
        hf = self._numfield(NSMakeRect(LP+129, y, 64, 22), "64", tag=2)
        cv.addSubview_(hf); self.__dict__["h_field"] = hf

        lb = NSButton.alloc().initWithFrame_(NSMakeRect(LP+202, y, 70, 22))
        lb.setButtonType_(NSSwitchButton); lb.setTitle_("Lock ⛓")
        lb.setState_(NSOnState); lb.setTarget_(self); lb.setAction_("onLock:")
        cv.addSubview_(lb); self.__dict__["lock_btn"] = lb

        # ── Colors
        y -= 36
        cl = self._lbl("Colors: 24", NSMakeRect(LP, y, 88, 22))
        cv.addSubview_(cl); self.__dict__["colors_lbl"] = cl

        sl = NSSlider.alloc().initWithFrame_(NSMakeRect(LP+92, y+2, PW-92, 20))
        sl.setMinValue_(4); sl.setMaxValue_(64); sl.setIntValue_(24)
        sl.setTarget_(self); sl.setAction_("onColors:")
        cv.addSubview_(sl); self.__dict__["colors_sl"] = sl

        # ── Palette
        y -= 32
        cv.addSubview_(self._lbl("Palette", NSMakeRect(LP, y, 56, 22)))
        pal = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(LP+58, y-2, PW-58, 26), False)
        for name in LOSPEC_PALETTES.keys():
            pal.addItemWithTitle_(name)
        pal.menu().addItem_(NSMenuItem.separatorItem())
        pal.addItemWithTitle_(LOSPEC_LOAD_OPTION)
        pal.selectItemAtIndex_(0)
        pal.setTarget_(self); pal.setAction_("onPalette:")
        cv.addSubview_(pal); self.__dict__["palette_pop"] = pal

        # Restore palettes saved in previous sessions (Lospec downloads etc.)
        saved = self._load_saved_palettes()
        for name, hex_list in saved.items():
            if name in self.__dict__["custom_palettes"]: continue
            self.__dict__["custom_palettes"][name] = hex_list
            # Insert before "Load from Lospec…" so saved palettes appear right
            # after the bundled ones, in their own section after the separator.
            pal.insertItemWithTitle_atIndex_(name, pal.numberOfItems() - 1)

        # ── Image adjustments (Brightness / Contrast / Saturation)
        for spec in [
            ("bright_lbl", "bright_sl", "Bright",  -100, 100, 0, "Bright: 0"),
            ("contr_lbl",  "contr_sl",  "Contr",   -100, 100, 0, "Contr: 0"),
            ("sat_lbl",    "sat_sl",    "Sat",     -100, 100, 0, "Sat: 0"),
        ]:
            lbl_key, sl_key, _name, mn, mx, dv, lbl_txt = spec
            y -= 28
            lab = self._lbl(lbl_txt, NSMakeRect(LP, y, 80, 22))
            cv.addSubview_(lab); self.__dict__[lbl_key] = lab
            sl = NSSlider.alloc().initWithFrame_(NSMakeRect(LP+84, y+2, PW-84, 20))
            sl.setMinValue_(mn); sl.setMaxValue_(mx); sl.setIntValue_(dv)
            sl.setTarget_(self); sl.setAction_("onAdjust:")
            cv.addSubview_(sl); self.__dict__[sl_key] = sl

        # ── Toggles
        y -= 30
        dc = self._check("Dithering (Bayer 8×8)", NSMakeRect(LP, y, PW, 22))
        cv.addSubview_(dc); self.__dict__["dither_chk"] = dc

        y -= 28
        rc = self._check("Remove Background  ·  rembg AI", NSMakeRect(LP, y, PW, 22))
        cv.addSubview_(rc); self.__dict__["rembg_chk"] = rc

        y -= 26
        cv.addSubview_(self._lbl("  Model", NSMakeRect(LP, y, 52, 22)))
        mp = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(LP+56, y-2, PW-56, 24), False)
        for m in ["isnet-general-use", "isnet-anime", "u2net", "u2net_human_seg"]:
            mp.addItemWithTitle_(m)
        mp.menu().addItem_(NSMenuItem.separatorItem())
        mp.addItemWithTitle_(EDGE_COLOR_OPTION)
        mp.selectItemAtIndex_(0)
        mp.setTarget_(self); mp.setAction_("onConvertSettings:")
        cv.addSubview_(mp); self.__dict__["bg_model_pop"] = mp

        y -= 28
        oc = self._check("Selective Outline (hue-aware)", NSMakeRect(LP, y, PW, 22))
        oc.setState_(NSOnState)
        cv.addSubview_(oc); self.__dict__["outline_chk"] = oc

        # ── Preview scale + grid toggle
        y -= 34
        cv.addSubview_(self._lbl("Preview Scale", NSMakeRect(LP, y, 96, 22)))
        sc = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(LP+100, y-2, 80, 26), False)
        for s in SCALES: sc.addItemWithTitle_(f"{s}×")
        sc.selectItemAtIndex_(2)
        sc.setTarget_(self); sc.setAction_("onScale:")
        cv.addSubview_(sc); self.__dict__["scale_pop"] = sc

        gc = NSButton.alloc().initWithFrame_(NSMakeRect(LP+190, y, 80, 22))
        gc.setButtonType_(NSSwitchButton); gc.setTitle_("Grid")
        gc.setTarget_(self); gc.setAction_("onGrid:")
        cv.addSubview_(gc); self.__dict__["grid_chk"] = gc

        self._sep(cv, LP, y-16, PW)

        # ── Status
        y -= 42
        st = self._lbl("Drop a PNG to begin", NSMakeRect(LP, y, PW, 20))
        st.setTextColor_(NSColor.secondaryLabelColor())
        st.setAlignment_(NSTextAlignmentCenter)
        cv.addSubview_(st); self.__dict__["status"] = st

        # ── Buttons
        for label, action, key, always_on in [
            ("New Image",           "onNew:",         "new_btn",    True),
            ("Save Pixel Art PNG",  "onSave:",        "save_btn",   False),
            ("Open in Krita",       "onKrita:",       "krita_btn",  False),
            ("Copy to Clipboard",   "onCopy:",        "copy_btn",   False),
            ("AI Prompt Samples",   "onPromptShow:",  "prompt_btn", True),
            (f"Check for Updates  ·  v{__version__}",
                                    "onUpdateCheck:", "update_btn", True),
        ]:
            y -= 40
            b = self._btn(label, NSMakeRect(LP, y, PW, 32), action, enabled=always_on)
            cv.addSubview_(b); self.__dict__[key] = b

        # ── Divider
        div = NSBox.alloc().initWithFrame_(NSMakeRect(LP+PW+8, 0, 1, H))
        div.setBoxType_(NSBoxSeparator); cv.addSubview_(div)
        self.__dict__["divider"] = div

        # ── Right panel — references kept so we can re-layout on window resize
        RX   = LP + PW + 20
        RW   = W - RX - 14
        half = (RW - 12) // 2

        ol = self._lbl("Original", NSMakeRect(RX, H-32, half, 20))
        ol.setFont_(NSFont.boldSystemFontOfSize_(12)); cv.addSubview_(ol)
        self.__dict__["orig_label"] = ol

        rl = self._lbl("Pixel Art", NSMakeRect(RX+half+12, H-32, half, 20))
        rl.setFont_(NSFont.boldSystemFontOfSize_(12)); cv.addSubview_(rl)
        self.__dict__["result_label"] = rl

        IVH = H - 32 - 18 - 62
        for key, rx in [("orig_view", RX), ("result_view", RX+half+12)]:
            v = CheckerImageView.alloc().initWithFrame_(NSMakeRect(rx, 60, half, IVH))
            v.setImageScaling_(NSImageScaleProportionallyUpOrDown)
            v.setImageAlignment_(NSImageAlignCenter)
            v.setWantsLayer_(True); v.layer().setCornerRadius_(6)
            cv.addSubview_(v); self.__dict__[key] = v

        pl = self._lbl("Palette", NSMakeRect(RX+half+12, 44, 55, 14))
        pl.setFont_(NSFont.boldSystemFontOfSize_(9)); cv.addSubview_(pl)
        self.__dict__["palette_label"] = pl

        pv = PaletteView.alloc().initWithFrame_(NSMakeRect(RX+half+12, 26, half, 16))
        cv.addSubview_(pv); self.__dict__["palette"] = pv

        il = self._lbl("", NSMakeRect(RX, 12, half, 36))
        il.setTextColor_(NSColor.tertiaryLabelColor())
        cv.addSubview_(il); self.__dict__["info"] = il

        # ── Resize behavior ───────────────────────────────────────────────
        # Autoresize masks for the LEFT panel: keep every control top-anchored
        # at its built X. Mask = NSViewMaxXMargin | NSViewMinYMargin = 12.
        # (Right margin grows with window width, bottom margin grows with height.)
        for v in cv.subviews():
            if v.frame().origin.x < LP + PW:
                v.setAutoresizingMask_(12)
        # Divider stretches vertically: HeightSizable | MaxXMargin = 16 | 4 = 20.
        div.setAutoresizingMask_(20)

        # Window callbacks for manual layout of the right-side preview panels
        # (two columns sharing the available width — autoresize alone can't
        # express that cleanly).
        win.setDelegate_(self)
        win.setMinSize_(__import__("Foundation").NSMakeSize(W, H))

        win.makeKeyAndOrderFront_(None)
        self._layout_preview_panels()

    # ── Window resize handling ────────────────────────────────────────────

    def windowDidResize_(self, _notification):
        self._layout_preview_panels()

    @objc.python_method
    def _layout_preview_panels(self):
        d = self.__dict__
        win = d.get("win")
        if not win: return
        size = win.contentView().frame().size
        W, H = float(size.width), float(size.height)

        LP, PW = 14, 268
        RX   = LP + PW + 20
        RW   = max(40.0, W - RX - 14)
        half = max(20.0, (RW - 12) / 2)
        IVH  = max(60.0, H - 32 - 18 - 62)

        d["orig_label"  ].setFrame_(NSMakeRect(RX,           H-32, half, 20))
        d["result_label"].setFrame_(NSMakeRect(RX+half+12,   H-32, half, 20))

        d["orig_view"   ].setFrame_(NSMakeRect(RX,           60, half, IVH))
        d["result_view" ].setFrame_(NSMakeRect(RX+half+12,   60, half, IVH))

        d["palette_label"].setFrame_(NSMakeRect(RX+half+12,  44, 55, 14))
        d["palette"      ].setFrame_(NSMakeRect(RX+half+12,  26, half, 16))
        d["info"         ].setFrame_(NSMakeRect(RX,          12, half, 36))

        # The image views compute centering + clamp pan inside drawRect_, so
        # just trigger a redraw — they'll re-fit themselves automatically.
        d["orig_view"  ].setNeedsDisplay_(True)
        d["result_view"].setNeedsDisplay_(True)

    # ── UI helpers ────────────────────────────────────────────────────────

    @objc.python_method
    def _lbl(self, text, frame):
        t = NSTextField.alloc().initWithFrame_(frame)
        t.setStringValue_(text); t.setEditable_(False)
        t.setBordered_(False); t.setDrawsBackground_(False)
        # labelColor auto-adapts: black on Light, near-white on Dark.
        t.setTextColor_(NSColor.labelColor())
        t.setFont_(NSFont.systemFontOfSize_(12)); return t

    @objc.python_method
    def _numfield(self, frame, default, tag):
        t = NSTextField.alloc().initWithFrame_(frame)
        t.setStringValue_(default); t.setEditable_(True)
        t.setFont_(NSFont.systemFontOfSize_(12))
        t.setTag_(tag); t.setTarget_(self); t.setAction_("onDim:")
        return t

    @objc.python_method
    def _btn(self, title, frame, action, enabled=True):
        b = NSButton.alloc().initWithFrame_(frame)
        b.setTitle_(title); b.setBezelStyle_(NSBezelStyleRounded)
        b.setTarget_(self); b.setAction_(action); b.setEnabled_(enabled); return b

    # ── Saved-palette persistence ─────────────────────────────────────────
    # Lospec palettes loaded by URL/slug are written here so they survive
    # restarts. Path follows the macOS Application Support convention.

    @objc.python_method
    def _palettes_file_path(self):
        base = os.path.expanduser("~/Library/Application Support/PixelArtConverter")
        return os.path.join(base, "palettes.json")

    @objc.python_method
    def _load_saved_palettes(self):
        import json
        path = self._palettes_file_path()
        try:
            with open(path, "r") as f:
                data = json.load(f)
            # Defensively check shape: dict[str, list[str]]
            if not isinstance(data, dict): return {}
            return {k: list(v) for k, v in data.items()
                    if isinstance(v, (list, tuple))}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    @objc.python_method
    def _save_all_palettes(self):
        import json
        path = self._palettes_file_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.__dict__.get("custom_palettes", {}), f, indent=2)
        except Exception as e:
            print(f"Warning: could not save palettes: {e}")

    @objc.python_method
    def _check(self, title, frame):
        b = NSButton.alloc().initWithFrame_(frame)
        b.setButtonType_(NSSwitchButton); b.setTitle_(title); b.setState_(0)
        b.setTarget_(self); b.setAction_("onConvertSettings:"); return b

    @objc.python_method
    def _sep(self, parent, x, y, w):
        s = NSBox.alloc().initWithFrame_(NSMakeRect(x, y, w, 1))
        s.setBoxType_(NSBoxSeparator); parent.addSubview_(s)

    @objc.python_method
    def _params(self):
        d = self.__dict__
        try:   w = max(1, int(d["w_field"].stringValue()))
        except: w = 64
        try:   h = max(1, int(d["h_field"].stringValue()))
        except: h = 64
        colors   = int(d["colors_sl"].intValue())
        dither   = d["dither_chk"].state()   == NSOnState
        rembg    = d["rembg_chk"].state()    == NSOnState
        outline  = d["outline_chk"].state()  == NSOnState
        # titleOfSelectedItem returns NSString — must convert to Python str
        bg_model = str(d["bg_model_pop"].titleOfSelectedItem())

        # Resolve fixed palette (None = K-means auto)
        palette_name = str(d["palette_pop"].titleOfSelectedItem())
        fixed_palette = None
        if palette_name in LOSPEC_PALETTES and LOSPEC_PALETTES[palette_name]:
            fixed_palette = _palette_to_rgb_array(LOSPEC_PALETTES[palette_name])
        elif palette_name in d.get("custom_palettes", {}):
            fixed_palette = _palette_to_rgb_array(d["custom_palettes"][palette_name])

        bright   = int(d["bright_sl"].intValue())
        contr    = int(d["contr_sl"].intValue())
        sat      = int(d["sat_sl"].intValue())
        return (w, h, colors, dither, rembg, outline, bg_model,
                fixed_palette, palette_name, bright, contr, sat)

    @objc.python_method
    def _lock_ui(self, locked):
        """Disable/enable every interactive control while processing."""
        d  = self.__dict__
        on = not locked
        for k in ("preset_pop", "size_pop_unused",
                  "colors_sl", "dither_chk", "rembg_chk",
                  "outline_chk", "bg_model_pop", "scale_pop",
                  "palette_pop", "bright_sl", "contr_sl", "sat_sl",
                  "grid_chk", "sheet_chk",
                  "new_btn", "lock_btn", "save_btn", "krita_btn", "copy_btn"):
            ctrl = d.get(k)
            if ctrl is not None:
                ctrl.setEnabled_(on)
        # Fields need both enabled + editable
        for k in ("w_field", "h_field", "sheet_cols", "sheet_rows"):
            ctrl = d.get(k)
            if ctrl is not None:
                ctrl.setEnabled_(on)
                ctrl.setEditable_(on)
        # Preset popup
        pp = d.get("preset_pop")
        if pp: pp.setEnabled_(on)
        # Drop zone: store flag; mouseDown_ / performDragOperation_ check it
        d["ui_locked"] = locked

    @objc.python_method
    def _enable_export(self, on):
        for k in ("save_btn", "krita_btn", "copy_btn"):
            self.__dict__[k].setEnabled_(on)

    @objc.python_method
    def _set_status(self, msg):
        self.__dict__["status"].setStringValue_(msg)

    # ── Load ──────────────────────────────────────────────────────────────

    @objc.python_method
    def _load(self, paths):
        """Accept a list of file paths. Multiple paths → animation frames.
        Single path with Sprite Sheet checked → split by Cols × Rows."""
        # Backwards-compatibility: tolerate a single string too.
        if isinstance(paths, str):
            paths = [paths]
        if not paths:
            return
        try:
            d = self.__dict__
            sheet_mode = (d.get("sheet_chk") is not None and
                          d["sheet_chk"].state() == NSOnState)
            frames = []
            if len(paths) == 1 and sheet_mode:
                img = Image.open(paths[0]).convert("RGBA")
                cols = max(1, int(d["sheet_cols"].stringValue() or "1"))
                rows = max(1, int(d["sheet_rows"].stringValue() or "1"))
                frames = split_sprite_sheet(img, cols, rows)
                label = f"{os.path.basename(paths[0])}  {cols}×{rows} = {len(frames)} frames"
                preview_img = img            # show the whole sheet in Original panel
            else:
                for p in paths:
                    frames.append(Image.open(p).convert("RGBA"))
                if len(frames) > 1:
                    label = f"{len(frames)} frames  ({frames[0].width}×{frames[0].height}px)"
                    preview_img = compose_sprite_sheet(frames)
                else:
                    label = f"{os.path.basename(paths[0])}  {frames[0].width}×{frames[0].height}px"
                    preview_img = frames[0]

            d["frames"]    = frames
            d["src_paths"] = paths
            ov = d["orig_view"]
            ov.setImage_(pil_to_nsimage(preview_img))
            # Auto-fit: scale the source image so the whole thing is visible
            # in the Original panel on load. User can scroll/pinch from there.
            ps = ov.frame().size
            iw, ih = preview_img.size
            if iw > 0 and ih > 0 and ps.width > 0 and ps.height > 0:
                fit = min(ps.width / iw, ps.height / ih)
                fit = min(1.0, max(SCALE_MIN, fit))
                ov.setPixelScale(fit)
            else:
                ov.setPixelScale(1)
            self._set_status(label)
            self._run_convert()
        except Exception as e:
            self._set_status(f"Error loading: {e}")

    # ── Convert ───────────────────────────────────────────────────────────

    @objc.python_method
    def _run_convert(self):
        d = self.__dict__
        if not d.get("frames") or d["busy"]: return
        d["busy"] = True
        try:
            (w, h, colors, dither, rembg, outline, bg_model,
             fixed_palette, _pname, bright, contr, sat) = self._params()
        except Exception as e:
            self._set_status(f"Settings error: {e}")
            d["busy"] = False
            return
        n = len(d["frames"])
        if n > 1:
            status = f"Processing {n} frames (shared palette)…"
        else:
            status = "Removing background (AI)…" if rembg else "Processing…"
        self._set_status(status)
        self._lock_ui(True)
        if d.get("drop_zone"): d["drop_zone"].__dict__["locked"] = True
        args = ([f.copy() for f in d["frames"]], w, h, colors, dither, rembg, outline,
                bg_model, fixed_palette, bright, contr, sat)
        threading.Thread(target=self._thread, args=(args,), daemon=True).start()

    @objc.python_method
    def _thread(self, args):
        (frames, w, h, colors, dither, rembg, outline, bg_model,
         fixed_palette, bright, contr, sat) = args
        try:
            import sys
            mod = sys.modules[__name__]
            mod._last_rembg_status = "ok"
            if len(frames) > 1:
                result_frames = make_pixel_art_animation(
                    frames, w, h, colors, dither, rembg, outline,
                    bg_model, fixed_palette=fixed_palette,
                    brightness=bright, contrast=contr, saturation=sat)
                self.__dict__["result_frames"] = result_frames
                # The composed sheet is what the preview shows and what gets saved.
                result = compose_sprite_sheet(result_frames)
            else:
                result = make_pixel_art(
                    frames[0], w, h, colors, dither, rembg, outline,
                    bg_model, fixed_palette=fixed_palette,
                    brightness=bright, contrast=contr, saturation=sat)
                self.__dict__["result_frames"] = [result]
            self.__dict__["rembg_status"] = mod._last_rembg_status
            self.__dict__["result_img"] = result
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "onDone:", None, False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.__dict__["thread_err"] = str(e)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "onErr:", None, False)

    def onDone_(self, _):
        d      = self.__dict__
        result = d["result_img"]
        w, h   = result.size
        scale  = SCALES[d["scale_pop"].indexOfSelectedItem()]
        rv     = d["result_view"]
        rv.setImage_(pil_to_nsimage(result))
        rv.setPixelScale(scale)
        d["palette"].setColors(extract_palette(result))
        n_colors = int(d["colors_sl"].intValue())
        n_frames = len(d.get("result_frames") or [])
        if n_frames > 1:
            fw, fh = d["result_frames"][0].size
            d["info"].setStringValue_(
                f"{n_frames} frames · {fw}×{fh}px each · {n_colors} colors (shared)")
        else:
            d["info"].setStringValue_(f"{w}×{h}px  ·  {n_colors} colors")
        if d.get("rembg_status") == "fallback":
            self._set_status("⚠ rembg found no subject — original alpha kept")
        else:
            self._set_status("Done ✓")
        d["busy"] = False
        self._lock_ui(False)
        if d.get("drop_zone"): d["drop_zone"].__dict__["locked"] = False
        self._enable_export(True)

    def onErr_(self, _):
        d = self.__dict__
        self._set_status(f"Error: {d.get('thread_err','unknown')}")
        d["busy"] = False
        self._lock_ui(False)
        if d.get("drop_zone"): d["drop_zone"].__dict__["locked"] = False

    # ── Actions ───────────────────────────────────────────────────────────

    @objc.IBAction
    def onPreset_(self, sender):
        idx = sender.indexOfSelectedItem()
        if idx < len(PRESETS) - 1:
            _, pw, ph = PRESETS[idx]
            d = self.__dict__
            d["w_field"].setStringValue_(str(pw))
            d["h_field"].setStringValue_(str(ph))
        self._run_convert()

    @objc.IBAction
    def onDim_(self, sender):
        d = self.__dict__
        # Update the other field if aspect is locked
        if d.get("aspect_locked") and d.get("frames"):
            # Use first frame for aspect calc (animation frames share dimensions)
            sw, sh = d["frames"][0].size
            try:
                if sender.tag() == 1:   # W field
                    nw = max(1, int(sender.stringValue()))
                    nh = max(1, round(nw * sh / sw))
                    d["h_field"].setStringValue_(str(nh))
                else:                   # H field
                    nh = max(1, int(sender.stringValue()))
                    nw = max(1, round(nh * sw / sh))
                    d["w_field"].setStringValue_(str(nw))
            except Exception:
                pass
        # Switch preset popup to Custom
        d["preset_pop"].selectItemAtIndex_(len(PRESETS) - 1)
        self._run_convert()

    @objc.IBAction
    def onLock_(self, sender):
        self.__dict__["aspect_locked"] = (sender.state() == NSOnState)

    @objc.IBAction
    def onColors_(self, sender):
        n = int(sender.intValue())
        self.__dict__["colors_lbl"].setStringValue_(f"Colors: {n}")
        self._run_convert()

    @objc.IBAction
    def onAdjust_(self, sender):
        d = self.__dict__
        d["bright_lbl"].setStringValue_(f"Bright: {int(d['bright_sl'].intValue())}")
        d["contr_lbl"].setStringValue_(f"Contr: {int(d['contr_sl'].intValue())}")
        d["sat_lbl"].setStringValue_(f"Sat: {int(d['sat_sl'].intValue())}")
        self._run_convert()

    @objc.IBAction
    def onConvertSettings_(self, _):
        self._run_convert()

    @objc.IBAction
    def onPalette_(self, sender):
        title = str(sender.titleOfSelectedItem())
        if title == LOSPEC_LOAD_OPTION:
            # Don't trigger conversion until we've actually loaded something.
            self._prompt_lospec(sender)
            return
        self._run_convert()

    @objc.python_method
    def _prompt_lospec(self, popup):
        # Custom modal NSWindow — has a normal responder chain so Cmd+V works.
        rect = NSMakeRect(0, 0, 480, 150)
        mask = NSWindowStyleMaskTitled
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, mask, NSBackingStoreBuffered, False)
        win.setTitle_("Load palette from Lospec")
        win.center()
        cv = win.contentView()

        lbl = self._lbl("Slug (e.g. 'vintage-berry') or full Lospec URL:",
                        NSMakeRect(20, 110, 440, 22))
        cv.addSubview_(lbl)

        # Pre-fill from clipboard if it looks like a URL/slug — saves the user a paste.
        pb = NSPasteboard.generalPasteboard()
        clip = pb.stringForType_("public.utf8-plain-text") or ""
        clip = str(clip).strip()
        prefill = clip if (clip.startswith("http") and "lospec" in clip) else "vintage-berry"

        field = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 78, 400, 26))
        field.setStringValue_(prefill)
        field.setBezeled_(True)
        field.setEditable_(True)
        field.setSelectable_(True)
        cv.addSubview_(field)

        # Explicit Paste button — guaranteed to work regardless of menu/responder issues.
        paste_btn = NSButton.alloc().initWithFrame_(NSMakeRect(425, 78, 35, 26))
        paste_btn.setTitle_("📋")
        paste_btn.setBezelStyle_(NSBezelStyleRounded)
        paste_btn.setTarget_(self); paste_btn.setAction_("onLospecPasteClip:")
        cv.addSubview_(paste_btn)

        cancel = NSButton.alloc().initWithFrame_(NSMakeRect(280, 20, 90, 30))
        cancel.setTitle_("Cancel")
        cancel.setBezelStyle_(NSBezelStyleRounded)
        cancel.setKeyEquivalent_("\x1b")   # Esc
        cancel.setTarget_(self); cancel.setAction_("onLospecCancel:")
        cv.addSubview_(cancel)

        load = NSButton.alloc().initWithFrame_(NSMakeRect(375, 20, 90, 30))
        load.setTitle_("Load")
        load.setBezelStyle_(NSBezelStyleRounded)
        load.setKeyEquivalent_("\r")       # Return = default
        load.setTarget_(self); load.setAction_("onLospecOK:")
        cv.addSubview_(load)

        d = self.__dict__
        d["lospec_win"]   = win
        d["lospec_field"] = field
        d["lospec_popup"] = popup
        d.pop("lospec_slug", None)

        win.makeKeyAndOrderFront_(None)
        win.makeFirstResponder_(field)
        ed = field.currentEditor()
        if ed: ed.selectAll_(None)

        NSApplication.sharedApplication().runModalForWindow_(win)
        win.orderOut_(None)

        slug = d.pop("lospec_slug", None)
        if not slug:
            popup.selectItemAtIndex_(0)
            return

        self._set_status(f"Fetching {slug} from Lospec…")
        self._lock_ui(True)
        threading.Thread(target=self._fetch_thread,
                         args=(slug,), daemon=True).start()

    # ── AI prompt template window ─────────────────────────────────────────

    @objc.IBAction
    def onPromptShow_(self, _):
        d = self.__dict__
        if d.get("prompt_win") is not None:
            d["prompt_win"].makeKeyAndOrderFront_(None)
            return

        rect = NSMakeRect(0, 0, 720, 800)
        mask = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                NSWindowStyleMaskResizable)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, mask, NSBackingStoreBuffered, False)
        win.setTitle_("AI Prompt — generate input for the converter")
        win.center()
        cv = win.contentView()

        # Header + mode/target/preset pickers
        header = self._lbl(
            "Edit the values below. The prompt updates live. Variables are highlighted in blue.",
            NSMakeRect(20, 760, 680, 22))
        header.setTextColor_(NSColor.secondaryLabelColor())
        cv.addSubview_(header)

        cv.addSubview_(self._lbl("Type:", NSMakeRect(20, 725, 50, 22)))
        mode_pop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(75, 723, 250, 26), False)
        mode_pop.addItemWithTitle_("Animation frames sprite sheet")
        mode_pop.addItemWithTitle_("Single image / object")
        mode_pop.selectItemAtIndex_(0)
        mode_pop.setTarget_(self); mode_pop.setAction_("onPromptModeChange:")
        cv.addSubview_(mode_pop); d["prompt_mode_pop"] = mode_pop

        # Action preset popup (Frames-mode only) — picks a pre-written
        # frame-by-frame action choreography.
        ap_lbl = self._lbl("Action preset:", NSMakeRect(335, 725, 95, 22))
        cv.addSubview_(ap_lbl); d["prompt_action_preset_lbl"] = ap_lbl
        ap = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(430, 723, 270, 26), False)
        for name in ACTION_PRESETS.keys():
            ap.addItemWithTitle_(name)
        ap.selectItemAtIndex_(0)   # "Custom" first
        ap.setTarget_(self); ap.setAction_("onPromptActionPreset:")
        cv.addSubview_(ap); d["prompt_action_preset_pop"] = ap

        # Target model — switches between ChatGPT/DALL-E and Gemini/Imagen
        # variants of the prompt. Gemini variant pushes harder for iconic
        # mascot detail since plain prompts give it under-detailed art.
        cv.addSubview_(self._lbl("Target:", NSMakeRect(20, 685, 60, 22)))
        target_pop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(75, 683, 250, 26), False)
        target_pop.addItemWithTitle_("ChatGPT (DALL-E 3)")
        target_pop.addItemWithTitle_("Gemini (Imagen)")
        target_pop.selectItemAtIndex_(0)
        target_pop.setTarget_(self); target_pop.setAction_("onPromptTargetChange:")
        cv.addSubview_(target_pop); d["prompt_target_pop"] = target_pop

        # ── FRAMES MODE FIELDS ────────────────────────────────────────────
        # Frame count
        f_lbl1 = self._lbl("Frame count (N):", NSMakeRect(20, 645, 130, 22))
        cv.addSubview_(f_lbl1)
        nf = PasteableTextField.alloc().initWithFrame_(NSMakeRect(155, 642, 60, 26))
        nf.setStringValue_(PROMPT_DEFAULTS_FRAMES["N"])
        nf.setBezeled_(True); nf.setEditable_(True); nf.setSelectable_(True)
        nf.setTarget_(self); nf.setAction_("onPromptVarChanged:")
        nf.setDelegate_(self)
        cv.addSubview_(nf); d["prompt_n"] = nf

        # Subject (frames)
        f_lbl2 = self._lbl("Subject:", NSMakeRect(20, 605, 130, 22))
        cv.addSubview_(f_lbl2)
        sf = PasteableTextField.alloc().initWithFrame_(NSMakeRect(155, 602, 545, 26))
        sf.setStringValue_(PROMPT_DEFAULTS_FRAMES["SUBJECT"])
        sf.setBezeled_(True); sf.setEditable_(True); sf.setSelectable_(True)
        sf.setTarget_(self); sf.setAction_("onPromptVarChanged:")
        sf.setDelegate_(self)
        cv.addSubview_(sf); d["prompt_subject"] = sf

        # View / angle (frames) — combo box: pick from preset list OR type custom
        f_lbl4 = self._lbl("View:", NSMakeRect(20, 565, 130, 22))
        cv.addSubview_(f_lbl4)
        f_view = NSComboBox.alloc().initWithFrame_(NSMakeRect(155, 562, 545, 26))
        for v in VIEW_PRESETS: f_view.addItemWithObjectValue_(v)
        f_view.setStringValue_(PROMPT_DEFAULTS_FRAMES["VIEW"])
        f_view.setNumberOfVisibleItems_(8)
        f_view.setEditable_(True); f_view.setSelectable_(True)
        f_view.setDelegate_(self)
        cv.addSubview_(f_view); d["prompt_frames_view"] = f_view

        # Background color (frames) — combo box of common solid colors with hex codes
        f_lbl5 = self._lbl("Background:", NSMakeRect(20, 525, 130, 22))
        cv.addSubview_(f_lbl5)
        f_bg = NSComboBox.alloc().initWithFrame_(NSMakeRect(155, 522, 545, 26))
        for c in BACKGROUND_PRESETS: f_bg.addItemWithObjectValue_(c)
        f_bg.setStringValue_(PROMPT_DEFAULTS_FRAMES["BACKGROUND"])
        f_bg.setNumberOfVisibleItems_(8)
        f_bg.setEditable_(True); f_bg.setSelectable_(True)
        f_bg.setDelegate_(self)
        cv.addSubview_(f_bg); d["prompt_frames_bg"] = f_bg

        # Action (multi-line)
        f_lbl3 = self._lbl("Action:", NSMakeRect(20, 480, 130, 22))
        cv.addSubview_(f_lbl3)
        action_scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(155, 440, 545, 70))
        action_scroll.setHasVerticalScroller_(True)
        action_scroll.setBorderType_(2)
        action_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 545, 70))
        action_view.setString_(PROMPT_DEFAULTS_FRAMES["ACTION"])
        action_view.setFont_(NSFont.systemFontOfSize_(12))
        action_view.setRichText_(False)
        action_view.setDelegate_(self)
        action_scroll.setDocumentView_(action_view)
        cv.addSubview_(action_scroll)
        d["prompt_action"] = action_view
        d["prompt_action_scroll"] = action_scroll
        d["prompt_frames_views"] = [f_lbl1, nf, f_lbl2, sf, f_lbl4, f_view,
                                    f_lbl5, f_bg, f_lbl3, action_scroll]

        # ── SINGLE-IMAGE MODE FIELDS ──────────────────────────────────────
        # Subject (single)
        s_lbl1 = self._lbl("Subject:", NSMakeRect(20, 645, 130, 22))
        cv.addSubview_(s_lbl1)
        s_subj = PasteableTextField.alloc().initWithFrame_(NSMakeRect(155, 642, 545, 26))
        s_subj.setStringValue_(PROMPT_DEFAULTS_SINGLE["SUBJECT"])
        s_subj.setBezeled_(True); s_subj.setEditable_(True); s_subj.setSelectable_(True)
        s_subj.setTarget_(self); s_subj.setAction_("onPromptVarChanged:")
        s_subj.setDelegate_(self)
        cv.addSubview_(s_subj); d["prompt_single_subject"] = s_subj

        # View / angle — combo box: pick from preset list OR type custom
        s_lbl2 = self._lbl("View:", NSMakeRect(20, 605, 130, 22))
        cv.addSubview_(s_lbl2)
        s_view = NSComboBox.alloc().initWithFrame_(NSMakeRect(155, 602, 545, 26))
        for v in VIEW_PRESETS: s_view.addItemWithObjectValue_(v)
        s_view.setStringValue_(PROMPT_DEFAULTS_SINGLE["VIEW"])
        s_view.setNumberOfVisibleItems_(8)
        s_view.setEditable_(True); s_view.setSelectable_(True)
        s_view.setDelegate_(self)
        cv.addSubview_(s_view); d["prompt_single_view"] = s_view

        # Background color — combo box of common solid colors with hex codes
        s_lbl3 = self._lbl("Background:", NSMakeRect(20, 565, 130, 22))
        cv.addSubview_(s_lbl3)
        s_bg = NSComboBox.alloc().initWithFrame_(NSMakeRect(155, 562, 545, 26))
        for c in BACKGROUND_PRESETS: s_bg.addItemWithObjectValue_(c)
        s_bg.setStringValue_(PROMPT_DEFAULTS_SINGLE["BACKGROUND"])
        s_bg.setNumberOfVisibleItems_(8)
        s_bg.setEditable_(True); s_bg.setSelectable_(True)
        s_bg.setDelegate_(self)
        cv.addSubview_(s_bg); d["prompt_single_bg"] = s_bg

        d["prompt_single_views"] = [s_lbl1, s_subj, s_lbl2, s_view, s_lbl3, s_bg]

        # Hide single-mode fields initially (frames is default)
        for v in d["prompt_single_views"]: v.setHidden_(True)

        # ── Rendered prompt (read-only, colored variables) ────────────────
        cv.addSubview_(self._lbl("Rendered prompt:", NSMakeRect(20, 410, 200, 22)))
        prompt_scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, 70, 680, 335))
        prompt_scroll.setHasVerticalScroller_(True)
        prompt_scroll.setBorderType_(2)
        prompt_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 680, 335))
        prompt_view.setEditable_(False)
        prompt_view.setSelectable_(True)
        prompt_view.setFont_(NSFont.systemFontOfSize_(12))
        prompt_view.setRichText_(True)
        prompt_view.setBackgroundColor_(NSColor.textBackgroundColor())
        prompt_view.setTextColor_(NSColor.textColor())
        prompt_scroll.setDocumentView_(prompt_view)
        cv.addSubview_(prompt_scroll)
        d["prompt_view"] = prompt_view

        # Buttons
        copy_btn = NSButton.alloc().initWithFrame_(NSMakeRect(480, 20, 110, 32))
        copy_btn.setTitle_("Copy Prompt")
        copy_btn.setBezelStyle_(NSBezelStyleRounded)
        copy_btn.setTarget_(self); copy_btn.setAction_("onPromptCopy:")
        cv.addSubview_(copy_btn)

        close_btn = NSButton.alloc().initWithFrame_(NSMakeRect(600, 20, 100, 32))
        close_btn.setTitle_("Close")
        close_btn.setBezelStyle_(NSBezelStyleRounded)
        close_btn.setKeyEquivalent_("\x1b")
        close_btn.setTarget_(self); close_btn.setAction_("onPromptClose:")
        cv.addSubview_(close_btn)

        d["prompt_win"]    = win
        d["prompt_mode"]   = "frames"    # default
        d["prompt_target"] = "chatgpt"   # default
        self._render_prompt_view()
        win.makeKeyAndOrderFront_(None)

    @objc.IBAction
    def onPromptModeChange_(self, sender):
        """Toggle between Frames mode and Single-image mode."""
        d = self.__dict__
        idx = sender.indexOfSelectedItem()
        d["prompt_mode"] = "frames" if idx == 0 else "single"
        is_frames = (idx == 0)
        for v in d.get("prompt_frames_views", []): v.setHidden_(not is_frames)
        for v in d.get("prompt_single_views",  []): v.setHidden_(is_frames)
        # Action preset popup is meaningful only in Frames mode
        ap_lbl = d.get("prompt_action_preset_lbl")
        ap_pop = d.get("prompt_action_preset_pop")
        if ap_lbl: ap_lbl.setHidden_(not is_frames)
        if ap_pop: ap_pop.setHidden_(not is_frames)
        self._render_prompt_view()

    @objc.IBAction
    def onPromptTargetChange_(self, sender):
        """Switch between ChatGPT and Gemini prompt variants."""
        idx = sender.indexOfSelectedItem()
        self.__dict__["prompt_target"] = "chatgpt" if idx == 0 else "gemini"
        self._render_prompt_view()

    @objc.IBAction
    def onPromptActionPreset_(self, sender):
        """Apply a pre-written action choreography to N + Action fields."""
        title = str(sender.titleOfSelectedItem())
        n, action = ACTION_PRESETS.get(title, (None, None))
        d = self.__dict__
        if n is not None and d.get("prompt_n"):
            d["prompt_n"].setStringValue_(str(n))
        if action is not None and d.get("prompt_action"):
            d["prompt_action"].setString_(action)
        self._render_prompt_view()

    @objc.python_method
    def _current_prompt_values(self):
        d = self.__dict__
        if d.get("prompt_mode", "frames") == "single":
            return {
                "SUBJECT":    str(d["prompt_single_subject"].stringValue()).strip()
                              or PROMPT_DEFAULTS_SINGLE["SUBJECT"],
                "VIEW":       str(d["prompt_single_view"].stringValue()).strip()
                              or PROMPT_DEFAULTS_SINGLE["VIEW"],
                "BACKGROUND": str(d["prompt_single_bg"].stringValue()).strip()
                              or PROMPT_DEFAULTS_SINGLE["BACKGROUND"],
            }
        action_view = d.get("prompt_action")
        return {
            "N":          str(d["prompt_n"].stringValue()).strip()              or PROMPT_DEFAULTS_FRAMES["N"],
            "SUBJECT":    str(d["prompt_subject"].stringValue()).strip()        or PROMPT_DEFAULTS_FRAMES["SUBJECT"],
            "ACTION":     str(action_view.string()).strip()                     or PROMPT_DEFAULTS_FRAMES["ACTION"],
            "VIEW":       str(d["prompt_frames_view"].stringValue()).strip()    or PROMPT_DEFAULTS_FRAMES["VIEW"],
            "BACKGROUND": str(d["prompt_frames_bg"].stringValue()).strip()      or PROMPT_DEFAULTS_FRAMES["BACKGROUND"],
        }

    @objc.python_method
    def _current_prompt_template(self):
        d = self.__dict__
        mode   = d.get("prompt_mode",   "frames")
        target = d.get("prompt_target", "chatgpt")
        return PROMPT_TEMPLATES[(mode, target)]

    @objc.python_method
    def _render_prompt_view(self):
        d = self.__dict__
        view = d.get("prompt_view")
        if view is None: return
        text, ranges = render_prompt(self._current_prompt_template(),
                                     self._current_prompt_values())
        attr = NSMutableAttributedString.alloc().initWithString_(text)
        # Base color: light grey (the template body)
        full = NSMakeRange(0, len(text))
        attr.addAttribute_value_range_(
            NSForegroundColorAttributeName,
            NSColor.textColor(),  # auto-adapts to appearance
            full)
        attr.addAttribute_value_range_(
            NSFontAttributeName,
            NSFont.systemFontOfSize_(12),
            full)
        # Variable values: accent blue
        accent = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.35, 0.7, 1.0, 1.0)
        bold = NSFont.boldSystemFontOfSize_(12)
        for start, length in ranges:
            r = NSMakeRange(start, length)
            attr.addAttribute_value_range_(NSForegroundColorAttributeName, accent, r)
            attr.addAttribute_value_range_(NSFontAttributeName, bold, r)
        view.textStorage().setAttributedString_(attr)

    # NSTextField + NSTextView delegate hook — fires on every keystroke
    def controlTextDidChange_(self, _):
        self._render_prompt_view()

    def textDidChange_(self, _):
        self._render_prompt_view()

    @objc.IBAction
    def onPromptVarChanged_(self, _):
        self._render_prompt_view()

    @objc.IBAction
    def onPromptCopy_(self, _):
        text, _ = render_prompt(self._current_prompt_template(),
                                self._current_prompt_values())
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, "public.utf8-plain-text")
        mode = "frames" if self.__dict__.get("prompt_mode", "frames") == "frames" else "single"
        self._set_status(f"AI prompt ({mode}) copied ✓")

    @objc.IBAction
    def onPromptClose_(self, _):
        d = self.__dict__
        win = d.pop("prompt_win", None)
        if win is not None: win.orderOut_(None)
        for k in ("prompt_view", "prompt_n", "prompt_subject", "prompt_action",
                  "prompt_action_scroll", "prompt_mode_pop", "prompt_mode",
                  "prompt_single_subject", "prompt_single_view", "prompt_single_bg",
                  "prompt_frames_views", "prompt_single_views",
                  "prompt_action_preset_pop", "prompt_action_preset_lbl"):
            d.pop(k, None)

    # ── Auto-update ───────────────────────────────────────────────────────
    # Pipeline: fetch update.json → compare versions → download new script
    # → SHA256 verify → backup current → write new → relaunch new process
    # → terminate current. No reinstall, no manual download.

    @objc.IBAction
    def onUpdateCheck_(self, _):
        self._set_status("Checking for updates…")
        self.__dict__["update_btn"].setEnabled_(False)
        threading.Thread(target=self._update_check_thread, daemon=True).start()

    @objc.python_method
    def _update_check_thread(self):
        import urllib.request, json
        try:
            req = urllib.request.Request(
                _UPDATE_MANIFEST_URL,
                headers={"User-Agent": f"PixelArtConverter/{__version__}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.__dict__["update_manifest"] = json.loads(
                    resp.read().decode("utf-8", errors="replace"))
            self.__dict__["update_check_err"] = None
        except Exception as e:
            self.__dict__["update_manifest"] = None
            self.__dict__["update_check_err"] = str(e)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "onUpdateCheckDone:", None, False)

    def onUpdateCheckDone_(self, _):
        d = self.__dict__
        d["update_btn"].setEnabled_(True)
        err = d.pop("update_check_err", None)
        manifest = d.pop("update_manifest", None)
        if err or not manifest:
            self._set_status(f"Update check failed: {err or 'no data'}")
            return
        latest = str(manifest.get("version", "0.0.0"))
        if _version_tuple(latest) <= _version_tuple(__version__):
            self._set_status(f"You're on the latest version (v{__version__})")
            return
        self._show_update_dialog(manifest)

    @objc.python_method
    def _show_update_dialog(self, manifest):
        latest = manifest.get("version", "?")
        notes  = manifest.get("notes", "(no release notes)")
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Update available — v{latest}")
        alert.setInformativeText_(
            f"You are running v{__version__}.\n\n"
            f"What's new in v{latest}:\n\n{notes}\n\n"
            f"The app will download, install, and relaunch automatically.")
        alert.addButtonWithTitle_("Update Now")
        alert.addButtonWithTitle_("Later")
        if alert.runModal() == NSAlertFirstButtonReturn:
            self._set_status(f"Downloading v{latest}…")
            self._lock_ui(True)
            threading.Thread(
                target=self._download_thread, args=(manifest,), daemon=True
            ).start()

    @objc.python_method
    def _download_thread(self, manifest):
        import urllib.request, hashlib, sys
        url = manifest.get("url")
        expected = (manifest.get("sha256") or "").lower().strip()
        try:
            if not url:
                raise ValueError("manifest missing 'url'")
            req = urllib.request.Request(
                url, headers={"User-Agent": f"PixelArtConverter/{__version__}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read()
            if expected:
                got = hashlib.sha256(payload).hexdigest().lower()
                if got != expected:
                    raise ValueError(
                        f"SHA256 mismatch (got {got[:12]}…, expected {expected[:12]}…)")
            # Write to disk: backup current, replace with new bytes.
            script_path = os.path.abspath(__file__)
            if not os.access(os.path.dirname(script_path), os.W_OK):
                raise PermissionError(
                    f"No write permission in {os.path.dirname(script_path)}")
            backup_path = script_path + ".bak"
            try:
                with open(script_path, "rb") as f: cur = f.read()
                with open(backup_path, "wb") as f: f.write(cur)
            except Exception:
                pass   # backup is best-effort; don't fail the update on it
            with open(script_path, "wb") as f: f.write(payload)
            self.__dict__["update_ok"]   = True
            self.__dict__["update_path"] = script_path
        except Exception as e:
            self.__dict__["update_ok"]  = False
            self.__dict__["update_err"] = str(e)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "onUpdateDownloaded:", None, False)

    def onUpdateDownloaded_(self, _):
        import sys
        d = self.__dict__
        self._lock_ui(False)
        if not d.pop("update_ok", False):
            err = d.pop("update_err", "unknown error")
            self._set_status(f"Update failed: {err}")
            return
        path = d.pop("update_path")
        self._set_status("Update installed. Relaunching…")
        # Spawn the new process and terminate the old one. The script file is
        # already replaced on disk; the new process picks up the new version.
        subprocess.Popen([sys.executable, path],
                         start_new_session=True)
        # Tiny delay so the user can see the status flip; then quit cleanly.
        NSApplication.sharedApplication().performSelector_withObject_afterDelay_(
            "terminate:", None, 0.3)

    @objc.IBAction
    def onLospecPasteClip_(self, _):
        # Read the system clipboard directly and stuff its text into the field.
        pb = NSPasteboard.generalPasteboard()
        text = pb.stringForType_("public.utf8-plain-text") or ""
        self.__dict__["lospec_field"].setStringValue_(str(text).strip())

    @objc.IBAction
    def onLospecOK_(self, _):
        d = self.__dict__
        d["lospec_slug"] = str(d["lospec_field"].stringValue()).strip()
        NSApplication.sharedApplication().stopModal()

    @objc.IBAction
    def onLospecCancel_(self, _):
        NSApplication.sharedApplication().stopModal()

    @objc.python_method
    def _fetch_thread(self, slug):
        try:
            name, hex_list = fetch_lospec_palette(slug)
            self.__dict__["_lospec_result"] = (name, hex_list)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "onLospecDone:", None, False)
        except Exception as e:
            self.__dict__["_lospec_err"] = str(e)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "onLospecErr:", None, False)

    def onLospecDone_(self, _):
        d = self.__dict__
        name, hex_list = d.pop("_lospec_result")
        title = f"Lospec: {name}"
        already_loaded = title in d["custom_palettes"]
        d["custom_palettes"][title] = hex_list
        pop = d["palette_pop"]
        if not already_loaded:
            # Insert before the "Load from Lospec…" entry (last item)
            pop.insertItemWithTitle_atIndex_(title, pop.numberOfItems() - 1)
        pop.selectItemWithTitle_(title)
        # Persist so the palette is available next time the app starts
        self._save_all_palettes()
        self._lock_ui(False)
        self._set_status(f"Loaded {title}  ·  saved for next session")
        self._run_convert()

    def onLospecErr_(self, _):
        d = self.__dict__
        err = d.pop("_lospec_err", "unknown error")
        d["palette_pop"].selectItemAtIndex_(0)
        self._lock_ui(False)
        self._set_status(f"Lospec error: {err}")

    @objc.IBAction
    def onScale_(self, _):
        # The Preview Scale popup controls the Pixel Art panel only.
        # The Original panel keeps its own independent zoom (changeable via
        # scroll/pinch on the Original panel itself).
        d = self.__dict__
        scale = SCALES[d["scale_pop"].indexOfSelectedItem()]
        if d.get("result_view") is not None:
            d["result_view"].setPixelScale(scale)

    @objc.python_method
    def _sync_scale(self, scale, sender=None):
        """Called by a CheckerImageView when scroll/pinch changes its zoom.
        Each panel zooms independently — only the sender view is updated.
        The Preview Scale popup tracks the Pixel Art panel only."""
        scale = max(SCALE_MIN, min(SCALE_MAX, float(scale)))
        d = self.__dict__
        if sender is None:
            # Popup-driven (no gesture sender) — Pixel Art panel only.
            target = d.get("result_view")
            if target is not None:
                target.setPixelScale(scale)
            return
        # Gesture path: update only the panel the user scrolled/pinched.
        sender.setPixelScale(scale)
        # Pop-up reflects the Pixel Art panel only; Original is independent.
        if sender is d.get("result_view") and d.get("scale_pop") is not None:
            idx = min(range(len(SCALES)), key=lambda i: abs(SCALES[i] - scale))
            d["scale_pop"].selectItemAtIndex_(idx)

    @objc.IBAction
    def onGrid_(self, sender):
        show = sender.state() == NSOnState
        d = self.__dict__
        for k in ("orig_view", "result_view"):
            v = d.get(k)
            if v is not None: v.setShowGrid(show)

    @objc.IBAction
    def onNew_(self, _):
        """Clear all loaded data and reset every setting back to defaults."""
        d = self.__dict__
        # If a conversion is running, ignore — _lock_ui already disables the button.
        if d.get("busy"): return

        # Clear loaded source + result state
        d["frames"]        = []
        d["src_paths"]     = []
        d["result_img"]    = None
        d["result_frames"] = []
        d["rembg_status"]  = "ok"

        # Clear the preview views
        d["orig_view"  ].setImage_(None); d["orig_view"  ].setNeedsDisplay_(True)
        d["result_view"].setImage_(None); d["result_view"].setNeedsDisplay_(True)
        d["palette"].setColors([])

        # Reset every parameter to its default
        d["preset_pop"].selectItemAtIndex_(4)               # 64×64 preset
        d["w_field"   ].setStringValue_("64")
        d["h_field"   ].setStringValue_("64")
        d["lock_btn"  ].setState_(NSOnState); d["aspect_locked"] = True

        d["colors_sl"].setIntValue_(24); d["colors_lbl"].setStringValue_("Colors: 24")
        d["palette_pop"].selectItemAtIndex_(0)              # Auto (K-means)

        d["bright_sl"].setIntValue_(0); d["bright_lbl"].setStringValue_("Bright: 0")
        d["contr_sl" ].setIntValue_(0); d["contr_lbl" ].setStringValue_("Contr: 0")
        d["sat_sl"   ].setIntValue_(0); d["sat_lbl"   ].setStringValue_("Sat: 0")

        d["dither_chk"].setState_(0)
        d["rembg_chk" ].setState_(0)
        d["bg_model_pop"].selectItemAtIndex_(0)             # isnet-general-use
        d["outline_chk"].setState_(NSOnState)               # outline ON by default

        d["scale_pop"].selectItemAtIndex_(2)                # 4×
        d["grid_chk" ].setState_(0)

        d["sheet_chk" ].setState_(0)
        d["sheet_cols"].setStringValue_("4")
        d["sheet_rows"].setStringValue_("1")

        # Drop zone is unlocked, export buttons disabled until a new image is loaded
        if d.get("drop_zone"): d["drop_zone"].__dict__["locked"] = False
        self._enable_export(False)

        d["info"].setStringValue_("")
        self._set_status("Drop a PNG to begin")

    @objc.python_method
    def _build_save_accessory(self):
        """Build the NSSavePanel accessory view with extra export options."""
        d = self.__dict__
        n_frames = len(d.get("result_frames") or [])
        is_anim = n_frames > 1

        # Accessory height depends on animation vs single — anim adds GIF + frames rows.
        height = 168 if is_anim else 112
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 360, height))

        def chk(title, frame, default_on=False):
            b = NSButton.alloc().initWithFrame_(frame)
            b.setButtonType_(NSSwitchButton); b.setTitle_(title)
            b.setState_(NSOnState if default_on else 0)
            return b

        y = height - 4
        # Header
        y -= 22
        view.addSubview_(self._lbl("Companion files (saved alongside the PNG):",
                                   NSMakeRect(10, y, 340, 18)))

        # Multi-resolution
        y -= 26
        mr = chk("Also save at 32× and 128× variants",
                 NSMakeRect(15, y, 340, 22))
        view.addSubview_(mr)
        d["_save_multires_chk"] = mr

        # TexturePacker JSON
        y -= 26
        tp = chk("TexturePacker JSON (atlas metadata for game engines)",
                 NSMakeRect(15, y, 340, 22),
                 default_on=is_anim)   # ON by default for animations
        view.addSubview_(tp)
        d["_save_json_chk"] = tp

        if is_anim:
            # Animated GIF (preview format)
            y -= 26
            gif = chk("Animated GIF preview (8 fps)",
                      NSMakeRect(15, y, 340, 22))
            view.addSubview_(gif)
            d["_save_gif_chk"] = gif

            # Individual frames
            y -= 26
            ind = chk(f"Individual frame PNGs ({n_frames} files)",
                      NSMakeRect(15, y, 340, 22))
            view.addSubview_(ind)
            d["_save_indiv_chk"] = ind
        else:
            d["_save_gif_chk"]   = None
            d["_save_indiv_chk"] = None

        return view

    @objc.IBAction
    def onSave_(self, _):
        d = self.__dict__
        if d["result_img"] is None: return

        panel = NSSavePanel.savePanel()
        panel.setAllowedFileTypes_(["png"])
        panel.setAccessoryView_(self._build_save_accessory())

        paths = d.get("src_paths") or []
        n_frames = len(d.get("result_frames") or [])
        if paths:
            base = os.path.splitext(os.path.basename(paths[0]))[0]
            w, h = self._params()[:2]
            if n_frames > 1:
                panel.setNameFieldStringValue_(f"{base}_{n_frames}frames_{w}x{h}.png")
            else:
                panel.setNameFieldStringValue_(f"{base}_{w}x{h}.png")

        if panel.runModal() != NSModalResponseOK: return
        path = panel.URL().path()

        # Write the primary PNG (sprite sheet for animations, single image otherwise)
        d["result_img"].save(path)
        written = [os.path.basename(path)]

        # Read the accessory checkboxes
        want_multires = (d.get("_save_multires_chk") is not None and
                         d["_save_multires_chk"].state() == NSOnState)
        want_json     = (d.get("_save_json_chk")     is not None and
                         d["_save_json_chk"].state() == NSOnState)
        want_gif      = (d.get("_save_gif_chk")      is not None and
                         d["_save_gif_chk"].state() == NSOnState)
        want_indiv    = (d.get("_save_indiv_chk")    is not None and
                         d["_save_indiv_chk"].state() == NSOnState)

        try:
            if want_json:
                jp = self._write_texturepacker_json(path)
                if jp: written.append(os.path.basename(jp))

            if want_gif and n_frames > 1:
                gp = self._write_animated_gif(path)
                if gp: written.append(os.path.basename(gp))

            if want_indiv and n_frames > 1:
                count = self._write_individual_frames(path)
                if count: written.append(f"{count} frame PNGs")

            if want_multires:
                paths_mr = self._write_multires_variants(path)
                for p in paths_mr: written.append(os.path.basename(p))
        except Exception as e:
            self._set_status(f"Saved primary, companion error: {e}")
            return

        self._set_status("Saved → " + ", ".join(written))

    # ── Companion file writers ────────────────────────────────────────────

    @objc.python_method
    def _write_texturepacker_json(self, png_path):
        """Write a TexturePacker-compatible JSON sidecar so engines can auto-slice
        the sprite sheet on import. Format reference:
        https://www.codeandweb.com/texturepacker/documentation/texture-settings#data-formats"""
        import json as _json
        d = self.__dict__
        result = d["result_img"]
        frames = d.get("result_frames") or []
        n = len(frames)
        sheet_w, sheet_h = result.size
        if n > 1:
            fw, fh = frames[0].size
        else:
            fw, fh = sheet_w, sheet_h

        base_no_ext = os.path.splitext(png_path)[0]
        base_name   = os.path.splitext(os.path.basename(png_path))[0]
        png_name    = os.path.basename(png_path)

        # JSON-Hash format (most widely supported by engines)
        frame_dict = {}
        if n > 1:
            for i in range(n):
                key = f"{base_name}_{i:02d}"
                frame_dict[key] = {
                    "frame":            {"x": i*fw, "y": 0, "w": fw, "h": fh},
                    "rotated":          False,
                    "trimmed":          False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": fw, "h": fh},
                    "sourceSize":       {"w": fw, "h": fh},
                    "pivot":            {"x": 0.5, "y": 1.0},  # bottom-center for chars
                }
        else:
            frame_dict[base_name] = {
                "frame":            {"x": 0, "y": 0, "w": fw, "h": fh},
                "rotated":          False,
                "trimmed":          False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": fw, "h": fh},
                "sourceSize":       {"w": fw, "h": fh},
                "pivot":            {"x": 0.5, "y": 1.0},
            }

        manifest = {
            "frames": frame_dict,
            "meta": {
                "app":       "Pixel Art Converter",
                "version":   __version__,
                "image":     png_name,
                "format":    "RGBA8888",
                "size":      {"w": sheet_w, "h": sheet_h},
                "scale":     "1",
                "frameTags": ([{"name": "default", "from": 0, "to": n-1, "direction": "forward"}]
                              if n > 1 else []),
            },
        }
        json_path = f"{base_no_ext}.json"
        with open(json_path, "w") as f:
            _json.dump(manifest, f, indent=2)
        return json_path

    @objc.python_method
    def _write_animated_gif(self, png_path):
        """Write an animated GIF preview at 8 fps (125 ms per frame)."""
        d = self.__dict__
        frames = d.get("result_frames") or []
        if len(frames) < 2: return None
        gif_path = os.path.splitext(png_path)[0] + ".gif"
        # GIF doesn't support alpha well; we put fully-transparent pixels on a
        # transparent palette index so most viewers show transparency.
        first = frames[0].convert("RGBA")
        rest  = [f.convert("RGBA") for f in frames[1:]]
        first.save(gif_path,
                   save_all=True, append_images=rest,
                   duration=125, loop=0, disposal=2, transparency=0)
        return gif_path

    @objc.python_method
    def _write_individual_frames(self, png_path):
        """Write each animation frame as its own PNG (frame_01.png, etc.)."""
        d = self.__dict__
        frames = d.get("result_frames") or []
        if len(frames) < 2: return 0
        base_no_ext = os.path.splitext(png_path)[0]
        # Strip any "_Nframes_WxH" suffix that came from the auto-suggested name
        import re
        clean = re.sub(r"_\d+frames_\d+x\d+$", "", base_no_ext)
        for i, f in enumerate(frames, start=1):
            f.save(f"{clean}_frame_{i:02d}.png")
        return len(frames)

    @objc.python_method
    def _write_multires_variants(self, png_path):
        """Re-render and save the same sprite at 32× and 128× resolutions.
        Uses the existing pipeline so palette/dithering/outline are consistent."""
        d = self.__dict__
        if not d.get("frames"): return []
        try:
            (w, h, colors, dither, rembg, outline, bg_model,
             fixed_palette, _pname, bright, contr, sat) = self._params()
        except Exception:
            return []
        base_no_ext = os.path.splitext(png_path)[0]
        # Strip any "_Nframes_WxH" or "_WxH" suffix from base
        import re
        clean = re.sub(r"(_\d+frames)?_\d+x\d+$", "", base_no_ext)
        out_paths = []
        ratio = h / max(w, 1)   # preserve aspect
        for sz in (32, 128):
            if sz == w: continue   # skip the size we just saved
            tw, th = sz, max(1, int(round(sz * ratio)))
            try:
                src_frames = [f.copy() for f in d["frames"]]
                if len(src_frames) > 1:
                    res = make_pixel_art_animation(
                        src_frames, tw, th, colors, dither, rembg, outline,
                        bg_model, fixed_palette=fixed_palette,
                        brightness=bright, contrast=contr, saturation=sat)
                    img = compose_sprite_sheet(res)
                    n = len(res)
                    p = f"{clean}_{n}frames_{tw}x{th}.png"
                else:
                    img = make_pixel_art(
                        src_frames[0], tw, th, colors, dither, rembg, outline,
                        bg_model, fixed_palette=fixed_palette,
                        brightness=bright, contrast=contr, saturation=sat)
                    p = f"{clean}_{tw}x{th}.png"
                img.save(p)
                out_paths.append(p)
            except Exception:
                continue
        return out_paths

    @objc.IBAction
    def onSheet_(self, _):
        # Toggling sprite-sheet mode doesn't auto-reload (we don't keep raw bytes);
        # the user re-drops the file once the toggle is set the way they want.
        d = self.__dict__
        if d["sheet_chk"].state() == NSOnState:
            self._set_status("Sprite-sheet mode ON — drop a single sheet image")
        else:
            self._set_status("Sprite-sheet mode OFF — drop frames or a single image")

    @objc.IBAction
    def onKrita_(self, _):
        d = self.__dict__
        if d["result_img"] is None: return
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        d["result_img"].save(tmp.name); tmp.close()
        subprocess.Popen(["open", "-a", "Krita", tmp.name])
        self._set_status("Opened in Krita")

    @objc.IBAction
    def onCopy_(self, _):
        d = self.__dict__
        if d["result_img"] is None: return
        NSPasteboard.generalPasteboard().clearContents()
        NSPasteboard.generalPasteboard().writeObjects_([pil_to_nsimage(d["result_img"])])
        self._set_status("Copied ✓")


# ── Entry ─────────────────────────────────────────────────────────────────

def _install_app_menu():
    """Install a minimal main menu so Cmd+C/V/X/A reach the focused field.
    Without this, NSAlert text fields silently drop those shortcuts."""
    menu = NSMenu.alloc().init()

    # App menu (left-most, owns Quit)
    app_holder = NSMenuItem.alloc().init()
    menu.addItem_(app_holder)
    app_menu = NSMenu.alloc().init()
    app_holder.setSubmenu_(app_menu)
    app_menu.addItem_(NSMenuItem.alloc()
        .initWithTitle_action_keyEquivalent_("Quit", "terminate:", "q"))

    # Edit menu — this is the part that actually fixes paste
    edit_holder = NSMenuItem.alloc().init()
    menu.addItem_(edit_holder)
    edit_menu = NSMenu.alloc().initWithTitle_("Edit")
    edit_holder.setSubmenu_(edit_menu)
    for title, action, key in [
        ("Undo",       "undo:",       "z"),
        ("Redo",       "redo:",       "Z"),
        (None, None, None),
        ("Cut",        "cut:",        "x"),
        ("Copy",       "copy:",       "c"),
        ("Paste",      "paste:",      "v"),
        ("Select All", "selectAll:",  "a"),
    ]:
        if title is None:
            edit_menu.addItem_(NSMenuItem.separatorItem())
        else:
            edit_menu.addItem_(NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_(title, action, key))

    NSApplication.sharedApplication().setMainMenu_(menu)


def _is_dark_appearance(app):
    """Return True when macOS is currently in Dark mode (system or app-level)."""
    try:
        appearance = app.effectiveAppearance()
        match = appearance.bestMatchFromAppearancesWithNames_(
            ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"])
        return str(match) == "NSAppearanceNameDarkAqua"
    except Exception:
        return False


def _is_dark_view(view):
    """True when the given view is currently rendering in a Dark appearance.

    Use at draw time inside drawRect_ — picks up per-window appearance
    overrides so a Dark-themed window inside a Light system still draws Dark.
    """
    try:
        appearance = view.effectiveAppearance()
        match = appearance.bestMatchFromAppearancesWithNames_(
            ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"])
        return str(match) == "NSAppearanceNameDarkAqua"
    except Exception:
        return False


def _load_app_icon(app):
    """Load docs/icon.png (or icon-dark.png in Dark mode) as the dock icon."""
    here = os.path.dirname(os.path.abspath(__file__))

    # On Tahoe (macOS 26+), the bundle ships Assets.car with the layered
    # AppIcon. Let the system handle styling (light/dark/tinted/clear/glass)
    # natively — setApplicationIconImage_ would override the dynamic layers
    # with a flat PNG.
    if os.path.exists(os.path.join(here, "Assets.car")):
        # operatingSystemVersion() returns a 3-tuple (major, minor, patch)
        # in this PyObjC version, not an NSOperatingSystemVersion struct.
        major = NSProcessInfo.processInfo().operatingSystemVersion()[0]
        if major >= 26:
            return

    dark = _is_dark_appearance(app)
    name = "icon-dark.png" if dark else "icon.png"
    path = os.path.join(here, "docs", name)
    if not os.path.exists(path):
        # Fall back to the light icon if the dark variant is missing.
        path = os.path.join(here, "docs", "icon.png")
    if os.path.exists(path):
        img = NSImage.alloc().initByReferencingFile_(path)
        if img is not None and img.isValid():
            app.setApplicationIconImage_(img)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    _install_app_menu()
    _load_app_icon(app)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.activateIgnoringOtherApps_(True)
    app.run()

if __name__ == "__main__":
    main()
