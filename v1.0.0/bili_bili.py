#!/usr/bin/env python3
"""

BiliBili Video Downloader
--------------------------

        pudszTTIOT

--------------------------

"""

import os
import sys
import re
import math
import shutil
from pathlib import Path

try:
    from yt_dlp import YoutubeDL
except Exception as e:
    print("ERROR: yt-dlp module not found. Install with: python3 -m pip install -U yt-dlp")
    sys.exit(1)

# ---------- Helpers ----------
def human_size(n):
    """Return human-readable file size in MB/KB if n is bytes or None."""
    if not n:
        return "unknown"
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def default_output_dir():
    
    p1 = Path.home() / "storage" / "shared" / "Download"
    p2 = Path.home() / "downloads"
    target = p1 if p1.exists() else p2
    target.mkdir(parents=True, exist_ok=True)
    return str(target)

def parse_bv_av(url):
    """
    Try to parse a BiliBili video ID from the URL (BV... or av...).
    Returns None if not found. (yt-dlp does its own parsing too.)
    """
    m = re.search(r'(BV[0-9A-Za-z]{10})', url)
    if m:
        return m.group(1)
    m = re.search(r'av(\d+)', url)
    if m:
        return 'av' + m.group(1)
    return None

# ---------- Progress Hook ----------
def progress_hook(d):
    """
    Simple progress hook for yt-dlp events.
    """
    status = d.get('status')
    if status == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        speed = d.get('speed')
        eta = d.get('eta')
        perc = (downloaded / total * 100) if total else 0.0
        bar_len = 30
        filled = int(bar_len * perc / 100) if total else 0
        bar = '=' * filled + '-' * (bar_len - filled)
        print(f"\r[{bar}] {perc:5.1f}% {human_size(downloaded)} / {human_size(total)} "
              f"{'@ ' + human_size(speed) + '/s' if speed else ''} "
              f"{'(eta: ' + str(eta) + 's)' if eta else ''}", end='', flush=True)
    elif status == 'finished':
        print("\nDownload finished, post-processing...")

# ---------- Main logic ----------
def list_resolutions(info):
    """
    Extract available numeric heights (resolutions) from info['formats'], sorted desc.
    Returns list of ints (heights).
    """
    formats = info.get('formats') or []
    heights = set()
    for f in formats:
        h = f.get('height')
        if h and isinstance(h, int):
            heights.add(h)
    return sorted(heights, reverse=True)

def main():
    print("BiliBili Video Downloader (uses yt-dlp).")
    url = input("Enter BiliBili video URL (or paste): ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return

    vid = parse_bv_av(url)
    if vid:
        print(f"Detected video id: {vid}")
    else:
        print("No BV/av extracted (yt-dlp will still try to handle the URL).")

    # Optional cookies (for private/restricted content)
    cookies = input("Optional: path to cookies.txt (press Enter to skip): ").strip()
    if cookies and not Path(cookies).exists():
        print("Cookies file not found; continuing without cookies.")
        cookies = None

    outdir = default_output_dir()
    print(f"Output directory: {outdir}")

    # Basic ydl options for metadata retrieval
    info_ld_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    if cookies:
        info_ld_opts['cookiefile'] = cookies

    try:
        with YoutubeDL(info_ld_opts) as ydl:
            print("Extracting video info...")
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print("Failed to extract info from the URL. Error:")
        print(str(e))
        return

    # If a playlist was returned, pick the first entry (common for some sharer URLs)
    if 'entries' in info and isinstance(info['entries'], list):
        if len(info['entries']) == 0:
            print("No videos found in the provided URL.")
            return
        print("Playlist/collection detected - selecting the first video.")
        info = info['entries'][0]

    title = info.get('title', 'video')
    uploader = info.get('uploader') or info.get('uploader_id') or ''
    print(f"\nTitle: {title}\nUploader: {uploader}\n")

    # List resolutions and present menu
    heights = list_resolutions(info)
    print("Quality options:")
    print("  0) Best available (highest combined quality)")
    for i, h in enumerate(heights, start=1):
        print(f"  {i}) Up to {h}p")
    print("  X) Cancel / Exit")

    choice = input(f"Choose a number (0-{len(heights)}), default 0: ").strip().lower()
    if choice in ('x','q','quit','exit'):
        print("Exit.")
        return
    if choice == '':
        choice_idx = 0
    else:
        try:
            choice_idx = int(choice)
            if choice_idx < 0 or choice_idx > len(heights):
                print("Invalid choice. Using best (0).")
                choice_idx = 0
        except:
            print("Invalid input. Using best (0).")
            choice_idx = 0

    # Build format selector
    if choice_idx == 0:
        format_selector = 'best'
        print("Selected: best available.")
    else:
        h = heights[choice_idx - 1]
        # This expression tries:
        # 1) bestvideo with height <= chosen + bestaudio (merge)
        # 2) or best combined with height <= chosen
        # 3) or overall best (fallback)
        format_selector = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
        print(f"Selected: up to {h}p -> will download video up to {h}p and merge best audio.")

    # Prepare download options
    outtmpl = os.path.join(outdir, '%(title)s.%(ext)s')
    ydl_opts = {
        'format': format_selector,
        'outtmpl': outtmpl,
        'noplaylist': True,
        'merge_output_format': 'mp4',  # prefer mp4 container when merging
        'progress_hooks': [progress_hook],
        'continuedl': True,
        'no_warnings': False,
        'quiet': False,
    }
    if cookies:
        ydl_opts['cookiefile'] = cookies

    # Check ffmpeg
    if shutil.which('ffmpeg') is None:
        print("\nWARNING: 'ffmpeg' not found in PATH. If the selected format requires merging (video+audio), post-processing may fail.")
        print("Install ffmpeg with: pip install ffmpeg")
        # still proceed; yt-dlp may download already merged formats

    try:
        with YoutubeDL(ydl_opts) as ydl:
            print("\nStarting download - this may take a while depending on size / network...")
            ydl.download([url])
            print("\nDone. Saved to:", outdir)
    except Exception as e:
        print("\nDownload failed. Error details:")
        print(str(e))
        # optional: print traceback for debugging
        # import traceback; traceback.print_exc()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
