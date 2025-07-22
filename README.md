# BUPTT

A PyQt5 desktop application for generating, storing, visualizing, and post‑processing randomly dispersed particle ensembles (spheres & rods) for DDSCAT/T‑DDA style simulations. It wraps:

- **Ensemble creation** (cell‑to‑ensemble & volume‑to‑ensemble strategies)
- **Dipole discretization & DDSCAT input generation**
- **Batch execution of `ddscat` and `ddpostprocess`**
- **Histogram/statistics generation & CSV export**
- **SQLite-backed persistence and GUI browsing/3‑D visualization (PyVista)**

---

## Features

- 🔧 **Configurable directories** (output, DDSCAT binaries, materials) persisted via `QSettings`
- 🧪 **Two placement modes**: C2E (cell‑to‑ensemble) and V2E (volume‑to‑ensemble)
- 🔬 **Particle geometries**: spheres and rods for ensemble generation
- 📦 **SQLite database** for ensembles, particles, and scattering results
- 📈 **Auto-generated histograms** (angles/distances) and CSV export
- 🖥️ **PyVista 3‑D viewer** for any stored ensemble
- 🚀 **One‑click run**: generate, run DDSCAT, run ddpostprocess—selective per ensemble
- 🖱️ **Desktop shortcut** creator (install scripts)

---

## Project Layout

```
.
├─ installation/
│  ├─ install.sh          # macOS/Linux installer (env + Desktop shortcut)
│  ├─ install.bat         # Windows installer (env + Desktop shortcut)
│  └─ pttenv.yml          # Conda environment file (portable)
├─ src/
│  ├─ main_page.py        # MainWindow (tabs)
│  ├─ run_page.py         # ParameterWindow (ensemble generation)
│  ├─ store_page.py       # Ensemble/particle browsers + 3D view
│  ├─ setup_page.py       # SettingsWindow & DirectoryDialog
│  ├─ Storer.py           # SQLite schema & CRUD
│  ├─ Runner.py           # Distribution runner -> CSV + DB flags
│  ├─ Executer.py         # DDSCAT / ddpostprocess launcher
│  ├─ discretization.py   # Sphere/Rod classes & ShapeFactory
│  ├─ Calculator.py       # Distances/angles + histograms
│  └─ cloud_generation.py # CloudGenerator (C2E, V2E) + reload utilities
├─ materials/             # Optical constant files (nk tables, etc.)
├─ temp_file/             # Template dir copied for standard ddscat runs
└─ temp_file_base/        # Template dir for baseline runs
```

---

## Prerequisites

- **Conda** (Miniconda/Anaconda)
- **DDSCAT / ddpostprocess binaries** built and available
- **Python 3.9+** (handled by the provided environment)
- **PyVista + pyvistaqt** (already in `pttenv.yml`)

Optional:
- CUDA/OpenMP settings if you want to tune performance (`OMP_NUM_THREADS` is set to 16 by default in `Executer`).

---

## Quick Start

### 1. Clone & cd

```bash
git clone https://github.com/BU-Thermal-and-Energy-Systems-Lab/BUPTT.git
cd BUPTT
```

### 2. Install the environment & shortcut

#### macOS / Linux

```bash
bash installation/install.sh
```

This will:
- Create/update the `pttenv` Conda environment from `pttenv.yml`
- Place a `BUPTT` shortcut on your Desktop
- Double‑click it any time to launch the GUI

#### Windows

Double‑click `installation\install.bat` (or run in cmd):

```bat
installation\install.bat
```

This will:
- Create/update the `pttenv` Conda environment
- Put `BUPTT.bat` on your Desktop—double‑click to run

> **Note:** The installer parses `name:` from the YAML. If you ever see a path as the env name, edit the first line of `pttenv.yml` to a simple name (e.g. `pttenv`).

---

## First Run

1. Launch the app (Desktop shortcut or `python src/main_page.py` inside the env).
2. Open **Setup Program** tab and set:
   - **Output Directory** – where ensembles & outputs are stored
   - **DDSCAT Directory** – root folder containing `src/ddscat`, `src/ddpostprocess`, and `temp_file`, `temp_file_base`
   - **Materials Directory** – folder with optical data files
3. After saving, the **Generate New Ensembles** and **Old Ensembles** tabs unlock.

---

## Workflow

1. **Generate New Ensembles tab**  
   - Fill Plasmonic / Dielectric forms (sphere/rod shapes, volume fractions, materials).
   - Set system params: cloud radius, dipole size, number of ensembles, wavelength.
   - Choose **Cell-to-Ensemble** or **Volume-to-Ensemble** strategy.
   - Check which tasks to run automatically (Ensemble Data, DDA, Postprocessing).
   - Click **Run**.

2. **Old Ensembles tab**  
   - Double-click any row to see particles, 3‑D view, and pending tasks.  
   - Use the multi-select dropdown to run missing steps.

3. **Outputs**  
   - CSV histograms saved under `<outputDir>/ensembles/<ensemble_id>/`
   - DDSCAT input/output & VTR files saved to `<outputDir>/<ensemble_id>/`
   - Database: `ensembles.db` in the project root (or in outputDir if you change code)

---

## Environment Notes

- The provided `pttenv.yml` is **portable** (`--no-builds`, no `prefix:`).  
  To re-export from your current env:
  ```bash
  conda env export --no-builds | grep -v "^prefix:" > pttenv.yml
  ```
- Minimal (from-history) export if you prefer lighter specs:
  ```bash
  conda env export --from-history --no-builds | grep -v "^prefix:" > pttenv_min.yml
  ```

---

## DDSCAT Templates

- `temp_file/` and `temp_file_base/` contain template `ddscat.par`, `shape.dat` headers, etc.
- `Executer.run_ddscat()` copies these into the ensemble’s target directory and formats placeholders (`{eff_rad}`, `{mat1}`, `{mat2}`, …).

Make sure placeholders in your templates match those used in `Executer.py`.

---

## Troubleshooting

- **Near-field line sampling disabled**  
  → `ILINE=0` means no line cuts; use `IVTR=1` in `ddpostprocess.par` to get full-volume VTR output.

---

## Contributing

Issues & PRs welcome! Please:

- Follow the existing docstring style (numpy-style sections).
- Keep DB migrations backwards-compatible or provide a migration script.
- Add unit tests for geometry/distance functions when possible.

---

## License

If you’re reusing DDSCAT or material files, respect their licenses and cite accordingly.

```
