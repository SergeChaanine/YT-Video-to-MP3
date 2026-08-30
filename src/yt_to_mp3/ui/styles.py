from __future__ import annotations

import tkinter as tk
from tkinter import ttk

DARK = {
    "background": "#111827",
    "surface": "#1f2937",
    "surface_alt": "#273449",
    "text": "#f3f4f6",
    "muted": "#aeb8c7",
    "accent": "#ef4444",
    "accent_active": "#dc2626",
    "border": "#3a4659",
    "selection": "#374a68",
}

LIGHT = {
    "background": "#f3f4f6",
    "surface": "#ffffff",
    "surface_alt": "#e9edf3",
    "text": "#18202c",
    "muted": "#5d6978",
    "accent": "#dc2626",
    "accent_active": "#b91c1c",
    "border": "#ccd3dd",
    "selection": "#dce8f8",
}


def apply_theme(root: tk.Misc, theme_name: str) -> dict[str, str]:
    palette = LIGHT if theme_name == "light" else DARK
    root.configure(background=palette["background"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", 10))
    style.configure("App.TFrame", background=palette["background"])
    style.configure("Card.TFrame", background=palette["surface"])
    style.configure(
        "TLabel",
        background=palette["background"],
        foreground=palette["text"],
    )
    style.configure("Card.TLabel", background=palette["surface"], foreground=palette["text"])
    style.configure(
        "Muted.TLabel",
        background=palette["background"],
        foreground=palette["muted"],
    )
    style.configure(
        "CardMuted.TLabel",
        background=palette["surface"],
        foreground=palette["muted"],
    )
    style.configure(
        "Title.TLabel",
        background=palette["background"],
        foreground=palette["text"],
        font=("Segoe UI Semibold", 20),
    )
    style.configure(
        "Accent.TButton",
        background=palette["accent"],
        foreground="#ffffff",
        padding=(16, 9),
        borderwidth=0,
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Accent.TButton",
        background=[("active", palette["accent_active"]), ("disabled", palette["border"])],
        foreground=[("disabled", palette["muted"])],
    )
    style.configure(
        "TButton",
        background=palette["surface_alt"],
        foreground=palette["text"],
        padding=(11, 7),
        borderwidth=0,
    )
    style.map("TButton", background=[("active", palette["selection"])])
    style.configure(
        "TCheckbutton",
        background=palette["surface"],
        foreground=palette["text"],
    )
    style.map("TCheckbutton", background=[("active", palette["surface"])])
    style.configure(
        "TCombobox",
        fieldbackground=palette["surface_alt"],
        background=palette["surface_alt"],
        foreground=palette["text"],
        arrowcolor=palette["text"],
        bordercolor=palette["border"],
        lightcolor=palette["border"],
        darkcolor=palette["border"],
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette["surface_alt"])],
        foreground=[("readonly", palette["text"])],
    )
    style.configure(
        "Treeview",
        background=palette["surface"],
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        rowheight=32,
        bordercolor=palette["border"],
    )
    style.configure(
        "Treeview.Heading",
        background=palette["surface_alt"],
        foreground=palette["text"],
        relief="flat",
        padding=(8, 8),
        font=("Segoe UI Semibold", 9),
    )
    style.map(
        "Treeview",
        background=[("selected", palette["selection"])],
        foreground=[("selected", palette["text"])],
    )
    style.configure(
        "Horizontal.TProgressbar",
        background=palette["accent"],
        troughcolor=palette["surface_alt"],
        bordercolor=palette["surface_alt"],
        lightcolor=palette["accent"],
        darkcolor=palette["accent"],
    )
    return palette
