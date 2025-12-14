#!/usr/bin/env python3
"""
Signal Viewer Pro - Application Launcher
=========================================

This is the entry point for the PyInstaller executable.
It handles proper path setup for both development and packaged modes.
"""

import sys
import os
import webbrowser
import threading
import time

def get_base_path():
    """Get the base path for the application."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys._MEIPASS
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def setup_environment():
    """Setup the environment for the application."""
    base_path = get_base_path()
    
    # Add base path to Python path for imports
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    # Change to base directory so relative paths work
    os.chdir(base_path)
    
    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.join(base_path, 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    return base_path

def open_browser(port):
    """Open the default browser after a short delay."""
    time.sleep(1.5)  # Wait for server to start
    webbrowser.open(f'http://127.0.0.1:{port}')

def main():
    """Main entry point for the application."""
    print("=" * 60)
    print("  Signal Viewer Pro - Starting...")
    print("=" * 60)
    
    # Setup environment
    base_path = setup_environment()
    print(f"  Base path: {base_path}")
    
    # Import the app after environment is setup
    try:
        from app import SignalViewerApp
        from config import APP_HOST, APP_PORT
    except ImportError as e:
        print(f"Error importing application: {e}")
        print("Please ensure all dependencies are installed.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Create and configure the app
    viewer = SignalViewerApp()
    
    print(f"  Server: http://{APP_HOST}:{APP_PORT}")
    print("=" * 60)
    print("  Opening browser automatically...")
    print("  Close this window or press Ctrl+C to stop the server.")
    print("=" * 60)
    
    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(APP_PORT,), daemon=True)
    browser_thread.start()
    
    # Run the server - use viewer.app.run_server() for Dash apps
    try:
        viewer.app.run_server(debug=False, port=APP_PORT, host=APP_HOST)
    except KeyboardInterrupt:
        print("\n  Server stopped by user.")
    except Exception as e:
        print(f"\n  Error running server: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()
