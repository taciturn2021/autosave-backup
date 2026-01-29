#!/usr/bin/env python3

import json
import os
import shutil
import threading
import time
import zipfile
import sys
from datetime import datetime
from pathlib import Path
from tkinter import (
    END, DISABLED, NORMAL, VERTICAL, WORD, Tk, StringVar, IntVar, 
    Frame, Label, Entry, Button, OptionMenu, Scrollbar, Text,
    filedialog, messagebox, ttk
)


# ============================================================================
# Configuration & Constants
# ============================================================================

CONFIG_FILE = "profiles.json"
DEFAULT_INTERVAL = 60  # seconds
DEFAULT_MAX_BACKUPS = 100


def get_config_path():
    """Get the path to the config file (same directory as the script/exe)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys.executable).parent / CONFIG_FILE
    else:
        # Running as script
        return Path(__file__).parent / CONFIG_FILE


# ============================================================================
# Profile Manager
# ============================================================================

class ProfileManager:
    """Handles loading, saving, and managing game profiles."""
    
    def __init__(self):
        self.profiles = {}
        self.settings = {
            "backup_interval": DEFAULT_INTERVAL,
            "max_backups": DEFAULT_MAX_BACKUPS
        }
        self.load()
    
    def load(self):
        """Load profiles from JSON file."""
        config_path = get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = data.get("profiles", {})
                    self.settings = data.get("settings", self.settings)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                self.profiles = {}
    
    def save(self):
        """Save profiles to JSON file."""
        config_path = get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "profiles": self.profiles,
                    "settings": self.settings
                }, f, indent=2)
        except IOError as e:
            print(f"Error saving config: {e}")
    
    def get_profile(self, name):
        """Get a profile by name."""
        return self.profiles.get(name, {"source": "", "destination": ""})
    
    def set_profile(self, name, source, destination):
        """Create or update a profile."""
        self.profiles[name] = {
            "source": source,
            "destination": destination
        }
        self.save()
    
    def delete_profile(self, name):
        """Delete a profile by name."""
        if name in self.profiles:
            del self.profiles[name]
            self.save()
    
    def get_profile_names(self):
        """Get list of all profile names."""
        return list(self.profiles.keys())
    
    def get_interval(self):
        """Get backup interval in seconds."""
        return self.settings.get("backup_interval", DEFAULT_INTERVAL)
    
    def set_interval(self, seconds):
        """Set backup interval in seconds."""
        self.settings["backup_interval"] = max(5, int(seconds))
        self.save()
    
    def get_max_backups(self):
        """Get maximum number of backups to keep."""
        return self.settings.get("max_backups", DEFAULT_MAX_BACKUPS)
    
    def set_max_backups(self, count):
        """Set maximum number of backups to keep."""
        self.settings["max_backups"] = max(1, int(count))
        self.save()


# ============================================================================
# Backup Service
# ============================================================================

class BackupService:
    """Handles the backup operations in a background thread."""
    
    def __init__(self, log_callback):
        self.log = log_callback
        self.running = False
        self.thread = None
        self.source_path = ""
        self.dest_path = ""
        self.interval = DEFAULT_INTERVAL
        self.max_backups = DEFAULT_MAX_BACKUPS
        self._stop_event = threading.Event()
        self._backup_now_event = threading.Event()
    
    def start(self, source, destination, interval, max_backups):
        """Start the backup service."""
        if self.running:
            return False
        
        self.source_path = source
        self.dest_path = destination
        self.interval = interval
        self.max_backups = max_backups
        
        # Validate paths
        if not os.path.isdir(source):
            self.log(f"ERROR: Source folder does not exist: {source}")
            return False
        
        if not os.path.isdir(destination):
            try:
                os.makedirs(destination, exist_ok=True)
                self.log(f"Created destination folder: {destination}")
            except OSError as e:
                self.log(f"ERROR: Cannot create destination folder: {e}")
                return False
        
        self._stop_event.clear()
        self._backup_now_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        self.log(f"Backup service STARTED")
        self.log(f"  Source: {source}")
        self.log(f"  Destination: {destination}")
        self.log(f"  Interval: {interval} seconds")
        self.log(f"  Max backups: {max_backups}")
        
        return True
    
    def stop(self):
        """Stop the backup service."""
        if not self.running:
            return
        
        self._stop_event.set()
        self._backup_now_event.set()  # Wake up the thread if waiting
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
        
        self.log("Backup service STOPPED")
    
    def backup_now(self):
        """Trigger an immediate backup."""
        if self.running:
            self._backup_now_event.set()
    
    def _run(self):
        """Background thread loop."""
        while not self._stop_event.is_set():
            # Perform backup
            self._perform_backup()
            
            # Wait for interval or stop signal
            self.log(f"Waiting {self.interval} seconds until next backup...")
            
            # Wait with the ability to be interrupted
            wait_start = time.time()
            while time.time() - wait_start < self.interval:
                if self._stop_event.is_set():
                    return
                if self._backup_now_event.is_set():
                    self._backup_now_event.clear()
                    self.log("Manual backup triggered!")
                    break
                time.sleep(0.5)
    
    def _perform_backup(self):
        """Create a backup zip file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"save_backup_{timestamp}.zip"
        zip_path = os.path.join(self.dest_path, zip_name)
        
        try:
            # Create zip archive
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                source_path = Path(self.source_path)
                for file in source_path.rglob('*'):
                    if file.is_file():
                        try:
                            arcname = file.relative_to(source_path)
                            zf.write(file, arcname)
                        except PermissionError:
                            self.log(f"  WARNING: Permission denied for {file.name} (file might be locked)")
                        except Exception as e:
                            self.log(f"  WARNING: Could not add {file.name}: {e}")
            
            self.log(f"Backup created: {zip_name}")
            
            # Rotate old backups
            self._rotate_backups()
            
        except PermissionError as e:
            self.log(f"ERROR: Permission denied - {e}")
        except Exception as e:
            self.log(f"ERROR: Backup failed - {e}")
    
    def _rotate_backups(self):
        """Delete oldest backup if over the limit (one at a time)."""
        try:
            # Get all backup files
            backup_files = []
            for f in os.listdir(self.dest_path):
                if f.startswith("save_backup_") and f.endswith(".zip"):
                    full_path = os.path.join(self.dest_path, f)
                    backup_files.append((f, os.path.getmtime(full_path)))
            
            # Sort by modification time (oldest first)
            backup_files.sort(key=lambda x: x[1])
            
            # Delete only ONE oldest backup if over limit (gradual deletion)
            if len(backup_files) > self.max_backups:
                oldest = backup_files[0]
                oldest_path = os.path.join(self.dest_path, oldest[0])
                os.remove(oldest_path)
                self.log(f"  Rotated out old backup: {oldest[0]}")
                
        except Exception as e:
            self.log(f"  WARNING: Backup rotation failed - {e}")


# ============================================================================
# Main Application GUI
# ============================================================================

class AutoSaveManagerApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AutoSave Manager")
        self.root.geometry("650x550")
        self.root.minsize(550, 450)
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Initialize managers
        self.profile_manager = ProfileManager()
        self.backup_service = BackupService(self.log_message)
        
        # Variables
        self.current_profile = StringVar(value="")
        self.source_path = StringVar(value="")
        self.dest_path = StringVar(value="")
        self.interval_var = IntVar(value=self.profile_manager.get_interval())
        self.max_backups_var = IntVar(value=self.profile_manager.get_max_backups())
        self.is_running = False
        self._loading_profile = False  # Flag to prevent auto-save during profile load
        
        # Build UI
        self._create_widgets()
        
        # Set up auto-save traces (after widgets are created)
        self.source_path.trace_add('write', self._auto_save_profile)
        self.dest_path.trace_add('write', self._auto_save_profile)
        self.interval_var.trace_add('write', self._auto_save_settings)
        self.max_backups_var.trace_add('write', self._auto_save_settings)
        
        # Load first profile if available
        profiles = self.profile_manager.get_profile_names()
        if profiles:
            self.current_profile.set(profiles[0])
            self._on_profile_change()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """Create all UI widgets."""
        main_frame = Frame(self.root, padx=15, pady=15)
        main_frame.pack(fill='both', expand=True)
        
        # === Profile Section ===
        profile_frame = ttk.LabelFrame(main_frame, text="Profile", padding=10)
        profile_frame.pack(fill='x', pady=(0, 10))
        
        # Profile dropdown row
        profile_row = Frame(profile_frame)
        profile_row.pack(fill='x', pady=(0, 5))
        
        Label(profile_row, text="Select Profile:", width=12, anchor='w').pack(side='left')
        
        self.profile_menu = ttk.Combobox(
            profile_row, 
            textvariable=self.current_profile,
            state='readonly',
            width=25
        )
        self.profile_menu.pack(side='left', padx=(0, 10))
        self.profile_menu.bind('<<ComboboxSelected>>', lambda e: self._on_profile_change())
        self._update_profile_menu()
        
        self.new_profile_btn = ttk.Button(profile_row, text="New Profile", command=self._new_profile)
        self.new_profile_btn.pack(side='left', padx=2)
        self.edit_profile_btn = ttk.Button(profile_row, text="Edit Profile", command=self._rename_profile)
        self.edit_profile_btn.pack(side='left', padx=2)
        self.delete_profile_btn = ttk.Button(profile_row, text="Delete Profile", command=self._delete_profile)
        self.delete_profile_btn.pack(side='left', padx=2)
        
        # === Paths Section ===
        paths_frame = ttk.LabelFrame(main_frame, text="Paths", padding=10)
        paths_frame.pack(fill='x', pady=(0, 10))
        
        # Source path row
        source_row = Frame(paths_frame)
        source_row.pack(fill='x', pady=(0, 5))
        
        Label(source_row, text="Source Folder:", width=14, anchor='w').pack(side='left')
        self.source_entry = Entry(source_row, textvariable=self.source_path, width=45)
        self.source_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.source_browse_btn = ttk.Button(source_row, text="Browse", command=self._browse_source)
        self.source_browse_btn.pack(side='left')
        
        # Destination path row
        dest_row = Frame(paths_frame)
        dest_row.pack(fill='x')
        
        Label(dest_row, text="Backup Folder:", width=14, anchor='w').pack(side='left')
        self.dest_entry = Entry(dest_row, textvariable=self.dest_path, width=45)
        self.dest_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.dest_browse_btn = ttk.Button(dest_row, text="Browse", command=self._browse_dest)
        self.dest_browse_btn.pack(side='left')
        
        # === Settings Section ===
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.pack(fill='x', pady=(0, 10))
        
        settings_row = Frame(settings_frame)
        settings_row.pack(fill='x')
        
        Label(settings_row, text="Backup Interval (seconds):").pack(side='left')
        self.interval_entry = ttk.Spinbox(
            settings_row, 
            textvariable=self.interval_var, 
            from_=5, to=3600, 
            width=8
        )
        self.interval_entry.pack(side='left', padx=(5, 20))
        
        Label(settings_row, text="Max Backups to Keep:").pack(side='left')
        self.max_backups_entry = ttk.Spinbox(
            settings_row, 
            textvariable=self.max_backups_var, 
            from_=1, to=1000, 
            width=8
        )
        self.max_backups_entry.pack(side='left', padx=(5, 10))
        
        # === Control Section ===
        control_frame = Frame(main_frame)
        control_frame.pack(fill='x', pady=(0, 10))
        
        self.toggle_btn = Button(
            control_frame,
            text="▶ START BACKUP SERVICE",
            command=self._toggle_service,
            bg='#28a745',
            fg='white',
            font=('Segoe UI', 12, 'bold'),
            height=2,
            cursor='hand2'
        )
        self.toggle_btn.pack(fill='x', pady=(0, 5))
        
        self.backup_now_btn = ttk.Button(
            control_frame,
            text="📷 Create Backup Now",
            command=self._backup_now,
            state=DISABLED
        )
        self.backup_now_btn.pack(fill='x')
        
        # === Log Section ===
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding=10)
        log_frame.pack(fill='both', expand=True)
        
        # Log text with scrollbar
        log_container = Frame(log_frame)
        log_container.pack(fill='both', expand=True)
        
        scrollbar = Scrollbar(log_container, orient=VERTICAL)
        scrollbar.pack(side='right', fill='y')
        
        self.log_text = Text(
            log_container,
            height=10,
            wrap=WORD,
            yscrollcommand=scrollbar.set,
            state=DISABLED,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#d4d4d4'
        )
        self.log_text.pack(fill='both', expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Initial log message
        self.log_message("AutoSave Manager initialized. Select or create a profile to begin.")
    
    def _update_profile_menu(self):
        """Update the profile dropdown menu."""
        profiles = self.profile_manager.get_profile_names()
        self.profile_menu['values'] = profiles if profiles else ["(No profiles)"]
    
    def _on_profile_change(self, *args):
        """Handle profile selection change."""
        name = self.current_profile.get()
        if name and name != "(No profiles)":
            self._loading_profile = True  # Prevent auto-save while loading
            profile = self.profile_manager.get_profile(name)
            self.source_path.set(profile.get("source", ""))
            self.dest_path.set(profile.get("destination", ""))
            self._loading_profile = False
            self.log_message(f"Loaded profile: {name}")
    
    def _new_profile(self):
        """Create a new profile."""
        from tkinter import simpledialog
        name = simpledialog.askstring("New Profile", "Enter profile name:", parent=self.root)
        if name:
            name = name.strip()
            if name:
                self.profile_manager.set_profile(name, "", "")
                self._update_profile_menu()
                self.current_profile.set(name)
                self.source_path.set("")
                self.dest_path.set("")
                self.log_message(f"Created new profile: {name}")
    
    def _delete_profile(self):
        """Delete the current profile."""
        name = self.current_profile.get()
        if name and name != "(No profiles)":
            if messagebox.askyesno("Delete Profile", f"Are you sure you want to delete '{name}'?"):
                self.profile_manager.delete_profile(name)
                self._update_profile_menu()
                
                profiles = self.profile_manager.get_profile_names()
                if profiles:
                    self.current_profile.set(profiles[0])
                    self._on_profile_change()
                else:
                    self.current_profile.set("")
                    self.source_path.set("")
                    self.dest_path.set("")
                
                self.log_message(f"Deleted profile: {name}")
    
    def _rename_profile(self):
        """Rename the current profile."""
        old_name = self.current_profile.get()
        if not old_name or old_name == "(No profiles)":
            messagebox.showwarning("No Profile", "Please select a profile to rename.")
            return
        
        from tkinter import simpledialog
        new_name = simpledialog.askstring(
            "Rename Profile", 
            f"Enter new name for '{old_name}':",
            initialvalue=old_name,
            parent=self.root
        )
        
        if new_name and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            # Get the old profile data
            profile = self.profile_manager.get_profile(old_name)
            # Create new profile with same data
            self.profile_manager.set_profile(new_name, profile.get("source", ""), profile.get("destination", ""))
            # Delete old profile
            self.profile_manager.delete_profile(old_name)
            # Update UI
            self._update_profile_menu()
            self.current_profile.set(new_name)
            self.log_message(f"Renamed profile: {old_name} -> {new_name}")
    
    def _auto_save_profile(self, *args):
        """Auto-save profile when paths change."""
        if self._loading_profile:
            return
        name = self.current_profile.get()
        if name and name != "(No profiles)":
            self.profile_manager.set_profile(
                name,
                self.source_path.get(),
                self.dest_path.get()
            )
    
    def _auto_save_settings(self, *args):
        """Auto-save settings when they change."""
        try:
            new_max = self.max_backups_var.get()
            current_max = self.profile_manager.get_max_backups()
            
            # Check if lowering max_backups and show confirmation
            if new_max < current_max:
                # Count existing backups in the backup folder if a profile is selected
                name = self.current_profile.get()
                if name and name != "(No profiles)":
                    dest = self.dest_path.get().strip()
                    if dest and os.path.isdir(dest):
                        backup_count = len([f for f in os.listdir(dest) 
                                          if f.startswith("save_backup_") and f.endswith(".zip")])
                        if backup_count > new_max:
                            excess = backup_count - new_max
                            if not messagebox.askyesno(
                                "Confirm Setting Change",
                                f"You have {backup_count} backups. Lowering to {new_max} will gradually delete {excess} old backup(s) (one per backup cycle).\n\nContinue?"
                            ):
                                # Revert to old value
                                self._loading_profile = True
                                self.max_backups_var.set(current_max)
                                self._loading_profile = False
                                return
            
            self.profile_manager.set_interval(self.interval_var.get())
            self.profile_manager.set_max_backups(new_max)
        except Exception:
            pass  # Ignore errors during typing (e.g., empty field)
    
    def _browse_source(self):
        """Open folder browser for source path."""
        folder = filedialog.askdirectory(title="Select Game Save Folder")
        if folder:
            self.source_path.set(folder)
    
    def _browse_dest(self):
        """Open folder browser for destination path."""
        folder = filedialog.askdirectory(title="Select Backup Destination Folder")
        if folder:
            self.dest_path.set(folder)
    
    def _toggle_service(self):
        """Toggle the backup service on/off."""
        if self.is_running:
            self._stop_service()
        else:
            self._start_service()
    
    def _start_service(self):
        """Start the backup service."""
        source = self.source_path.get().strip()
        dest = self.dest_path.get().strip()
        
        if not source or not dest:
            messagebox.showwarning("Missing Paths", "Please set both Source and Backup folders.")
            return
        
        # Validate settings
        try:
            interval = self.interval_var.get()
            if interval < 5:
                messagebox.showwarning("Invalid Settings", "Backup interval must be at least 5 seconds.")
                return
        except Exception:
            messagebox.showwarning("Invalid Settings", "Please enter a valid backup interval.")
            return
        
        try:
            max_backups = self.max_backups_var.get()
            if max_backups < 1:
                messagebox.showwarning("Invalid Settings", "Max backups must be at least 1.")
                return
        except Exception:
            messagebox.showwarning("Invalid Settings", "Please enter a valid max backups value.")
            return
        
        success = self.backup_service.start(
            source,
            dest,
            interval,
            max_backups
        )
        
        if success:
            self.is_running = True
            self.toggle_btn.config(
                text="■ STOP BACKUP SERVICE",
                bg='#dc3545'
            )
            self.backup_now_btn.config(state=NORMAL)
            self._set_controls_state(DISABLED)
    
    def _stop_service(self):
        """Stop the backup service."""
        self.backup_service.stop()
        self.is_running = False
        self.toggle_btn.config(
            text="▶ START BACKUP SERVICE",
            bg='#28a745'
        )
        self.backup_now_btn.config(state=DISABLED)
        self._set_controls_state(NORMAL)
    
    def _set_controls_state(self, state):
        """Enable or disable controls that shouldn't be changed while running."""
        # Profile controls
        self.profile_menu.config(state='readonly' if state == NORMAL else DISABLED)
        self.new_profile_btn.config(state=state)
        self.edit_profile_btn.config(state=state)
        self.delete_profile_btn.config(state=state)
        # Path controls
        self.source_entry.config(state=state)
        self.dest_entry.config(state=state)
        self.source_browse_btn.config(state=state)
        self.dest_browse_btn.config(state=state)
        # Settings controls
        self.interval_entry.config(state=state)
        self.max_backups_entry.config(state=state)
    
    def _backup_now(self):
        """Trigger an immediate backup."""
        if self.is_running:
            self.backup_service.backup_now()
    
    def log_message(self, message):
        """Add a message to the log window (thread-safe)."""
        def _log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.config(state=NORMAL)
            self.log_text.insert(END, f"[{timestamp}] {message}\n")
            self.log_text.see(END)
            self.log_text.config(state=DISABLED)
        
        # Schedule on main thread if called from background thread
        self.root.after(0, _log)
    
    def _on_close(self):
        """Handle window close event."""
        if self.is_running:
            self.backup_service.stop()
        self.root.destroy()


# ============================================================================
# Entry Point
# ============================================================================

import sys

if __name__ == "__main__":
    root = Tk()
    app = AutoSaveManagerApp(root)
    root.mainloop()
