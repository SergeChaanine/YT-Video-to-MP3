from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from urllib.parse import parse_qs, urlparse

from yt_to_mp3.config import SettingsStore
from yt_to_mp3.models import AppEvent, ItemStatus, NormalizationSettings, QueueItem, TrackMetadata
from yt_to_mp3.services.audio import AudioProcessingError
from yt_to_mp3.services.downloader import DownloadCancelled, DownloadService
from yt_to_mp3.services.filenames import available_output_path, build_filename
from yt_to_mp3.services.javascript import JavaScriptRuntimeError
from yt_to_mp3.ui.styles import apply_theme

YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:(?:www|music)\.)?(?:youtube\.com|youtu\.be)/[^\s<>\"']+",
    flags=re.IGNORECASE,
)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"
MODE_LABELS = {
    "balanced": "Balanced (−16 LUFS)",
    "gentle": "Gentle (−18 LUFS)",
}
MODE_VALUES = {label: value for value, label in MODE_LABELS.items()}


class MainWindow(tk.Tk):
    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        super().__init__()
        self.settings_store = settings_store or SettingsStore()
        self.settings = self.settings_store.load()
        self.items: dict[str, QueueItem] = {}
        self.item_order: list[str] = []
        self.known_urls: set[str] = set()
        self.events: queue.Queue[AppEvent] = queue.Queue()
        self.cancel_event = threading.Event()
        self.download_active = False
        self.last_clipboard = ""
        self.palette = apply_theme(self, self.settings.theme)
        self.service = DownloadService(log_callback=self._thread_log)

        self.title("YouTube to MP3 Converter · Serge Chaanine")
        self.geometry("1060x780")
        self.minsize(900, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._create_variables()
        self._build_ui()
        self._apply_text_colors()
        self.after(100, self._process_events)
        self.after(1_000, self._clipboard_loop)
        self.after(250, self._check_dependencies)

    def _create_variables(self) -> None:
        self.output_directory_var = tk.StringVar(value=self.settings.output_directory)
        self.normalize_var = tk.BooleanVar(value=self.settings.normalize_quiet_audio)
        self.mode_var = tk.StringVar(
            value=MODE_LABELS.get(self.settings.normalization_mode, MODE_LABELS["balanced"])
        )
        self.playlists_var = tk.BooleanVar(value=self.settings.allow_playlists)
        self.clipboard_var = tk.BooleanVar(value=self.settings.auto_add_clipboard_urls)
        self.theme_var = tk.StringVar(value=self.settings.theme.title())
        self.current_progress_var = tk.DoubleVar(value=0.0)
        self.overall_progress_var = tk.DoubleVar(value=0.0)
        self.current_status_var = tk.StringVar(value="Ready")
        self.overall_status_var = tk.StringVar(value="No downloads started")
        self.dependency_status_var = tk.StringVar(value="Checking download tools…")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, style="App.TFrame", padding=(22, 18, 22, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="YouTube to MP3 Converter", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Maximum-quality MP3 · smart volume normalization · reliable artist and title",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(header, textvariable=self.dependency_status_var, style="Muted.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        settings_card = ttk.Frame(self, style="Card.TFrame", padding=14)
        settings_card.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))
        settings_card.columnconfigure(1, weight=1)
        ttk.Label(settings_card, text="Output folder", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.output_entry = ttk.Entry(
            settings_card,
            textvariable=self.output_directory_var,
            state="readonly",
        )
        self.output_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(settings_card, text="Change", command=self._change_output_directory).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Button(settings_card, text="Open", command=self._open_output_directory).grid(
            row=0, column=3, padx=(8, 0)
        )

        options = ttk.Frame(settings_card, style="Card.TFrame")
        options.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        self.normalize_check = ttk.Checkbutton(
            options,
            text="Normalize quiet audio",
            variable=self.normalize_var,
            command=self._settings_changed,
        )
        self.normalize_check.pack(side="left")
        ttk.Label(options, text="Mode", style="CardMuted.TLabel").pack(side="left", padx=(18, 6))
        self.mode_combo = ttk.Combobox(
            options,
            textvariable=self.mode_var,
            values=list(MODE_LABELS.values()),
            width=22,
            state="readonly",
        )
        self.mode_combo.pack(side="left")
        self.mode_combo.bind("<<ComboboxSelected>>", self._settings_changed)
        ttk.Checkbutton(
            options,
            text="Allow playlists",
            variable=self.playlists_var,
            command=self._settings_changed,
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            options,
            text="Watch clipboard",
            variable=self.clipboard_var,
            command=self._settings_changed,
        ).pack(side="left", padx=(18, 0))
        ttk.Label(options, text="Theme", style="CardMuted.TLabel").pack(side="right", padx=(8, 6))
        theme_combo = ttk.Combobox(
            options,
            textvariable=self.theme_var,
            values=("Dark", "Light"),
            width=8,
            state="readonly",
        )
        theme_combo.pack(side="right")
        theme_combo.bind("<<ComboboxSelected>>", self._theme_changed)

        input_card = ttk.Frame(self, style="Card.TFrame", padding=14)
        input_card.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 10))
        input_card.columnconfigure(0, weight=1)
        ttk.Label(
            input_card,
            text="Paste YouTube URLs — one per line",
            style="Card.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 7))
        self.url_text = scrolledtext.ScrolledText(
            input_card,
            height=4,
            wrap="word",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        self.url_text.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        input_buttons = ttk.Frame(input_card, style="Card.TFrame")
        input_buttons.grid(row=1, column=1, sticky="ns")
        ttk.Button(input_buttons, text="Add to queue", command=self._add_from_input).pack(fill="x")
        ttk.Button(input_buttons, text="Paste", command=self._paste_urls).pack(
            fill="x", pady=(7, 0)
        )

        queue_card = ttk.Frame(self, style="Card.TFrame", padding=14)
        queue_card.grid(row=3, column=0, sticky="nsew", padx=22, pady=(0, 10))
        queue_card.columnconfigure(0, weight=1)
        queue_card.rowconfigure(1, weight=1)
        ttk.Label(queue_card, text="Download queue", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.tree = ttk.Treeview(
            queue_card,
            columns=("filename", "duration", "status", "progress"),
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("filename", text="Singer - Music name")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("status", text="Status")
        self.tree.heading("progress", text="Progress")
        self.tree.column("filename", width=500, minwidth=260, stretch=True)
        self.tree.column("duration", width=85, minwidth=75, anchor="center", stretch=False)
        self.tree.column("status", width=150, minwidth=120, stretch=False)
        self.tree.column("progress", width=80, minwidth=70, anchor="e", stretch=False)
        self.tree.grid(row=1, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(queue_card, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<Double-1>", lambda _event: self._edit_selected_name())

        queue_buttons = ttk.Frame(queue_card, style="Card.TFrame")
        queue_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.edit_button = ttk.Button(
            queue_buttons,
            text="Edit name",
            command=self._edit_selected_name,
        )
        self.edit_button.pack(side="left")
        self.remove_button = ttk.Button(queue_buttons, text="Remove", command=self._remove_selected)
        self.remove_button.pack(side="left", padx=(7, 0))
        self.clear_button = ttk.Button(
            queue_buttons,
            text="Clear completed",
            command=self._clear_completed,
        )
        self.clear_button.pack(side="left", padx=(7, 0))
        ttk.Button(queue_buttons, text="Show log", command=self._toggle_log).pack(side="right")

        progress_card = ttk.Frame(self, style="Card.TFrame", padding=14)
        progress_card.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 18))
        progress_card.columnconfigure(0, weight=1)
        ttk.Label(progress_card, textvariable=self.current_status_var, style="Card.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Progressbar(
            progress_card,
            variable=self.current_progress_var,
            maximum=100,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 9))
        ttk.Label(
            progress_card,
            textvariable=self.overall_status_var,
            style="CardMuted.TLabel",
        ).grid(row=2, column=0, sticky="w")
        ttk.Progressbar(
            progress_card,
            variable=self.overall_progress_var,
            maximum=100,
        ).grid(row=3, column=0, sticky="ew", pady=(5, 0))
        actions = ttk.Frame(progress_card, style="Card.TFrame")
        actions.grid(row=0, column=1, rowspan=4, sticky="e", padx=(18, 0))
        self.download_button = ttk.Button(
            actions,
            text="Download all",
            style="Accent.TButton",
            command=self._start_downloads,
        )
        self.download_button.pack(fill="x")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self._cancel_downloads)
        self.cancel_button.pack(fill="x", pady=(8, 0))
        self.cancel_button.configure(state="disabled")

        self.log_frame = ttk.Frame(self, style="Card.TFrame", padding=14)
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(1, weight=1)
        ttk.Label(self.log_frame, text="Activity log", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            height=9,
            state="disabled",
            relief="flat",
            borderwidth=0,
            font=("Cascadia Mono", 9),
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        self.log_visible = False

    def _apply_text_colors(self) -> None:
        for widget in (self.url_text, self.log_text):
            widget.configure(
                background=self.palette["surface_alt"],
                foreground=self.palette["text"],
                insertbackground=self.palette["text"],
                selectbackground=self.palette["selection"],
                selectforeground=self.palette["text"],
            )
        self.option_add("*TCombobox*Listbox.background", self.palette["surface_alt"])
        self.option_add("*TCombobox*Listbox.foreground", self.palette["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", self.palette["selection"])

    def _theme_changed(self, _event: tk.Event | None = None) -> None:
        self.settings.theme = self.theme_var.get().lower()
        self.palette = apply_theme(self, self.settings.theme)
        self._apply_text_colors()
        self._save_settings()

    def _settings_changed(self, _event: tk.Event | None = None) -> None:
        self.settings.normalize_quiet_audio = self.normalize_var.get()
        self.settings.normalization_mode = MODE_VALUES.get(self.mode_var.get(), "balanced")
        self.settings.allow_playlists = self.playlists_var.get()
        self.settings.auto_add_clipboard_urls = self.clipboard_var.get()
        self.mode_combo.configure(state="readonly" if self.normalize_var.get() else "disabled")
        self._save_settings()

    def _normalization_settings(self) -> NormalizationSettings:
        mode = MODE_VALUES.get(self.mode_var.get(), "balanced")
        if mode == "gentle":
            return NormalizationSettings(
                enabled=self.normalize_var.get(),
                target_lufs=-18.0,
                max_limiter_reduction_db=1.5,
            )
        return NormalizationSettings(enabled=self.normalize_var.get())

    def _change_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_directory_var.get())
        if selected:
            self.output_directory_var.set(selected)
            self.settings.output_directory = selected
            self._save_settings()

    def _open_output_directory(self) -> None:
        directory = Path(self.output_directory_var.get()).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(directory)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except OSError as error:
            messagebox.showerror("Cannot open folder", str(error), parent=self)

    def _add_from_input(self) -> None:
        text = self.url_text.get("1.0", "end").strip()
        urls = extract_youtube_urls(text)
        if not urls:
            messagebox.showwarning(
                "No YouTube URLs",
                "Paste at least one valid YouTube or YouTube Music URL.",
                parent=self,
            )
            return
        self.url_text.delete("1.0", "end")
        self._enqueue_urls(urls)

    def _paste_urls(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Clipboard", "The clipboard does not contain text.", parent=self)
            return
        urls = extract_youtube_urls(text)
        if not urls:
            messagebox.showinfo("Clipboard", "No YouTube URLs were found.", parent=self)
            return
        self._enqueue_urls(urls)

    def _enqueue_urls(self, urls: list[str]) -> None:
        new_items: list[QueueItem] = []
        for url in urls:
            key = canonical_url_key(url)
            if key in self.known_urls:
                self._append_log(f"Skipped duplicate URL: {url}")
                continue
            self.known_urls.add(key)
            item = QueueItem(url=url, status=ItemStatus.READING_METADATA)
            self.items[item.id] = item
            self.item_order.append(item.id)
            new_items.append(item)
            self._refresh_item(item)
        if not new_items:
            return
        self._append_log(f"Reading metadata for {len(new_items)} URL(s)…")
        thread = threading.Thread(
            target=self._metadata_worker,
            args=(new_items, self.playlists_var.get()),
            daemon=True,
            name="metadata-worker",
        )
        thread.start()

    def _metadata_worker(self, items: list[QueueItem], allow_playlists: bool) -> None:
        service = DownloadService(log_callback=self._thread_log)
        for item in items:
            try:
                tracks = service.fetch_metadata(item.url, allow_playlists)
                self.events.put(AppEvent("metadata_ready", item.id, {"tracks": tracks}))
            except Exception as error:
                self.events.put(AppEvent("metadata_failed", item.id, {"error": str(error)}))

    def _start_downloads(self) -> None:
        if self.download_active:
            return
        candidates = [
            self.items[item_id]
            for item_id in self.item_order
            if self.items[item_id].metadata
            and self.items[item_id].status
            in {ItemStatus.READY, ItemStatus.FAILED, ItemStatus.CANCELLED}
        ]
        if not candidates:
            messagebox.showinfo(
                "Nothing ready",
                "Add a URL and wait for its artist and title to appear first.",
                parent=self,
            )
            return
        try:
            self.service.check_dependencies()
        except (AudioProcessingError, JavaScriptRuntimeError) as error:
            messagebox.showerror("Download tool unavailable", str(error), parent=self)
            return

        output_directory = Path(self.output_directory_var.get()).expanduser()
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror("Output folder unavailable", str(error), parent=self)
            return

        jobs: list[tuple[str, TrackMetadata, Path, bool]] = []
        for item in candidates:
            assert item.metadata is not None
            destination = output_directory / build_filename(
                item.metadata.artist,
                item.metadata.title,
            )
            overwrite = False
            if destination.exists():
                answer = messagebox.askyesnocancel(
                    "File already exists",
                    f"{destination.name} already exists.\n\n"
                    "Yes: replace it\nNo: save a numbered copy\nCancel: skip this track",
                    parent=self,
                )
                if answer is None:
                    continue
                if answer:
                    overwrite = True
                else:
                    destination = available_output_path(output_directory, destination.name)
            item.output_path = destination
            item.overwrite = overwrite
            jobs.append((item.id, replace(item.metadata), destination, overwrite))
        if not jobs:
            return

        self.download_active = True
        self.cancel_event.clear()
        self._set_controls_for_download(True)
        self.overall_progress_var.set(0)
        self.current_progress_var.set(0)
        thread = threading.Thread(
            target=self._download_worker,
            args=(jobs, self._normalization_settings()),
            daemon=True,
            name="download-worker",
        )
        thread.start()

    def _download_worker(
        self,
        jobs: list[tuple[str, TrackMetadata, Path, bool]],
        normalization: NormalizationSettings,
    ) -> None:
        service = DownloadService(log_callback=self._thread_log)
        completed = 0
        failed = 0
        for index, (item_id, metadata, destination, overwrite) in enumerate(jobs):
            if self.cancel_event.is_set():
                self.events.put(AppEvent("item_cancelled", item_id))
                continue
            self.events.put(AppEvent("item_started", item_id, {"index": index, "total": len(jobs)}))

            def progress(
                fraction: float,
                message: str,
                current_index: int = index,
                current_item_id: str = item_id,
                job_count: int = len(jobs),
            ) -> None:
                overall = (current_index + fraction) / job_count
                self.events.put(
                    AppEvent(
                        "download_progress",
                        current_item_id,
                        {"fraction": fraction, "overall": overall, "message": message},
                    )
                )

            try:
                result = service.download_track(
                    metadata=metadata,
                    destination=destination,
                    normalization=normalization,
                    overwrite=overwrite,
                    cancel_event=self.cancel_event,
                    progress_callback=progress,
                )
                completed += 1
                self.events.put(AppEvent("item_completed", item_id, {"path": result}))
            except DownloadCancelled as error:
                self.events.put(AppEvent("item_cancelled", item_id, {"error": str(error)}))
            except Exception as error:
                failed += 1
                self.events.put(AppEvent("item_failed", item_id, {"error": str(error)}))
        self.events.put(
            AppEvent(
                "batch_finished",
                data={
                    "completed": completed,
                    "failed": failed,
                    "cancelled": self.cancel_event.is_set(),
                },
            )
        )

    def _cancel_downloads(self) -> None:
        if self.download_active:
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.current_status_var.set("Cancelling safely…")
            self._append_log("Cancellation requested. Temporary files will be removed.")

    def _edit_selected_name(self) -> None:
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("Edit name", "Select one ready track to edit.", parent=self)
            return
        item = self.items.get(selected[0])
        if not item or not item.metadata:
            return
        artist = simpledialog.askstring(
            "Singer / artist",
            "Singer or artist:",
            initialvalue=item.metadata.artist,
            parent=self,
        )
        if artist is None or not artist.strip():
            return
        title = simpledialog.askstring(
            "Music name",
            "Song or music name:",
            initialvalue=item.metadata.title,
            parent=self,
        )
        if title is None or not title.strip():
            return
        item.metadata.artist = artist.strip()
        item.metadata.title = title.strip()
        item.metadata.needs_review = False
        item.status = ItemStatus.READY
        self._refresh_item(item)
        self._append_log(f"Filename updated: {build_filename(artist, title)}")

    def _remove_selected(self) -> None:
        for item_id in self.tree.selection():
            item = self.items.get(item_id)
            if not item or item.status in {
                ItemStatus.DOWNLOADING,
                ItemStatus.ANALYZING,
                ItemStatus.CONVERTING,
                ItemStatus.FINALIZING,
            }:
                continue
            self._remove_item(item_id)

    def _clear_completed(self) -> None:
        for item_id in list(self.item_order):
            if self.items[item_id].status == ItemStatus.COMPLETED:
                self._remove_item(item_id)

    def _remove_item(self, item_id: str) -> None:
        item = self.items.pop(item_id, None)
        if not item:
            return
        self.item_order.remove(item_id)
        self.known_urls.discard(canonical_url_key(item.url))
        if self.tree.exists(item_id):
            self.tree.delete(item_id)

    def _toggle_log(self) -> None:
        if self.log_visible:
            self.log_frame.grid_remove()
            self.geometry(f"{self.winfo_width()}x{max(650, self.winfo_height() - 190)}")
        else:
            self.log_frame.grid(row=5, column=0, sticky="nsew", padx=22, pady=(0, 18))
            self.geometry(f"{self.winfo_width()}x{self.winfo_height() + 190}")
        self.log_visible = not self.log_visible

    def _process_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _handle_event(self, event: AppEvent) -> None:
        item = self.items.get(event.item_id) if event.item_id else None
        if event.kind == "log":
            self._append_log(str(event.data.get("message", "")))
        elif event.kind == "dependency_ready":
            self.dependency_status_var.set("Download tools ready")
        elif event.kind == "dependency_failed":
            self.dependency_status_var.set("Download tool unavailable")
            self._append_log(str(event.data.get("error", "A required tool is unavailable.")))
        elif event.kind == "metadata_ready" and item:
            tracks = event.data.get("tracks") or []
            if tracks:
                self._apply_metadata(item, tracks[0])
                for metadata in tracks[1:]:
                    key = canonical_url_key(metadata.url)
                    if key in self.known_urls:
                        continue
                    self.known_urls.add(key)
                    extra = QueueItem(url=metadata.url, metadata=metadata, status=ItemStatus.READY)
                    self.items[extra.id] = extra
                    self.item_order.append(extra.id)
                    self._refresh_item(extra)
            self._append_log(f"Metadata ready: {self._display_filename(item)}")
        elif event.kind == "metadata_failed" and item:
            item.status = ItemStatus.FAILED
            item.message = str(event.data.get("error", "Could not read metadata."))
            self._refresh_item(item)
            self._append_log(f"Metadata failed: {item.message}")
        elif event.kind == "item_started" and item:
            item.status = ItemStatus.DOWNLOADING
            item.progress = 0
            self.current_progress_var.set(0)
            self.current_status_var.set(f"Downloading {self._display_filename(item)}")
            self.overall_status_var.set(
                f"Track {event.data.get('index', 0) + 1} of {event.data.get('total', 1)}"
            )
            self._refresh_item(item)
        elif event.kind == "download_progress" and item:
            fraction = float(event.data.get("fraction", 0.0))
            message = str(event.data.get("message", "Working…"))
            item.progress = fraction
            item.message = message
            item.status = _status_for_progress(fraction)
            self.current_progress_var.set(fraction * 100)
            self.overall_progress_var.set(float(event.data.get("overall", 0.0)) * 100)
            self.current_status_var.set(f"{message} · {self._display_filename(item)}")
            self._refresh_item(item)
        elif event.kind == "item_completed" and item:
            item.status = ItemStatus.COMPLETED
            item.progress = 1.0
            item.output_path = Path(event.data["path"])
            self._refresh_item(item)
            self._append_log(f"Completed: {item.output_path}")
        elif event.kind == "item_failed" and item:
            item.status = ItemStatus.FAILED
            item.message = str(event.data.get("error", "Download failed."))
            self._refresh_item(item)
            self._append_log(f"Failed: {self._display_filename(item)} — {item.message}")
        elif event.kind == "item_cancelled" and item:
            item.status = ItemStatus.CANCELLED
            item.message = str(event.data.get("error", "Cancelled"))
            self._refresh_item(item)
        elif event.kind == "batch_finished":
            self.download_active = False
            self._set_controls_for_download(False)
            completed = event.data.get("completed", 0)
            failed = event.data.get("failed", 0)
            cancelled = event.data.get("cancelled", False)
            self.current_status_var.set("Cancelled" if cancelled else "All downloads finished")
            self.overall_status_var.set(f"Completed: {completed} · Failed: {failed}")
            if not cancelled:
                self.overall_progress_var.set(100)

    def _apply_metadata(self, item: QueueItem, metadata: TrackMetadata) -> None:
        item.url = metadata.url
        item.metadata = metadata
        item.status = ItemStatus.READY
        item.message = "Review name" if metadata.needs_review else ""
        self.known_urls.add(canonical_url_key(metadata.url))
        self._refresh_item(item)

    def _refresh_item(self, item: QueueItem) -> None:
        values = (
            self._display_filename(item),
            format_duration(item.metadata.duration if item.metadata else None),
            str(item.status),
            f"{item.progress * 100:.0f}%" if item.progress else "—",
        )
        if self.tree.exists(item.id):
            self.tree.item(item.id, values=values)
        else:
            self.tree.insert("", "end", iid=item.id, values=values)

    @staticmethod
    def _display_filename(item: QueueItem) -> str:
        if item.metadata:
            return build_filename(item.metadata.artist, item.metadata.title)
        return item.url

    def _set_controls_for_download(self, active: bool) -> None:
        state = "disabled" if active else "normal"
        self.download_button.configure(state=state)
        self.edit_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.cancel_button.configure(state="normal" if active else "disabled")

    def _check_dependencies(self) -> None:
        def worker() -> None:
            try:
                self.service.check_dependencies()
                self.events.put(AppEvent("dependency_ready"))
            except (AudioProcessingError, JavaScriptRuntimeError) as error:
                self.events.put(AppEvent("dependency_failed", data={"error": str(error)}))

        threading.Thread(target=worker, daemon=True, name="dependency-check").start()

    def _clipboard_loop(self) -> None:
        if self.clipboard_var.get() and not self.download_active:
            try:
                content = self.clipboard_get().strip()
                if content and content != self.last_clipboard:
                    self.last_clipboard = content
                    urls = extract_youtube_urls(content)
                    if urls:
                        self._enqueue_urls(urls)
            except tk.TclError:
                pass
        self.after(1_000, self._clipboard_loop)

    def _thread_log(self, message: str) -> None:
        self.events.put(AppEvent("log", data={"message": message}))

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _save_settings(self) -> None:
        try:
            self.settings_store.save(self.settings)
        except OSError as error:
            self._append_log(f"Could not save settings: {error}")

    def _on_close(self) -> None:
        if self.download_active and not messagebox.askyesno(
            "Download in progress",
            "Cancel the current downloads and close the application?",
            parent=self,
        ):
            return
        self.cancel_event.set()
        self.settings.output_directory = self.output_directory_var.get()
        self._settings_changed()
        self.destroy()


def extract_youtube_urls(text: str) -> list[str]:
    normalized_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        youtube_hosts = (
            "youtube.com/",
            "www.youtube.com/",
            "youtu.be/",
            "music.youtube.com/",
        )
        if stripped.lower().startswith(youtube_hosts):
            stripped = f"https://{stripped}"
        normalized_lines.append(stripped)
    matches = YOUTUBE_URL_PATTERN.findall("\n".join(normalized_lines))
    unique: list[str] = []
    seen: set[str] = set()
    for match in matches:
        url = match.rstrip(TRAILING_URL_PUNCTUATION)
        key = canonical_url_key(url)
        if key not in seen:
            seen.add(key)
            unique.append(url)
    return unique


def canonical_url_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("music.")
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        return f"video:{video_id}" if video_id else url
    query = parse_qs(parsed.query)
    if query.get("v"):
        return f"video:{query['v'][0]}"
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
        return f"video:{path_parts[1]}"
    if query.get("list"):
        return f"playlist:{query['list'][0]}"
    return url.rstrip("/")


def format_duration(duration: float | None) -> str:
    if not duration:
        return "—"
    total_seconds = max(0, int(duration))
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def _status_for_progress(fraction: float) -> ItemStatus:
    if fraction < 0.64:
        return ItemStatus.DOWNLOADING
    if fraction < 0.70:
        return ItemStatus.ANALYZING
    if fraction < 0.96:
        return ItemStatus.CONVERTING
    return ItemStatus.FINALIZING
