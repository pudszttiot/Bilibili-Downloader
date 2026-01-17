#!/usr/bin/env python3
"""

BiliBili Video Downloader (v1.0.4)
--------------------------

        pudszTTIOT

--------------------------

"""

from __future__ import annotations
import os
import sys
import shutil
import math
import time
import re
from pathlib import Path

# ---- Colors (Termux-safe ANSI) ----
CSI = "\x1b["
RESET = CSI + "0m"
FG_RED = CSI + "31m"
FG_GREEN = CSI + "32m"
FG_YELLOW = CSI + "33m"
FG_BLUE = CSI + "34m"
FG_MAGENTA = CSI + "35m"
FG_CYAN = CSI + "36m"

def cprint(msg: str, color: str = RESET, end: str = "\n"):
    sys.stdout.write(f"{color}{msg}{RESET}{end}")
    sys.stdout.flush()

# ----- Ensure yt-dlp available -----
try:
    import yt_dlp
except Exception:
    cprint("[!] yt-dlp Python module not found.", FG_RED)
    cprint("    Install/upgrade with: pip install -U 'yt-dlp[default]'", FG_YELLOW)
    sys.exit(1)

# ----- Helpers -----
def human_size(num_bytes):
    if num_bytes is None:
        return "N/A"
    num = float(num_bytes)
    for unit in ['B','KB','MB','GB','TB','PB']:
        if num < 1024:
            return f"{num:.2f}{unit}"
        num /= 1024.0
    return f"{num:.2f}EB"

def choose_download_dir():
    home = Path.home()
    candidates = [
        home / "storage" / "downloads",
        home / "storage" / "shared",
        home / "downloads",
        home
    ]
    for p in candidates:
        if p.exists() and os.access(p, os.W_OK):
            return str(p)
    # fallback to cwd
    return os.getcwd()

def safe_filename(name: str) -> str:
    # Make a filesystem-safe filename (reasonable for Android)
    name = name.strip()
    # replace problematic characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # collapse whitespace
    name = re.sub(r'\s+', ' ', name)
    return name

def prompt_with_default(prompt: str, default: str = "") -> str:
    if default:
        return input(f"{FG_YELLOW}{prompt} [{default}]: {RESET}").strip() or default
    else:
        return input(f"{FG_YELLOW}{prompt}: {RESET}").strip()

# ----- Automatic cookiefile detection -----
def auto_detect_cookiefile() -> str | None:
    possible_names = ["cookies.txt", "bili_cookies.txt", "cookies2.txt", "bilibili_cookies.txt"]
    search_dirs = [
        Path.home(),
        Path.home() / "storage" / "downloads",
        Path.home() / "storage" / "shared",
        Path.home() / "Download",
        Path("/sdcard/Download"),
        Path("/sdcard"),
    ]
    found = []
    for d in search_dirs:
        try:
            for name in possible_names:
                candidate = d / name
                if candidate.exists() and candidate.is_file():
                    found.append(str(candidate))
        except Exception:
            continue
    if not found:
        return None
    # Prefer the one in storage/downloads if present
    for f in found:
        if "/storage" in f or "/sdcard" in f:
            cprint(f"[+] Auto-detected cookiefile: {f}", FG_CYAN)
            return f
    cprint(f"[+] Auto-detected cookiefile: {found[0]}", FG_CYAN)
    return found[0]

# ----- Format list printing -----
def print_format_list(formats):
    cprint("\nAvailable formats (top entries shown):", FG_BLUE)
    filtered = [f for f in formats if 'format_id' in f]
    sorted_f = sorted(filtered, key=lambda x: (x.get('height') or 0, x.get('filesize') or 0), reverse=True)
    header = f"{'Idx':>4} {'format_id':>12} {'note':>12} {'res':>9} {'fps':>5} {'size':>10} {'type':>10}"
    cprint(header, FG_MAGENTA)
    for i, f in enumerate(sorted_f[:30], start=1):
        fid = f.get('format_id') or ''
        note = f.get('format_note') or ''
        res = f"{f.get('width') or '?'}x{f.get('height') or '?'}"
        fps = str(f.get('fps') or '')
        size = human_size(f.get('filesize') or f.get('filesize_approx'))
        typ = 'video+audio' if f.get('vcodec') != 'none' and f.get('acodec') != 'none' else ('video' if f.get('vcodec') != 'none' else 'audio')
        line = f"{i:4d} {fid:>12} {note:>12} {res:>9} {fps:>5} {size:>10} {typ:>10}"
        cprint(line)
    cprint("\nIndex 0 = automatic BEST (bestvideo+bestaudio/best)", FG_BLUE)

# ----- Progress hook for yt-dlp -----
def make_progress_hook():
    last_print = {'t': 0}
    def hook(d):
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            pct = (downloaded / total * 100) if total else 0.0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            now = time.time()
            # throttle updates to ~5 per second
            if now - last_print['t'] > 0.18:
                last_print['t'] = now
                sys.stdout.write(f"\r{FG_GREEN}Downloading: {pct:5.1f}% {human_size(downloaded)}/{human_size(total)}  ETA:{eta}s  {human_size(speed)}/s{RESET}")
                sys.stdout.flush()
        elif status == 'finished':
            cprint("\n[+] Download finished, post-processing (if any) ...", FG_GREEN)
        elif status == 'error':
            cprint("\n[!] Error during download: " + str(d), FG_RED)
    return hook

# ----- Main flow -----
def main():
    cprint("=== BiliBili Video Downloader ===", FG_CYAN)
    # Optional command-line URL(s)
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        # interactive single or multiple
        mode = input(f"{FG_YELLOW}Paste multiple URLs? (y/N): {RESET}").strip().lower()
        if mode == 'y':
            cprint("Paste URLs one per line. Enter an empty line to finish:", FG_BLUE)
            lines = []
            while True:
                ln = input("> ").strip()
                if not ln:
                    break
                lines.append(ln)
            urls = lines
        else:
            u = prompt_with_default("Enter BiliBili video URL", "")
            if not u:
                cprint("[!] No URL provided. Exiting.", FG_RED)
                return
            urls = [u]

    download_dir = choose_download_dir()
    cprint(f"[i] Download directory: {download_dir}", FG_CYAN)

    # Cookie auto-detect
    cookiefile = auto_detect_cookiefile()
    if cookiefile:
        use_cookie = input(f"{FG_YELLOW}Use this cookiefile? (Y/n): {RESET}").strip().lower()
        if use_cookie == 'n':
            cookiefile = None
    else:
        manual = input(f"{FG_YELLOW}No cookiefile auto-detected. Do you want to provide a cookies.txt path? (y/N): {RESET}").strip().lower()
        if manual == 'y':
            path_in = input("Enter path to cookies.txt: ").strip()
            path_in = os.path.expanduser(path_in)
            if os.path.isfile(path_in):
                cookiefile = path_in
                cprint(f"[+] Using cookiefile: {cookiefile}", FG_CYAN)
            else:
                cprint("[!] Cookie file not found; continuing without cookies.", FG_YELLOW)
                cookiefile = None

    # Detect aria2c and ffmpeg
    aria2_path = shutil.which('aria2c')
    ffmpeg_path = shutil.which('ffmpeg')
    if aria2_path:
        cprint(f"[i] aria2c found at: {aria2_path}", FG_CYAN)
        use_aria2 = input(f"{FG_YELLOW}Use aria2c for segmented downloads? (y/N): {RESET}").strip().lower() == 'y'
    else:
        use_aria2 = False
    if not ffmpeg_path:
        cprint("[!] ffmpeg not found — merges or re-muxing may fail for separate streams. Install with: pip install ffmpeg", FG_YELLOW)

    # Offer yt-dlp auto-update
    try_update = input(f"{FG_YELLOW}Check for yt-dlp updates before downloading? (y/N): {RESET}").strip().lower() == 'y'
    if try_update:
        cprint("[i] Attempting to update yt-dlp via pip ...", FG_CYAN)
        try:
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"], check=False)
            cprint("[i] Update attempt finished. Continuing...", FG_CYAN)
        except Exception:
            cprint("[!] Could not auto-update yt-dlp. Please update manually if needed.", FG_YELLOW)

    # Loop through urls
    for url in urls:
        url = url.strip()
        if not url:
            continue
        cprint(f"\n=== Processing: {url} ===", FG_MAGENTA)
        # Extract info (no download)
        ydl_opts_info = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            # get manifests and formats
            'allow_unplayable_formats': False,
        }
        if cookiefile:
            ydl_opts_info['cookiefile'] = cookiefile

        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            cprint("[!] Error extracting video info: " + str(e), FG_RED)
            cprint("    Make sure the URL is valid and yt-dlp is updated.", FG_YELLOW)
            continue

        # handle playlist: choose first entry and inform user
        if 'entries' in info and info['entries']:
            cprint("[!] URL is a playlist — selecting first entry by default.", FG_YELLOW)
            info = info['entries'][0] or {}

        title = safe_filename(info.get('title') or "video")
        
        # FIXED: Handle duration properly - ensure it's an integer before formatting
        duration = info.get('duration', 0)
        cprint(f"[i] Title: {title}", FG_CYAN)
        
        if duration:
            try:
                # Convert to integer to avoid float formatting issues
                total_seconds = int(float(duration))
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                cprint(f"[i] Duration: {minutes}:{seconds:02d}", FG_CYAN)
            except (ValueError, TypeError) as e:
                # Fallback if conversion fails
                cprint(f"[i] Duration: {duration} seconds", FG_CYAN)

        formats = info.get('formats') or []
        if not formats:
            cprint("[!] No formats found. Try cookies or update yt-dlp.", FG_RED)
            continue

        # Show a condensed format list and allow selection
        print_format_list(formats)

        # Ask download type (enhanced interactivity)
        cprint("\nDownload type options:", FG_BLUE)
        cprint("  0 = Automatic BEST (bestvideo+bestaudio/best)", FG_BLUE)
        cprint("  1 = Best (video+audio)", FG_BLUE)
        cprint("  2 = Audio only (bestaudio/best)", FG_BLUE)
        cprint("  3 = Video only (bestvideo)", FG_BLUE)

        # allow multiple attempts for a valid selection
        attempts = 0
        selected_fmt = None
        while attempts < 3:
            sel = input(f"{FG_YELLOW}Enter index number shown above to pick a specific format, or 0 for automatic BEST (press Enter for 0): {RESET}").strip()
            if sel == '' or sel == '0':
                # ask for download type refinement
                dtype = input(f"{FG_YELLOW}Which download type? (0=auto,1=best,2=audio-only,3=video-only) [0]: {RESET}").strip() or '0'
                if dtype == '2':
                    selected_fmt = 'bestaudio/best'
                elif dtype == '3':
                    selected_fmt = 'bestvideo'
                else:
                    selected_fmt = 'bestvideo+bestaudio/best'
                break
            # try interpret as index
            try:
                idx = int(sel)
                if idx < 0:
                    raise ValueError
                if idx == 0:
                    selected_fmt = 'bestvideo+bestaudio/best'
                    break
                # map to sorted list
                sorted_f = sorted(formats, key=lambda x: (x.get('height') or 0, x.get('filesize') or 0), reverse=True)
                if 1 <= idx <= len(sorted_f):
                    chosen = sorted_f[idx-1]
                    fid = chosen.get('format_id')
                    if not fid:
                        cprint("[!] Selected entry has no format id; choose another or use 0 for best.", FG_YELLOW)
                        attempts += 1
                        continue
                    selected_fmt = fid
                    cprint(f"[i] Selected format id: {selected_fmt}", FG_CYAN)
                    break
                else:
                    cprint("[!] Index out of shown range, try again.", FG_YELLOW)
            except ValueError:
                cprint("[!] Invalid input; enter a number from the list or 0.", FG_YELLOW)
            attempts += 1

        if not selected_fmt:
            cprint("[!] No valid format selected after multiple tries — defaulting to best.", FG_YELLOW)
            selected_fmt = 'bestvideo+bestaudio/best'

        # Build yt-dlp options for download
        outtmpl = os.path.join(download_dir, '%(title)s.%(ext)s')
        ydl_opts_dl = {
            'format': selected_fmt,
            'outtmpl': outtmpl,
            'merge_output_format': 'mp4',
            'progress_hooks': [make_progress_hook()],
            'noprogress': False,
            'restrictfilenames': False,
            'quiet': False,
            'no_warnings': True,
            'keep_fragments': False,
        }
        if cookiefile:
            ydl_opts_dl['cookiefile'] = cookiefile
        if use_aria2 and aria2_path:
            ydl_opts_dl['external_downloader'] = 'aria2c'
            ydl_opts_dl['external_downloader_args'] = [
                '-x', '16', '-s', '16', '-k', '1M', '--file-allocation=none'
            ]

        # Commence download with error handling
        try:
            with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                cprint("\n[+] Starting download ...\n", FG_GREEN)
                ydl.download([url])
            cprint(f"\n[+] Done. File should be in: {download_dir}", FG_GREEN)
        except yt_dlp.utils.DownloadError as de:
            cprint("[!] DownloadError: " + str(de), FG_RED)
            cprint("    If this is member-only content, try exporting cookies from a browser and placing cookies.txt in your storage.", FG_YELLOW)
        except Exception as e:
            cprint("[!] Unexpected error: " + str(e), FG_RED)

    cprint("\n=== All tasks complete ===", FG_CYAN)

if __name__ == '__main__':
    main()
