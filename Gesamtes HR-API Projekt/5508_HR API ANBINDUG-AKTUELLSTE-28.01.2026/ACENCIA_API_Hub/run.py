import socket
import os
import sys
from waitress import serve
from acencia_hub.app import app
from acencia_hub import updater

def print_access_urls(port):
    """
    Detects and prints the URLs that can be used to access the application.
    """
    # Header
    print("\n[INFO] Acencia Hub is starting...")
    print("[INFO] You can access the application at the following addresses:")

    # Standard localhost addresses
    localhost_url = f"http://localhost:{port}"
    ip_127_url = f"http://127.0.0.1:{port}"
    print(f"    --> {localhost_url}")
    print(f"    --> {ip_127_url}")

    # Attempt to find all non-local IP addresses
    try:
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]

        # Filter out loopback addresses and add other IPs
        network_ips_found = False
        for ip in ip_addresses:
            if not ip.startswith("127."):
                network_url = f"http://{ip}:{port}"
                print(f"    --> {network_url} (for other devices on the same network)")
                network_ips_found = True

        if not network_ips_found:
             print("[INFO] No external network IP addresses found. The server might only be accessible from this computer.")

    except socket.gaierror:
        # This can happen on machines with unusual network configurations (e.g., no network connection)
        print("[WARN] Could not automatically determine network IP address due to a hostname lookup error.")

    print("\n[INFO] Press CTRL+C in this window to stop the server.")
    print("-" * 60)


if __name__ == '__main__':
    # --- Attempt to run the self-updater first ---
    print("[INFO] Checking for updates before starting the server...")
    try:
        updater.run_update()
    except Exception as e:
        print(f"[ERROR] The update process failed with an unexpected error: {e}", file=sys.stderr)
        print("[WARN] Continuing with the current version...")
    print("-" * 60)
    # --- Update check finished ---

    host = '0.0.0.0'
    port = 5001

    # Print the informational URLs before starting the server
    print_access_urls(port)

    # Start the production server
    serve(app, host=host, port=port)
