#!/usr/bin/env python3
import subprocess
import os
import platform

# --- Colors ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

if platform.system() == "Windows":
    os.system('color')

def log(msg, color=Colors.ENDC):
    print(f"{color}{msg}{Colors.ENDC}")

def main():
    log("\nStopping Digital Marketplace...", Colors.HEADER)
    try:
        subprocess.run(["docker-compose", "down"], check=True)
        log("✓ Services stopped successfully", Colors.GREEN)
    except subprocess.CalledProcessError:
        log("❌ Failed to stop services", Colors.FAIL)

if __name__ == "__main__":
    main()
