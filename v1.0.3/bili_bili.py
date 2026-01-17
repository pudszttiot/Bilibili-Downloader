#!/usr/bin/env python3
"""

BiliBili Video Downloader (v1.0.3)
--------------------------

        pudszTTIOT

--------------------------

"""

import os
import sys
import subprocess

# ===========================
# ANSI Colors (Termux Safe)
# ===========================
C_RESET   = "\033[0m"
C_RED     = "\033[31m"
C_GREEN   = "\033[32m"
C_YELLOW  = "\033[33m"
C_BLUE    = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN    = "\033[36m"
C_BOLD    = "\033[1m"


# ===========================
# Utility Functions
# ===========================

def auto_detect_cookiefile():
    """Automatically detect cookies.txt or similar."""
    possible = ["cookies.txt", "cookies2.txt", "cookie.txt"]

    for file in possible:
        if os.path.isfile(file):
            return file

    # Search current dir for any txt containing "cookie"
    for f in os.listdir("."):
        if f.lower().startswith("cookie") and f.lower().endswith(".txt"):
            return f

    return None


def clear_screen():
    os.system("clear" if os.name == "posix" else "cls")


def run_aria(url, cookiefile):
    """Run aria2c with cookiefile support."""
    cmd = [
        "aria2c",
        "--seed-time=0",
        "--enable-dht=true",
        "--enable-peer-exchange=true",
    ]

    if cookiefile:
        cmd.append(f"--load-cookies={cookiefile}")

    cmd.append(url)

    print(f"{C_CYAN}Running:{C_RESET} {' '.join(cmd)}\n")

    try:
        subprocess.run(cmd, check=True)
        print(f"{C_GREEN}[✓] Download completed.{C_RESET}")
    except subprocess.CalledProcessError:
        print(f"{C_RED}[X] Download failed.{C_RESET}")


# ===========================
# Interactive Prompt System
# ===========================

def prompt_url():
    """Ask the user for a URL."""
    while True:
        url = input(f"{C_GREEN}[?]{C_RESET} Enter download URL: ").strip()
        if url:
            return url
        else:
            print(f"{C_RED}[!] URL cannot be empty.{C_RESET}")


def prompt_cookie_override():
    """Let the user override cookiefile manually."""
    while True:
        file = input(f"{C_GREEN}[?]{C_RESET} Enter cookie file path: ").strip()

        if file.lower() in ["none", "no", "n"]:
            return None

        if os.path.isfile(file):
            return file
        else:
            print(f"{C_RED}[!] File not found. Try again.{C_RESET}")


def show_settings(cookiefile):
    print(f"\n{C_CYAN}=== Current Settings ==={C_RESET}")
    print(f"{C_YELLOW}Cookie file:{C_RESET} {cookiefile if cookiefile else 'None detected'}")
    print()


def ask_main_menu():
    print(f"""
{C_BOLD}{C_CYAN}=== MAIN MENU ==={C_RESET}
{C_YELLOW}1){C_RESET} Start Download
{C_YELLOW}2){C_RESET} Change Cookie File
{C_YELLOW}3){C_RESET} Show Current Settings
{C_YELLOW}4){C_RESET} Quit
    """)

    while True:
        choice = input(f"{C_GREEN}[?]{C_RESET} Select an option: ").strip()
        if choice in ["1", "2", "3", "4"]:
            return choice
        print(f"{C_RED}[!] Invalid selection — choose 1, 2, 3, or 4.{C_RESET}")


# ===========================
# Main Program Logic
# ===========================

def main():
    clear_screen()
    print(f"{C_MAGENTA}{C_BOLD}Welcome to the BiliBili Video Downloader!{C_RESET}\n")

    cookiefile = auto_detect_cookiefile()

    if cookiefile:
        print(f"{C_GREEN}[✓]{C_RESET} Auto-detected cookie file: {C_CYAN}{cookiefile}{C_RESET}")
    else:
        print(f"{C_YELLOW}[!] No cookie file detected.{C_RESET}")

    while True:
        choice = ask_main_menu()

        if choice == "1":
            # Start download
            url = prompt_url()
            run_aria(url, cookiefile)

        elif choice == "2":
            # Change cookie file
            new_cookie = prompt_cookie_override()
            cookiefile = new_cookie
            print(f"{C_GREEN}[✓] Cookie file updated.{C_RESET}")

        elif choice == "3":
            # Show settings
            show_settings(cookiefile)

        elif choice == "4":
            print(f"{C_GREEN}[✓] Exiting — goodbye mybro!{C_RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
