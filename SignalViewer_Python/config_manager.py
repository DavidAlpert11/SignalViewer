"""
ConfigManager - Handles configuration and session management
"""
import json
import os
from typing import Dict, Optional
from datetime import datetime


class ConfigManager:
    """Manages application configuration and sessions"""
    
    def __init__(self, app):
        self.app = app
        self.config_file = "signal_viewer_config.json"
        self.sessions_dir = "sessions"
        self.templates_dir = "templates"
        
        # Create directories
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
    
    def save_config(self, config: Dict):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load_config(self) -> Optional[Dict]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        return None
    
    def save_session(self, session_name: str) -> bool:
        """Save current session"""
        try:
            session_data = {
                'timestamp': datetime.now().isoformat(),
                'csv_file_paths': self.app.data_manager.csv_file_paths,
                'signal_assignments': self.app.plot_manager.assigned_signals,
                'signal_scaling': self.app.data_manager.signal_scaling,
                'state_signals': self.app.data_manager.state_signals,
                'derived_signals': list(self.app.signal_operations.derived_signals.keys()),
                'current_tab': self.app.plot_manager.current_tab_idx,
                'current_subplot': self.app.plot_manager.selected_subplot_idx,
            }
            
            session_file = os.path.join(self.sessions_dir, f"{session_name}.json")
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def load_session(self, session_name: str) -> bool:
        """Load session"""
        try:
            session_file = os.path.join(self.sessions_dir, f"{session_name}.json")
            if not os.path.exists(session_file):
                return False
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Restore CSV file paths
            self.app.data_manager.csv_file_paths = session_data.get('csv_file_paths', [])
            self.app.data_manager.data_tables = [None] * len(self.app.data_manager.csv_file_paths)
            
            # Load data
            self.app.data_manager.load_data_once()
            
            # Restore signal assignments
            self.app.plot_manager.assigned_signals = session_data.get('signal_assignments', [])
            
            # Restore scaling and state
            self.app.data_manager.signal_scaling = session_data.get('signal_scaling', {})
            self.app.data_manager.state_signals = session_data.get('state_signals', {})
            
            # Restore current tab/subplot
            self.app.plot_manager.current_tab_idx = session_data.get('current_tab', 0)
            self.app.plot_manager.selected_subplot_idx = session_data.get('current_subplot', 0)
            
            # Refresh plots
            self.app.plot_manager.refresh_plots()
            
            return True
        except Exception as e:
            print(f"Error loading session: {e}")
            return False
    
    def list_sessions(self) -> list:
        """List available sessions"""
        sessions = []
        if os.path.exists(self.sessions_dir):
            for filename in os.listdir(self.sessions_dir):
                if filename.endswith('.json'):
                    sessions.append(filename[:-5])  # Remove .json extension
        return sorted(sessions)
    
    def save_template(self, template_name: str, template_data: Dict) -> bool:
        """Save template"""
        try:
            template_file = os.path.join(self.templates_dir, f"{template_name}.json")
            with open(template_file, 'w') as f:
                json.dump(template_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving template: {e}")
            return False
    
    def load_template(self, template_name: str) -> Optional[Dict]:
        """Load template"""
        try:
            template_file = os.path.join(self.templates_dir, f"{template_name}.json")
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading template: {e}")
        return None

