#!/usr/bin/env python3
"""

BiliBili Video Downloader (v1.0.1)
--------------------------

        pudszTTIOT

--------------------------

"""

import os
import sys
import shutil
import math
from pathlib import Path

try:
    import yt_dlp
except Exception as e:
    print("yt-dlp Python module not found. Please run: pip install -U 'yt-dlp[default]'")
    sys.exit(1)

# ----- Helpers -----
def human_size(num_bytes):
    if num_bytes is None:
        return "N/A"
    num = float(num_bytes)
    for unit in ['B','KB','MB','GB','TB']:
        if num < 1024:
            return f"{num:.2f}{unit}"
        num /= 1024.0
    return f"{num:.2f}PB"

def choose_download_dir():
    
    home = Path.home()
    downloads = home / "storage" / "downloads"
    if downloads.exists():
        return str(downloads)
    # fallback to current dir
    return str(home)

def print_format_list(formats):
    print("\nAvailable formats (top entries shown):")
    # sort by resolution (height) then by filesize
    filtered = [f for f in formats if 'format_id' in f]
    sorted_f = sorted(filtered, key=lambda x: (x.get('height') or 0, x.get('filesize') or 0), reverse=True)
    # print header
    print(f"{'Index':>5} {'format_id':>10} {'note':>10} {'res':>7} {'fps':>5} {'size':>9} {'type':>10}")
    for i, f in enumerate(sorted_f[:20], start=1):
        fid = f.get('format_id')
        note = f.get('format_note') or ''
        res = f"{f.get('width') or '?'}x{f.get('height') or '?'}"
        fps = str(f.get('fps') or '')
        size = human_size(f.get('filesize') or f.get('filesize_approx'))
        typ = 'video+audio' if f.get('vcodec') != 'none' and f.get('acodec') != 'none' else ('video' if f.get('vcodec') != 'none' else 'audio')
        print(f"{i:5d} {fid:>10} {note:>10} {res:>7} {fps:>5} {size:>9} {typ:>10}")
    print("\nIndex 0 = automatic BEST (bestvideo+bestaudio/best)")

# ----- Progress hook for yt-dlp -----
def make_progress_hook():
    def hook(d):
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            pct = (downloaded / total * 100) if total else 0.0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            sys.stdout.write(f"\rDownloading: {pct:5.1f}% {human_size(downloaded)}/{human_size(total)}  ETA:{eta}s  {human_size(speed)}/s")
            sys.stdout.flush()
        elif status == 'finished':
            print("\nDownload finished, post-processing (if any) ...")
        elif status == 'error':
            print("\nError during download:", d)
    return hook

# ----- Main flow -----
def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter BiliBili video URL: ").strip()
        if not url:
            print("No URL provided. Exiting.")
            return

    download_dir = choose_download_dir()
    print(f"Download directory: {download_dir}")

    # Extract info (no download) to list formats
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        # ensure manifests are gathered
        'allow_unplayable_formats': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print("Error extracting video info:", str(e))
        print("Make sure the URL is valid and yt-dlp is updated.")
        return

    # If playlist, pick first entry by default
    if 'entries' in info and info['entries']:
        print("Note: URL is a playlist - selecting first entry.")
        info = info['entries'][0]

    title = info.get('title') or 'video'
    print(f"\nTitle: {title}")
    formats = info.get('formats') or []
    if not formats:
        print("No formats found. Try updating yt-dlp or using a cookiefile for locked content.")
        return

    # Show formats
    print_format_list(formats)

    # Ask about cookies (optional)
    cookiefile = None
    cookie_input = input("If you have a cookies.txt for logged-in access, enter its path (or just press Enter to skip): ").strip()
    if cookie_input:
        cookiefile = os.path.expanduser(cookie_input)
        if not os.path.isfile(cookiefile):
            print("Cookie file not found. Ignoring cookies.")
            cookiefile = None
        else:
            print("Using cookiefile:", cookiefile)

    # Detect aria2c
    aria2_path = shutil.which('aria2c')
    use_aria2 = False
    if aria2_path:
        ans = input("aria2c available — use it as external downloader for faster segmented download? (y/N): ").strip().lower()
        if ans == 'y':
            use_aria2 = True

    # Ask user to choose
    choice = input("\nEnter index number shown above to pick a specific format, or 0 for automatic BEST (recommended): ").strip()
    fmt_spec = None
    if choice == '0' or choice == '':
        fmt_spec = 'bestvideo+bestaudio/best'
    else:
        try:
            i = int(choice)
            # map chosen index to sorted list as printed earlier
            sorted_f = sorted(formats, key=lambda x: (x.get('height') or 0, x.get('filesize') or 0), reverse=True)
            sel = sorted_f[i-1]  # cause printed i started at 1
            fmt_spec = sel.get('format_id')
            if not fmt_spec:
                print("Couldn't determine format id; falling back to best.")
                fmt_spec = 'bestvideo+bestaudio/best'
        except Exception as e:
            print("Invalid choice, defaulting to best.")
            fmt_spec = 'bestvideo+bestaudio/best'

    print("Selected format spec:", fmt_spec)

    # Build yt-dlp options for actual download
    outtmpl = os.path.join(download_dir, '%(title)s.%(ext)s')
    ydl_opts_dl = {
        'format': fmt_spec,
        'outtmpl': outtmpl,
        'merge_output_format': 'mp4',   # ensure final container is mp4 if merging occurs
        'progress_hooks': [make_progress_hook()],
        'noprogress': False,
        'restrictfilenames': False,
        'quiet': False,
        'no_warnings': True,
        # keep fragments until merging (optional)
        'keep_fragments': False,
    }

    if cookiefile:
        ydl_opts_dl['cookiefile'] = cookiefile

    if use_aria2:
        # Use aria2c as external downloader with some recommended args
        ydl_opts_dl['external_downloader'] = 'aria2c'
        ydl_opts_dl['external_downloader_args'] = [
            '-x', '16',    # 16 connections
            '-s', '16',
            '-k', '1M',    # 1M split size
            '--file-allocation=none'  # avoid prealloc on limited Android storage
        ]

    # Start download
    try:
        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
            print("\nStarting download ...\n")
            ydl.download([url])
        print("\nAll done — check your Downloads folder.")
    except yt_dlp.utils.DownloadError as de:
        print("DownloadError:", str(de))
        print("If this is a high-quality or member-only video, try exporting cookies and passing the cookiefile.")
    except Exception as e:
        print("Unexpected error:", str(e))


if __name__ == '__main__':
    main()
