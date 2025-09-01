import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import winreg

# --- Configuration ---
SETTINGS_SECTION = "playstation_vr2_ex"

class Psvr2SettingsEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lazy PSVR2Toolkit Settings Editor")
        self.geometry("520x210")

        self.vrsettings_path = None
        self.settings_data = {}

        # --- UI Variables ---
        self.disable_chaperone_var = tk.BooleanVar()
        self.disable_overlay_var = tk.BooleanVar()
        self.disable_dialog_var = tk.BooleanVar()
        self.disable_sense_var = tk.BooleanVar()
        self.disable_gaze_var = tk.BooleanVar()

        self.init_ui()
        self.load_path_and_settings()

    def find_steam_path(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            winreg.CloseKey(key)
            return steam_path
        except Exception:
            return None

    def get_vrsettings_path(self):
        steam_path = self.find_steam_path()
        if steam_path:
            config_path = os.path.join(steam_path, "config", "steamvr.vrsettings")
            if os.path.exists(config_path):
                return config_path
        return None

    def load_vrsettings(self):
        if not self.vrsettings_path or not os.path.exists(self.vrsettings_path):
            messagebox.showerror("Error", f"File not found: {self.vrsettings_path}")
            return None
        try:
            with open(self.vrsettings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Error parsing steamvr.vrsettings.\nThis can happen if the file is corrupted.\n\nDetails: {e}")
            return None
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred while reading the file: {e}")
            return None

    def save_vrsettings(self):
        if not self.vrsettings_path:
            messagebox.showerror("Error", "Settings file path is not set.")
            return

        full_data = self.load_vrsettings()
        if full_data is None:
            return

        if SETTINGS_SECTION not in full_data:
            full_data[SETTINGS_SECTION] = {}
        
        psvr_settings = full_data[SETTINGS_SECTION]

        psvr_settings["disableChaperone"] = self.disable_chaperone_var.get()
        psvr_settings["disableOverlay"] = self.disable_overlay_var.get()
        psvr_settings["disableDialog"] = self.disable_dialog_var.get()
        psvr_settings["disableSense"] = self.disable_sense_var.get()
        psvr_settings["disableGaze"] = self.disable_gaze_var.get()
        
        # Remove unsupported setting if it exists.
        psvr_settings.pop("enableHDR10", None)

        full_data[SETTINGS_SECTION] = psvr_settings

        try:
            with open(self.vrsettings_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_path_and_settings(self):
        self.vrsettings_path = self.get_vrsettings_path()
        if not self.vrsettings_path:
            messagebox.showinfo("Information", "Could not automatically find steamvr.vrsettings. Please locate it manually.")
            self.vrsettings_path = filedialog.askopenfilename(
                title="Select steamvr.vrsettings",
                filetypes=(("VR Settings", "*.vrsettings"), ("All files", "*.*"))
            )
        
        if not self.vrsettings_path:
            self.destroy()
            return
            
        self.path_label.config(text=f"Editing: {self.vrsettings_path}")
        self.settings_data = self.load_vrsettings()
        
        if self.settings_data is None:
            self.destroy()
            return
            
        self.load_settings_into_ui()

    def load_settings_into_ui(self):
        psvr_settings = self.settings_data.get(SETTINGS_SECTION, {})
        
        # Default to False (unchecked) if a setting is not in the file.
        self.disable_chaperone_var.set(psvr_settings.get("disableChaperone", False))
        self.disable_overlay_var.set(psvr_settings.get("disableOverlay", False))
        self.disable_dialog_var.set(psvr_settings.get("disableDialog", False))
        self.disable_sense_var.set(psvr_settings.get("disableSense", False))
        self.disable_gaze_var.set(psvr_settings.get("disableGaze", False))

    def init_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))
        self.path_label = ttk.Label(top_frame, text="Locating steamvr.vrsettings...", wraplength=420, anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True, padx=(0, 10))
        save_button = ttk.Button(top_frame, text="Save Settings", command=self.save_vrsettings)
        save_button.pack(side="right")
        
        general_frame = ttk.LabelFrame(main_frame, text="General Settings", padding="10")
        general_frame.pack(fill="x", expand=True, pady=5)
        
        checkbox_frame = ttk.Frame(general_frame)
        checkbox_frame.pack(pady=5)
        
        ttk.Checkbutton(checkbox_frame, text="Disable Chaperone", variable=self.disable_chaperone_var).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        ttk.Checkbutton(checkbox_frame, text="Disable Overlay", variable=self.disable_overlay_var).grid(row=0, column=1, sticky='w', padx=10, pady=5)
        ttk.Checkbutton(checkbox_frame, text="Disable Dialog", variable=self.disable_dialog_var).grid(row=1, column=0, sticky='w', padx=10, pady=5)
        ttk.Checkbutton(checkbox_frame, text="Disable Sense Haptics", variable=self.disable_sense_var).grid(row=1, column=1, sticky='w', padx=10, pady=5)
        ttk.Checkbutton(checkbox_frame, text="Disable Gaze", variable=self.disable_gaze_var).grid(row=2, column=0, sticky='w', padx=10, pady=5)

if __name__ == "__main__":
    app = Psvr2SettingsEditor()
    app.mainloop()