"""
Signal Viewer Pro - Entry Point
================================
Run this file to start the application.

Usage:
    python run.py

Then open http://127.0.0.1:8050 in your browser.
"""

import webbrowser
import threading
import time


def open_browser():
    """Open browser after a short delay"""
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8050")


if __name__ == "__main__":
    # Start browser opener in background
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Import and run app
    from app import app, APP_HOST, APP_PORT, APP_TITLE
    
    print(f"\n{'='*50}")
    print(f"  {APP_TITLE}")
    print(f"  Open: http://{APP_HOST}:{APP_PORT}")
    print(f"{'='*50}\n")
    
    app.run_server(
        host=APP_HOST,
        port=APP_PORT,
        debug=False,
    )
