"""
Execution helpers for running external DDSCAT / DDPOSTPROCESS binaries.

Classes
-------
Executer
    Prepares DDSCAT input files (shape.dat, ddscat.par), launches the
    solver and optional baseline run, and triggers ddpostprocess to
    generate near‑field volume output.
"""

import os, subprocess
from shutil import copytree
import numpy as np
from PyQt5.QtCore import QSettings


class Executer:
    """
    Wraps DDSCAT and ddpostprocess invocation for a single ensemble.

    Parameters
    ----------
    ensemble : object
        In‑memory ensemble providing geometry, materials, and derived
        attributes (e.g. ``cloud_radius``, ``dipole_size``,
        ``particle_data``).
    wavelength : float, default=800
        Illumination wavelength in nanometers.
    target : str, optional
        Output directory into which DDSCAT input/output files are written.
        Defaults to ``<outputDir>/ensembles/<ensemble_id>`` from ``QSettings``.
    """
    def __init__(self, ensemble, wavelength = 800, target=None):
        """Store configuration and prepare an environment with OMP threads."""
        self.ensemble = ensemble
        self.settings = QSettings("LogicLorenzo", "PTTool")
        self.wavelength = wavelength / 1000
        if target is None:
            target = os.path.join(self.settings.value("outputDir"), "ensembles", self.ensemble.ensemble_id)
        self.target = target

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "16"
        self.env = env

    
    def run_ddscat(self, make_baseline=False):
        """
        Construct DDSCAT shape/material files and execute the solver.

        Generates ``shape.dat``, reads template parameter files, formats 
        ``ddscat.par`` template placeholders with ensemble‑specific values 
        (effective radius, material paths, etc.). All integer dipole lattice 
        coordinates are appended to ``shape.dat`` after computing per‑body
        discretizations.

        If ``make_baseline`` is ``True`` a second “baseline” run is
        created in a sibling directory containing only spherical bodies.

        Parameters
        ----------
        make_baseline : bool, default=False
            Whether to execute an additional baseline DDSCAT run using
            only the spherical subset of bodies.
        """
        
        def make_files(bodies, target, baseline=False):
            if baseline:
                temp_path = os.path.join(self.settings.value("DDSCATDir"), "temp_file", "baseline.par")
                with open(temp_path, "r+") as f:
                    content = f.read()

                with open(f"{target}/ddscat.par", "r+") as f:
                    modified_content = content.format(
                        mat=os.path.join(self.settings.value("materialDir"), self.ensemble.materials["plasmonic"]),
                        wav=self.wavelength,
                        eff_rad=round(((3 * total_vol / (4 * np.pi)) ** (1/3))*self.ensemble.dipole_size/10**3, 4))
                    f.seek(0)  # Move the file pointer to the beginning of the file
                    f.write(modified_content)
                    f.truncate()  # Ensure the file is truncated to the new size
            else: 
                temp_path = os.path.join(self.settings.value("DDSCATDir"), "temp_file", "mixture.par")
                with open(temp_path, "r+") as f:
                    content = f.read()

                with open(f"{target}/ddscat.par", "r+") as f:
                    modified_content = content.format(
                        mat1=os.path.join(self.settings.value("materialDir"), self.ensemble.materials["plasmonic"]),
                        mat2=os.path.join(self.settings.value("materialDir"), self.ensemble.materials["dielectric"]),
                        wav=self.wavelength,
                        eff_rad=round(((3 * total_vol / (4 * np.pi)) ** (1/3))*self.ensemble.dipole_size/10**3, 4))
                    f.seek(0)  # Move the file pointer to the beginning of the file
                    f.write(modified_content)
                    f.truncate()  # Ensure the file is truncated to the new size
            
            total_dipoles = 0
            total_vol = 0
            pre = [
            "1.000000  0.000000  0.000000 = A_1 vector\n",
            "0.000000  1.000000  0.000000 = A_2 vector\n",
            "1.000000  1.000000  1.000000 = lattice spacings (d_x,d_y,d_z)/d\n",
            "0.000000  0.000000  0.000000 = lattice offset x0(1-3) = (x_TF,y_TF,z_TF)/d for dipole 0 0 0\n",
            "JA  IX  IY  IZ ICOMP(x,y,z)\n",
            ]
            for body in bodies:
                total_vol += body.volume
                
            with open(f"{target}/shape.dat", "w") as f:
                f.write(f"{self.ensemble.ensemble_id}\n"),
                f.write("{total_dipoles} = NAT \n"),
                f.writelines(pre)    
        
            for body in bodies:
                body_dipoles = body.discretize()
                num_dipoles = len(body_dipoles)
                dipole_points = np.hstack(
                    (
                        np.array(range(total_dipoles + 1, total_dipoles + num_dipoles + 1)).reshape(num_dipoles, 1).astype(int),
                        np.around(body_dipoles).astype(int),
                        np.array([body.material_idx] * 3 * num_dipoles).reshape(num_dipoles, 3).astype(int),
                    )
                )
                with open(f"{target}/shape.dat", "a+") as f:
                    for line in dipole_points:
                        f.write(" ".join(map(str, line)) + "\n")
                total_dipoles += num_dipoles
                
            with open(f"{target}/shape.dat", "r+") as f:
                modified_content = f.read().format(total_dipoles= str(total_dipoles))
                f.seek(0)  # Move the file pointer to the beginning of the file
                f.write(modified_content)
                f.truncate()  # Ensure the file is truncated to the new size
        
        os.makedirs(self.target, exist_ok=True)
        ddscat_path = os.path.join(self.settings.value("DDSCATDir"), "src/ddscat")
        make_files(self.ensemble.bodies, self.target)
        subprocess.run([ddscat_path], cwd=self.target, check=False, env=self.env)
        if make_baseline:
            baseline_dir = os.path.join(self.target, "_baseline")
            os.makedirs(baseline_dir, exist_ok=True)
            make_files(
                [body for body in self.ensemble.bodies if body.material_idx == 1],
                baseline_dir,
                baseline=make_baseline
            )
            subprocess.run([ddscat_path], cwd=self.target, check=False, env=self.env)
        
                

    def run_ddpostprocess(self):
        """
        Write a minimal ``ddpostprocess.par`` and invoke ddpostprocess.

        Produces VTR output (|E| field) by setting ``IVTR=1`` and
        disabling line sampling. The external binary is executed in the
        ensemble's target directory.
        """
        
        preamble = [
        "’w000r000k000.E1’ = name of file with E stored\n",
        "’VTRoutput’ = prefix for name of VTR output files\n",
        "1 = IVTR (set to 1 to create VTR file with |E|)\n",
        "0 = ILINE (set to 1 to evaluate E along a line)\n"]

        with open(f"{self.target}/ddpostprocess.par", "w") as f:
            f.writelines(preamble)

        ddpost_path = os.path.join(self.settings.value("DDSCATDir"), "src/ddpostprocess")
        subprocess.run(ddpost_path, cwd=self.target, check=False, env=self.env)
        
