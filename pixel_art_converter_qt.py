#!/usr/bin/env python3
"""
Pixel Art Converter — cross-platform PySide6 GUI.

Sister of pixel_art_converter.py (the macOS-native AppKit GUI). Both
import shared image-processing logic, palette tables, prompt templates,
and presets from core.py. macOS users should keep using the AppKit
build for native dock-icon / Dark-mode / Tahoe styling; Windows and
Linux users run this one.

Run from source:
    python3 -m pip install PySide6 numpy Pillow scikit-image scikit-learn scipy
    python3 pixel_art_converter_qt.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import threading
import urllib.request

from PIL import Image
from PySide6 import QtCore, QtGui, QtWidgets

import core


# ── Constants ──────────────────────────────────────────────────────────

PRESETS = [
    ("16 × 16",   16, 16),  ("32 × 32",   32, 32),  ("32 × 48",   32, 48),
    ("48 × 48",   48, 48),  ("64 × 64",   64, 64),  ("64 × 96",   64, 96),
    ("96 × 96",   96, 96),  ("128 × 128", 128, 128), ("256 × 256", 256, 256),
    ("Custom…",    0,   0),
]

BG_MODELS = ["isnet-general-use", "isnet-anime", "u2net", "u2net_human_seg",
             core.EDGE_COLOR_OPTION]

SCALE_MIN = 0.05
SCALE_MAX = 32.0
SCALE_PRESETS = [1, 2, 4, 8, 16, 32]

# Auto-convert debounce delay — match AppKit version's responsiveness on
# slider tweaks (the bilateral-cache hits make repeated runs cheap).
DEBOUNCE_MS = 150


# ── Helpers: PIL ↔ Qt ─────────────────────────────────────────────────

def pil_to_qimage(img: Image.Image) -> QtGui.QImage:
    """Convert a PIL RGBA image to a QImage (no buffer aliasing)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QtGui.QImage(data, img.width, img.height,
                        4 * img.width, QtGui.QImage.Format.Format_RGBA8888)
    # .copy() so the underlying PIL bytes can be GC'd without invalidating Qt.
    return qimg.copy()


def pil_to_qpixmap(img: Image.Image) -> QtGui.QPixmap:
    return QtGui.QPixmap.fromImage(pil_to_qimage(img))


# ── Palette swatch bar ────────────────────────────────────────────────

class PaletteBar(QtWidgets.QWidget):
    """Horizontal row of color swatches — mirrors the AppKit PaletteView."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: list[tuple[int, int, int]] = []
        self.setMinimumHeight(28)

    def setColors(self, colors):
        self._colors = list(colors)
        self.update()

    def paintEvent(self, _ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        if not self._colors:
            return
        n = len(self._colors)
        w = self.width() / n
        for i, (r, g, b) in enumerate(self._colors):
            x0 = int(i * w)
            x1 = int((i + 1) * w)
            p.fillRect(x0, 0, x1 - x0, self.height(), QtGui.QColor(r, g, b))


# ── Checkerboard image preview ────────────────────────────────────────

class ImagePreview(QtWidgets.QGraphicsView):
    """
    Pixel-art preview with checkerboard background, nearest-neighbor
    scaling, mouse-drag pan, and Ctrl/⌘+wheel zoom.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QtGui.QPainter.RenderHint.SmoothPixmapTransform |
                            QtGui.QPainter.RenderHint.TextAntialiasing)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(self.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._pixitem: QtWidgets.QGraphicsPixmapItem | None = None
        self._refresh_checker()

    def _refresh_checker(self):
        win_color = self.palette().color(QtGui.QPalette.ColorRole.Base)
        is_dark = (win_color.red() + win_color.green() + win_color.blue()) / 3 < 128
        if is_dark:
            light, dark = QtGui.QColor(60, 60, 60), QtGui.QColor(40, 40, 40)
        else:
            light, dark = QtGui.QColor(220, 220, 220), QtGui.QColor(180, 180, 180)
        self.setBackgroundBrush(self._make_checker(light, dark))

    @staticmethod
    def _make_checker(c1: QtGui.QColor, c2: QtGui.QColor) -> QtGui.QBrush:
        size = 16
        pix = QtGui.QPixmap(size, size)
        pix.fill(c1)
        p = QtGui.QPainter(pix)
        p.fillRect(0, 0, size // 2, size // 2, c2)
        p.fillRect(size // 2, size // 2, size // 2, size // 2, c2)
        p.end()
        return QtGui.QBrush(pix)

    def changeEvent(self, ev: QtCore.QEvent):
        if ev.type() == QtCore.QEvent.Type.PaletteChange:
            self._refresh_checker()
        super().changeEvent(ev)

    def setImage(self, img: Image.Image | None):
        self._scene.clear()
        self._pixitem = None
        if img is None:
            return
        pm = pil_to_qpixmap(img)
        self._pixitem = self._scene.addPixmap(pm)
        # nearest-neighbor for crisp pixels
        self._pixitem.setTransformationMode(QtCore.Qt.TransformationMode.FastTransformation)
        self._scene.setSceneRect(QtCore.QRectF(pm.rect()))
        self.fitInView(self._pixitem, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def fit(self):
        if self._pixitem is not None:
            self.fitInView(self._pixitem, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_by(self, factor: float):
        if self._pixitem is None:
            return
        new_scale = self.transform().m11() * factor
        if SCALE_MIN <= new_scale <= SCALE_MAX:
            self.scale(factor, factor)

    def zoom_in(self):  self.zoom_by(1.25)
    def zoom_out(self): self.zoom_by(0.8)

    def wheelEvent(self, ev: QtGui.QWheelEvent):
        factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.zoom_by(factor)
        ev.accept()


# ── Worker: runs core.make_pixel_art on a background thread ───────────

class _WheelGuard(QtCore.QObject):
    """Drops wheel events on installed widgets so a parent scroll area gets
    them instead. Stops sliders / spinboxes / combos from changing value
    when the user is just scrolling the panel past them."""
    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if ev.type() == QtCore.QEvent.Type.Wheel:
            ev.ignore()
            return True
        return False


class ConvertWorker(QtCore.QObject):
    finished = QtCore.Signal(object, list, str)   # result PIL, frames list, status
    failed   = QtCore.Signal(str)

    @QtCore.Slot(dict)
    def run(self, args: dict):
        try:
            core._last_rembg_status = "ok"
            frames = args["frames"]
            params = dict(
                w=args["w"], h=args["h"], num_colors=args["colors"],
                dither=args["dither"], remove_bg=args["remove_bg"],
                outline=args["outline"], bg_model=args["bg_model"],
                fixed_palette=args["fixed_palette"],
                brightness=args["brightness"], contrast=args["contrast"],
                saturation=args["saturation"],
            )
            if len(frames) > 1:
                out_frames = core.make_pixel_art_animation(frames, **params)
                result = core.compose_sprite_sheet(out_frames)
                self.finished.emit(result, out_frames, core._last_rembg_status)
            else:
                result = core.make_pixel_art(frames[0], **params)
                self.finished.emit(result, [result], core._last_rembg_status)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.failed.emit(str(e))


# ── AI Prompt Samples dialog ──────────────────────────────────────────

class PromptSamplesDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Prompt Samples")
        self.resize(720, 800)
        self._build_ui()
        self._render()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)

        # Mode + target row
        top = QtWidgets.QHBoxLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Frames (sprite sheet)", "Single image"])
        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.addItems(["ChatGPT (DALL-E 3)", "Gemini (Imagen)"])
        top.addWidget(QtWidgets.QLabel("Mode:"))
        top.addWidget(self.mode_combo, 1)
        top.addWidget(QtWidgets.QLabel("Target:"))
        top.addWidget(self.target_combo, 1)
        outer.addLayout(top)

        # Stacked: frames vs single
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._build_frames_panel())
        self.stack.addWidget(self._build_single_panel())
        outer.addWidget(self.stack)

        # Rendered preview
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QtGui.QFont(
            "Menlo,Consolas,Courier New", 11))
        outer.addWidget(self.preview, 2)

        # Bottom: Copy + Close
        btns = QtWidgets.QHBoxLayout()
        self.copy_btn = QtWidgets.QPushButton("Copy")
        close_btn = QtWidgets.QPushButton("Close")
        btns.addStretch()
        btns.addWidget(self.copy_btn)
        btns.addWidget(close_btn)
        outer.addLayout(btns)

        # Wire signals
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        self.target_combo.currentIndexChanged.connect(self._render)
        self.copy_btn.clicked.connect(self._copy)
        close_btn.clicked.connect(self.accept)

    def _build_frames_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        d = core.PROMPT_DEFAULTS_FRAMES

        self.f_action_preset = QtWidgets.QComboBox()
        self.f_action_preset.addItems(list(core.ACTION_PRESETS.keys()))
        self.f_action_preset.currentTextChanged.connect(self._on_action_preset)

        self.f_n = QtWidgets.QLineEdit(d["N"])
        self.f_subject = QtWidgets.QLineEdit(d["SUBJECT"])

        self.f_view = QtWidgets.QComboBox()
        self.f_view.setEditable(True)
        self.f_view.addItems(core.VIEW_PRESETS)
        self.f_view.setCurrentText(d["VIEW"])

        self.f_bg = QtWidgets.QComboBox()
        self.f_bg.setEditable(True)
        self.f_bg.addItems(core.BACKGROUND_PRESETS)
        self.f_bg.setCurrentText(d["BACKGROUND"])

        self.f_action = QtWidgets.QPlainTextEdit(d["ACTION"])
        self.f_action.setMaximumHeight(110)

        form.addRow("Preset:",     self.f_action_preset)
        form.addRow("Frames (N):", self.f_n)
        form.addRow("Subject:",    self.f_subject)
        form.addRow("View:",       self.f_view)
        form.addRow("Background:", self.f_bg)
        form.addRow("Action:",     self.f_action)

        for widget in [self.f_n, self.f_subject, self.f_action]:
            widget.textChanged.connect(self._render)
        for widget in [self.f_view, self.f_bg]:
            widget.currentTextChanged.connect(self._render)
        return w

    def _build_single_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        d = core.PROMPT_DEFAULTS_SINGLE

        self.s_subject = QtWidgets.QLineEdit(d["SUBJECT"])
        self.s_view = QtWidgets.QComboBox()
        self.s_view.setEditable(True)
        self.s_view.addItems(core.VIEW_PRESETS)
        self.s_view.setCurrentText(d["VIEW"])
        self.s_bg = QtWidgets.QComboBox()
        self.s_bg.setEditable(True)
        self.s_bg.addItems(core.BACKGROUND_PRESETS)
        self.s_bg.setCurrentText(d["BACKGROUND"])

        form.addRow("Subject:",    self.s_subject)
        form.addRow("View:",       self.s_view)
        form.addRow("Background:", self.s_bg)

        self.s_subject.textChanged.connect(self._render)
        self.s_view.currentTextChanged.connect(self._render)
        self.s_bg.currentTextChanged.connect(self._render)
        return w

    def _on_mode_change(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self._render()

    def _on_action_preset(self, name: str):
        n, action = core.ACTION_PRESETS.get(name, (None, None))
        if n is not None:
            self.f_n.setText(str(n))
        if action is not None:
            self.f_action.setPlainText(action)
        self._render()

    def _current_template(self):
        mode   = "frames" if self.mode_combo.currentIndex() == 0 else "single"
        target = "chatgpt" if self.target_combo.currentIndex() == 0 else "gemini"
        return core.PROMPT_TEMPLATES[(mode, target)]

    def _current_values(self) -> dict:
        if self.mode_combo.currentIndex() == 0:
            return {
                "N":          self.f_n.text().strip()           or core.PROMPT_DEFAULTS_FRAMES["N"],
                "SUBJECT":    self.f_subject.text().strip()     or core.PROMPT_DEFAULTS_FRAMES["SUBJECT"],
                "ACTION":     self.f_action.toPlainText().strip()
                              or core.PROMPT_DEFAULTS_FRAMES["ACTION"],
                "VIEW":       self.f_view.currentText().strip() or core.PROMPT_DEFAULTS_FRAMES["VIEW"],
                "BACKGROUND": self.f_bg.currentText().strip()   or core.PROMPT_DEFAULTS_FRAMES["BACKGROUND"],
            }
        return {
            "SUBJECT":    self.s_subject.text().strip()     or core.PROMPT_DEFAULTS_SINGLE["SUBJECT"],
            "VIEW":       self.s_view.currentText().strip() or core.PROMPT_DEFAULTS_SINGLE["VIEW"],
            "BACKGROUND": self.s_bg.currentText().strip()   or core.PROMPT_DEFAULTS_SINGLE["BACKGROUND"],
        }

    def _render(self):
        text, ranges = core.render_prompt(self._current_template(),
                                          self._current_values())
        # Render with substituted ranges colored.
        self.preview.clear()
        cursor = self.preview.textCursor()
        i = 0
        accent = QtGui.QColor(0, 122, 255)   # macOS-ish blue
        normal_fmt = QtGui.QTextCharFormat()
        accent_fmt = QtGui.QTextCharFormat()
        accent_fmt.setForeground(QtGui.QBrush(accent))
        accent_fmt.setFontWeight(QtGui.QFont.Weight.Bold)
        for start, length in ranges:
            if i < start:
                cursor.insertText(text[i:start], normal_fmt)
            cursor.insertText(text[start:start+length], accent_fmt)
            i = start + length
        if i < len(text):
            cursor.insertText(text[i:], normal_fmt)

    def _copy(self):
        text, _ = core.render_prompt(self._current_template(),
                                     self._current_values())
        QtWidgets.QApplication.clipboard().setText(text)
        self.copy_btn.setText("Copied!")
        QtCore.QTimer.singleShot(1200, lambda: self.copy_btn.setText("Copy"))


# ── Main window ───────────────────────────────────────────────────────

class MainWindow(QtWidgets.QMainWindow):
    convert_requested = QtCore.Signal(dict)
    update_checked    = QtCore.Signal(object, str)  # manifest dict (or None), error str

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Pixel Art Converter v{core.__version__}")
        self.setAcceptDrops(True)

        self._frames: list[Image.Image] = []     # input frames (1 = single image)
        self._result_img: Image.Image | None = None
        self._result_frames: list[Image.Image] = []
        self._loaded_lospec: dict = {}           # name -> hex_list (user-loaded)
        self._sheet_cols = 1
        self._sheet_rows = 1
        self._busy = False

        self._build_ui()
        self._build_menu()
        self._spawn_worker()
        self.update_checked.connect(self._show_update_result)

        # Debounce timer for slider-driven auto-convert
        self._debounce = QtCore.QTimer(self, singleShot=True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.do_convert)

        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1600, 900)
        self.resize(min(1119, avail.width()  - 40),
                    min(920,  avail.height() - 40))

    # ---- UI construction ------------------------------------------------

    def _build_menu(self):
        bar = self.menuBar()
        m_file = bar.addMenu("&File")
        a_open = m_file.addAction("Open Image…")
        a_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        a_open.triggered.connect(self.on_open)
        a_save = m_file.addAction("Save Output As…")
        a_save.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        a_save.triggered.connect(self.on_save)
        m_file.addSeparator()
        a_quit = m_file.addAction("Quit")
        a_quit.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        a_quit.triggered.connect(self.close)

        m_image = bar.addMenu("&Image")
        a_new = m_image.addAction("New Image (Reset)")
        a_new.triggered.connect(self.on_new_image)
        a_image_prompt = m_image.addAction("AI Prompt Samples…")
        a_image_prompt.triggered.connect(self.on_show_prompts)

        m_update = bar.addMenu("&Update")
        a_check = m_update.addAction("Check for Updates…")
        a_check.triggered.connect(self.on_check_update)
        self._check_update_action = a_check

    def _build_ui(self):
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._controls_panel = self._build_controls_panel()
        splitter.addWidget(self._controls_panel)
        splitter.addWidget(self._build_preview_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        panel_w = self._controls_panel.minimumWidth() or 480
        splitter.setSizes([panel_w, max(640, 1280 - panel_w)])
        self.setCentralWidget(splitter)

        self.statusBar().showMessage("Drop an image or use File → Open.")

    def _build_controls_panel(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QtWidgets.QWidget()
        scroll.setWidget(host)
        v = QtWidgets.QVBoxLayout(host)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # Open / New buttons
        row = QtWidgets.QHBoxLayout()
        b_open = QtWidgets.QPushButton("Open Image…")
        b_open.clicked.connect(self.on_open)
        b_new = QtWidgets.QPushButton("New Image")
        b_new.clicked.connect(self.on_new_image)
        row.addWidget(b_open); row.addWidget(b_new)
        v.addLayout(row)

        # Sprite-sheet split
        v.addWidget(self._section_label("Sprite-sheet split"))
        ssr = QtWidgets.QHBoxLayout()
        self.cols_spin = QtWidgets.QSpinBox(); self.cols_spin.setRange(1, 32); self.cols_spin.setValue(1)
        self.rows_spin = QtWidgets.QSpinBox(); self.rows_spin.setRange(1, 32); self.rows_spin.setValue(1)
        b_split = QtWidgets.QPushButton("Split")
        b_split.clicked.connect(self.on_split_sheet)
        ssr.addWidget(QtWidgets.QLabel("Cols:")); ssr.addWidget(self.cols_spin)
        ssr.addSpacing(10)
        ssr.addWidget(QtWidgets.QLabel("Rows:")); ssr.addWidget(self.rows_spin)
        ssr.addSpacing(10); ssr.addWidget(b_split); ssr.addStretch()
        v.addLayout(ssr)

        # Output dimensions
        v.addWidget(self._section_label("Output dimensions"))
        self.preset_combo = QtWidgets.QComboBox()
        for name, _, _ in PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText("64 × 64")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_change)

        dim_row = QtWidgets.QHBoxLayout()
        self.w_spin = QtWidgets.QSpinBox(); self.w_spin.setRange(2, 4096); self.w_spin.setValue(64)
        self.h_spin = QtWidgets.QSpinBox(); self.h_spin.setRange(2, 4096); self.h_spin.setValue(64)
        dim_row.addWidget(QtWidgets.QLabel("W:")); dim_row.addWidget(self.w_spin)
        dim_row.addWidget(QtWidgets.QLabel("H:")); dim_row.addWidget(self.h_spin)
        dim_row.addStretch()
        v.addWidget(self.preset_combo)
        v.addLayout(dim_row)

        # Colors
        v.addWidget(self._section_label("Colors"))
        cr = QtWidgets.QHBoxLayout()
        self.colors_spin = QtWidgets.QSpinBox(); self.colors_spin.setRange(2, 64); self.colors_spin.setValue(16)
        cr.addWidget(QtWidgets.QLabel("Number of colors:"))
        cr.addWidget(self.colors_spin); cr.addStretch()
        v.addLayout(cr)

        # Palette
        self.palette_combo = QtWidgets.QComboBox()
        for name in core.LOSPEC_PALETTES.keys():
            self.palette_combo.addItem(name)
        self.palette_combo.addItem(core.LOSPEC_LOAD_OPTION)
        self.palette_combo.currentTextChanged.connect(self._on_palette_change)
        v.addWidget(QtWidgets.QLabel("Palette:"))
        v.addWidget(self.palette_combo)

        self.palette_bar = PaletteBar()
        v.addWidget(self.palette_bar)

        # Toggles
        v.addWidget(self._section_label("Options"))
        self.dither_chk  = QtWidgets.QCheckBox("Dither (Bayer 8×8)")
        self.outline_chk = QtWidgets.QCheckBox("Outline (selout)")
        self.outline_chk.setChecked(True)
        self.rembg_chk   = QtWidgets.QCheckBox("Remove background")
        self.rembg_chk.setChecked(True)
        v.addWidget(self.dither_chk)
        v.addWidget(self.outline_chk)
        v.addWidget(self.rembg_chk)

        bg_row = QtWidgets.QHBoxLayout()
        self.bg_combo = QtWidgets.QComboBox()
        self.bg_combo.addItems(BG_MODELS)
        self.bg_combo.setCurrentText(core.EDGE_COLOR_OPTION)
        bg_row.addWidget(QtWidgets.QLabel("BG model:"))
        bg_row.addWidget(self.bg_combo, 1)
        v.addLayout(bg_row)

        # Adjustments — grid-aligned so every slider starts/ends at the same X
        v.addWidget(self._section_label("Adjustments"))
        adj_grid = QtWidgets.QGridLayout()
        adj_grid.setHorizontalSpacing(8)
        adj_grid.setVerticalSpacing(6)
        adj_grid.setColumnStretch(1, 1)
        v.addLayout(adj_grid)
        self.brightness_slider, self.brightness_lbl = self._slider_grid_row(adj_grid, 0, "Brightness", -100, 100, 0)
        self.contrast_slider,   self.contrast_lbl   = self._slider_grid_row(adj_grid, 1, "Contrast",   -100, 100, 0)
        self.saturation_slider, self.saturation_lbl = self._slider_grid_row(adj_grid, 2, "Saturation", -100, 100, 0)

        # Convert / Save buttons
        v.addSpacing(8)
        cv = QtWidgets.QHBoxLayout()
        self.convert_btn = QtWidgets.QPushButton("Convert")
        self.convert_btn.clicked.connect(self.do_convert)
        self.convert_btn.setDefault(True)
        self.convert_btn.setProperty("accent", True)
        self.save_btn = QtWidgets.QPushButton("Save Output…")
        self.save_btn.clicked.connect(self.on_save)
        cv.addWidget(self.convert_btn); cv.addWidget(self.save_btn)
        v.addLayout(cv)

        v.addStretch()

        # Stop wheel events from changing slider / spinbox / combo values
        # when the user is just scrolling the panel past them.
        self._wheel_guard = _WheelGuard(self)
        for w in host.findChildren(QtWidgets.QAbstractSpinBox) \
               + host.findChildren(QtWidgets.QSlider) \
               + host.findChildren(QtWidgets.QComboBox):
            w.installEventFilter(self._wheel_guard)
            w.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # Wire up auto-convert triggers (debounced)
        for w in [self.w_spin, self.h_spin, self.colors_spin]:
            w.valueChanged.connect(self._schedule_convert)
        for chk in [self.dither_chk, self.outline_chk, self.rembg_chk]:
            chk.toggled.connect(self._schedule_convert)
        self.bg_combo.currentTextChanged.connect(self._schedule_convert)
        for s in [self.brightness_slider, self.contrast_slider, self.saturation_slider]:
            # Trigger only when the user finishes dragging (mouse release) or
            # uses keyboard arrows (valueChanged with the handle not held down).
            s.sliderReleased.connect(self._schedule_convert)
            s.valueChanged.connect(
                lambda _v, sl=s: None if sl.isSliderDown() else self._schedule_convert()
            )
        self.palette_combo.currentTextChanged.connect(self._schedule_convert)

        # Make sure the panel is wide enough for its widest row, plus a
        # vertical scrollbar, plus the layout margin. Otherwise text/buttons
        # get clipped or the user has to resize the splitter manually.
        host.adjustSize()
        sb_w = scroll.verticalScrollBar().sizeHint().width()
        scroll.setMinimumWidth(host.sizeHint().width() + sb_w + 8)

        return scroll

    def _build_preview_panel(self) -> QtWidgets.QWidget:
        host = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(host); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(8)

        self.original_view = ImagePreview()
        self.output_view   = ImagePreview()

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        split.addWidget(self._labeled_view("Original",  self.original_view))
        split.addWidget(self._labeled_view("Pixel art", self.output_view))
        split.setSizes([1, 1])
        split.setChildrenCollapsible(False)
        v.addWidget(split, 1)

        # Quick info row
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet("color: palette(placeholder-text);")
        v.addWidget(self.info_label)

        return host

    @staticmethod
    def _labeled_view(title: str, view: "ImagePreview") -> QtWidgets.QWidget:
        host = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(title)
        f = lbl.font(); f.setBold(True); lbl.setFont(f)
        header.addStretch(1)
        header.addWidget(lbl)
        header.addStretch(1)

        def _mk(text: str, tip: str, slot) -> QtWidgets.QToolButton:
            b = QtWidgets.QToolButton()
            b.setText(text); b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            return b

        header.addWidget(_mk("−",   "Zoom out",  view.zoom_out))
        header.addWidget(_mk("+",   "Zoom in",   view.zoom_in))
        header.addWidget(_mk("Fit", "Fit to view", view.fit))

        v.addLayout(header)
        v.addWidget(view, 1)
        return host

    @staticmethod
    def _section_label(text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        f = lbl.font(); f.setBold(True); lbl.setFont(f)
        return lbl

    def _slider_grid_row(self, grid: QtWidgets.QGridLayout, row: int,
                         label: str, lo: int, hi: int, default: int):
        s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        s.setRange(lo, hi); s.setValue(default); s.setMinimumWidth(180)
        v_lbl = QtWidgets.QLabel(f"{default:+d}")
        v_lbl.setMinimumWidth(36)
        v_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(QtWidgets.QLabel(label), row, 0)
        grid.addWidget(s, row, 1)
        grid.addWidget(v_lbl, row, 2)
        s.valueChanged.connect(lambda v, lbl=v_lbl: lbl.setText(f"{v:+d}"))
        return s, v_lbl

    # ---- Worker thread setup -------------------------------------------

    def _spawn_worker(self):
        self._worker_thread = QtCore.QThread(self)
        self._worker = ConvertWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.start()
        self.convert_requested.connect(self._worker.run)
        self._worker.finished.connect(self._on_convert_done)
        self._worker.failed.connect(self._on_convert_failed)
        # Stop the thread on app quit too — closeEvent only covers the
        # user-clicks-X path, not GC-time teardown.
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_worker)

    def _stop_worker(self):
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(2000)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        self._stop_worker()
        super().closeEvent(ev)

    # ---- Drag & drop ----------------------------------------------------

    def dragEnterEvent(self, ev: QtGui.QDragEnterEvent):
        if not self._busy and ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev: QtGui.QDropEvent):
        if self._busy:
            return
        urls = ev.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self._load_path(path)

    # ---- File ops -------------------------------------------------------

    def on_open(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)")
        if path:
            self._load_path(path)

    def _load_path(self, path: str):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Open failed", str(e))
            return
        self._frames = [img]
        self._sheet_cols = 1
        self._sheet_rows = 1
        self.cols_spin.setValue(1); self.rows_spin.setValue(1)
        self.original_view.setImage(img)
        self.original_view.fit()
        self.info_label.setText(
            f"Loaded {os.path.basename(path)} — {img.width}×{img.height}")
        self.statusBar().showMessage(os.path.basename(path))
        self.do_convert()

    def on_new_image(self):
        self._frames = []
        self._result_img = None
        self._result_frames = []
        self.original_view.setImage(None)
        self.output_view.setImage(None)
        self.palette_bar.setColors([])
        self.info_label.setText("")
        self.statusBar().showMessage("Drop an image or use File → Open.")

    def on_split_sheet(self):
        if not self._frames:
            return
        cols = self.cols_spin.value()
        rows = self.rows_spin.value()
        if cols == 1 and rows == 1:
            return
        # Re-split from the *original* loaded image
        sheet = self._frames[0] if self._sheet_cols == 1 and self._sheet_rows == 1 \
                                  else core.compose_sprite_sheet(self._frames)
        self._frames = core.split_sprite_sheet(sheet, cols, rows)
        self._sheet_cols, self._sheet_rows = cols, rows
        self.info_label.setText(
            f"Split into {len(self._frames)} frames "
            f"({self._frames[0].width}×{self._frames[0].height} each)")
        self.do_convert()

    def on_save(self):
        if self._result_img is None:
            QtWidgets.QMessageBox.information(self, "Nothing to save",
                                              "Convert an image first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Output", "pixel_art.png",
            "PNG image (*.png);;All files (*.*)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            self._result_img.save(path, "PNG")
            self.statusBar().showMessage(f"Saved → {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))

    # ---- Settings change handlers --------------------------------------

    def _on_preset_change(self, _idx: int):
        name = self.preset_combo.currentText()
        for n, w, h in PRESETS:
            if n == name and (w, h) != (0, 0):
                self.w_spin.setValue(w); self.h_spin.setValue(h)
                self._schedule_convert()
                return
        # Custom… — leave spinboxes alone, let user edit them.

    def _on_palette_change(self, name: str):
        if name == core.LOSPEC_LOAD_OPTION:
            self._prompt_load_lospec()

    def _prompt_load_lospec(self):
        slug, ok = QtWidgets.QInputDialog.getText(
            self, "Load Lospec palette",
            "Lospec slug or URL (e.g. 'pico-8' or "
            "https://lospec.com/palette-list/pico-8):")
        if not ok or not slug.strip():
            self.palette_combo.setCurrentIndex(0)
            return
        try:
            display, hex_list = core.fetch_lospec_palette(slug.strip())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lospec fetch failed", str(e))
            self.palette_combo.setCurrentIndex(0)
            return
        # Insert above the "Load…" option, select it.
        if display in self._loaded_lospec:
            idx = self.palette_combo.findText(display)
        else:
            self._loaded_lospec[display] = hex_list
            idx = self.palette_combo.count() - 1
            self.palette_combo.insertItem(idx, display)
        self.palette_combo.setCurrentIndex(idx)

    # ---- Convert flow ---------------------------------------------------

    def _schedule_convert(self, *_):
        if not self._frames or self._busy:
            return
        self._debounce.start()

    def _gather_args(self) -> dict | None:
        if not self._frames:
            return None
        name = self.palette_combo.currentText()
        fixed_palette = None
        if name == core.LOSPEC_LOAD_OPTION:
            return None
        if name in core.LOSPEC_PALETTES and core.LOSPEC_PALETTES[name]:
            fixed_palette = core._palette_to_rgb_array(core.LOSPEC_PALETTES[name])
        elif name in self._loaded_lospec:
            fixed_palette = core._palette_to_rgb_array(self._loaded_lospec[name])
        return {
            "frames":       [f.copy() for f in self._frames],
            "w":            self.w_spin.value(),
            "h":            self.h_spin.value(),
            "colors":       self.colors_spin.value(),
            "dither":       self.dither_chk.isChecked(),
            "remove_bg":    self.rembg_chk.isChecked(),
            "outline":      self.outline_chk.isChecked(),
            "bg_model":     self.bg_combo.currentText(),
            "fixed_palette": fixed_palette,
            "brightness":   self.brightness_slider.value(),
            "contrast":     self.contrast_slider.value(),
            "saturation":   self.saturation_slider.value(),
        }

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._controls_panel.setEnabled(not busy)
        self.menuBar().setEnabled(not busy)
        if busy:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    @QtCore.Slot()
    def do_convert(self):
        if self._busy:
            return
        args = self._gather_args()
        if args is None:
            return
        self._set_busy(True)
        self.statusBar().showMessage("Converting…")
        self.convert_requested.emit(args)

    @QtCore.Slot(object, list, str)
    def _on_convert_done(self, result, frames, status):
        self._set_busy(False)
        self._result_img = result
        self._result_frames = frames
        self.output_view.setImage(result)
        self.output_view.fit()
        self.palette_bar.setColors(core.extract_palette(result))
        msg = f"Done — {result.width}×{result.height}"
        if status == "fallback":
            msg += " (BG removal fell back: original passed through)"
        self.statusBar().showMessage(msg)

    @QtCore.Slot(str)
    def _on_convert_failed(self, err: str):
        self._set_busy(False)
        QtWidgets.QMessageBox.critical(self, "Conversion failed", err)
        self.statusBar().showMessage("Conversion failed")

    # ---- Update check ---------------------------------------------------

    def on_check_update(self):
        self._check_update_action.setEnabled(False)
        self.statusBar().showMessage("Checking for updates…")
        threading.Thread(target=self._fetch_update_manifest, daemon=True).start()

    def _fetch_update_manifest(self):
        try:
            req = urllib.request.Request(
                core._UPDATE_MANIFEST_URL,
                headers={"User-Agent": f"PixelArtConverter/{core.__version__}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                manifest = json.loads(resp.read().decode("utf-8"))
            self.update_checked.emit(manifest, "")
        except Exception as e:
            self.update_checked.emit(None, str(e))

    @QtCore.Slot(object, str)
    def _show_update_result(self, manifest, err: str):
        self._check_update_action.setEnabled(True)
        self.statusBar().clearMessage()
        if err or not manifest:
            QtWidgets.QMessageBox.warning(
                self, "Update check failed",
                f"Couldn't reach the update server.\n\n{err or 'Unknown error.'}")
            return

        latest = str(manifest.get("version", "0"))
        notes  = str(manifest.get("notes", "")).strip()
        if core._version_tuple(latest) > core._version_tuple(core.__version__):
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Information)
            box.setWindowTitle("Update available")
            box.setText(f"A new version is available: v{latest}\n"
                        f"You're running v{core.__version__}.")
            if notes:
                box.setDetailedText(notes)
            open_btn  = box.addButton("Open Release Page", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Later", QtWidgets.QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is open_btn:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(
                    "https://github.com/ahmetolcum/PixelArtConverter/releases/latest"))
        else:
            QtWidgets.QMessageBox.information(
                self, "Up to date",
                f"You're running the latest version (v{core.__version__}).")

    # ---- Menus ----------------------------------------------------------

    def on_show_prompts(self):
        dlg = PromptSamplesDialog(self)
        dlg.exec()


# ── Entry point ───────────────────────────────────────────────────────

_arrow_cache: dict = {}

def _arrow_pixmap_path(direction: str, color_hex: str) -> str:
    """Render a chevron PNG to a temp file once per (direction, color) and
    return a forward-slashed absolute path suitable for `image: url(...)`.
    QSS data-URI / SVG support is unreliable across Qt builds; a real PNG
    file is the most portable option."""
    import tempfile
    key = (direction, color_hex)
    if key in _arrow_cache:
        return _arrow_cache[key]

    size = 16
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor(color_hex))
    pen.setWidthF(1.8)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    if direction == "up":
        path = QtGui.QPainterPath()
        path.moveTo(4, 10); path.lineTo(8, 6); path.lineTo(12, 10)
    else:
        path = QtGui.QPainterPath()
        path.moveTo(4, 6); path.lineTo(8, 10); path.lineTo(12, 6)
    p.drawPath(path)
    p.end()

    tmp = tempfile.NamedTemporaryFile(
        suffix=f"_{direction}_{color_hex.lstrip('#')}.png",
        prefix="pac_arrow_", delete=False)
    tmp.close()
    pm.save(tmp.name, "PNG")
    url = tmp.name.replace("\\", "/")
    _arrow_cache[key] = url
    return url


def _build_qss(dark: bool) -> str:
    if dark:
        accent          = "#60CDFF"
        accent_hover    = "#82D6FF"
        accent_pressed  = "#3FB8F0"
        accent_text     = "#000000"
        border          = "rgba(255,255,255,0.10)"
        border_strong   = "rgba(255,255,255,0.20)"
        hover_bg        = "rgba(255,255,255,0.06)"
        pressed_bg      = "rgba(255,255,255,0.10)"
        disabled_text   = "rgba(255,255,255,0.40)"
        slider_groove   = "rgba(255,255,255,0.15)"
        slider_handle   = "#E6E6E6"
        slider_h_border = "rgba(0,0,0,0.40)"
        arrow_hex       = "#E6E6E6"
        arrow_dim_hex   = "#6E6E6E"
    else:
        accent          = "#0067C0"
        accent_hover    = "#1975D2"
        accent_pressed  = "#00569C"
        accent_text     = "#FFFFFF"
        border          = "rgba(0,0,0,0.10)"
        border_strong   = "rgba(0,0,0,0.20)"
        hover_bg        = "rgba(0,0,0,0.04)"
        pressed_bg      = "rgba(0,0,0,0.08)"
        disabled_text   = "rgba(0,0,0,0.35)"
        slider_groove   = "rgba(0,0,0,0.15)"
        slider_handle   = "#FFFFFF"
        slider_h_border = "rgba(0,0,0,0.30)"
        arrow_hex       = "#202020"
        arrow_dim_hex   = "#A0A0A0"

    up_url       = _arrow_pixmap_path("up",   arrow_hex)
    down_url     = _arrow_pixmap_path("down", arrow_hex)
    up_dim_url   = _arrow_pixmap_path("up",   arrow_dim_hex)
    down_dim_url = _arrow_pixmap_path("down", arrow_dim_hex)

    return f"""
* {{ font-family: "Segoe UI Variable Display", "Segoe UI", "Inter", system-ui, sans-serif; }}

QMainWindow {{ background: palette(window); }}
QScrollArea {{ border: none; background: transparent; }}

QPushButton {{
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid {border};
    background: palette(button);
}}
QPushButton:hover    {{ background: {hover_bg}; }}
QPushButton:pressed  {{ background: {pressed_bg}; }}
QPushButton:disabled {{ color: {disabled_text}; }}

QPushButton[accent="true"] {{
    color: {accent_text};
    background: {accent};
    border: 1px solid {accent};
}}
QPushButton[accent="true"]:hover    {{ background: {accent_hover}; }}
QPushButton[accent="true"]:pressed  {{ background: {accent_pressed}; }}
QPushButton[accent="true"]:disabled {{ color: {disabled_text}; }}

QComboBox, QSpinBox, QLineEdit, QPlainTextEdit, QTextEdit {{
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid {border_strong};
    background: palette(base);
    color: palette(text);
    selection-background-color: {accent};
}}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}

QSpinBox {{
    padding-right: 28px;
    min-height: 28px;
}}
QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    border-left: 1px solid {border_strong};
    border-top-right-radius: 6px;
    background: transparent;
}}
QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 24px;
    border: none;
    border-left: 1px solid {border_strong};
    border-bottom-right-radius: 6px;
    background: transparent;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {hover_bg};
}}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
    background: {pressed_bg};
}}
QSpinBox::up-arrow {{
    image: url({up_url});
    width: 12px; height: 12px;
}}
QSpinBox::down-arrow {{
    image: url({down_url});
    width: 12px; height: 12px;
}}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off {{
    image: url({up_dim_url});
}}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off {{
    image: url({down_dim_url});
}}

QComboBox {{
    padding-right: 28px;
    min-height: 28px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    border-left: 1px solid {border_strong};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background: transparent;
}}
QComboBox::drop-down:hover    {{ background: {hover_bg}; }}
QComboBox::drop-down:pressed  {{ background: {pressed_bg}; }}
QComboBox::down-arrow {{
    image: url({down_url});
    width: 12px; height: 12px;
}}
QComboBox::down-arrow:disabled, QComboBox::down-arrow:off {{
    image: url({down_dim_url});
}}
QComboBox QAbstractItemView {{
    border: 1px solid {border_strong};
    background: palette(base);
    selection-background-color: {accent};
    selection-color: {accent_text};
    outline: 0;
    padding: 4px;
}}

QCheckBox {{ spacing: 8px; padding: 2px 0; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid {border_strong};
    background: palette(base);
}}
QCheckBox::indicator:hover   {{ border: 1px solid {accent}; }}
QCheckBox::indicator:checked {{
    background: {accent};
    border: 1px solid {accent};
    image: none;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {slider_groove};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px;
    margin: -7px 0;
    border-radius: 8px;
    background: {slider_handle};
    border: 1px solid {slider_h_border};
}}
QSlider::handle:horizontal:hover {{ border: 4px solid {accent}; }}

QGraphicsView {{
    border: 1px solid {border};
    border-radius: 8px;
    background: palette(base);
}}

QStatusBar {{ border-top: 1px solid {border}; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QSplitter::handle:vertical   {{ height: 6px; }}

QToolTip {{
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid {border_strong};
    background: palette(base);
    color: palette(text);
}}
"""


def _build_palette(dark: bool) -> QtGui.QPalette:
    pal = QtGui.QPalette()
    if dark:
        window = QtGui.QColor(32, 32, 32)
        base   = QtGui.QColor(43, 43, 43)
        alt    = QtGui.QColor(50, 50, 50)
        text   = QtGui.QColor(240, 240, 240)
        disabled_text = QtGui.QColor(140, 140, 140)
        button = QtGui.QColor(45, 45, 45)
        highlight = QtGui.QColor(96, 205, 255)
        highlight_text = QtGui.QColor(0, 0, 0)
    else:
        window = QtGui.QColor(243, 243, 243)
        base   = QtGui.QColor(255, 255, 255)
        alt    = QtGui.QColor(247, 247, 247)
        text   = QtGui.QColor(20, 20, 20)
        disabled_text = QtGui.QColor(140, 140, 140)
        button = QtGui.QColor(252, 252, 252)
        highlight = QtGui.QColor(0, 103, 192)
        highlight_text = QtGui.QColor(255, 255, 255)

    Role = QtGui.QPalette.ColorRole
    Group = QtGui.QPalette.ColorGroup
    pal.setColor(Role.Window, window)
    pal.setColor(Role.WindowText, text)
    pal.setColor(Role.Base, base)
    pal.setColor(Role.AlternateBase, alt)
    pal.setColor(Role.ToolTipBase, base)
    pal.setColor(Role.ToolTipText, text)
    pal.setColor(Role.Text, text)
    pal.setColor(Role.Button, button)
    pal.setColor(Role.ButtonText, text)
    pal.setColor(Role.Highlight, highlight)
    pal.setColor(Role.HighlightedText, highlight_text)
    pal.setColor(Role.PlaceholderText, disabled_text)
    pal.setColor(Group.Disabled, Role.Text, disabled_text)
    pal.setColor(Group.Disabled, Role.ButtonText, disabled_text)
    pal.setColor(Group.Disabled, Role.WindowText, disabled_text)
    return pal


def apply_theme(app: QtWidgets.QApplication, dark: bool):
    app.setPalette(_build_palette(dark))
    app.setStyleSheet(_build_qss(dark))


def main():
    QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Pixel Art Converter")
    app.setApplicationVersion(core.__version__)

    if "windows11" in QtWidgets.QStyleFactory.keys():
        app.setStyle("windows11")
    elif "Fusion" in QtWidgets.QStyleFactory.keys():
        app.setStyle("Fusion")

    families = QtGui.QFontDatabase.families()
    for fam in ("Segoe UI Variable Display", "Segoe UI", "Inter"):
        if fam in families:
            app.setFont(QtGui.QFont(fam, 10))
            break

    def _is_dark() -> bool:
        hints = app.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        if callable(scheme):
            return scheme() == QtCore.Qt.ColorScheme.Dark
        # Fallback: infer from current palette luminance
        c = app.palette().color(QtGui.QPalette.ColorRole.Window)
        return (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 < 128

    apply_theme(app, _is_dark())

    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda _s: apply_theme(app, _is_dark()))

    # Try to load the same icon the mac app uses, if present.
    here = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(here, "docs", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))

    win = MainWindow()
    win.show()

    # Open file argv (Windows / Linux drop-on-icon)
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        win._load_path(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
