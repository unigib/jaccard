"""Download a small, selected range of Project Gutenberg plain-text books."""

from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable


APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = APP_DIR / "corpus"
LOGO_PATH = APP_DIR / "logo.png"
MAX_IDS_PER_RUN = 1000
REQUEST_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "GibraltarJaccardDemo/1.0 (educational corpus downloader)"
BOOK_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"


@dataclass(frozen=True)
class DownloadSummary:
    downloaded: int
    skipped: int
    missing: int
    errors: tuple[str, ...]
    cancelled: bool


def parse_id_range(start_text: str, end_text: str) -> tuple[int, int]:
    """Validate a positive, bounded inclusive Gutenberg ID range."""
    try:
        start_id = int(start_text)
        end_id = int(end_text)
    except ValueError as error:
        raise ValueError("Enter whole numbers for both Gutenberg IDs.") from error
    if start_id < 1 or end_id < 1:
        raise ValueError("Gutenberg IDs must be positive numbers.")
    if end_id < start_id:
        raise ValueError("The ending ID must be the same as or greater than the starting ID.")
    if end_id - start_id + 1 > MAX_IDS_PER_RUN:
        raise ValueError(f"Limit each run to {MAX_IDS_PER_RUN} IDs or fewer.")
    return start_id, end_id


def download_id_range(
    start_id: int,
    end_id: int,
    output_dir: Path,
    *,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[int, int, int, str], None] | None = None,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> DownloadSummary:
    """Download available plain-text books, one ID at a time."""
    parse_id_range(str(start_id), str(end_id))
    if request_delay < 0:
        raise ValueError("Request delay cannot be negative.")
    stop_event = cancel_event or threading.Event()
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    missing = 0
    errors: list[str] = []
    ids = range(start_id, end_id + 1)

    for position, book_id in enumerate(ids, start=1):
        if stop_event.is_set():
            break
        destination = output_dir / f"pg{book_id}.txt"
        if destination.exists():
            skipped += 1
            result = "already exists — skipped"
        else:
            request = urllib.request.Request(
                BOOK_URL.format(book_id=book_id),
                headers={"User-Agent": USER_AGENT},
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=REQUEST_TIMEOUT_SECONDS
                ) as response:
                    content = response.read()
                text = content.decode("utf-8-sig")
                if "<html" in text[:500].casefold():
                    raise ValueError("The server returned a web page, not plain text.")
                if not text.strip():
                    raise ValueError("The downloaded text file was empty.")
                destination.write_text(text, encoding="utf-8")
                downloaded += 1
                result = "downloaded"
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    missing += 1
                    result = "not found"
                else:
                    message = f"ID {book_id}: HTTP {error.code}"
                    errors.append(message)
                    result = f"error — HTTP {error.code}"
            except (OSError, UnicodeError, ValueError) as error:
                message = f"ID {book_id}: {error}"
                errors.append(message)
                result = f"error — {error}"

        if on_progress is not None:
            on_progress(position, end_id - start_id + 1, book_id, result)

        if position < end_id - start_id + 1 and not stop_event.is_set():
            if stop_event.wait(request_delay):
                break

    return DownloadSummary(
        downloaded=downloaded,
        skipped=skipped,
        missing=missing,
        errors=tuple(errors),
        cancelled=stop_event.is_set(),
    )


class GutenbergDownloader(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("University of Gibraltar | Gutenberg Corpus Downloader")
        self.geometry("760x650")
        self.minsize(650, 540)
        self.configure(bg="#f1f5f9")

        self.start_id = tk.StringVar(value="16328")
        self.end_id = tk.StringVar(value="16328")
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.status_text = tk.StringVar(value="Ready — choose a Gutenberg ID range.")
        self._events: queue.Queue[tuple] = queue.Queue()
        self._cancel_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._build_ui()
        self.after(100, self._process_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        header = tk.Frame(
            self,
            bg="#ffffff",
            padx=22,
            pady=12,
            highlightbackground="#e2e8f0",
            highlightthickness=1,
        )
        header.pack(fill="x")
        if LOGO_PATH.exists():
            self.logo_image = tk.PhotoImage(master=self, file=str(LOGO_PATH)).subsample(2, 2)
            tk.Label(header, image=self.logo_image, bg="#ffffff").pack(
                side="left", padx=(0, 18)
            )
        heading = tk.Frame(header, bg="#ffffff")
        heading.pack(side="left", fill="x", expand=True)
        tk.Label(
            heading,
            text="UNIVERSITY OF GIBRALTAR",
            font=("Segoe UI", 10, "bold"),
            fg="#a6192e",
            bg="#ffffff",
        ).pack(anchor="w")
        tk.Label(
            heading,
            text="Project Gutenberg Corpus Downloader",
            font=("Segoe UI", 17, "bold"),
            fg="#1e293b",
            bg="#ffffff",
        ).pack(anchor="w", pady=(3, 0))

        body = ttk.Frame(self, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text=(
                "Download public-domain plain-text books by Gutenberg ID. "
                "For example, ID 16328 uses "
                "https://www.gutenberg.org/cache/epub/16328/pg16328.txt"
            ),
            wraplength=700,
        ).pack(anchor="w", pady=(0, 15))

        ids_frame = ttk.LabelFrame(body, text="Inclusive ID range", padding=12)
        ids_frame.pack(fill="x")
        ttk.Label(ids_frame, text="Start ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(ids_frame, textvariable=self.start_id, width=18).grid(
            row=0, column=1, padx=(8, 24), sticky="w"
        )
        ttk.Label(ids_frame, text="End ID").grid(row=0, column=2, sticky="w")
        ttk.Entry(ids_frame, textvariable=self.end_id, width=18).grid(
            row=0, column=3, padx=(8, 0), sticky="w"
        )
        ttk.Label(
            ids_frame,
            text=f"Maximum {MAX_IDS_PER_RUN} IDs per run; unavailable IDs are skipped.",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))

        folder_frame = ttk.LabelFrame(body, text="Save downloaded text files to", padding=12)
        folder_frame.pack(fill="x", pady=(14, 0))
        ttk.Entry(folder_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(folder_frame, text="Browse…", command=self._choose_folder).pack(
            side="left", padx=(8, 0)
        )

        controls = ttk.Frame(body, padding=(0, 14, 0, 10))
        controls.pack(fill="x")
        self.start_button = ttk.Button(
            controls,
            text="Download range",
            command=self._start_download,
            style="Accent.TButton",
        )
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(
            controls, text="Cancel", command=self._cancel_download, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            controls, text="One request per second; existing files are preserved."
        ).pack(side="left", padx=(14, 0))

        self.progress = ttk.Progressbar(body, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 7))
        ttk.Label(body, textvariable=self.status_text).pack(anchor="w", pady=(0, 8))

        log_frame = ttk.LabelFrame(body, text="Download activity", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose corpus folder", initialdir=self.output_dir.get()
        )
        if selected:
            self.output_dir.set(selected)

    def _start_download(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        try:
            start_id, end_id = parse_id_range(
                self.start_id.get().strip(), self.end_id.get().strip()
            )
            destination = Path(self.output_dir.get()).expanduser()
            if not destination.is_dir() and destination.exists():
                raise ValueError("The selected output path is not a folder.")
        except (OSError, ValueError) as error:
            messagebox.showwarning("Check download settings", str(error), parent=self)
            return

        self._cancel_event = threading.Event()
        self.progress.configure(maximum=end_id - start_id + 1, value=0)
        self._append_log(f"Starting IDs {start_id}–{end_id} in {destination}")
        self.status_text.set("Downloading…")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._worker = threading.Thread(
            target=self._download_worker,
            args=(start_id, end_id, destination, self._cancel_event),
            daemon=True,
        )
        self._worker.start()

    def _download_worker(
        self,
        start_id: int,
        end_id: int,
        destination: Path,
        cancel_event: threading.Event,
    ) -> None:
        try:
            summary = download_id_range(
                start_id,
                end_id,
                destination,
                cancel_event=cancel_event,
                on_progress=lambda position, total, book_id, result: self._events.put(
                    ("progress", position, total, book_id, result)
                ),
            )
        except (OSError, ValueError) as error:
            self._events.put(("fatal", str(error)))
        else:
            self._events.put(("finished", summary))

    def _cancel_download(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.status_text.set("Cancelling after the current request…")
            self.cancel_button.configure(state="disabled")

    def _process_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                _, position, total, book_id, result = event
                self.progress.configure(value=position)
                self.status_text.set(f"Processed {position} of {total} IDs.")
                self._append_log(f"ID {book_id}: {result}")
            elif event[0] == "finished":
                summary: DownloadSummary = event[1]
                self.start_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")
                state = "Cancelled" if summary.cancelled else "Finished"
                self.status_text.set(
                    f"{state}: {summary.downloaded} downloaded, "
                    f"{summary.skipped} already existed, {summary.missing} not found, "
                    f"{len(summary.errors)} errors."
                )
                if summary.errors:
                    self._append_log("Errors:\n" + "\n".join(summary.errors))
            elif event[0] == "fatal":
                self.start_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")
                self.status_text.set("Download stopped because of an error.")
                messagebox.showerror("Download failed", event[1], parent=self)
        self.after(100, self._process_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    GutenbergDownloader().mainloop()
