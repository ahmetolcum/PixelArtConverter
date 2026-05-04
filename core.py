"""
Pixel Art Converter — pure (cross-platform) core.

Image-processing pipeline, palette tables, prompt templates, and shared
state. No AppKit / objc / Foundation here on purpose: this module is what
the macOS native GUI (pixel_art_converter.py) AND a future cross-platform
GUI (e.g. PySide6) both import from.

Heavy deps (skimage, sklearn, rembg) are imported lazily inside the
functions that use them, so importing `core` itself stays cheap.
"""

import io
import urllib.request

import numpy as np
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
__version__ = "2.0.0"
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
