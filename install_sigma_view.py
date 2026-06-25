import os
import sys
import platform
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import subprocess
import logging
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class InstallAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SigmaView Installer")
        self.root.geometry("450x700")
        self.os_type = self.detect_os()
        logger.info(f"Detected OS: {self.os_type}")
        self.conda_base = self.detect_conda_base()
        self.env_name = "toto"
        self.env_path = os.path.join(self.conda_base, "envs", self.env_name) if self.conda_base else ""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir_var = tk.StringVar(value=os.path.join(base_dir, "data"))
        self.models_dir_var = tk.StringVar(value=os.path.join(base_dir, "models"))
        self.output_dir_var = tk.StringVar(value=os.path.join(base_dir, "outputs"))
        self.conda_base_var = tk.StringVar(value=self.conda_base if self.conda_base else "")
        self.setup_ui()
        logger.info("Installation interface initialized")

    def detect_os(self):
        system = platform.system().lower()
        if system == "linux":
            return "linux"
        elif system == "darwin":
            return "mac"
        else:
            messagebox.showwarning("Warning", "Unsupported OS. Only Linux/Mac are fully supported.")
            return "other"

    def detect_conda_base(self):
        try:
            result = subprocess.run(['conda', 'info', '--base'], capture_output=True, text=True, check=True)
            conda_base = result.stdout.strip()
            if os.path.exists(conda_base):
                return conda_base
            result = subprocess.run(['mamba', 'info', '--base'], capture_output=True, text=True, check=True)
            conda_base = result.stdout.strip()
            if os.path.exists(conda_base):
                return conda_base
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        default_paths = [
            os.path.join(os.path.expanduser("~"), "anaconda3"),
            os.path.join(os.path.expanduser("~"), "miniconda3"),
            os.path.join(os.path.expanduser("~"), "opt", "miniconda3")
        ]
        for path in default_paths:
            if os.path.exists(path):
                return path
        return ""

    def setup_ui(self):
        tk.Label(self.root, text="Installation Configuration", font=("Arial", 14)).pack(pady=10)
        tk.Label(self.root, text=f"Detected OS: {self.os_type.upper()}").pack()
        tk.Label(self.root, text="Anaconda/Mamba path:").pack()
        tk.Entry(self.root, textvariable=self.conda_base_var, width=50).pack(pady=5)
        tk.Button(self.root, text="Browse", command=self.browse_conda).pack()
        tk.Label(self.root, text="Data directory:").pack()
        tk.Entry(self.root, textvariable=self.data_dir_var).pack(pady=5)
        tk.Button(self.root, text="Browse", command=lambda: self.browse_dir("data")).pack()
        tk.Label(self.root, text="Models directory:").pack()
        tk.Entry(self.root, textvariable=self.models_dir_var).pack(pady=5)
        tk.Button(self.root, text="Browse", command=lambda: self.browse_dir("models")).pack()
        tk.Label(self.root, text="Output directory:").pack()
        tk.Entry(self.root, textvariable=self.output_dir_var).pack(pady=5)
        tk.Button(self.root, text="Browse", command=lambda: self.browse_dir("output")).pack()
        tk.Button(self.root, text="Install Mamba", command=self.install_mamba).pack(pady=10)
        tk.Button(self.root, text="Create Environment", command=self.create_environment).pack(pady=10)
        tk.Button(self.root, text="Setup Directories", command=self.setup_directories).pack(pady=10)
        tk.Button(self.root, text="Full Install", command=self.run_full_install).pack(pady=10)
        self.progress = ttk.Progressbar(self.root, length=300, mode="determinate")
        self.progress.pack(pady=20)

    def browse_conda(self):
        conda_path = filedialog.askdirectory(
            title="Select Anaconda/Mamba directory",
            initialdir=self.conda_base_var.get() or os.path.expanduser("~")
        )
        if conda_path:
            conda_bin = "conda.bat" if sys.platform == "win32" else "conda"
            conda_path = os.path.normpath(conda_path)
            if os.path.exists(os.path.join(conda_path, "condabin", conda_bin)) or \
               os.path.exists(os.path.join(conda_path, "bin", conda_bin)):
                self.conda_base_var.set(conda_path)
                self.conda_base = conda_path
                self.env_path = os.path.join(self.conda_base, "envs", self.env_name)
                logger.info(f"New Anaconda/Mamba path: {conda_path}")
            else:
                messagebox.showerror("Error", "Invalid path. Directory must contain conda/mamba executable.")
                logger.error("Invalid Anaconda/Mamba path")

    def browse_dir(self, dir_type):
        initial_dir = getattr(self, f"{dir_type}_dir_var").get()
        dir_path = filedialog.askdirectory(initialdir=initial_dir, title=f"Select {dir_type} directory")
        if dir_path:
            getattr(self, f"{dir_type}_dir_var").set(dir_path)
            logger.info(f"Directory {dir_type}: {dir_path}")

    def install_mamba(self):
        if not self.conda_base:
            messagebox.showerror("Error", "Anaconda path not set")
            return
        try:
            self.progress["value"] = 0
            self.root.update_idletasks()
            conda_exec = os.path.join(self.conda_base, "bin", "conda")
            if not os.path.exists(conda_exec):
                conda_exec = os.path.join(self.conda_base, "condabin", "conda")
            logger.info(f"Installing Mamba with {conda_exec}")
            subprocess.check_call([conda_exec, "install", "-n", "base", "-c", "conda-forge", "mamba", "-y"])
            self.progress["value"] = 100
            self.root.update_idletasks()
            messagebox.showinfo("Success", "Mamba installed successfully!")
            logger.info("Mamba installed")
        except subprocess.CalledProcessError as e:
            self.progress["value"] = 0
            self.root.update_idletasks()
            messagebox.showerror("Error", f"Mamba installation failed: {e}")
            logger.error(f"Mamba installation error: {e}")

    def create_environment(self):
        if not self.conda_base:
            messagebox.showerror("Error", "Anaconda/Mamba path not set")
            return
        try:
            self.progress["value"] = 0
            self.root.update_idletasks()
            env_file = "envmac.yml" if self.os_type == "mac" else "envlinux.yml"
            env_yml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), env_file)
            if not os.path.exists(env_yml_path):
                raise FileNotFoundError(f"File {env_file} not found")
            with open(env_yml_path, 'r') as file:
                env_config = yaml.safe_load(file)
                self.env_name = env_config.get('name', 'default_env')
            logger.info(f"Using file: {env_yml_path}")
            logger.info(f"Environment name: {self.env_name}")
            for cmd in ["mamba", "conda"]:
                try:
                    executable = os.path.join(self.conda_base, "bin", cmd)
                    if not os.path.exists(executable):
                        executable = os.path.join(self.conda_base, "condabin", cmd)
                    logger.info(f"Creating environment with {executable}")
                    subprocess.check_call([
                        executable, "env", "create", 
                        "-f", env_yml_path, 
                        "-n", self.env_name,
                        "--quiet"
                    ])
                    break
                except subprocess.CalledProcessError:
                    if cmd == "conda":
                        raise
                    continue
            self.progress["value"] = 100
            self.root.update_idletasks()
            messagebox.showinfo("Success", f"Environment {self.env_name} created successfully!")
            logger.info("Environment created")
        except Exception as e:
            self.progress["value"] = 0
            self.root.update_idletasks()
            messagebox.showerror("Error", f"Environment creation failed: {e}")
            logger.error(f"Environment creation error: {e}")

    def setup_directories(self):
        try:
            self.progress["value"] = 0
            self.root.update_idletasks()
            for dir_var in [self.data_dir_var, self.models_dir_var, self.output_dir_var]:
                os.makedirs(dir_var.get(), exist_ok=True)
                self.progress["value"] += 33
                self.root.update_idletasks()
            messagebox.showinfo("Success", "Directories configured successfully!")
            logger.info("Directories created")
        except Exception as e:
            self.progress["value"] = 0
            self.root.update_idletasks()
            messagebox.showerror("Error", f"Directory setup failed: {e}")
            logger.error(f"Directory setup error: {e}")

    def run_full_install(self):
        self.install_mamba()
        self.create_environment()
        self.setup_directories()


if __name__ == "__main__":
    root = tk.Tk()
    app = InstallAppGUI(root)
    root.mainloop()
