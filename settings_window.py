import ctypes
import math
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# Enable DPI awareness before any window is created — prevents OS upscaling blur
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── design tokens ─────────────────────────────────────────────────────────────
BG       = '#FAFAF9'
SURFACE  = '#F5F4F1'
BORDER   = '#D0CEC8'
TRACK_BG = '#C8C6C0'   # unfilled slider track
TEXT     = '#2C2C2A'
MUTED    = '#8C8A84'
ACCENT   = '#B45309'
LABEL    = '#C46010'
FONT     = 'Segoe UI'

STATUS_COLOR = {
    'listening':    '#22C55E',
    'paused':       '#B45309',
    'disconnected': '#6B7280',
}
STATUS_TEXT = {
    'listening':    'Listening',
    'paused':       'Paused — someone is talking',
    'disconnected': 'Voice app not detected',
}

# ── threshold ↔ slider helpers ────────────────────────────────────────────────

def _slider_to_threshold(pct: float) -> float:
    pct = max(1.0, min(99.0, float(pct)))
    lo, hi = math.log10(0.001), math.log10(0.1)
    return 10 ** (hi - (pct - 1) / 98.0 * (hi - lo))

def _threshold_to_slider(t: float) -> int:
    t = max(0.001, min(0.1, float(t)))
    lo, hi = math.log10(0.001), math.log10(0.1)
    return round(1 + (hi - math.log10(t)) / (hi - lo) * 98)


# ── custom canvas slider ──────────────────────────────────────────────────────

class Slider(tk.Canvas):
    """A clean slider with a two-tone rounded track and a circular thumb."""

    TRACK_H  = 6
    THUMB_R  = 9

    def __init__(self, parent, from_=0, to=100, value=50, command=None, **kw):
        super().__init__(parent, height=28, bg=BG, highlightthickness=0, **kw)
        self._from   = from_
        self._to     = to
        self._value  = float(value)
        self._cmd    = command
        self._drag   = False

        self.bind('<Configure>',        self._draw)
        self.bind('<ButtonPress-1>',    self._on_press)
        self.bind('<B1-Motion>',        self._on_drag)
        self.bind('<ButtonRelease-1>',  self._on_release)

    def get(self):
        return self._value

    def set(self, value):
        self._value = max(float(self._from), min(float(self._to), float(value)))
        self._draw()

    def _frac(self):
        return (self._value - self._from) / (self._to - self._from)

    @staticmethod
    def _make_track(width: int, height: int, color: str) -> ImageTk.PhotoImage:
        """Render a pill-shaped track segment via PIL oversampling."""
        over = 4
        w, h = max(1, width) * over, height * over
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = h // 2
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=color)
        img = img.resize((max(1, width), height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    @staticmethod
    def _make_thumb(radius: int, fill: str, outline: str, outline_w: int) -> ImageTk.PhotoImage:
        """Render a smooth circle via PIL oversampling."""
        over = 4
        d = (radius * 2 + 2) * over
        img = Image.new('RGBA', (d, d), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        ow = outline_w * over
        draw.ellipse([ow, ow, d - ow, d - ow], fill=fill, outline=outline, width=ow)
        img = img.resize((radius * 2 + 2, radius * 2 + 2), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def _draw(self, _event=None):
        self.delete('all')
        w  = self.winfo_width()
        h  = self.winfo_height()
        tr = self.THUMB_R
        cy = h // 2
        th = self.TRACK_H
        r  = th // 2

        x0 = tr
        x1 = w - tr
        tx = x0 + (x1 - x0) * self._frac()

        # tracks rendered via PIL for symmetric rounded caps
        self._track_bg_img = self._make_track(int(x1 - x0), th, TRACK_BG)
        self.create_image(x0, cy, image=self._track_bg_img, anchor='w')
        if tx > x0:
            self._track_fg_img = self._make_track(max(th, int(tx - x0)), th, ACCENT)
            self.create_image(x0, cy, image=self._track_fg_img, anchor='w')

        # smooth thumb via PIL — keep reference to prevent GC
        self._thumb_img = self._make_thumb(tr, 'white', ACCENT, 2)
        self.create_image(tx, cy, image=self._thumb_img, anchor='center')

    def _rounded_rect(self, x0, y0, x1, y1, r, color):
        self.create_arc(x0, y0, x0 + 2*r, y0 + 2*r, start=90,  extent=90,  fill=color, outline='')
        self.create_arc(x1 - 2*r, y0, x1, y0 + 2*r, start=0,   extent=90,  fill=color, outline='')
        self.create_arc(x0, y1 - 2*r, x0 + 2*r, y1, start=180, extent=90,  fill=color, outline='')
        self.create_arc(x1 - 2*r, y1 - 2*r, x1, y1, start=270, extent=90,  fill=color, outline='')
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline='')
        self.create_rectangle(x0, y0 + r, x1, y1 - r, fill=color, outline='')

    def _x_to_value(self, x):
        w  = self.winfo_width()
        tr = self.THUMB_R
        frac = (x - tr) / max(1, w - 2 * tr)
        frac = max(0.0, min(1.0, frac))
        return self._from + frac * (self._to - self._from)

    def _on_press(self, e):
        self._drag  = True
        self._value = self._x_to_value(e.x)
        self._draw()
        if self._cmd:
            self._cmd(self._value)

    def _on_drag(self, e):
        if not self._drag:
            return
        self._value = self._x_to_value(e.x)
        self._draw()
        if self._cmd:
            self._cmd(self._value)

    def _on_release(self, e):
        self._drag = False


# ── main window ───────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, config: dict, save_fn, status: str = 'disconnected'):
        self.config  = config
        self.save_fn = save_fn
        self._status = status
        self.root: tk.Tk | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def open(self):
        if self.root:
            try:
                self.root.lift()
                self.root.focus_force()
                return
            except tk.TclError:
                pass

        try:
            from icon_gen import clear_cache
            clear_cache()
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.title('Media Manager')
        self.root.geometry('300x600')
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        # Replace feather icon with our generated icon
        try:
            from icon_gen import make_icon
            img = make_icon('disconnected', size=64)
            self._win_icon = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self._win_icon)
        except Exception:
            pass

        self._build()
        self.root.mainloop()
        self.root = None

    def set_status(self, status: str):
        self._status = status
        if self.root:
            try:
                self.root.after(0, lambda s=status: self._apply_status(s))
            except tk.TclError:
                pass

    def _apply_status(self, status: str):
        self._status_lbl.config(
            text=STATUS_TEXT.get(status, ''),
            fg=STATUS_COLOR.get(status, '#6B7280'),
        )
        if self._icon_lbl:
            try:
                from icon_gen import make_icon
                img = make_icon(status, size=28)
                self._icon_img = ImageTk.PhotoImage(img)
                self._icon_lbl.config(image=self._icon_img)
            except Exception:
                pass

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        r = self.root

        # header
        hdr = tk.Frame(r, bg=SURFACE, height=72)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        title_frame = tk.Frame(hdr, bg=SURFACE)
        title_frame.place(relx=0, rely=0.18, x=16)

        try:
            from icon_gen import make_icon
            img = make_icon(self._status, size=28)
            self._icon_img = ImageTk.PhotoImage(img)
            self._icon_lbl = tk.Label(title_frame, image=self._icon_img, bg=SURFACE)
            self._icon_lbl.pack(side='left', padx=(0, 8))
        except Exception:
            self._icon_lbl = None

        tk.Label(title_frame, text='Media Manager', bg=SURFACE, fg=TEXT,
                 font=(FONT, 11, 'bold')).pack(side='left')

        self._status_lbl = tk.Label(
            hdr,
            text=STATUS_TEXT.get(self._status, ''),
            fg=STATUS_COLOR.get(self._status, '#6B7280'),
            bg=SURFACE, font=(FONT, 8),
        )
        self._status_lbl.place(relx=0, rely=0.65, x=16)

        tk.Frame(r, bg=BORDER, height=1).pack(fill='x')

        # body
        body = tk.Frame(r, bg=BG, padx=20, pady=18)
        body.pack(fill='both', expand=True)

        # ── resume delay ──────────────────────────────────────────────────────
        tk.Label(body, text='RESUME AFTER SILENCE', bg=BG,
                 fg=LABEL, font=(FONT, 8)).pack(anchor='w')

        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill='x', pady=(6, 16))

        self._delay_lbl = tk.Label(row1, text=f"{self.config.get('resume_delay', 10)}s",
                                   bg=BG, fg=TEXT, font=(FONT, 11, 'bold'),
                                   width=4, anchor='e')
        self._delay_lbl.pack(side='right')

        self._delay_sl = Slider(row1, from_=1, to=30,
                                value=self.config.get('resume_delay', 10),
                                command=self._on_delay)
        self._delay_sl.pack(side='left', fill='x', expand=True, padx=(0, 8))

        # ── trigger sensitivity ───────────────────────────────────────────────
        tk.Label(body, text='TRIGGER SENSITIVITY', bg=BG,
                 fg=LABEL, font=(FONT, 8)).pack(anchor='w')

        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill='x', pady=(6, 16))

        init_sens = _threshold_to_slider(self.config.get('threshold', 0.01))
        self._sens_lbl = tk.Label(row2, text=f"{init_sens}%",
                                  bg=BG, fg=TEXT, font=(FONT, 11, 'bold'),
                                  width=4, anchor='e')
        self._sens_lbl.pack(side='right')

        self._sens_sl = Slider(row2, from_=1, to=99, value=init_sens,
                               command=self._on_sens)
        self._sens_sl.pack(side='left', fill='x', expand=True, padx=(0, 8))

        # ── mic sensitivity ───────────────────────────────────────────────────
        tk.Label(body, text='MIC SENSITIVITY', bg=BG,
                 fg=LABEL, font=(FONT, 8)).pack(anchor='w')

        row3 = tk.Frame(body, bg=BG)
        row3.pack(fill='x', pady=(6, 16))

        init_mic = _threshold_to_slider(self.config.get('mic_threshold', 0.05))
        self._mic_lbl = tk.Label(row3, text=f"{init_mic}%",
                                 bg=BG, fg=TEXT, font=(FONT, 11, 'bold'),
                                 width=4, anchor='e')
        self._mic_lbl.pack(side='right')

        self._mic_sl = Slider(row3, from_=1, to=99, value=init_mic,
                              command=self._on_mic_sens)
        self._mic_sl.pack(side='left', fill='x', expand=True, padx=(0, 8))

        # ── voice app selector ────────────────────────────────────────────────
        tk.Label(body, text='VOICE APP', bg=BG,
                 fg=LABEL, font=(FONT, 8)).pack(anchor='w')

        from audio_monitor import VOICE_APPS
        voice_app_names = list(VOICE_APPS.keys())
        self._voice_var = tk.StringVar(value=self.config.get('voice_app', 'Discord'))

        voice_row = tk.Frame(body, bg=BG)
        voice_row.pack(fill='x', pady=(6, 16))

        self._voice_menu = tk.OptionMenu(voice_row, self._voice_var, *voice_app_names,
                                         command=self._on_voice_app)
        self._voice_menu.config(bg=BG, fg=TEXT, font=(FONT, 9), relief='flat',
                                bd=0, highlightthickness=1,
                                highlightbackground=BORDER, activebackground=SURFACE,
                                cursor='hand2')
        self._voice_menu['menu'].config(bg=BG, fg=TEXT, font=(FONT, 9),
                                        activebackground=SURFACE, bd=0)
        self._voice_menu.pack(fill='x')

        # ── mic device selector ───────────────────────────────────────────────
        tk.Label(body, text='MICROPHONE', bg=BG,
                 fg=LABEL, font=(FONT, 8)).pack(anchor='w')

        try:
            from audio_monitor import get_input_devices
            self._mic_devices = get_input_devices()
        except Exception:
            self._mic_devices = []

        device_names = ['Auto-detect'] + [name for _, name in self._mic_devices]
        self._mic_var = tk.StringVar()

        saved_id = self.config.get('mic_device_id')
        if saved_id is not None:
            match = next((name for did, name in self._mic_devices if did == saved_id), None)
            self._mic_var.set(match if match else 'Auto-detect')
        else:
            self._mic_var.set('Auto-detect')

        mic_row = tk.Frame(body, bg=BG)
        mic_row.pack(fill='x', pady=(6, 16))

        self._mic_menu = tk.OptionMenu(mic_row, self._mic_var, *device_names,
                                       command=self._on_mic_device)
        self._mic_menu.config(bg=BG, fg=TEXT, font=(FONT, 9), relief='flat',
                              bd=0, highlightthickness=1,
                              highlightbackground=BORDER, activebackground=SURFACE,
                              cursor='hand2')
        self._mic_menu['menu'].config(bg=BG, fg=TEXT, font=(FONT, 9),
                                      activebackground=SURFACE, bd=0)
        self._mic_menu.pack(fill='x')

        # ── divider + toggles ─────────────────────────────────────────────────
        tk.Frame(body, bg=BORDER, height=1).pack(fill='x', pady=(0, 14))

        tog_row = tk.Frame(body, bg=BG, height=36)
        tog_row.pack(fill='x', pady=(0, 8))
        tog_row.pack_propagate(False)

        tk.Label(tog_row, text='Active', bg=BG, fg=TEXT,
                 font=(FONT, 10, 'bold')).pack(side='left', anchor='center')

        self._tog_btn = tk.Button(
            tog_row, text='', relief='flat', bd=0,
            cursor='hand2', padx=14,
            font=(FONT, 9, 'bold'),
            command=self._on_toggle,
        )
        self._tog_btn.pack(side='right', fill='y')
        self._refresh_toggle()

        self_row = tk.Frame(body, bg=BG, height=36)
        self_row.pack(fill='x', pady=(0, 8))
        self_row.pack_propagate(False)

        tk.Label(self_row, text='Pause when I speak', bg=BG, fg=TEXT,
                 font=(FONT, 10, 'bold')).pack(side='left', anchor='center')

        self._self_btn = tk.Button(
            self_row, text='', relief='flat', bd=0,
            cursor='hand2', padx=14,
            font=(FONT, 9, 'bold'),
            command=self._on_self_toggle,
        )
        self._self_btn.pack(side='right', fill='y')
        self._refresh_self_toggle()

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_delay(self, val):
        v = max(1, min(30, round(val)))
        self._delay_lbl.config(text=f"{v}s")
        self.config['resume_delay'] = v
        self.save_fn(self.config)

    def _on_sens(self, val):
        v = max(1, min(99, round(val)))
        self._sens_lbl.config(text=f"{v}%")
        self.config['threshold'] = _slider_to_threshold(v)
        self.save_fn(self.config)

    def _on_voice_app(self, name: str):
        self.config['voice_app'] = name
        self.save_fn(self.config)

    def _on_mic_device(self, name: str):
        if name == 'Auto-detect':
            self.config['mic_device_id'] = None
        else:
            match = next((did for did, n in self._mic_devices if n == name), None)
            self.config['mic_device_id'] = match
        self.save_fn(self.config)
        try:
            from audio_monitor import set_mic_device
            set_mic_device(self.config['mic_device_id'])
        except Exception:
            pass

    def _on_mic_sens(self, val):
        v = max(1, min(99, round(val)))
        self._mic_lbl.config(text=f"{v}%")
        self.config['mic_threshold'] = _slider_to_threshold(v)
        self.save_fn(self.config)

    def _on_toggle(self):
        self.config['enabled'] = not self.config.get('enabled', True)
        self._refresh_toggle()
        self.save_fn(self.config)

    def _refresh_toggle(self):
        on = self.config.get('enabled', True)
        self._tog_btn.config(
            text='On' if on else 'Off',
            bg=ACCENT if on else BORDER,
            fg='white' if on else MUTED,
        )

    def _on_self_toggle(self):
        self.config['pause_on_self'] = not self.config.get('pause_on_self', False)
        self._refresh_self_toggle()
        self.save_fn(self.config)

    def _refresh_self_toggle(self):
        on = self.config.get('pause_on_self', True)
        self._self_btn.config(
            text='On' if on else 'Off',
            bg=ACCENT if on else BORDER,
            fg='white' if on else MUTED,
        )

    def _on_close(self):
        if self.root:
            self.root.destroy()
