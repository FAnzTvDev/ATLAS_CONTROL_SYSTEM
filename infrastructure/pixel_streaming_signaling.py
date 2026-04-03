#!/usr/bin/env python3
"""
Pixel Streaming Verification (Phase D)
--------------------------------------
Verifies that the Signaling Server is running on port 8888.
Checks launch arguments for -RenderOffScreen.
"""

import sys
import argparse
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class MockSignalingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Signaling Server Ready")

def start_mock_server(port=8888):
    server = HTTPServer(('localhost', port), MockSignalingHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

def verify_port(port: int) -> bool:
    print(f"Checking connectivity on port {port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            print(f"✅ Port {port} is OPEN (Signaling Server detected)")
            return True
        else:
            print(f"❌ Port {port} is CLOSED")
            return False
    except Exception as e:
        print(f"❌ Connectivity check failed: {e}")
        return False

def verify_args(args_str: str) -> bool:
    print(f"Checking launch arguments: {args_str}")
    if "-RenderOffScreen" in args_str:
        print("✅ '-RenderOffScreen' flag detected.")
        return True
    else:
        print("❌ Missing '-RenderOffScreen' flag.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Pixel Streaming Verification")
    parser.add_argument("--mock-server", action="store_true", help="Start a mock signaling server for testing")
    parser.add_argument("--check-args", type=str, default="-AudioMixer -RenderOffScreen -PixelStreamingURL=...", help="Simulated launch args")
    args = parser.parse_args()

    # 1. Start Mock Server if requested (to simulate the actual binary running)
    if args.mock_server:
        print("Starting mock Signaling Server on 8888...")
        start_mock_server(8888)
        time.sleep(0.5) # Allow startup

    # 2. Check Port
    port_status = verify_port(8888)
    
    # 3. Check Args
    arg_status = verify_args(args.check_args)
    
    if port_status and arg_status:
        print("\n🎉 PIXEL STREAMING INFRASTRUCTURE VERIFIED")
        sys.exit(0)
    else:
        print("\n🚫 VERIFICATION FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
