# App Logo / Icon Generation Prompts

Use either of the prompts below in ChatGPT (with image generation enabled) or any DALL-E / Midjourney interface.

The first prompt produces a **macOS app icon** (squircle, for the dock and `.dmg`). The second produces a **branding logo / wordmark** (for the README header, GitHub social card, website).

You'll typically want both. Generate, pick the one you like, and save them at:

- `docs/icon.png` (1024×1024)
- `docs/logo.png` (transparent, ~1200×400)

---

## Prompt 1 — macOS App Icon (squircle, 1024×1024)

```
Design a modern macOS app icon for a tool called "Pixel Art Converter" — a desktop app that turns AI-generated illustrations into game-ready pixel-art sprites. 1024×1024 PNG, transparent corners outside the squircle.

COMPOSITION
- A rounded-square (squircle) tile centered on a transparent canvas with about 80px padding on every side so it sits properly in the macOS dock.
- On top of the squircle, a single iconic pixel-art subject: an 8-bit green tree with a brown trunk, made of clearly visible chunky square pixels, centered, occupying about 60% of the squircle's area.
- The tree must show its discrete pixel grid — every leaf cluster and trunk segment is a hard-edged square, no anti-aliasing, no gradients on the tree.

PALETTE (strict)
- Background squircle: deep indigo-to-teal vertical gradient, hex roughly #1a2538 at top to #1f3a4a at bottom. Subtle.
- Tree: 4 colors only — dark green #2d5a3d, mid green #4a8a4f, light green #7ac070, brown trunk #6b3a1f, dark trunk shadow #3d2310. Total icon palette: 6 colors.

STYLE
- The squircle has a soft outer drop shadow and a subtle top-edge highlight, like polished modern macOS app icons (Big Sur / Sonoma / Sequoia language).
- The pixel-art tree on top is 100% flat — no shading on the tree itself, no glow, no glassy effect, no soft edges. The contrast between the polished frame and the deliberately retro pixel art is the entire visual idea.

DO NOT INCLUDE
- Text, letters, numbers, arrows
- Photographic elements, 3D rendering of the tree
- Gradients within the pixel-art tree itself
- "Before/after" splits or UI mockups
- Watermarks

Must read clearly at 32×32 in the dock.
```

---

## Prompt 2 — Branding Logo / Wordmark (transparent, ~1200×400)

```
Design a horizontal logo for "Pixel Art Converter," a desktop app that turns AI illustrations into pixel art sprites. PNG with transparent background, roughly 1200×400 pixels.

LAYOUT
- Left third: a small mark / symbol — a 16×16 stylized pixel-art square showing a tiny tree silhouette (3-4 visible chunky pixels), in green and brown, on a dark indigo tile with rounded corners. Mark size: about 300×300px in the canvas.
- Right two-thirds: the wordmark "PIXEL ART CONVERTER" rendered in a clean, slightly chunky geometric sans-serif (think Inter Bold, Space Grotesk Bold, or a custom pixel-style font). All caps. Each letter solid, no outline.
- Vertical centering: mark and wordmark share a common centerline.

TYPOGRAPHY
- "PIXEL ART" in bold geometric sans (slightly larger), positioned on top.
- "CONVERTER" below it, same width as "PIXEL ART," in a thinner weight or slight letter-spacing.
- Both in a near-white off-white color (#e8eef2). Or, for a colored variant, a warm yellow #f6b75c.

PALETTE
- Mark tile: dark indigo #1a2538.
- Mark contents: same green/brown as the app icon (#4a8a4f green, #6b3a1f brown).
- Wordmark: off-white #e8eef2.
- All 5 colors. No gradients. No drop shadows on the text.

STYLE
- Modern, clean, technical-looking — feels like a professional developer tool, not a children's app.
- The mark on the left echoes the app icon (so users instantly connect them) but simplified to read at small sizes.

DO NOT INCLUDE
- Photographic elements, 3D effects, glowing edges
- Gradients (anywhere)
- Stock-icon-looking decorations
- Multiple lines of tagline text
```

---

## Tips for getting better results

- **Generate 2–3 variations and pick the best.** ChatGPT/DALL-E rarely nails it on the first try, especially for the discrete-pixels constraint.
- **If the AI smooths the pixel art:** add to the prompt: *"Each pixel of the tree must be a deliberate solid color block at 16-bit retro-game fidelity, like Stardew Valley or Pokémon Gen 3 tile art. No anti-aliasing whatsoever."*
- **If the colors drift:** quote the exact hex codes again at the end: *"Strict palette — only these 6 hex codes: #1a2538, #1f3a4a, #2d5a3d, #4a8a4f, #7ac070, #6b3a1f, #3d2310. No other colors."*
- **For the wordmark:** if the typography looks off, render the text yourself in a real font (Inter, Space Grotesk, IBM Plex Sans) — AI is unreliable at letterforms. Just generate the tile/mark from prompt 1 and combine in a separate image editor.

---

## Where the files go in the repo

```
PixelArtConverter/
├── docs/
│   ├── icon.png          # 1024×1024 from Prompt 1 — also use as Finder/dock icon
│   ├── logo.png          # transparent wordmark from Prompt 2 — referenced in README
│   ├── screenshot.png    # in-app screenshot for the README hero
│   └── LOGO_PROMPT.md    # this file
├── pixel_art_converter.py
├── README.md
└── ...
```
