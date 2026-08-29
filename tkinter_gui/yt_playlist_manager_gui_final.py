#!/usr/bin/env python3
"""
yt_playlist_manager_gui.py

GUI wrapper for yt_playlist_audio_tools with:
- Table:
    Playlist | Last download | Last extract | Local videos | Playlist videos | Unavailable | URL
- Row highlight when local videos != downloadable playlist videos
- On startup, recomputes stats for all saved playlists and logs to app_startup.log
- For each playlist operation, logs to logs/<sanitized_playlist_title>.log
- Per-playlist excluded_ids: stored in config, auto-filled from failed downloads,
  and manually editable via GUI.
"""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from glob import glob
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor, as_completed

from yt_dlp import YoutubeDL
import yt_playlist_audio_tools as tools  # helper module


# ---------- LOGGING HELPERS ----------

# STARTUP_LOG will be set dynamically based on base_path from config
# Initially None until config is loaded
STARTUP_LOG = None


def get_startup_log_path(base_path: str) -> str:
    """Get the startup log path in the base download path."""
    logs_dir = get_logs_base_dir(base_path)
    return os.path.join(logs_dir, "app_startup.log")


def get_logs_base_dir(base_path: str) -> str:
    """Get the logs directory in the base download path."""
    logs_dir = os.path.join(base_path, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_playlist_log_path(base_path: str, playlist_title: str) -> str:
    """Get the log file path for a specific playlist."""
    logs_dir = get_logs_base_dir(base_path)
    safe_title = sanitize_for_filename(playlist_title)
    playlist_log_dir = os.path.join(logs_dir, safe_title)
    os.makedirs(playlist_log_dir, exist_ok=True)
    return os.path.join(playlist_log_dir, f"{safe_title}.log")

# Log rotation settings (can be overridden by config)
MAX_LOG_LINES = 5000  # Rotate after 5000 lines
MAX_LOG_SIZE_MB = 10  # Rotate after 10 MB


def _load_log_rotation_settings():
    """Load log rotation settings from config if available."""
    global MAX_LOG_LINES, MAX_LOG_SIZE_MB
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                MAX_LOG_LINES = config.get("max_log_lines", MAX_LOG_LINES)
                MAX_LOG_SIZE_MB = config.get("max_log_size_mb", MAX_LOG_SIZE_MB)
    except Exception:
        pass  # Use defaults if config can't be loaded


_load_log_rotation_settings()


def sanitize_for_filename(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_") or "playlist"


def _rotate_log_if_needed(log_path: str) -> None:
    """
    Rotate log file if it exceeds size or line limits.
    Renamed format: basename_YYYYMMDD_revision.log
    """
    if not os.path.exists(log_path):
        return
    
    # Check file size
    file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
    
    # Check line count
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
    except Exception:
        line_count = 0
    
    # Rotate if exceeds limits
    if file_size_mb > MAX_LOG_SIZE_MB or line_count > MAX_LOG_LINES:
        # Get file creation/modification time
        file_time = datetime.fromtimestamp(os.path.getmtime(log_path))
        date_str = file_time.strftime("%Y%m%d")
        
        # Get base name without extension
        base_dir = os.path.dirname(log_path)
        base_name = os.path.splitext(os.path.basename(log_path))[0]
        
        # Find next available revision number for today
        revision = 1
        while True:
            new_name = f"{base_name}_{date_str}_{revision:02d}.log"
            new_path = os.path.join(base_dir, new_name)
            if not os.path.exists(new_path):
                break
            revision += 1
        
        # Rename old log
        try:
            os.rename(log_path, new_path)
            print(f"Rotated log: {os.path.basename(log_path)} -> {os.path.basename(new_path)}")
        except Exception as e:
            print(f"Warning: Could not rotate log {log_path}: {e}")


def write_startup_log(message: str, base_path: str = None):
    """Write to startup log. If base_path not provided, tries to load from config."""
    global STARTUP_LOG
    
    try:
        # If base_path not provided, try to load from config
        if base_path is None:
            if STARTUP_LOG is None:
                # Try to get base_path from config
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        base_path = config.get("base_path")
                
                if base_path:
                    STARTUP_LOG = get_startup_log_path(base_path)
                else:
                    # Fallback to local logs if no config
                    local_log_dir = "logs"
                    os.makedirs(local_log_dir, exist_ok=True)
                    STARTUP_LOG = os.path.join(local_log_dir, "app_startup.log")
        else:
            STARTUP_LOG = get_startup_log_path(base_path)
        
        _rotate_log_if_needed(STARTUP_LOG)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(STARTUP_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}")
    except Exception as e:
        # Print to console if logging fails
        print(f"Warning: Could not write to startup log: {e}")


class TeeLogger:
    def __init__(self, q: queue.Queue, logfile_path: str):
        self.q = q
        self.logfile_path = logfile_path
        os.makedirs(os.path.dirname(self.logfile_path), exist_ok=True)
        # Rotate log before starting new operation
        _rotate_log_if_needed(self.logfile_path)
        # Keep file handle open for better performance
        # Use larger buffer (8KB) to reduce flush frequency
        self.file_handle = open(self.logfile_path, "a", encoding="utf-8", buffering=8192)
        self.write_count = 0
        self.flush_interval = 10  # Flush every 10 writes

    def write(self, s):
        if not s:
            return
        
        # Send to UI queue (non-blocking)
        try:
            self.q.put_nowait(s)
        except queue.Full:
            pass  # Drop message if queue full (prevents blocking)
        
        # Write to file (buffered, minimal blocking)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.file_handle.write(f"[{ts}] {s}")
            self.write_count += 1
            
            # Flush periodically instead of every write
            if self.write_count >= self.flush_interval:
                self.file_handle.flush()
                self.write_count = 0
        except Exception as e:
            # If write fails, try to reopen file
            try:
                self.file_handle.close()
                self.file_handle = open(self.logfile_path, "a", encoding="utf-8", buffering=8192)
                self.file_handle.write(f"[{ts}] {s}")
            except Exception:
                pass  # Silently fail to avoid blocking

    def flush(self):
        try:
            if self.file_handle and not self.file_handle.closed:
                self.file_handle.flush()
                self.write_count = 0
        except Exception:
            pass
    
    def close(self):
        try:
            if self.file_handle and not self.file_handle.closed:
                self.file_handle.flush()  # Ensure all data written
                self.file_handle.close()
        except Exception:
            pass


# ---------- CONFIG STORAGE ----------

CONFIG_FILE = "yt_playlist_gui_config.json"

default_config = {
    "base_path": tools.BASE_DOWNLOAD_PATH,
    "playlists": [],
}


def load_config():
    if not os.path.isfile(CONFIG_FILE):
        return default_config.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default_config.items():
            data.setdefault(k, v)
        for pl in data["playlists"]:
            pl.setdefault("last_download_ist", "")
            pl.setdefault("last_extract_ist", "")
            pl.setdefault("local_count", 0)
            pl.setdefault("playlist_count", 0)
            pl.setdefault("unavailable_count", 0)
            pl.setdefault("excluded_ids", [])
        return data
    except Exception:
        return default_config.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ---------- PLAYLIST STATS (LOCAL / AVAILABLE / UNAVAILABLE) ----------

def get_playlist_stats(base_path: str, title: str, url: str, excluded_ids: list[str], force_refresh: bool = False) -> tuple[int, int, int]:
    """
    Compute local_count, available_count, unavailable_count for a playlist.
    
    If force_refresh is False and playlist_info.json was created today,
    uses cached data instead of calling yt-dlp API.
    """
    safe_title = tools._sanitize_title(title)
    playlist_folder = os.path.join(base_path, safe_title)

    local_count = 0
    if os.path.isdir(playlist_folder):
        video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
        files = []
        for pat in video_exts:
            files.extend(glob(os.path.join(playlist_folder, pat)))
        local_count = len(files)

    available_count = 0
    unavailable_count = 0
    excluded_set = set(excluded_ids or [])

    try:
        # Try to use cached playlist info if fresh (created today)
        entries = tools._get_playlist_entries(url, playlist_folder, force_refresh=force_refresh)

        for e in entries:
            if tools.is_entry_unavailable(e, excluded_set):
                unavailable_count += 1
            else:
                available_count += 1
    except Exception as ex:
        write_startup_log(f"Error getting playlist stats for {url}: {ex}\n")
        available_count = 0
        unavailable_count = 0

    return local_count, available_count, unavailable_count


# ---------- EXCLUSIONS EDITOR DIALOG ----------

class ExclusionsEditorDialog(tk.Toplevel):
    """Dialog for managing excluded video IDs with titles."""
    
    def __init__(self, parent, playlist: dict, playlist_idx: int, config_data: dict, callback):
        super().__init__(parent)
        
        self.playlist = playlist
        self.playlist_idx = playlist_idx
        self.config_data = config_data
        self.callback = callback
        self.id_to_title = {}
        
        self.title(f"Edit Exclusions - {playlist.get('title', 'Playlist')}")
        self.geometry("800x600")
        self.transient(parent)
        
        # Load video titles
        self._load_video_titles()
        
        # Build UI
        self._build_ui()
        
        # Load current exclusions
        self._load_exclusions()
        
        # Make modal
        self.grab_set()
    
    def _load_video_titles(self):
        """Load video ID to title mapping from playlist_info.json."""
        base_path = self.config_data.get("base_path", "")
        playlist_title = self.playlist.get("title", "")
        safe_title = tools._sanitize_title(playlist_title)
        playlist_folder = os.path.join(base_path, safe_title)
        
        # Try new location first
        info_file = os.path.join(playlist_folder, "playlist_info_snapshot", "playlist_info.json")
        if not os.path.exists(info_file):
            info_file = os.path.join(playlist_folder, "playlist_info.json")
        
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    entries = info.get("entries") or []
                    for e in entries:
                        if e:
                            vid = e.get("id")
                            title = e.get("title")
                            if vid and title:
                                self.id_to_title[vid] = title
            except Exception as e:
                print(f"Error loading playlist info: {e}")
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Top frame with instructions
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Label(
            top_frame,
            text=f"Manage excluded videos for: {self.playlist.get('title', 'Playlist')}",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor=tk.W)
        
        ttk.Label(
            top_frame,
            text="Excluded videos will not be downloaded. Select videos and click 'Remove' to unexclude them.",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Middle frame with listbox and scrollbar
        middle_frame = ttk.Frame(self, padding=10)
        middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(middle_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scrollbar.set,
            font=("TkDefaultFont", 9)
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Right frame with buttons
        button_frame = ttk.Frame(middle_frame)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Remove Selected",
            command=self._remove_selected
        ).pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Add Video ID",
            command=self._add_video_id
        ).pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Clear All",
            command=self._clear_all
        ).pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(button_frame, text="Quick Actions:", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Copy Selected IDs",
            command=self._copy_selected_ids
        ).pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Open in YouTube",
            command=self._open_in_youtube
        ).pack(fill=tk.X)
        
        # Bottom frame with stats and action buttons
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.stats_label = ttk.Label(bottom_frame, text="", foreground="gray")
        self.stats_label.pack(side=tk.LEFT)
        
        ttk.Button(
            bottom_frame,
            text="Cancel",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            bottom_frame,
            text="Save",
            command=self._save_and_close
        ).pack(side=tk.RIGHT)
    
    def _load_exclusions(self):
        """Load current exclusions into listbox."""
        self.listbox.delete(0, tk.END)
        
        excluded_ids = self.playlist.get("excluded_ids", [])
        for vid in excluded_ids:
            title = self.id_to_title.get(vid, "Unknown Title")
            display_text = f"{title} [{vid}]"
            self.listbox.insert(tk.END, display_text)
        
        self._update_stats()
    
    def _update_stats(self):
        """Update the stats label."""
        count = self.listbox.size()
        self.stats_label.config(text=f"Excluded videos: {count}")
    
    def _remove_selected(self):
        """Remove selected items from exclusion list."""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select videos to remove from exclusions.")
            return
        
        # Remove in reverse order to maintain indices
        for idx in reversed(selected):
            self.listbox.delete(idx)
        
        self._update_stats()
    
    def _add_video_id(self):
        """Add a video ID to exclusions."""
        vid = simpledialog.askstring(
            "Add Video ID",
            "Enter video ID to exclude (11 characters):",
            parent=self
        )
        
        if not vid:
            return
        
        vid = vid.strip()
        
        # Validate video ID format
        if len(vid) != 11:
            messagebox.showerror("Invalid ID", "Video ID must be exactly 11 characters.")
            return
        
        # Check if already in list
        for i in range(self.listbox.size()):
            if f"[{vid}]" in self.listbox.get(i):
                messagebox.showinfo("Already Excluded", f"Video ID {vid} is already in the exclusion list.")
                return
        
        # Add to list
        title = self.id_to_title.get(vid, "Unknown Title")
        display_text = f"{title} [{vid}]"
        self.listbox.insert(tk.END, display_text)
        
        self._update_stats()
    
    def _clear_all(self):
        """Clear all exclusions."""
        if not messagebox.askyesno(
            "Clear All",
            "Remove all excluded videos? They will be available for download again.",
            parent=self
        ):
            return
        
        self.listbox.delete(0, tk.END)
        self._update_stats()
    
    def _copy_selected_ids(self):
        """Copy selected video IDs to clipboard."""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select videos to copy IDs.", parent=self)
            return
        
        ids = []
        for idx in selected:
            text = self.listbox.get(idx)
            # Extract ID from "[ID]" format
            if "[" in text and "]" in text:
                vid = text.split("[")[-1].rstrip("]")
                ids.append(vid)
        
        if ids:
            self.clipboard_clear()
            self.clipboard_append("\n".join(ids))
            messagebox.showinfo("Copied", f"Copied {len(ids)} video ID(s) to clipboard.", parent=self)
    
    def _open_in_youtube(self):
        """Open selected video in YouTube."""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a video to open.", parent=self)
            return
        
        if len(selected) > 1:
            messagebox.showwarning("Multiple Selection", "Please select only one video to open.", parent=self)
            return
        
        text = self.listbox.get(selected[0])
        # Extract ID from "[ID]" format
        if "[" in text and "]" in text:
            vid = text.split("[")[-1].rstrip("]")
            url = f"https://www.youtube.com/watch?v={vid}"
            
            import webbrowser
            webbrowser.open(url)
    
    def _save_and_close(self):
        """Save exclusions and close dialog."""
        # Extract video IDs from listbox
        excluded_ids = []
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            # Extract ID from "[ID]" format
            if "[" in text and "]" in text:
                vid = text.split("[")[-1].rstrip("]")
                excluded_ids.append(vid)
        
        # Update playlist config
        self.playlist["excluded_ids"] = sorted(set(excluded_ids))
        save_config(self.config_data)
        
        # Call callback to refresh stats
        if self.callback:
            self.callback(self.playlist_idx)
        
        self.destroy()


# ---------- MAIN APP ----------

class PlaylistManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Playlist Manager")
        self.geometry("1200x650")

        self.config_data = load_config()
        self.log_queue = queue.Queue()
        
        # Track multiple operations
        self.download_worker = None  # Only one download at a time
        self.extraction_workers = {}  # Multiple extractions: {playlist_title: worker_thread}
        self.is_downloading = False  # True if any download in progress
        self.downloading_playlist = None  # Title of playlist being downloaded
        
        self.total_items = 0
        self.current_item_index = 0
        self.cancel_requested = False

        # Initialize startup log with base_path from config
        base_path = self.config_data.get("base_path")
        write_startup_log("=== App startup ===\n", base_path)
        self._refresh_all_playlist_stats_from_disk()

        self._build_ui()
        self._refresh_playlist_table()
        self.after(100, self._poll_log_queue)

    # ---------- UI BUILD ----------

    def _build_ui(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(top_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        ttk.Label(left_frame, text="Base download path:").pack(anchor=tk.W)

        base_row = ttk.Frame(left_frame)
        base_row.pack(fill=tk.X, pady=(0, 6))

        self.base_path_var = tk.StringVar(value=self.config_data["base_path"])
        base_entry = ttk.Entry(base_row, textvariable=self.base_path_var, width=45)
        base_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(base_row, text="Browse...", command=self._choose_base_path).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        ttk.Button(left_frame, text="Save Base Path",
                   command=self._save_base_path).pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(left_frame, text="Playlists:").pack(anchor=tk.W)

        ttk.Button(left_frame, text="Add playlist",
                   command=self._add_playlist_dialog).pack(fill=tk.X, pady=(4, 2))

        ttk.Button(left_frame, text="Remove selected",
                   command=self._remove_selected_playlist).pack(fill=tk.X, pady=(0, 4))

        ttk.Button(left_frame, text="Edit exclusions for selected",
                   command=self._edit_exclusions_dialog).pack(fill=tk.X, pady=(0, 4))
        
        ttk.Button(left_frame, text="Refresh playlists (force)",
                   command=self._force_refresh_playlists).pack(fill=tk.X, pady=(0, 4))
        
        ttk.Button(left_frame, text="Fix folder structure for all",
                   command=self._fix_all_folder_structures).pack(fill=tk.X, pady=(0, 12))

        # Right: table
        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("title", "last_dl", "last_ex", "local", "plist", "unavail", "url")
        self.tree = ttk.Treeview(
            right_frame, columns=columns, show="headings", selectmode="browse"
        )

        self.tree.heading("title", text="Playlist")
        self.tree.heading("last_dl", text="Last download")
        self.tree.heading("last_ex", text="Last extract")
        self.tree.heading("local", text="Local videos")
        self.tree.heading("plist", text="Playlist videos")
        self.tree.heading("unavail", text="Unavailable")
        self.tree.heading("url", text="URL")

        self.tree.column("title", width=230, anchor=tk.W)
        self.tree.column("last_dl", width=140, anchor=tk.CENTER)
        self.tree.column("last_ex", width=140, anchor=tk.CENTER)
        self.tree.column("local", width=90, anchor=tk.E)
        self.tree.column("plist", width=100, anchor=tk.E)
        self.tree.column("unavail", width=100, anchor=tk.E)
        self.tree.column("url", width=320, anchor=tk.W)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(
            right_frame, orient="vertical", command=self.tree.yview
        )
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        style = ttk.Style(self)
        style.configure("Treeview", rowheight=22)
        self.tree.tag_configure("needs_update", background="#ffcccc")

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        action_frame = ttk.Frame(right_frame)
        action_frame.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))

        ttk.Button(action_frame, text="Run on selected playlist",
                   command=self._run_on_selected).pack(side=tk.LEFT)

        ttk.Button(action_frame, text="Stop current task",
                   command=self._request_cancel).pack(side=tk.LEFT, padx=(8, 0))

        # Bottom: log + progress
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))

        ttk.Label(bottom_frame, text="Log:").pack(anchor=tk.W)

        log_text_frame = ttk.Frame(bottom_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_text_frame, height=12, wrap="word", state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(log_text_frame, orient="vertical", command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=sb.set)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            bottom_frame, maximum=100.0, variable=self.progress_var
        )
        self.progress_bar.pack(fill=tk.X, pady=(4, 0))
        
        # Status label for active operations
        self.status_label = ttk.Label(bottom_frame, text="", foreground="blue")
        self.status_label.pack(fill=tk.X, pady=(2, 0))

    # ---------- CONFIG / PATHS ----------

    def _choose_base_path(self):
        path = filedialog.askdirectory(initialdir=self.base_path_var.get() or os.getcwd())
        if path:
            self.base_path_var.set(path)

    def _save_base_path(self):
        new_path = self.base_path_var.get().strip()
        if not new_path:
            messagebox.showerror("Error", "Base path cannot be empty.")
            return
        self.config_data["base_path"] = new_path
        save_config(self.config_data)
        tools.BASE_DOWNLOAD_PATH = new_path
        messagebox.showinfo("Saved", f"Base path set to:\n{new_path}")

    # ---------- TABLE ----------

    def _refresh_playlist_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for idx, pl in enumerate(self.config_data["playlists"]):
            title = pl.get("title", "")
            last_dl = pl.get("last_download_ist", "")
            last_ex = pl.get("last_extract_ist", "")
            local = pl.get("local_count", 0)
            plist = pl.get("playlist_count", 0)
            unavail = pl.get("unavailable_count", 0)
            url = pl.get("url", "")

            row_id = self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(title, last_dl, last_ex, local, plist, unavail, url),
            )
            if plist != 0 and local != plist:
                self.tree.item(row_id, tags=("needs_update",))

    # ---------- STARTUP STATS ----------

    def _process_single_playlist_startup(self, pl: dict, base_path: str, force_refresh: bool = False) -> dict:
        """
        Process a single playlist during startup (for parallel execution).
        
        If force_refresh is False, uses cached playlist_info.json if created today.
        If force_refresh is True, always fetches fresh data from yt-dlp API.
        """
        import threading
        
        thread_id = threading.current_thread().name
        url = pl.get("url", "")
        title = pl.get("title", "")
        
        if not url or not title:
            return pl
        
        log_messages = []
        
        # Ensure folder structure exists for existing playlists
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] Checking folder structure")
            playlist_folder, archive_file, audio_folder = tools._build_playlist_paths(title, create_folders=True)
            
            # Check if playlist_info.json exists in snapshot directory
            snapshot_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
            info_file = os.path.join(snapshot_dir, "playlist_info.json")
            
            if not os.path.exists(info_file):
                log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] Creating missing playlist_info.json")
                
                # Try to save playlist_info.json if we can fetch it
                try:
                    entries = tools._get_playlist_entries(url, playlist_folder, force_refresh=True)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ✓ Saved playlist_info.json with {len(entries)} entries")
                except Exception as e:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ⚠️  Could not save playlist_info.json: {e}")
            else:
                # Check if cache is fresh
                if not force_refresh and tools._is_playlist_info_fresh(playlist_folder):
                    log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ✓ Using cached playlist_info.json (created today)")
                else:
                    log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ✓ playlist_info.json exists")
                    
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ⚠️  Could not create folder structure: {e}")

        # Get stats
        excluded_ids = pl.get("excluded_ids", [])
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] Refreshing stats...")
        
        try:
            local_count, avail_count, unavail_count = get_playlist_stats(base_path, title, url, excluded_ids, force_refresh=force_refresh)
            pl["local_count"] = local_count
            pl["playlist_count"] = avail_count
            pl["unavailable_count"] = unavail_count
            timestamp = datetime.now().strftime("%H:%M:%S")
            cache_note = " (from cache)" if not force_refresh and tools._is_playlist_info_fresh(playlist_folder) else ""
            log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ✓ Stats{cache_note}: {local_count} local, {avail_count} available, {unavail_count} unavailable")
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_messages.append(f"[{timestamp}] [{thread_id}] [{title}] ⚠️  Error getting stats: {e}")
            pl["local_count"] = 0
            pl["playlist_count"] = 0
            pl["unavailable_count"] = 0

        if not pl.get("last_download_ist") or not pl.get("last_extract_ist"):
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pl.setdefault("last_download_ist", now_str)
            pl.setdefault("last_extract_ist", now_str)
        
        # Write all log messages for this playlist
        for msg in log_messages:
            write_startup_log(msg + "\n")
        
        return pl

    def _refresh_all_playlist_stats_from_disk(self, force_refresh: bool = False):
        """
        Refresh stats for all playlists.
        
        If force_refresh is False (default), uses cached playlist_info.json if created today.
        If force_refresh is True, always fetches fresh data from yt-dlp API.
        """
        base_path = self.config_data["base_path"]
        playlists = self.config_data["playlists"]
        
        if not playlists:
            return
        
        refresh_type = "force refresh" if force_refresh else "refresh (using cache when available)"
        write_startup_log(f"Starting parallel {refresh_type} of {len(playlists)} playlists...\n")
        start_time = datetime.now()
        
        # Use ThreadPoolExecutor for parallel processing
        # Limit to 5 concurrent threads to avoid overwhelming YouTube API
        max_workers = min(5, len(playlists))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all playlist processing tasks
            future_to_idx = {
                executor.submit(self._process_single_playlist_startup, pl, base_path, force_refresh): idx
                for idx, pl in enumerate(playlists)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    updated_pl = future.result()
                    self.config_data["playlists"][idx] = updated_pl
                except Exception as e:
                    write_startup_log(f"⚠️  Error processing playlist {playlists[idx].get('title', 'Unknown')}: {e}\n")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        write_startup_log(f"\n✓ Completed {refresh_type} of {len(playlists)} playlists in {duration:.1f} seconds\n")
        
        save_config(self.config_data)

    # ---------- PLAYLIST MANAGEMENT ----------

    def _add_playlist_dialog(self):
        url = simpledialog.askstring("Add playlist", "Enter YouTube playlist URL:")
        if not url:
            return

        self._append_log(f"\nFetching title for playlist:\n{url}\n")
        try:
            title = tools._get_playlist_info_title(url)
        except Exception as e:
            self._append_log(f"Could not fetch title automatically ({e}), using URL as title.\n")
            title = url

        base_path = self.config_data["base_path"]
        
        # Create playlist folder immediately
        try:
            playlist_folder, archive_file, audio_folder = tools._build_playlist_paths(title, create_folders=True)
            self._append_log(f"Created playlist folder: {playlist_folder}\n")
            
            # Save playlist_info.json immediately
            try:
                entries = tools._get_playlist_entries(url, playlist_folder)
                self._append_log(f"Saved playlist_info.json with {len(entries)} entries\n")
            except Exception as e:
                self._append_log(f"Warning: Could not save playlist_info.json: {e}\n")
        except Exception as e:
            self._append_log(f"Warning: Could not create playlist folder: {e}\n")
        
        local_count, avail_count, unavail_count = get_playlist_stats(base_path, title, url, [])

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_pl = {
            "url": url,
            "title": title,
            "last_download_ist": now_str,
            "last_extract_ist": now_str,
            "local_count": local_count,
            "playlist_count": avail_count,
            "unavailable_count": unavail_count,
            "excluded_ids": [],
        }

        self.config_data["playlists"].append(new_pl)
        save_config(self.config_data)
        self._refresh_playlist_table()
        self._append_log(
            f"Added playlist: {title}\n"
            f"Local videos: {local_count}\n"
            f"Downloadable in playlist: {avail_count}\n"
            f"Unavailable in playlist: {unavail_count}\n"
        )

    def _remove_selected_playlist(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a playlist to remove.")
            return
        idx = int(sel[0])
        pl = self.config_data["playlists"][idx]
        if not messagebox.askyesno("Confirm", f"Remove playlist:\n{pl.get('title')} ?"):
            return
        del self.config_data["playlists"][idx]
        save_config(self.config_data)
        self._refresh_playlist_table()
        self._append_log(f"Removed playlist: {pl.get('title')}\n")

    def _edit_exclusions_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a playlist.")
            return
        idx = int(sel[0])
        pl = self.config_data["playlists"][idx]
        
        # Create exclusions editor window
        ExclusionsEditorDialog(self, pl, idx, self.config_data, self._on_exclusions_updated)
    
    def _on_exclusions_updated(self, playlist_idx: int):
        """Callback when exclusions are updated."""
        pl = self.config_data["playlists"][playlist_idx]
        base_path = self.config_data["base_path"]
        url = pl.get("url", "")
        title = pl.get("title", "")
        
        # Refresh stats
        local_count, avail_count, unavail_count = get_playlist_stats(
            base_path, title, url, pl["excluded_ids"]
        )
        pl["local_count"] = local_count
        pl["playlist_count"] = avail_count
        pl["unavailable_count"] = unavail_count
        
        save_config(self.config_data)
        self._refresh_playlist_table()
        self._append_log(
            f"\nUpdated exclusions for {title}.\n"
            f"Excluded: {len(pl['excluded_ids'])} video(s)\n"
        )

    def _force_refresh_playlists(self):
        """Force refresh all playlist stats from yt-dlp API (ignore cache)."""
        if not messagebox.askyesno(
            "Force Refresh Playlists",
            "This will fetch fresh playlist data from YouTube for all playlists.\n\n"
            "This may take a few minutes depending on the number of playlists.\n\n"
            "Continue?"
        ):
            return
        
        self._append_log("\n=== Force refreshing all playlists ===\n")
        self._append_log("Fetching fresh data from YouTube API...\n")
        
        # Run refresh in background thread to avoid blocking UI
        def refresh_worker():
            try:
                self._refresh_all_playlist_stats_from_disk(force_refresh=True)
                self.log_queue.put("\n✓ Force refresh completed!\n")
            except Exception as e:
                self.log_queue.put(f"\n❌ Error during refresh: {e}\n")
            finally:
                # Refresh table on main thread
                self.after(100, self._refresh_playlist_table)
        
        worker = threading.Thread(target=refresh_worker, daemon=True)
        worker.start()

    def _fix_all_folder_structures(self):
        """Manually fix folder structures for all playlists."""
        if not messagebox.askyesno(
            "Fix Folder Structures",
            "This will create missing folders and playlist_info_snapshot directories for all playlists.\n\n"
            "Continue?"
        ):
            return
        
        self._append_log("\n=== Fixing folder structures for all playlists ===\n")
        base_path = self.config_data["base_path"]
        fixed_count = 0
        
        for pl in self.config_data["playlists"]:
            url = pl.get("url", "")
            title = pl.get("title", "")
            if not url or not title:
                continue
            
            try:
                self._append_log(f"\nChecking: {title}\n")
                
                # Create folder structure
                playlist_folder, archive_file, audio_folder = tools._build_playlist_paths(title, create_folders=True)
                
                # Check if playlist_info_snapshot exists
                snapshot_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
                info_file = os.path.join(snapshot_dir, "playlist_info.json")
                
                if not os.path.exists(info_file):
                    self._append_log(f"  Creating playlist_info_snapshot and fetching playlist info...\n")
                    try:
                        entries = tools._get_playlist_entries(url, playlist_folder)
                        self._append_log(f"  ✓ Saved playlist_info.json with {len(entries)} entries\n")
                        fixed_count += 1
                    except Exception as e:
                        self._append_log(f"  ⚠️  Could not fetch playlist info: {e}\n")
                else:
                    self._append_log(f"  ✓ Folder structure already complete\n")
                    
            except Exception as e:
                self._append_log(f"  ❌ Error: {e}\n")
        
        self._append_log(f"\n=== Fixed {fixed_count} playlist(s) ===\n")
        messagebox.showinfo("Complete", f"Fixed folder structures for {fixed_count} playlist(s).")

    # ---------- RUN MODES ----------

    def _on_tree_double_click(self, event):
        self._run_on_selected()

    def _run_on_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a playlist.")
            return
        idx = int(sel[0])
        pl = self.config_data["playlists"][idx]
        url = pl.get("url")
        title = pl.get("title")

        mode = self._ask_mode(title)
        if not mode:
            return
        
        # Check operation constraints
        is_download_mode = mode == "download_extract"
        is_extraction_mode = mode == "extract_only"
        
        if is_download_mode:
            # Only one download at a time
            if self.is_downloading:
                messagebox.showwarning(
                    "Download in Progress",
                    f"A download is already running for '{self.downloading_playlist}'.\n\n"
                    "Please wait for it to complete or cancel it first."
                )
                return
        
        if is_extraction_mode:
            # Can't extract from playlist being downloaded
            if self.is_downloading and self.downloading_playlist == title:
                messagebox.showwarning(
                    "Download in Progress",
                    f"Cannot extract audio while downloading '{title}'.\n\n"
                    "Please wait for download to complete first."
                )
                return
            
            # Check if already extracting this playlist
            if title in self.extraction_workers:
                messagebox.showwarning(
                    "Extraction in Progress",
                    f"Audio extraction is already running for '{title}'."
                )
                return

        self.progress_var.set(0.0)
        self.total_items = 0
        self.current_item_index = 0
        self._clear_log()
        self._append_log(
            f"Selected playlist: {title}\nURL: {url}\nMode: {mode}\n\n"
        )

        # Create and track worker based on operation type
        worker = threading.Thread(
            target=self._run_mode_worker,
            args=(idx, mode, url, title),
            daemon=True,
        )
        
        if is_download_mode:
            self.download_worker = worker
            self.is_downloading = True
            self.downloading_playlist = title
            self._append_log(f"🔽 Download started for '{title}'\n")
        else:  # extraction mode
            self.extraction_workers[title] = worker
            self._append_log(f"🎵 Audio extraction started for '{title}'\n")
        
        worker.start()

    def _ask_mode(self, playlist_title: str) -> str | None:
        dlg = tk.Toplevel(self)
        dlg.title("Select mode")
        dlg.transient(self)
        dlg.grab_set()

        choice = tk.StringVar(value="")

        # Check if batch is in progress
        base_path = self.config_data["base_path"]
        safe_title = tools._sanitize_title(playlist_title)
        playlist_folder = os.path.join(base_path, safe_title)
        batch_progress_file = os.path.join(playlist_folder, "batch_progress.json")
        
        has_batch_progress = False
        batch_info = ""
        
        if os.path.exists(batch_progress_file):
            try:
                with open(batch_progress_file, "r", encoding="utf-8") as f:
                    progress = json.load(f)
                    if not progress.get("completed", False) and progress.get("pending_video_ids"):
                        has_batch_progress = True
                        remaining = len(progress["pending_video_ids"])
                        total = progress.get("total_videos", 0)
                        downloaded = progress.get("downloaded_count", 0)
                        batch_info = f"\n⚠️ Batch in progress: {downloaded}/{total} downloaded, {remaining} remaining"
            except Exception:
                pass

        label_text = "Choose what to do for this playlist:"
        if batch_info:
            label_text += batch_info
        
        ttk.Label(dlg, text=label_text, wraplength=400).pack(
            padx=12, pady=(12, 6)
        )

        def set_choice(val):
            choice.set(val)
            dlg.destroy()

        # Single unified download button
        download_text = "1 - Download Videos + Extract Audio"
        if has_batch_progress:
            download_text += " (Auto-resume batch)"
        
        ttk.Button(
            dlg,
            text=download_text,
            command=lambda: set_choice("download_extract"),
        ).pack(fill=tk.X, padx=12, pady=4)

        ttk.Button(
            dlg,
            text="2 - Extract audio only (already downloaded)",
            command=lambda: set_choice("extract_only"),
        ).pack(fill=tk.X, padx=12, pady=(0, 12))

        dlg.wait_window()
        val = choice.get()
        return val or None

    def _request_cancel(self):
        # Check if any operations are running
        has_download = self.is_downloading
        has_extractions = len(self.extraction_workers) > 0
        
        if not has_download and not has_extractions:
            messagebox.showinfo("No task", "No task is currently running.")
            return
        
        # Build cancellation message
        operations = []
        if has_download:
            operations.append(f"Download: '{self.downloading_playlist}'")
        if has_extractions:
            for title in self.extraction_workers.keys():
                operations.append(f"Extraction: '{title}'")
        
        msg = "Cancel the following operations?\n\n" + "\n".join(operations)
        
        if not messagebox.askyesno("Cancel Operations", msg):
            return
        
        self.cancel_requested = True
        self._append_log("\n⚠️ Cancellation requested for all operations. Waiting for current steps to finish...\n")

    def _run_mode_worker(self, index: int, mode: str, url: str, title: str):
        import sys

        base_path = self.config_data["base_path"]
        playlist_log = get_playlist_log_path(base_path, title)

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        qlog = TeeLogger(self.log_queue, playlist_log)
        sys.stdout = qlog
        sys.stderr = qlog

        tools.BASE_DOWNLOAD_PATH = self.config_data["base_path"]

        runstate = SimpleNamespace(cancelled=False)

        def progress_cb(total, current_index):
            self.total_items = total
            self.current_item_index = current_index
            if self.cancel_requested or runstate.cancelled:
                raise KeyboardInterrupt("User requested cancellation")

        tools.GLOBAL_PROGRESS_CALLBACK = progress_cb
        tools.GLOBAL_RUNSTATE = runstate

        self.cancel_requested = False
        failed_ids = set()

        try:
            # Get excluded_ids from playlist config
            playlist_cfg = self._get_playlist_config(url)
            excluded_ids = set(playlist_cfg.get("excluded_ids", [])) if playlist_cfg else set()
            
            if mode == "download_extract":
                # Smart download: automatically handles batch resume/new batch/small updates
                failed_ids = tools.download_playlist_with_video_and_audio(url, as_mp3=True, excluded_ids=excluded_ids)
                
                # Check if cancelled before continuing
                if not runstate.cancelled and not self.cancel_requested:
                    self._merge_failed_ids_into_playlist(index, failed_ids)
                    self._update_playlist_stats_from_disk(index, url, title, updated_download=True)
                else:
                    print("\n❌ Download cancelled by user.\n")
                    
            elif mode == "extract_only":
                tools.extract_audio_for_existing_playlist(title)
                
                # Check if cancelled before updating stats
                if not runstate.cancelled and not self.cancel_requested:
                    self._update_playlist_stats_from_disk(index, url, title, updated_extract=True)
                else:
                    print("\n❌ Extraction cancelled by user.\n")
            else:
                print(f"Unknown mode: {mode}")
                
        except KeyboardInterrupt as e:
            print(f"\n❌ Task cancelled: {e}\n")
        except Exception as e:
            print(f"\n❌ ERROR in worker: {e}\n")
        finally:
            # Close the TeeLogger file handle
            qlog.close()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            # Clean up worker tracking based on operation type
            is_download_mode = mode == "download_extract"
            
            if is_download_mode:
                self.is_downloading = False
                self.downloading_playlist = None
                self.download_worker = None
                self.log_queue.put(f"\n✓ Download task ended for '{title}'.\n")
            else:  # extraction mode
                if title in self.extraction_workers:
                    del self.extraction_workers[title]
                self.log_queue.put(f"\n✓ Extraction task ended for '{title}'.\n")
            
            tools.GLOBAL_RUNSTATE = None
            self.progress_var.set(100.0)
            self._refresh_playlist_table()

    def _merge_failed_ids_into_playlist(self, index: int, failed_ids: set[str]):
        if not failed_ids:
            print(f"DEBUG: No failed IDs to merge")
            return
        pl = self.config_data["playlists"][index]
        existing = set(pl.get("excluded_ids", []))
        print(f"DEBUG: Existing excluded_ids: {existing}")
        print(f"DEBUG: New failed_ids: {failed_ids}")
        new_set = sorted(existing.union(failed_ids))
        print(f"DEBUG: Final excluded_ids: {new_set}")
        pl["excluded_ids"] = new_set
        save_config(self.config_data)
        self._append_log(
            f"\nMarked {len(failed_ids)} IDs as unavailable for this playlist:\n"
            + ", ".join(sorted(failed_ids)) + "\n"
        )

    # ---------- STATS UPDATE AFTER RUN ----------

    def _update_playlist_stats_from_disk(
        self,
        index: int,
        url: str,
        title: str,
        updated_download: bool = False,
        updated_extract: bool = False,
    ):
        base_path = self.config_data["base_path"]
        pl = self.config_data["playlists"][index]
        excluded_ids = pl.get("excluded_ids", [])
        local_count, avail_count, unavail_count = get_playlist_stats(base_path, title, url, excluded_ids)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        pl["local_count"] = local_count
        pl["playlist_count"] = avail_count
        pl["unavailable_count"] = unavail_count

        if updated_download:
            pl["last_download_ist"] = now_str
        if updated_extract:
            pl["last_extract_ist"] = now_str

        save_config(self.config_data)

    # ---------- LOG + PROGRESS LOOP ----------

    def _append_log(self, text: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_status_label(self):
        """Update status label to show active operations."""
        status_parts = []
        
        if self.is_downloading:
            status_parts.append(f"🔽 Downloading: {self.downloading_playlist}")
        
        if self.extraction_workers:
            extraction_list = ", ".join(self.extraction_workers.keys())
            status_parts.append(f"🎵 Extracting: {extraction_list}")
        
        if status_parts:
            self.status_label.config(text=" | ".join(status_parts))
        else:
            self.status_label.config(text="")
    
    def _poll_log_queue(self):
        # Process log messages (limit to prevent UI blocking)
        processed = 0
        max_messages_per_poll = 50  # Limit messages processed per poll
        
        try:
            while processed < max_messages_per_poll:
                s = self.log_queue.get_nowait()
                self._append_log(s)
                processed += 1
        except queue.Empty:
            pass

        # Update progress bar
        if self.total_items > 0:
            pct = min(100.0, max(0.0, 100.0 * self.current_item_index / self.total_items))
            self.progress_var.set(pct)

        # Update status label
        self._update_status_label()

        # Handle cancellation
        if getattr(self, "cancel_requested", False):
            rs = getattr(tools, "GLOBAL_RUNSTATE", None)
            if rs is not None:
                rs.cancelled = True

        # Force UI update to prevent "Not Responding"
        self.update_idletasks()
        
        # Schedule next poll (50ms for better responsiveness)
        self.after(50, self._poll_log_queue)

    def _get_playlist_config(self, url: str) -> dict | None:
        """Get playlist config from config_data by URL."""
        for playlist in self.config_data.get("playlists", []):
            if playlist.get("url") == url:
                return playlist
        return None


if __name__ == "__main__":
    #python yt_playlist_manager_gui_final.py
    app = PlaylistManagerApp()
    app.mainloop()
