"""
Signal Viewer Pro v4.0
======================
A modern, fast, user-friendly signal visualization application.

Features:
- Multi-CSV loading with auto-format detection
- Interactive time cursor with synchronized values
- Multi-subplot grid layouts
- Dark/Light theme support
- Session save/load
- Offline operation

Usage:
    python app.py

Author: Signal Viewer Team
Version: 4.0
"""

import dash
import dash_bootstrap_components as dbc
import webbrowser
import threading
import time

from config import APP_TITLE, APP_VERSION, APP_HOST, APP_PORT
from layout import create_layout
from callbacks import register_callbacks, register_clientside_callbacks


def create_app() -> dash.Dash:
    """Create and configure the Dash application."""
    
    # Initialize Dash app with Bootstrap theme
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
        ],
        title=APP_TITLE,
        update_title=None,  # Disable "Updating..." title
        suppress_callback_exceptions=True,
    )
    
    # Set layout
    app.layout = create_layout()
    
    # Register callbacks
    register_callbacks(app)
    register_clientside_callbacks(app)
    
    return app


def open_browser():
    """Open browser after a short delay."""
    time.sleep(1)
    webbrowser.open(f"http://{APP_HOST}:{APP_PORT}")


def main():
    """Main entry point."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📊 {APP_TITLE} v{APP_VERSION}                              ║
║                                                              ║
║   A modern signal visualization application                  ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   Starting server at: http://{APP_HOST}:{APP_PORT}             ║
║                                                              ║
║   Press Ctrl+C to stop                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app = create_app()
    
    # Open browser in separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    app.run(
        host=APP_HOST,
        port=APP_PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()

