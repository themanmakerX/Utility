import tkinter as tk
from PIL import Image, ImageTk

from ..utils.paths import resource_path
from ..utils.theme import Theme

class Header(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#29314f")

        # --- Top Header Frame ---
        self.header_frame = tk.Frame(self, bg="#29314f", height=80)
        self.header_frame.pack(fill="x", side="top")

        # --- Center Container Frame inside Header ---
        self.center_frame = tk.Frame(self.header_frame, bg="#29314f")
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")  # <-- Center the frame

        # --- Load Logo ---
        logo_path = resource_path("logo", "icon.png")
        try:
            original_logo = Image.open(logo_path).resize((100, 100), Image.LANCZOS)
        except Exception:
            original_logo = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        self.header_logo_img = ImageTk.PhotoImage(original_logo)

        self.logo_label = tk.Label(self.center_frame, image=self.header_logo_img, bg="#29314f")
        self.logo_label.pack(side="left", padx=(10, 10))

        # --- Title and Tagline beside Logo ---
        self.title_tagline_frame = tk.Frame(self.center_frame, bg="#29314f")
        self.title_tagline_frame.pack(side="left")

        self.title_label = tk.Label(
            self.title_tagline_frame,
            text="Testbench Ecosystem",
            font=("Segoe UI", 20, "bold"),
            bg="#29314f", fg="white"
        )
        self.title_label.pack(anchor="w")

        self.tagline_label = tk.Label(
            self.title_tagline_frame,
            text="From DUT to Debug - All in One Lab",
            font=("Segoe UI", 10),
            bg="#29314f", fg="#cccccc"
        )
        self.tagline_label.pack(anchor="w")

        # --- Dashboard Content Frame ---
        self.content_frame = tk.Frame(self, bg="#f8f8f8")
        self.content_frame.pack(fill="both", expand=True)

    def set_theme(self, theme: Theme) -> None:
        self.configure(bg=theme.panel)
        self.header_frame.configure(bg=theme.panel)
        self.center_frame.configure(bg=theme.panel)
        self.logo_label.configure(bg=theme.panel)
        self.title_tagline_frame.configure(bg=theme.panel)
        self.title_label.configure(bg=theme.panel, fg=theme.fg)
        self.tagline_label.configure(bg=theme.panel, fg=theme.fg_muted)
