from __future__ import annotations

from pathlib import Path
import tkinter as tk

from PIL import Image, ImageSequence, ImageTk

COPYRIGHT_SIGN = "\N{COPYRIGHT SIGN}"


class SplashScreen(tk.Toplevel):
    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.parent = parent
        self.overrideredirect(True)
        self.configure(bg="#0a0c1c")

        self._after_ids: list[str] = []
        self._closing = False

        self.opacity = 0.0
        self.fade_in_complete = False

        window_width = 1200
        window_height = 700
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.attributes("-alpha", self.opacity)

        base_dir = Path(__file__).resolve().parents[1]
        logo_dir = base_dir / "logo"

        self.tool_icon_path = logo_dir / "a_logo.png"
        self.company_logo_path = logo_dir / "c_logo.png"
        self.spinner_path = logo_dir / "load.gif"

        self.tool_logo_tk = self._load_photo(self.tool_icon_path, size=(300, 300))
        self.company_logo_tk = self._load_photo(self.company_logo_path, size=(40, 40))
        self.spinner_frames = self._load_gif_frames(self.spinner_path)
        self.spinner_index = 0

        self.footer_text = f" Powered by {COPYRIGHT_SIGN} LetsLearnTechnologies"
        self.footer_index = 0
        self.footer_cursor_visible = True
        self.glow_toggle = True

        self._build_ui()
        self.fade_in()

        self.animate_spinner()
        self.animate_footer_text()
        self.blink_footer_cursor()
        self.glow_footer_effect()

        self.bind("<Button-1>", self.skip_splash)
        self.bind("<Escape>", self.skip_splash)
        self._schedule(2000, self.show_skip_hint)
        self.after_id = self._schedule(7000, self.fade_out)

    def _schedule(self, ms: int, callback) -> str:
        after_id = self.after(ms, callback)
        self._after_ids.append(after_id)
        return after_id

    def _load_photo(self, path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage:
        try:
            img = Image.open(path).resize(size)
        except Exception:
            img = Image.new("RGBA", size, (0, 0, 0, 0))
        return ImageTk.PhotoImage(img)

    def _load_gif_frames(self, path: Path) -> list[ImageTk.PhotoImage]:
        try:
            spinner_img = Image.open(path)
            return [
                ImageTk.PhotoImage(frame.copy().convert("RGBA"))
                for frame in ImageSequence.Iterator(spinner_img)
            ]
        except Exception:
            fallback = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            return [ImageTk.PhotoImage(fallback)]

    def _build_ui(self) -> None:
        self.main_frame = tk.Frame(self, bg="#0a0c1c")
        self.main_frame.pack(fill="both", expand=True)

        header_frame = tk.Frame(self.main_frame, bg="#0a0c1c")
        header_frame.pack(side="top", anchor="n", pady=(40, 10))

        logo_text_frame = tk.Frame(header_frame, bg="#0a0c1c")
        logo_text_frame.pack()

        self.logo_label = tk.Label(logo_text_frame, image=self.tool_logo_tk, bg="#0a0c1c")
        self.logo_label.pack()

        center_frame = tk.Frame(self.main_frame, bg="#0a0c1c")
        center_frame.pack(expand=True)

        self.spinner_label = tk.Label(center_frame, bg="#0a0c1c")
        self.spinner_label.pack(pady=(20, 10))

        self.loading_text = tk.Label(
            center_frame,
            text="Initializing Modules...",
            font=("Segoe UI", 16, "italic"),
            fg="#cccccc",
            bg="#0a0c1c",
        )
        self.loading_text.pack()

        self.skip_hint = tk.Label(
            self.main_frame,
            text="",
            font=("Segoe UI", 9, "italic"),
            fg="#777777",
            bg="#0a0c1c",
        )
        self.skip_hint.pack(side="bottom", pady=(0, 4))

        footer_inner = tk.Frame(self.main_frame, bg="#0a0c1c")
        footer_inner.pack(side="bottom", pady=6)

        self.company_logo_label = tk.Label(
            footer_inner, image=self.company_logo_tk, bg="#0a0c1c"
        )
        self.company_logo_label.pack(side="left", padx=(0, 10))

        self.footer_label = tk.Label(
            footer_inner,
            text="",
            font=("Segoe UI", 10, "bold"),
            fg="#99e0ff",
            bg="#0a0c1c",
        )
        self.footer_label.pack(side="left")

    def fade_in(self) -> None:
        if self._closing:
            return
        if self.opacity < 1.0:
            self.opacity += 0.05
            self.attributes("-alpha", self.opacity)
            self._schedule(30, self.fade_in)
        else:
            self.fade_in_complete = True

    def fade_out(self) -> None:
        if self._closing:
            return

        alpha = float(self.attributes("-alpha"))
        alpha -= 0.05
        if alpha > 0:
            self.attributes("-alpha", alpha)
            self._schedule(50, self.fade_out)
            return

        self._closing = True
        try:
            self.destroy()
        finally:
            self.parent.start_main_app()

    def show_skip_hint(self) -> None:
        if self._closing:
            return
        self.skip_hint.config(text="Click anywhere or press ESC to skip")

    def skip_splash(self, event=None) -> None:
        if self._closing:
            return
        if hasattr(self, "after_id"):
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.fade_out()

    def animate_spinner(self) -> None:
        if self._closing:
            return
        frame = self.spinner_frames[self.spinner_index]
        self.spinner_label.configure(image=frame)
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        self._schedule(100, self.animate_spinner)

    def animate_footer_text(self) -> None:
        if self._closing:
            return
        if self.footer_index <= len(self.footer_text):
            current = self.footer_text[: self.footer_index]
            cursor = "|" if self.footer_cursor_visible else " "
            self.footer_label.config(text=current + cursor)
            self.footer_index += 1
            self._schedule(80, self.animate_footer_text)
        else:
            self.footer_label.config(text=self.footer_text)

    def blink_footer_cursor(self) -> None:
        if self._closing:
            return
        if self.footer_index < len(self.footer_text):
            self.footer_cursor_visible = not self.footer_cursor_visible
            current = self.footer_text[: self.footer_index]
            cursor = "|" if self.footer_cursor_visible else " "
            self.footer_label.config(text=current + cursor)
            self._schedule(500, self.blink_footer_cursor)

    def glow_footer_effect(self) -> None:
        if self._closing:
            return
        if self.footer_index >= len(self.footer_text):
            glow_color = "#99e0ff" if self.glow_toggle else "#33bbff"
            self.footer_label.config(fg=glow_color)
            self.glow_toggle = not self.glow_toggle
        self._schedule(400, self.glow_footer_effect)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            for after_id in self._after_ids:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
        finally:
            try:
                self.destroy()
            except tk.TclError:
                pass
