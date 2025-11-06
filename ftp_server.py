#!/usr/bin/env python3
"""
Simple FTP Server (pyftpdlib)
Usage:
    python ftp_server.py [folder_to_share] [port]

Defaults:
    folder_to_share = current working directory
    port = 2121
"""

import logging
import logging.handlers
import threading
import time
import os
import secrets
import sys
import socket
import sqlite3
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def get_local_ip():
    """Return the LAN IP address of this computer."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def get_all_local_ips():
    """Return a sorted list of local IPv4 addresses (non-loopback).

    Strategy (in order):
    1. UDP connect trick to discover primary outbound LAN IP.
    2. Parse OS network command output (Windows: ipconfig, Linux/macOS: ip/ifconfig).
    3. Hostname-based lookups (gethostbyname_ex/getaddrinfo) as fallback.

    This avoids adding external dependencies and covers common OSes.
    """
    import re
    import subprocess

    ips = set()

    # 1) UDP trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    # 2) Parse system command output
    try:
        if os.name == 'nt':
            # Windows
            out = subprocess.check_output(["ipconfig"], stderr=subprocess.DEVNULL)
            text = out.decode(errors='ignore')
            # Match IPv4 addresses
            for m in re.findall(r"IPv4[^:\r\n]*[:\.]\s*([0-9]+(?:\.[0-9]+){3})", text):
                ips.add(m)
        else:
            # Try `ip -4 addr` first (common on modern Linux)
            try:
                out = subprocess.check_output(["ip", "-4", "addr"], stderr=subprocess.DEVNULL)
                text = out.decode(errors='ignore')
                for m in re.findall(r"inet\s+([0-9]+(?:\.[0-9]+){3})/", text):
                    ips.add(m)
            except Exception:
                # Fallback to ifconfig
                try:
                    out = subprocess.check_output(["ifconfig"], stderr=subprocess.DEVNULL)
                    text = out.decode(errors='ignore')
                    for m in re.findall(r"inet\s+([0-9]+(?:\.[0-9]+){3})", text):
                        # On some systems 'inet 127.0.0.1' will appear; we'll filter later
                        ips.add(m)
                except Exception:
                    pass
    except Exception:
        pass

    # 3) Hostname lookups
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            ips.add(ip)
    except Exception:
        pass

    try:
        for res in socket.getaddrinfo(socket.gethostname(), None):
            if res and res[0] == socket.AF_INET:
                ips.add(res[4][0])
    except Exception:
        pass

    # Filter out loopback and empty
    clean = sorted(p for p in ips if p and not p.startswith("127."))
    if not clean:
        clean = ["127.0.0.1"]
    return clean


def prompt_with_default(prompt, default):
    """Prompt the user with a default. Return the entered value or default if empty."""
    if default is None:
        resp = input(f"{prompt}: ")
        return resp.strip()
    resp = input(f"{prompt} [{default}]: ")
    return resp.strip() or default


def main():
    # Initialize sqlite DB for persistent settings
    DB_PATH = os.path.join(os.path.dirname(__file__), "ftp_server.db")

    def init_db():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        # Remove any existing 'folder' entries to avoid persisting folder paths
        c.execute("DELETE FROM settings WHERE key='folder'")
        # defaults
        defaults = {
            "username": "user",
            "password": "12345",
            "port": "2121",
            # folder intentionally NOT persisted in DB for privacy/portability
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (k, str(v)))
        conn.commit()
        conn.close()

    def get_setting(key, default=None):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default

    def set_setting(key, value):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, str(value)))
        conn.commit()
        conn.close()

    init_db()
    # Support non-interactive mode via command-line flag only (--noninteractive)
    noninteractive = "--noninteractive" in sys.argv

    if noninteractive:
        # Read options from DB/defaults and optional positional args.
        # Positional args: [folder] [port]
        folder_arg = None
        port_arg = None
        if len(sys.argv) > 1:
            # find first arg that is not the --noninteractive flag
            for a in sys.argv[1:]:
                if a == "--noninteractive":
                    continue
                if not a.startswith("--") and folder_arg is None:
                    folder_arg = a
                elif not a.startswith("--") and port_arg is None:
                    port_arg = a
        folder = os.path.abspath(folder_arg or get_setting("folder", os.getcwd()))
        port = int(port_arg) if port_arg and str(port_arg).isdigit() else int(get_setting("port", "2121"))
        host = "0.0.0.0"
        username = get_setting("username", "user")
        password = get_setting("password", "")
        log_level = "INFO"
        log_file = None
        logging.info("Starting in non-interactive mode (DB/defaults)")
    else:
        # Interactive mode: start server on default IP/port immediately without logs
        folder = os.path.abspath(prompt_with_default("\nFolder to share", get_setting("folder", os.getcwd())))
        host = "0.0.0.0"
        port = int(get_setting("port", "2121"))
        username = get_setting("username", "user")
        password = get_setting("password", "12345")
        # default: no log output
        log_level = "CRITICAL"
        log_file = None
        # TLS and passive ports removed - simpler defaults

        # Helper to create and start server in background thread
        def create_server_instance(h, p, user, pwd, folder_path):
            auth = DummyAuthorizer()
            auth.add_user(user, pwd, folder_path, perm="elradfmwMT")
            handler_cls = FTPHandler
            handler_cls.authorizer = auth
            try:
                server = FTPServer((h, p), handler_cls)
                return server
            except Exception as e:
                # Logging may be disabled in interactive mode, so print the error to console
                err_msg = f"Failed to bind server to {h}:{p} -- {e}"
                try:
                    logging.error(err_msg)
                except Exception:
                    pass
                print(err_msg)
                return None

        # Silence logging from pyftpdlib and other libraries in interactive menu mode
        logging.disable(logging.CRITICAL)

        server = create_server_instance(host, port, username, password, folder)
        server_thread = None
        server_running = False

        def start_server(srv):
            nonlocal server_thread, server_running
            if srv is None:
                logging.error("Server instance is None, cannot start")
                return
            def run():
                try:
                    srv.serve_forever()
                except Exception as e:
                    logging.error("Server stopped with error: %s", e)
            server_thread = threading.Thread(target=run, daemon=True)
            server_thread.start()
            server_running = True

        def stop_server(srv):
            nonlocal server_thread, server_running
            if srv:
                try:
                    srv.close_all()
                except Exception:
                    pass
            if server_thread:
                server_thread.join(timeout=2)
            server_running = False

        # Start server initially
        if server:
            start_server(server)
            print(f"Server started on {host}:{port} (user: {username}) -- no logging by default")
            # Show detected local IPs and recommended access URLs at runtime
            try:
                local_ip = get_local_ip()
                all_ips = get_all_local_ips()
                # Print short summary to console for interactive users
                print("Detected local IPs:", ", ".join(all_ips))
                # concise output for easy copy/paste in cmd
                print(" ")
                print(f"ip: {local_ip}")
                print(f"port: {port}")
                print(f"username: {username}")
                print(f"password: {password}")
                print(" ")
                
                print(f"Listening on {host}:{port} (bind address). Primary outbound IP: {local_ip}")
            except Exception:
                # Don't break startup if IP detection fails
                pass
        else:
            print("Failed to start server on default settings. Use menu to reconfigure.")

        # Interactive menu loop
        while True:
            print("\nOptions:\n1) Change username\n2) Change password\n3) Change port\n4) Change folder\n5) Restart server\n6) Show credentials\n7) Stop server and exit")
            choice = input("Select option (1-7): ").strip()
            if choice == "1":
                new_user = input("\nNew username: ").strip()
                if new_user:
                    username = new_user
                    # Restart to apply new credentials immediately
                    print(f"Username changed to: {username} - restarting server...")
                    try:
                        stop_server(server)
                    except Exception:
                        pass
                    server = create_server_instance(host, port, username, password, folder)
                    if server:
                        start_server(server)
                        print(f"Server restarted on {host}:{port} (user: {username})")
                    else:
                        print("Failed to restart server after username change.")
                    # persist change
                    set_setting("username", username)
            elif choice == "2":
                new_pass = input("\nNew password: ").strip()
                if new_pass:
                    password = new_pass
                    print("Password updated - restarting server...")
                    try:
                        stop_server(server)
                    except Exception:
                        pass
                    server = create_server_instance(host, port, username, password, folder)
                    if server:
                        start_server(server)
                        print(f"Server restarted on {host}:{port} (user: {username})")
                    else:
                        print("Failed to restart server after password change.")
                    # persist change
                    set_setting("password", password)
            elif choice == "3":
                new_port = input(f"\nNew port (current {port}): ").strip()
                if new_port.isdigit():
                    port = int(new_port)
                    print(f"Port set to {port} - restarting now...")
                    # Restart server immediately to apply new port
                    try:
                        stop_server(server)
                    except Exception:
                        pass
                    server = create_server_instance(host, port, username, password, folder)
                    if server:
                        start_server(server)
                        print(f"Server restarted on {host}:{port} (user: {username})")
                    else:
                        print("Failed to restart server on the new port. Check for port conflicts and try again.")
                else:
                    print("Invalid port")
            elif choice == "4":
                new_folder = input(f"\nNew folder (current {folder}): ").strip()
                if new_folder:
                    folder = os.path.abspath(new_folder)
                    print(f"Folder set to {folder} - restarting server...")
                    try:
                        stop_server(server)
                    except Exception:
                        pass
                    server = create_server_instance(host, port, username, password, folder)
                    if server:
                        start_server(server)
                        print(f"Server restarted on {host}:{port} (user: {username})")
                    else:
                        print("Failed to restart server after folder change.")
                    # Do not persist folder to DB (user requested not to save folder path)
            elif choice == "5":
                print("\nRestarting server with current settings...")
                try:
                    stop_server(server)
                except Exception:
                    pass
                server = create_server_instance(host, port, username, password, folder)
                if server:
                    start_server(server)
                    print(f"Server restarted on {host}:{port} (user: {username})")
                else:
                    print("Failed to restart server. Check settings and try again.")
                    # persist change
                    set_setting("port", port)
            elif choice == "6":
                # Show credentials and recommended access
                try:
                    primary_ip = get_local_ip()
                except Exception:
                    primary_ip = None
                if primary_ip:
                    print(f"\nip: {primary_ip}")
                else:
                    print("\nip: (unknown)")
                print(f"port: {port}")
                print(f"username: {username}")
                print(f"password: {password}")
            elif choice == "7":
                print("\nStopping server and exiting...")
                try:
                    stop_server(server)
                except Exception:
                    pass
                return
            else:
                print("Unknown selection")

    # Configure logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    # By default in interactive menu mode we don't want console log output
    # Show console logs only if user requested a log file, set a non-CRITICAL level,
    # or when running non-interactively (so scripts/containers can see logs).
    show_console = False
    if noninteractive:
        show_console = True
    elif log_file:
        show_console = True
    elif log_level and log_level.upper() != "CRITICAL":
        show_console = True

    if show_console:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root_logger.addHandler(sh)

    if log_file:
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setFormatter(fmt)
        root_logger.addHandler(fh)

    # --- Ensure folder exists ---
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        logging.error("Failed to create folder %s: %s", folder, e)
        sys.exit(1)

    # --- Setup FTP user ---
    authorizer = DummyAuthorizer()

    # Password handling: use provided password, environment variable, or generate a secure one
    if not password:
        # generate a secure random password for short-lived/test runs
        password = secrets.token_urlsafe(12)
        logging.warning("No password supplied via prompt or $FTP_PASS; a temporary password was generated. Change it for production.")

    authorizer.add_user(username, password, folder, perm="elradfmwMT")

    # Use plain FTPHandler (TLS/passive-port support removed)
    handler = FTPHandler
    handler.authorizer = authorizer

    # --- Determine IP ---
    local_ip = get_local_ip()
    all_ips = get_all_local_ips()

    # --- Display info ---
    logging.info("FTP server configured to bind %s:%d", host, port)
    logging.info("Recommended access (on this host): ftp://%s:%d", local_ip, port)
    logging.info("Detected local IPs: %s", ", ".join(all_ips))
    logging.info("Sharing folder: %s", folder)
    logging.info("Username: %s", username)

    # Also print concise info to console so users can easily copy/paste from cmd
    try:
        # Primary outbound IP (single) and core connection info in simple lines
        print(f"ip: {local_ip}")
        print(f"port: {port}")
        print(f"username: {username}")
        print(f"password: {password}")
        # Print all detected local IPs too (comma-separated)
        print("all_ips: ", ", ".join(all_ips))
    except Exception:
        pass

    # --- Start server ---
    # Create and run server
    server = FTPServer((host, port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down server")


if __name__ == "__main__":
    main()
