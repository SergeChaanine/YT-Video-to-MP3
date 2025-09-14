import os
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import re

class YTDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube to MP3 Converter     ©Serge Chaanine")
        self.geometry("700x550")

        self.output_dir = os.path.expanduser("~/Desktop/YT-MP3")

        self.last_clipboard = ""
        self.youtube_url_pattern = re.compile(
            r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]+"
        )

        self.create_widgets()
        self.check_clipboard_loop()

    def create_widgets(self):
        tk.Label(self, text="Output folder:").pack(anchor='w', padx=10, pady=(10,0))
        self.output_label = tk.Label(self, text=self.output_dir, fg="blue")
        self.output_label.pack(anchor='w', padx=10)
        tk.Button(self, text="Change Folder", command=self.change_output_folder).pack(anchor='w', padx=10, pady=(0,10))

        tk.Label(self, text="Paste YouTube URLs (one per line):").pack(anchor='w', padx=10)
        self.url_text = scrolledtext.ScrolledText(self, height=12)
        self.url_text.pack(fill='both', padx=10, pady=(0,10), expand=False)

        self.download_btn = tk.Button(self, text="Download All", command=self.start_downloads)
        self.download_btn.pack(pady=(0,10))

        tk.Label(self, text="Log:").pack(anchor='w', padx=10)
        self.log_box = scrolledtext.ScrolledText(self, height=15, state='disabled')
        self.log_box.pack(fill='both', padx=10, pady=(0,10), expand=True)

    def change_output_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            self.output_label.config(text=self.output_dir)

    def log(self, message):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def start_downloads(self):
        urls = self.url_text.get("1.0", tk.END).strip().splitlines()
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            messagebox.showwarning("No URLs", "Please enter at least one YouTube URL.")
            return

        self.download_btn.config(state='disabled')
        threading.Thread(target=self.download_all, args=(urls,), daemon=True).start()

    def download_all(self, urls):
        for i, url in enumerate(urls, 1):
            self.log(f"Downloading {i}/{len(urls)}: {url}")
            result = self.download_youtube_as_mp3(url)
            if result:
                self.log(f"✅ Finished: {url}")
            else:
                self.log(f"❌ Failed: {url}")
        self.log("All downloads complete.")
        self.download_btn.config(state='normal')

    def download_youtube_as_mp3(self, youtube_url):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            command = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--postprocessor-args=-ac 2",  # ✅ FIXED
                "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s"),
                youtube_url
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                self.log(f"yt-dlp error:\n{result.stderr.strip()}")
                return False
            return True
        except Exception as e:
            self.log(f"Error: {e}")
            return False

    def check_clipboard_loop(self):
        try:
            clipboard_content = self.clipboard_get().strip()
            if clipboard_content != self.last_clipboard:
                self.last_clipboard = clipboard_content
                # Check if clipboard content matches YouTube URL pattern and not already in the box
                if self.youtube_url_pattern.search(clipboard_content):
                    current_text = self.url_text.get("1.0", tk.END)
                    if clipboard_content not in current_text:
                        # Append the new URL on a new line
                        if not current_text.strip():
                            self.url_text.insert(tk.END, clipboard_content)
                        else:
                            self.url_text.insert(tk.END, "\n" + clipboard_content)
                        self.log(f"Added URL from clipboard: {clipboard_content}")
        except tk.TclError:
            # Clipboard could be empty or unavailable, ignore silently
            pass

        # Check again after 1000ms (1 second)
        self.after(1000, self.check_clipboard_loop)


if __name__ == "__main__":
    app = YTDownloaderApp()
    app.mainloop()
