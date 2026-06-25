# SigmaView

SigmaView is a graphical tool for dendritic spine analysis in 3D+time fluorescence microscopy images. It provides an end-to-end pipeline for spine segmentation, tracking, and annotation using deep learning (U-Net).

## Features

- **Spine Segmentation** — U-Net based segmentation of dendritic spines in 3D volumes
- **Temporal Tracking** — Multi-frame spine tracking with global motion compensation and Hungarian algorithm association
- **Interactive GUI** — Tkinter-based interface for configuring and launching analyses
- **Multi-format Output** — Results exported as TIFF (ImageJ-compatible), CSV (spine properties), and Zarr (Napari-ready)
- **Cross-platform** — Works on Linux and macOS via conda environments

## Requirements

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/)
- Python 3.9
- Linux or macOS (Windows not yet tested)

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/sigmaview.git
cd sigmaview
```

### Automatic Installation

Run the graphical installer:

```bash
python install_sigma_view.py
```

The installer will guide you through:
- Selecting your Anaconda installation path
- Creating the conda environment (`sigma_env_linux` or `sigma_env_mac`)
- Setting up required directories (`data/`, `models/`, `outputs/`)

### Manual Installation

Create the conda environment manually:

**Linux:**
```bash
conda env create -f envlinux.yml
conda activate sigma_env_linux
```

**macOS:**
```bash
conda env create -f envmac.yml
conda activate sigma_env_mac
```

## Usage

### Launching the GUI

Make the script executable and run:

**Linux:**
```bash
chmod +x Execute_Linux.bash
./Execute_Linux.bash
```

**macOS:**
```bash
chmod +x Execute_Mac.bash
./Execute_Mac.bash
```

### Pipeline Steps

1. **Select a TIFF file** (or leave empty to process all files in `data/`)
2. **Choose a U-Net model** (`.h5` file in `models/`)
3. **Configure parameters** (skeleton channel, tracking distance, etc.)
4. **Click "Générer annotations"** to start processing

### Output

- `outputs/tracked_*.tif` — Multi-channel TIFF stack (skeleton, binary mask, labels)
- `outputs/tracked_*.csv` — Spine tracking data (frame, ID, centroid coordinates, volume)
- `outputs/tracked_*.zarr` — Zarr directory for visualization in Napari (optional)

## Project Structure

```
sigmaview/
├── gui/
│   ├── SigmaView_tools_gui.py    # Main GUI application
│   └── generation_annotation.py  # Core processing pipeline
├── envlinux.yml                   # Linux conda environment
├── envmac.yml                     # macOS conda environment
├── install_sigma_view.py         # Graphical installer
├── Execute_Linux.bash            # Linux launcher script
├── Execute_Mac.bash              # macOS launcher script
└── models/                       # Pre-trained U-Net models (not included)
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Citation

If you use SigmaView in your research, please cite:

```
[Citation information to be added]
```

## Contact

Alexandre Gosset — [alexandre.gosset@gmx.fr](mailto:alexandre.gosset@gmx.fr)
