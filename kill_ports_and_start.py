#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import platform
import re
import argparse
import socket
from datetime import datetime

# --- Configuration ---
PORTS = [27017, 8000, 8001, 8002, 8003, 8004]
SERVICES = {
    "mongodb": 27017,
    "api-gateway": 8000,
    "auth-service": 8001,
    "products-service": 8002,
    "orders-service": 8003,
    "payments-service": 8004
}
DOCKER_COMPOSE_FILE = "docker-compose.yml"

# --- Colors ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

if platform.system() == "Windows":
    os.system('color')  # Enable ANSI colors in Windows terminal

def log(msg, color=Colors.ENDC, bold=False):
    prefix = ""
    if bold:
        prefix = Colors.BOLD
    print(f"{prefix}{color}{msg}{Colors.ENDC}")

def print_header():
    log("\n" + "═" * 40, Colors.HEADER)
    log("DIGITAL MARKETPLACE - PORT CLEANUP & START", Colors.HEADER, bold=True)
    log("═" * 40 + "\n", Colors.HEADER)

# --- Port Management ---

def get_process_on_port(port):
    """Finds the PID of the process listening on the given port."""
    system = platform.system()
    try:
        if system == "Windows":
            # netstat -ano | findstr :<port>
            cmd = f'netstat -ano | findstr :{port}'
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.strip().split()
                        return parts[-1] # PID is the last element
        else: # Linux/MacOS
            cmd = ['lsof', '-t', f'-i:{port}']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split('\n')[0]
    except Exception as e:
        log(f"Error checking port {port}: {e}", Colors.WARNING)
    return None

def get_process_name(pid):
    """Gets the name of the process from its PID."""
    system = platform.system()
    try:
        if system == "Windows":
            cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.stdout:
                # Format: "image_name","pid","session_name","session_num","mem_usage"
                return result.stdout.strip().split(',')[0].strip('"')
        else:
            cmd = ['ps', '-p', str(pid), '-o', 'comm=']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.stdout:
                return result.stdout.strip()
    except:
        return "Unknown"
    return "Unknown"

def kill_process(pid):
    """Kills the process with the given PID."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(['kill', '-9', str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        log(f"  └─ Failed to kill PID {pid}: {e}", Colors.FAIL)
        return False

def clean_ports():
    log("[1/4] Checking ports...", Colors.BLUE, bold=True)
    killed_count = 0
    
    for port in PORTS:
        pid = get_process_on_port(port)
        if pid:
            pname = get_process_name(pid)
            log(f"✓ Port {port}: IN USE - {pname} (PID: {pid})", Colors.WARNING)
            log(f"  └─ Killing process...", Colors.WARNING, end=" ")
            if kill_process(pid):
                log("DONE", Colors.GREEN)
                killed_count += 1
            else:
                log("FAILED", Colors.FAIL)
                log("     Try running as Administrator/sudo", Colors.FAIL)
        else:
            log(f"✓ Port {port}: AVAILABLE", Colors.GREEN)
            
    log(f"\nSummary: Killed {killed_count} processes, all ports available.", Colors.CYAN)

# --- Docker Management ---

def clean_docker():
    log("\n[2/4] Cleaning old Docker containers...", Colors.BLUE, bold=True)
    try:
        subprocess.run(["docker-compose", "down", "-v"], check=False) # Don't error if already down
        log("✓ Stopped and removed existing containers", Colors.GREEN)
    except Exception as e:
        log(f"Error cleaning Docker: {e}", Colors.FAIL)

def start_docker(no_build=False):
    log("\n[3/4] Starting Docker services...", Colors.BLUE, bold=True)
    cmd = ["docker-compose", "up", "-d"]
    if not no_build:
        cmd.append("--build")
        log("✓ Building images...", Colors.CYAN)
    
    try:
        subprocess.run(cmd, check=True)
        log("✓ Services started", Colors.GREEN)
    except subprocess.CalledProcessError:
        log("❌ Failed to start Docker services", Colors.FAIL)
        sys.exit(1)

def wait_for_health():
    log("\n[4/4] Verifying services...", Colors.BLUE, bold=True)
    MAX_RETRIES = 30
    for service, port in SERVICES.items():
        log(f"Checking {service} on port {port}...", end=" ")
        healthy = False
        for _ in range(MAX_RETRIES):
            try:
                # Simple socket check first
                with socket.create_connection(("localhost", port), timeout=1):
                    pass
                healthy = True
                break
            except (OSError, ConnectionRefusedError):
                time.sleep(1)
        
        if healthy:
            log("HEALTHY", Colors.GREEN)
        else:
            log("TIMEOUT/FAILED", Colors.FAIL)

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Cleanup ports and start Digital Marketplace")
    parser.add_argument("--no-build", action="store_true", help="Skip rebuilding Docker images")
    parser.add_argument("--logs", action="store_true", help="Follow logs after starting")
    args = parser.parse_args()

    print_header()
    
    # 1. Clean Ports
    clean_ports()
    
    # 2. Clean Docker
    clean_docker()
    
    # 3. Start Docker
    start_docker(no_build=args.no_build)
    
    # 4. Verify
    wait_for_health()
    
    log("\n" + "═" * 40, Colors.HEADER)
    log("✓ ALL SERVICES RUNNING SUCCESSFULLY!", Colors.GREEN, bold=True)
    log("═" * 40, Colors.HEADER)
    
    log("\nAccess your API:")
    log(f"- API Gateway: {Colors.BLUE}http://localhost:8000{Colors.ENDC}")
    log(f"- Swagger UI:  {Colors.BLUE}http://localhost:8000/docs{Colors.ENDC}")
    
    if args.logs:
        log("\nTailing logs (Ctrl+C to exit)...", Colors.CYAN)
        subprocess.run(["docker-compose", "logs", "-f"])
    else:
        log(f"\nView logs: {Colors.BOLD}docker-compose logs -f{Colors.ENDC}")
        log(f"Stop all:  {Colors.BOLD}python stop_marketplace.py{Colors.ENDC}{Colors.ENDC}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nAborted by user.", Colors.WARNING)
        sys.exit(0)
