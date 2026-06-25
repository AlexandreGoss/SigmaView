import sys
import os
import json
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import subprocess
import logging
from pathlib import Path
from PIL import Image, ImageTk
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = "sigma_view_config.json"

class SigmaViewGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SigmaView")
        self.root.geometry("1200x610")
        self.primary_color = "#2c3e50"
        self.secondary_color = "#3498db"
        self.bg_color = "#ecf0f1"
        self.text_color = "#2c3e50"
        self.root.configure(bg=self.bg_color)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".", background=self.bg_color, foreground=self.text_color)
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, font=("Helvetica", 10))
        style.configure("TButton", padding=6, font=("Helvetica", 9, "bold"), 
                       background=self.secondary_color, foreground="white")
        style.map("TButton", background=[("active", "#2980b9")])
        style.configure("TProgressbar", thickness=20, troughcolor="#bdc3c7", 
                       background=self.secondary_color)
        style.configure("TLabelframe", background=self.bg_color)
        style.configure("TLabelframe.Label", background=self.bg_color, 
                       foreground=self.text_color)
        style.configure("Danger.TButton", foreground="white", background="#e74c3c")
        style.map("Danger.TButton",
                 background=[("active", "#c0392b"), ("disabled", "#f5b7b1")])
        self.create_header()
        script_dir = Path(__file__).parent
        self.models_dir_var = tk.StringVar(value=str(script_dir.parent / "models"))
        self.output_dir_var = tk.StringVar(value=str(script_dir.parent / "outputs"))
        self.data_dir_var = tk.StringVar(value=str(script_dir.parent / "data"))
        self.tif_file_var = tk.StringVar(value="")
        self.unet_model_path_var = tk.StringVar(value="")
        self.skeleton_channel_var = tk.IntVar(value=0)
        self.max_distance_var = tk.DoubleVar(value=5.0)
        self.include_skeleton_var = tk.BooleanVar(value=False)
        self.enhance_contrast_var = tk.BooleanVar(value=False)
        self.output_file_var = tk.StringVar(value="No file generated")
        self.process = None
        self.load_config()
        self.create_main_interface()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_header(self):
        header_frame = tk.Frame(self.root, bg=self.primary_color)
        header_frame.pack(fill="x", pady=(0, 10))
        logo_path = os.path.join(Path(__file__).parent, "SigmaViewLogo.png")
        if os.path.exists(logo_path):
            try:
                self.logo_img = Image.open(logo_path)
                self.logo_img = self.logo_img.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(self.logo_img)
                logo_container = tk.Frame(header_frame, bg=self.primary_color)
                logo_container.pack(side="left", padx=20, pady=10)
                logo_label = tk.Label(logo_container, image=self.logo_photo, bg=self.primary_color)
                logo_label.pack()
            except Exception as e:
                logger.error(f"Failed to load logo: {str(e)}")
        title_frame = tk.Frame(header_frame, bg=self.primary_color)
        title_frame.pack(side="left", fill="y", padx=10)
        title_label = tk.Label(title_frame, text="SigmaView", font=("Helvetica", 18, "bold"), fg="white", bg=self.primary_color)
        title_label.pack(pady=10)
        subtitle_label = tk.Label(title_frame, text="Dendritic Spine Analysis Tool", font=("Helvetica", 10), fg="#bdc3c7", bg=self.primary_color)
        subtitle_label.pack()

    def create_main_interface(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill="both", expand=True)
        left_frame = ttk.Frame(main_frame, padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        ttk.Label(left_frame, text="TIFF file:").grid(row=0, column=0, sticky="e", pady=5)
        ttk.Entry(left_frame, textvariable=self.tif_file_var, width=40).grid(row=0, column=1, pady=5)
        ttk.Button(left_frame, text="Browse", command=self.browse_tif, width=10).grid(row=0, column=2, pady=5)
        ttk.Label(left_frame, text="Leave empty to process all files", foreground="red").grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Separator(left_frame, orient="horizontal").grid(row=2, column=0, columnspan=3, pady=10, sticky="ew")
        ttk.Label(left_frame, text="Models directory:", font=("Helvetica", 10, "bold")).grid(row=3, column=0, sticky="e", pady=5)
        ttk.Entry(left_frame, textvariable=self.models_dir_var, width=40).grid(row=3, column=1, pady=5)
        ttk.Button(left_frame, text="Browse", command=lambda: self.browse_dir("models"), width=10).grid(row=3, column=2, pady=5)
        ttk.Label(left_frame, text="U-Net model file:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="e", pady=5)
        ttk.Entry(left_frame, textvariable=self.unet_model_path_var, width=40).grid(row=4, column=1, pady=5)
        ttk.Button(left_frame, text="Browse", command=self.browse_unet_model, width=10).grid(row=4, column=2, pady=5)
        ttk.Label(left_frame, text="Output directory:", font=("Helvetica", 10, "bold")).grid(row=5, column=0, sticky="e", pady=5)
        ttk.Entry(left_frame, textvariable=self.output_dir_var, width=40).grid(row=5, column=1, pady=5)
        ttk.Button(left_frame, text="Browse", command=lambda: self.browse_dir("output"), width=10).grid(row=5, column=2, pady=5)
        ttk.Label(left_frame, text="Data directory:", font=("Helvetica", 10)).grid(row=6, column=0, sticky="e", pady=5)
        ttk.Entry(left_frame, textvariable=self.data_dir_var, width=40).grid(row=6, column=1, pady=5)
        ttk.Button(left_frame, text="Browse", command=lambda: self.browse_dir("data"), width=10).grid(row=6, column=2, pady=5)
        params_frame = ttk.LabelFrame(left_frame, text="Advanced Parameters", padding="10")
        params_frame.grid(row=7, column=0, columnspan=3, pady=10, sticky="ew")
        ttk.Label(params_frame, text="Skeleton channel:").grid(row=0, column=0, padx=5, sticky="e")
        ttk.Spinbox(params_frame, from_=0, to=10, textvariable=self.skeleton_channel_var, width=5).grid(row=0, column=1, sticky="w")
        ttk.Label(params_frame, text="Max tracking dist. (px):").grid(row=1, column=0, padx=5, sticky="e")
        ttk.Spinbox(params_frame, from_=1.0, to=50.0, increment=1.0, textvariable=self.max_distance_var, width=5).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(params_frame, text="Include skeleton in annotations", variable=self.include_skeleton_var).grid(row=2, column=0, columnspan=2, pady=5, sticky="w")
        ttk.Checkbutton(params_frame, text="Enhance skeleton contrast", variable=self.enhance_contrast_var).grid(row=3, column=0, columnspan=2, pady=5, sticky="w")
        right_frame = ttk.Frame(main_frame, padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.create_tools_frame(right_frame)
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

    def create_tools_frame(self, parent):
        tools_frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        tools_frame.pack(fill="both", expand=True, pady=10)
        btn_frame = ttk.Frame(tools_frame)
        btn_frame.pack(fill="x", pady=5)
        self.annotate_button = ttk.Button(btn_frame, text="Generate Annotations", command=self.run_annotation)
        self.annotate_button.pack(side="left", expand=True, padx=2)
        self.stop_button = ttk.Button(btn_frame, text="Stop", 
                                    command=self.stop_execution,
                                    state="disabled",
                                    style="Danger.TButton")
        self.stop_button.pack(side="left", expand=True, padx=2)
        self.open_button = ttk.Button(tools_frame, text="Open Results", 
                                    command=self.open_output_dir, state="disabled")
        self.open_button.pack(fill="x", pady=5)
        ttk.Label(tools_frame, text="Last generated file:").pack(pady=(10, 0))
        self.output_file_label = ttk.Label(tools_frame, textvariable=self.output_file_var, 
                                         foreground="#7f8c8d", wraplength=300)
        self.output_file_label.pack()
        progress_frame = ttk.Frame(tools_frame)
        progress_frame.pack(fill="x", pady=10)
        self.progress = ttk.Progressbar(progress_frame, length=250, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.status_label = ttk.Label(progress_frame, text="Ready", foreground="#7f8c8d", width=15)
        self.status_label.pack(side="left", padx=5)

    def browse_tif(self):
        initial_dir = self.data_dir_var.get() if os.path.exists(self.data_dir_var.get()) else str(Path(__file__).parent.parent)
        tif_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select a TIFF file",
            filetypes=[("TIFF files", "*.tif *.tiff")]
        )
        if tif_path:
            self.tif_file_var.set(tif_path)

    def browse_unet_model(self):
        initial_dir = self.models_dir_var.get() if os.path.exists(self.models_dir_var.get()) else str(Path(__file__).parent.parent)
        model_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select U-Net model file",
            filetypes=[("HDF5 files", "*.h5")]
        )
        if model_path:
            self.unet_model_path_var.set(model_path)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.models_dir_var.set(config.get("models_dir", self.models_dir_var.get()))
                    self.output_dir_var.set(config.get("output_dir", self.output_dir_var.get()))
                    self.data_dir_var.set(config.get("data_dir", self.data_dir_var.get()))
                    self.unet_model_path_var.set(config.get("unet_model_path", self.unet_model_path_var.get()))
                    self.skeleton_channel_var.set(config.get("skeleton_channel", self.skeleton_channel_var.get()))
                    self.max_distance_var.set(config.get("max_distance", self.max_distance_var.get()))
                    self.include_skeleton_var.set(config.get("include_skeleton", self.include_skeleton_var.get()))
                    self.enhance_contrast_var.set(config.get("enhance_contrast", self.enhance_contrast_var.get()))
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

    def save_config(self):
        config = {
            "models_dir": self.models_dir_var.get(),
            "output_dir": self.output_dir_var.get(),
            "data_dir": self.data_dir_var.get(),
            "unet_model_path": self.unet_model_path_var.get(),
            "skeleton_channel": self.skeleton_channel_var.get(),
            "max_distance": self.max_distance_var.get(),
            "include_skeleton": self.include_skeleton_var.get(),
            "enhance_contrast": self.enhance_contrast_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
                logger.error(f"Failed to save config: {str(e)}")

    def on_close(self):
        self.save_config()
        self.root.destroy()

    def browse_dir(self, dir_type):
        current_val = getattr(self, f"{dir_type}_dir_var").get()
        initial_dir = current_val if os.path.exists(current_val) else str(Path(__file__).parent.parent)
        dir_path = filedialog.askdirectory(
            initialdir=initial_dir,
            title=f"Select {dir_type} directory"
        )
        if dir_path:
            getattr(self, f"{dir_type}_dir_var").set(dir_path)
            self.save_config()

    def open_output_dir(self):
        output_dir = self.output_dir_var.get()
        if os.path.exists(output_dir):
            try:
                if sys.platform == 'win32':
                    subprocess.run(['explorer', output_dir])
                elif sys.platform == 'darwin':
                    subprocess.run(['open', output_dir])
                else:
                    subprocess.run(['xdg-open', output_dir])
            except Exception as e:
                logger.error(f"Failed to open output directory: {str(e)}")
                messagebox.showerror("Error", f"Could not open directory: {str(e)}")
        else:
            messagebox.showerror("Error", "Output directory not found")

    def run_annotation(self):
        self.reset_ui_state()
        self.annotate_button.config(state="disabled")
        self.stop_button.config(state="normal")
        script_path = Path(__file__).parent / "generation_annotation.py"
        if not script_path.exists():
            messagebox.showerror("Error", f"Script {script_path} not found")
            self.reset_buttons_state()
            return
        if not self.unet_model_path_var.get():
            messagebox.showerror("Error", "Please select a U-Net model file")
            self.reset_buttons_state()
            return
        cmd = [
            "python", str(script_path),
            f"--data_dir={self.data_dir_var.get()}",
            f"--unet_model_path={self.unet_model_path_var.get()}",
            f"--output_dir={self.output_dir_var.get()}",
            f"--skeleton_channel={self.skeleton_channel_var.get()}",
            f"--tile_size=128",
            f"--overlap=16",
            f"--max_distance={self.max_distance_var.get()}"
        ]
        if self.tif_file_var.get():
            cmd.append(f"--input_tif={self.tif_file_var.get()}")
        if self.include_skeleton_var.get():
            cmd.append("--include_skeleton")
        if self.enhance_contrast_var.get():
            cmd.append("--enhance_contrast")
        try:
            self.progress["value"] = 30
            self.status_label.config(text="Generating annotations...")
            self.output_file_var.set("Processing...")
            self.root.update_idletasks()
            self.process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.monitor_process()
        except Exception as e:
            logger.error(f"Failed to launch: {str(e)}")
            self.execution_failed(str(e))

    def monitor_process(self):
        if self.process and self.process.poll() is None:
            self.root.after(500, self.monitor_process)
        else:
            return_code = self.process.returncode if self.process else None
            if return_code == 0:
                self.execution_succeeded()
            else:
                self.execution_failed(f"Return code: {return_code}")

    def stop_execution(self):
        if self.process:
            try:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                self.status_label.config(text="Stopped", foreground="orange")
                self.progress["value"] = 0
                messagebox.showinfo("Info", "Execution was stopped")
            except Exception as e:
                logger.error(f"Failed to stop: {str(e)}")
                messagebox.showerror("Error", f"Failed to stop: {str(e)}")
        else:
            logger.warning("No process to stop")
        self.reset_buttons_state()

    def reset_ui_state(self):
        self.progress["value"] = 0
        self.status_label.config(text="Preparing...", foreground="#757575")
        self.output_file_var.set("")
        self.open_button.config(state="disabled")
        self.root.update_idletasks()

    def reset_buttons_state(self):
        self.annotate_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.process = None

    def execution_succeeded(self):
        self.progress["value"] = 100
        self.status_label.config(text="Completed", foreground="green")
        self.open_button.config(state="normal")
        output_file = self.get_output_filename()
        self.output_file_var.set(f"Generated file: {output_file}")
        self.reset_buttons_state()

    def execution_failed(self, error_msg):
        self.progress["value"] = 0
        self.status_label.config(text="Failed", foreground="red")
        self.output_file_var.set("Execution error")
        messagebox.showerror("Error", f"Execution failed: {error_msg}")
        self.reset_buttons_state()

    def get_output_filename(self):
        if not self.tif_file_var.get():
            return f"Multiple files in {self.output_dir_var.get()}"
        base_name = os.path.basename(self.tif_file_var.get())
        return os.path.join(self.output_dir_var.get(), f"tracked_annotated_{base_name}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SigmaViewGUI(root)
    root.mainloop()