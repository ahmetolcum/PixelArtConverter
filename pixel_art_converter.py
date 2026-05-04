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


# ── Pure logic + shared config — extracted to core.py ────────────────────
# Image processing, palette tables, prompt templates, presets, and shared
# mutable state live in core.py so a future cross-platform GUI (Qt/Web) can
# reuse them without touching this AppKit-bound file. _last_rembg_status is
# accessed as `core._last_rembg_status` (module attribute) — not via `from
# core import ...` — so the worker thread's writes are visible to the UI
# thread.
import core
from core import (
    LOSPEC_PALETTES, LOSPEC_LOAD_OPTION,
    __version__, _UPDATE_MANIFEST_URL, _version_tuple,
    EDGE_COLOR_OPTION,
    PROMPT_DEFAULTS_FRAMES, PROMPT_DEFAULTS_SINGLE, PROMPT_TEMPLATES,
    VIEW_PRESETS, BACKGROUND_PRESETS, ACTION_PRESETS,
    render_prompt,
    fetch_lospec_palette, _palette_to_rgb_array,
    make_pixel_art, make_pixel_art_animation,
    split_sprite_sheet, compose_sprite_sheet,
    extract_palette,
)




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
            core._last_rembg_status = "ok"
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
            self.__dict__["rembg_status"] = core._last_rembg_status
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
