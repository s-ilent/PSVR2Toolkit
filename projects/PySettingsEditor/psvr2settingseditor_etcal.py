import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Toplevel, Text
import json
import os
import winreg
import math

# --- Configuration ---
SETTINGS_SECTION = "playstation_vr2_ex"
CONFIG_SCALE = 100.0
DEFAULT_CALIBRATION_SAMPLES = 32
TAU = 2 * math.pi

# --- Helper function for symmetry detection ---
def check_symmetry(data):
    n = len(data)
    # Symmetry checks are only meaningful for an even number of samples divisible by 4
    if n == 0 or n % 4 != 0:
        return False, False
    
    is_x_sym = True # Top/Bottom symmetry
    is_y_sym = True # Left/Right symmetry

    half = n // 2
    quart = n // 4
    
    # Check X-Symmetry (top half vs bottom half)
    for i in range(1, half):
        if not math.isclose(data[i], data[n - i]):
            is_x_sym = False
            break
    
    # Check Y-Symmetry (right half vs left half)
    for i in range(1, quart + 1):
        # Compare top-right quadrant with top-left quadrant
        if not math.isclose(data[i], data[half - i]):
            is_y_sym = False
            break
        # Compare bottom-right quadrant with bottom-left quadrant
        if not math.isclose(data[n - i], data[half + i]):
            is_y_sym = False
            break
            
    return is_x_sym, is_y_sym


class GazeCalibrationEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PSVR2Toolkit Gaze Calibration Editor")
        self.geometry("900x750")

        self.vrsettings_path = None
        self.settings_data = {}
        self.gaze_data = {}

        self.init_ui()
        self.load_path_and_settings()

    def init_ui(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        top_frame.pack(fill="x")
        self.path_label = ttk.Label(top_frame, text="Locating steamvr.vrsettings...", wraplength=700, anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True, padx=(0, 10))
        save_button = ttk.Button(top_frame, text="Save Settings", command=self.save_vrsettings)
        save_button.pack(side="right")

        controls_frame = ttk.Frame(self, padding=(10,0,10,0))
        controls_frame.pack(fill="x")

        symmetry_frame = ttk.LabelFrame(controls_frame, text="Symmetry Modes", padding="10")
        symmetry_frame.pack(side="left", pady=10, padx=(0,10), fill="x", expand=True)
        
        self.global_symmetry_var = tk.BooleanVar()
        self.x_symmetry_var = tk.BooleanVar()
        self.y_symmetry_var = tk.BooleanVar()
        
        ttk.Checkbutton(symmetry_frame, text="Edit Both Eyes (Global)", variable=self.global_symmetry_var).pack(side="left", padx=10)
        ttk.Checkbutton(symmetry_frame, text="X-Axis Symmetry (Top/Bottom Mirror)", variable=self.x_symmetry_var).pack(side="left", padx=10)
        ttk.Checkbutton(symmetry_frame, text="Y-Axis Symmetry (Left/Right Mirror)", variable=self.y_symmetry_var).pack(side="left", padx=10)

        reset_frame = ttk.LabelFrame(controls_frame, text="Reset Options", padding="10")
        reset_frame.pack(side="left", pady=10)
        
        ttk.Label(reset_frame, text="Sample Count:").pack(side="left", padx=(0,5))
        self.sample_count_var = tk.StringVar(value=str(DEFAULT_CALIBRATION_SAMPLES))
        # Added '6' to the list of values
        sample_count_combo = ttk.Combobox(reset_frame, textvariable=self.sample_count_var, values=[6, 16, 32, 64], width=5)
        sample_count_combo.pack(side="left")

        content_frame = ttk.Frame(self)
        content_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.left_canvas = self._create_eye_widgets(content_frame, "LeftEye")
        self.right_canvas = self._create_eye_widgets(content_frame, "RightEye")
        
        self.left_canvas.other_canvas = self.right_canvas
        self.right_canvas.other_canvas = self.left_canvas

        close_button = ttk.Button(self, text="Close", command=self.destroy)
        close_button.pack(pady=10)

    def _create_eye_widgets(self, parent, eye):
        eye_frame = ttk.Frame(parent)
        eye_frame.pack(side="left", fill="both", expand=True, padx=10)
        center_frame = ttk.LabelFrame(eye_frame, text=f"{eye} Center Offset", padding=5)
        center_frame.pack(fill="x", pady=(0, 10))
        center_x_var, center_y_var = tk.DoubleVar(), tk.DoubleVar()

        ttk.Label(center_frame, text="X:").grid(row=0, column=0, padx=5)
        center_x_entry = ttk.Entry(center_frame, textvariable=center_x_var, width=10)
        center_x_entry.grid(row=0, column=1, padx=5)
        ttk.Label(center_frame, text="Y:").grid(row=0, column=2, padx=5)
        center_y_entry = ttk.Entry(center_frame, textvariable=center_y_var, width=10)
        center_y_entry.grid(row=0, column=3, padx=5)
        
        update_cmd = lambda e, eye=eye: self._update_center_from_ui(eye)
        center_x_entry.bind("<FocusOut>", update_cmd); center_x_entry.bind("<KeyRelease>", update_cmd)
        center_y_entry.bind("<FocusOut>", update_cmd); center_y_entry.bind("<KeyRelease>", update_cmd)
        
        canvas_frame = ttk.LabelFrame(eye_frame, text="Visual Editor", padding=5)
        canvas_frame.pack(fill="both", expand=True)
        canvas = CalibrationCanvas(canvas_frame, width=400, height=400, data_source=self.gaze_data.get(eye, {}),
                                   global_sym_var=self.global_symmetry_var, x_sym_var=self.x_symmetry_var, y_sym_var=self.y_symmetry_var)
        canvas.pack(fill="both", expand=True)

        button_frame = ttk.Frame(eye_frame)
        button_frame.pack(fill="x", pady=10)
        reset_button = ttk.Button(button_frame, text="Reset to Default", command=lambda eye=eye: self._reset_eye_data(eye))
        reset_button.pack(side="left", padx=5)
        raw_edit_button = ttk.Button(button_frame, text="Raw Edit...", command=lambda eye=eye: RawValuesEditor(self, eye, self.gaze_data[eye], canvas))
        raw_edit_button.pack(side="right", padx=5)
        
        canvas.center_x_var, canvas.center_y_var = center_x_var, center_y_var
        return canvas

    def _update_center_from_ui(self, eye):
        try:
            canvas = self.left_canvas if eye == "LeftEye" else self.right_canvas
            x, y = canvas.center_x_var.get(), canvas.center_y_var.get()
            self.gaze_data[eye]['center'] = [x, y]
            if self.global_symmetry_var.get():
                other_eye = "RightEye" if eye == "LeftEye" else "LeftEye"
                other_canvas = canvas.other_canvas
                if self.gaze_data[other_eye]['center'] != [x, y]:
                    self.gaze_data[other_eye]['center'] = [x, y]
                    other_canvas.center_x_var.set(x)
                    other_canvas.center_y_var.set(y)
        except (tk.TclError, ValueError): pass

    def _load_eye_data_into_ui(self, eye, canvas):
        center = self.gaze_data[eye]['center']
        canvas.center_x_var.set(center[0]); canvas.center_y_var.set(center[1])
        canvas.redraw()
    
    def _reset_eye_data(self, eye):
        try:
            num_samples = int(self.sample_count_var.get())
        except ValueError:
            num_samples = DEFAULT_CALIBRATION_SAMPLES
            self.sample_count_var.set(str(num_samples))

        self.gaze_data[eye] = {'center': [0.0, 0.0], 'calibration': [1.0] * num_samples}
        canvas = self.left_canvas if eye == "LeftEye" else self.right_canvas
        self._load_eye_data_into_ui(eye, canvas)
        if self.global_symmetry_var.get():
            other_eye = "RightEye" if eye == "LeftEye" else "LeftEye"
            other_canvas = self.right_canvas if eye == "LeftEye" else self.left_canvas
            self.gaze_data[other_eye] = {'center': [0.0, 0.0], 'calibration': [1.0] * num_samples}
            self._load_eye_data_into_ui(other_eye, other_canvas)
        
        self._infer_symmetry_modes()


    def _infer_symmetry_modes(self):
        left_cal, right_cal = self.gaze_data['LeftEye']['calibration'], self.gaze_data['RightEye']['calibration']
        is_global_sym = len(left_cal) == len(right_cal) and all(math.isclose(a, b) for a, b in zip(left_cal, right_cal))
        self.global_symmetry_var.set(is_global_sym)
        is_x_sym, is_y_sym = check_symmetry(left_cal)
        self.x_symmetry_var.set(is_x_sym); self.y_symmetry_var.set(is_y_sym)

    def find_steam_path(self):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Valve\Steam") as key:
                return winreg.QueryValueEx(key, "InstallPath")[0]
        except Exception: return None

    def get_vrsettings_path(self):
        steam_path = self.find_steam_path()
        if steam_path:
            config_path = os.path.join(steam_path, "config", "steamvr.vrsettings")
            if os.path.exists(config_path): return config_path
        return None

    def load_vrsettings(self):
        if not self.vrsettings_path or not os.path.exists(self.vrsettings_path):
            messagebox.showerror("Error", f"File not found: {self.vrsettings_path}")
            return None
        try:
            with open(self.vrsettings_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            messagebox.showerror("Error", f"Error parsing steamvr.vrsettings: {e}")
            return None

    def save_vrsettings(self):
        full_data = self.load_vrsettings()
        if full_data is None: return
        psvr_settings = full_data.get(SETTINGS_SECTION, {})
        for eye in ["LeftEye", "RightEye"]:
            center_key, cal_key = f"{eye}_Center", f"{eye}_Calibration"
            center_vals = self.gaze_data[eye]['center']
            cal_vals = self.gaze_data[eye]['calibration']
            psvr_settings[center_key] = f"{center_vals[0] * CONFIG_SCALE:.2f} {center_vals[1] * CONFIG_SCALE:.2f}"
            psvr_settings[cal_key] = " ".join([f"{v * CONFIG_SCALE:.2f}" for v in cal_vals])
        full_data[SETTINGS_SECTION] = psvr_settings
        try:
            with open(self.vrsettings_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=3, sort_keys=True)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_path_and_settings(self):
        self.vrsettings_path = self.get_vrsettings_path()
        if not self.vrsettings_path:
            self.vrsettings_path = filedialog.askopenfilename(title="Select steamvr.vrsettings")
        if not self.vrsettings_path: self.destroy(); return
        self.path_label.config(text=f"Editing: {self.vrsettings_path}")
        self.settings_data = self.load_vrsettings()
        if self.settings_data is None: self.destroy(); return
        self.load_settings_into_ui()

    def load_settings_into_ui(self):
        psvr_settings = self.settings_data.get(SETTINGS_SECTION, {})
        for eye in ["LeftEye", "RightEye"]:
            center_key, cal_key = f"{eye}_Center", f"{eye}_Calibration"
            center_str = psvr_settings.get(center_key, "0.0 0.0")
            center = [float(v) / CONFIG_SCALE for v in center_str.split()]
            cal_str = psvr_settings.get(cal_key, "")
            calibration = [float(v) / CONFIG_SCALE for v in cal_str.split()] if cal_str else [1.0] * DEFAULT_CALIBRATION_SAMPLES
            self.gaze_data[eye] = {"center": center, "calibration": calibration}
        
        self.left_canvas.data_source = self.gaze_data["LeftEye"]
        self.right_canvas.data_source = self.gaze_data["RightEye"]
        
        self._load_eye_data_into_ui("LeftEye", self.left_canvas)
        self._load_eye_data_into_ui("RightEye", self.right_canvas)
        self._infer_symmetry_modes()

class CalibrationCanvas(tk.Canvas):
    def __init__(self, parent, data_source, global_sym_var, x_sym_var, y_sym_var, **kwargs):
        super().__init__(parent, bg="white", **kwargs)
        self.data_source = data_source
        self.global_symmetry_var, self.x_symmetry_var, self.y_symmetry_var = global_sym_var, x_sym_var, y_sym_var
        self.other_canvas = None
        self.bind("<Configure>", lambda e: self.redraw())
        self._drag_data = {"index": -1, "item": None}
        self.tag_bind("handle", "<ButtonPress-1>", self.on_handle_press)
        self.tag_bind("handle", "<B1-Motion>", self.on_handle_drag)
        self.tag_bind("handle", "<ButtonRelease-1>", self.on_handle_release)
    def redraw(self):
        self.delete("all"); self.width, self.height = self.winfo_width(), self.winfo_height()
        if self.width < 10 or self.height < 10: return
        self.center_x, self.center_y = self.width / 2, self.height / 2
        self.radius = min(self.center_x, self.center_y) * 0.9
        self._draw_reference_shapes(); self._draw_editable_shapes()
    def _draw_reference_shapes(self):
        x0, y0 = self.center_x - self.radius, self.center_y - self.radius
        x1, y1 = self.center_x + self.radius, self.center_y + self.radius
        self.create_oval(x0, y0, x1, y1, outline="lightgrey", dash=(2, 2))
        self.create_line(self.center_x, 0, self.center_x, self.height, fill="lightgrey", dash=(2, 2))
        self.create_line(0, self.center_y, self.width, self.center_y, fill="lightgrey", dash=(2, 2))
    def _draw_editable_shapes(self):
        points = self._get_polygon_points()
        if len(points) < 2: return
        self.create_polygon(points, outline="blue", fill="", width=2, tags="polygon")
        for i in range(0, len(points), 2):
            self.create_oval(points[i] - 4, points[i+1] - 4, points[i] + 4, points[i+1] + 4, fill="lightblue", outline="blue", tags=("handle", f"h_{i//2}"))
    def _get_polygon_points(self):
        points = []
        calibration = self.data_source.get('calibration', [])
        if not calibration: return points
        for i, scale in enumerate(calibration):
            angle = i * TAU / len(calibration)
            dist = scale * self.radius
            points.extend([self.center_x + dist * math.cos(angle), self.center_y - dist * math.sin(angle)])
        return points
    def update_visuals_from_data(self):
        points = self._get_polygon_points()
        if not points: return
        try:
            poly_item = self.find_withtag("polygon")
            if poly_item: self.coords(poly_item[0], points)
            for i in range(0, len(points), 2):
                handle_item = self.find_withtag(f"h_{i//2}")
                if handle_item: self.coords(handle_item[0], points[i] - 4, points[i+1] - 4, points[i] + 4, points[i+1] + 4)
        except tk.TclError: pass
    def on_handle_press(self, event):
        item = self.find_closest(event.x, event.y)[0]; tags = self.gettags(item)
        if "handle" in tags:
            index = int(tags[1].split('_')[1])
            self._drag_data = {"index": index, "item": item}; self.itemconfig(item, fill="red")
    def on_handle_drag(self, event):
        if self._drag_data["index"] == -1: return
        index = self._drag_data["index"]
        
        num_samples = len(self.data_source['calibration'])
        if num_samples == 0: return

        angle = index * TAU / num_samples
        radial_unit_vec = (math.cos(angle), math.sin(angle))
        mouse_vec = (event.x - self.center_x, self.center_y - event.y)
        projected_distance = (mouse_vec[0] * radial_unit_vec[0]) + (mouse_vec[1] * radial_unit_vec[1])
        new_scale = max(0.0, projected_distance / self.radius)
        self._apply_calibration_change(index, new_scale)
    def _apply_calibration_change(self, initial_index, new_scale):
        n = len(self.data_source['calibration'])
        if n == 0: return

        indices_to_update = {initial_index}
        
        # Apply local symmetries first
        if self.x_symmetry_var.get(): # Top/Bottom
            indices_to_update.add((n - initial_index) % n)
        if self.y_symmetry_var.get(): # Left/Right
            half = n // 2
            temp_indices = set(indices_to_update)
            for i in temp_indices:
                indices_to_update.add((half - i + n) % n)

        # Update the primary data source
        for i in indices_to_update:
            self.data_source['calibration'][i] = new_scale
        self.update_visuals_from_data()
        
        # Apply global symmetry if enabled
        if self.global_symmetry_var.get() and self.other_canvas:
            for i in indices_to_update:
                self.other_canvas.data_source['calibration'][i] = new_scale
            self.other_canvas.update_visuals_from_data()
    def on_handle_release(self, event):
        if self._drag_data["item"]: self.itemconfig(self._drag_data["item"], fill="lightblue")
        self._drag_data = {"index": -1, "item": None}

class RawValuesEditor(Toplevel):
    def __init__(self, parent, eye_name, data_source, canvas_to_update):
        super().__init__(parent)
        self.transient(parent); self.title(f"Raw Editor - {eye_name}"); self.geometry("300x300")
        self.parent, self.data_source, self.canvas_to_update = parent, data_source, canvas_to_update
        
        center_frame = ttk.LabelFrame(self, text="Center (X Y)", padding=5)
        center_frame.pack(pady=10, padx=10, fill="x")
        self.center_var = tk.StringVar()
        ttk.Entry(center_frame, textvariable=self.center_var).pack(fill="x", expand=True)

        cal_frame = ttk.LabelFrame(self, text="Calibration Data (Space-separated)", padding=5)
        cal_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.cal_text = Text(cal_frame, wrap="word", height=8)
        self.cal_text.pack(fill="both", expand=True)

        self.populate_fields()

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        apply_button = ttk.Button(button_frame, text="Apply Changes", command=self.apply_changes)
        apply_button.pack(side="left", padx=10)
        close_button = ttk.Button(button_frame, text="Close", command=self.destroy)
        close_button.pack(side="right", padx=10)
        self.protocol("WM_DELETE_WINDOW", self.destroy); self.grab_set()

    def populate_fields(self):
        self.center_var.set(" ".join(map(str, self.data_source['center'])))
        self.cal_text.delete("1.0", tk.END)
        self.cal_text.insert("1.0", " ".join(map(str, self.data_source['calibration'])))

    def apply_changes(self):
        try:
            center_vals = [float(v) for v in self.center_var.get().strip().split()]
            if len(center_vals) != 2: raise ValueError("Center must have 2 values.")
            
            cal_vals = [float(v) for v in self.cal_text.get("1.0", tk.END).strip().split()]
            
            # Update data source and parent UI
            self.data_source['center'] = center_vals
            self.data_source['calibration'] = cal_vals
            self.parent._load_eye_data_into_ui(self.title().split(' - ')[1], self.canvas_to_update)
            self.parent._infer_symmetry_modes() # Re-check symmetry after raw edit
            messagebox.showinfo("Success", "Raw values applied.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Could not parse values:\n{e}", parent=self)

if __name__ == "__main__":
    app = GazeCalibrationEditor()
    app.mainloop()