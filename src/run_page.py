"""
Forms and controller for generating new ensembles from user input.

Classes
-------
ObjectInputForm
    Parameter entry widget for a single material family (plasmonic or
    dielectric). Supports sphere/rod shape‑specific fields via a stacked
    layout and returns normalized data dictionaries.
ParameterWindow
    Top‑level form that aggregates two :class:`ObjectInputForm` instances,
    system‑level parameters, and execution options (ensemble data, DDA,
    post‑processing). Generates one or more ensembles and dispatches
    selected computations.
"""

import sys, os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel, 
    QPushButton, QGroupBox, QComboBox, QHBoxLayout, QCheckBox, QStackedLayout
)
from PyQt5.QtCore import QSettings
from generate_ensemble import CloudGenerator
from Storer import Storer
from Runner import Runner
from Executer import Executer
                
    
class ObjectInputForm(QGroupBox):
    """
    Shape‑aware input form for a single material type.

    Presents a combo box to choose between *Sphere* and *Rod* and swaps
    the active page accordingly. The accessor :meth:`get_data` returns a
    dictionary containing the shape, physical parameters normalized by
    dipole size, volume fraction, material name, and the supplied
    material index.

    Parameters
    ----------
    title : str
        Group box title; also used as the material type label.
    """
    def __init__(self, title):
        super().__init__(title)
        self.type = title

        # Shared parameters
        self.shape_parameter = QComboBox(); self.shape_parameter.addItems(["Sphere", "Rod"])
        self.shape_parameter.currentIndexChanged.connect(self.switch_page)

        # 2️⃣ Create the stacked widget
        self.stacked = QStackedLayout()

        # 3️⃣ Create your pages
        page1 = QWidget()
        self.sphere_radius_input = QLineEdit(); self.sphere_radius_input.setPlaceholderText("Enter radius (in nm)")
        self.sphere_volume_fraction = QLineEdit(); self.sphere_volume_fraction.setPlaceholderText("Enter volume fraction (0-1)")
        self.sphere_material_input = QLineEdit(); self.sphere_material_input.setPlaceholderText("Enter material")
        layout1 = QVBoxLayout(page1)
        layout1.addWidget(self.sphere_radius_input)
        layout1.addWidget(self.sphere_volume_fraction)
        layout1.addWidget(self.sphere_material_input)

        page2 = QWidget()
        layout2 = QVBoxLayout(page2)
        self.rod_length_input = QLineEdit(); self.rod_length_input.setPlaceholderText("Enter length (in nm)")
        self.rod_radius_input = QLineEdit(); self.rod_radius_input.setPlaceholderText("Enter radius (in nm)")
        self.rod_volume_fraction = QLineEdit(); self.rod_volume_fraction.setPlaceholderText("Enter volume fraction (0-1)")
        self.rod_material_input = QLineEdit(); self.rod_material_input.setPlaceholderText("Enter material")
        layout2.addWidget(self.rod_radius_input)
        layout2.addWidget(self.rod_length_input)
        layout2.addWidget(self.rod_volume_fraction)
        layout2.addWidget(self.rod_material_input)
        
        
        # 4️⃣ Add pages to the stack (order matters!)
        for page in (page1, page2):
            self.stacked.addWidget(page)

        # 5️⃣ Lay everything out
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.shape_parameter)
        main_layout.addLayout(self.stacked)

    def switch_page(self, index: int):
        """
        Activate the selected shape page.

        Parameters
        ----------
        index : int
            Index from the shape selector combo box (0 = sphere, 1 = rod).
        """
        self.stacked.setCurrentIndex(index)

    def get_data(self, dipole_size, material_idx):
        """
        Extract current form values as a serializable dictionary.

        Numeric geometric inputs are divided by ``dipole_size`` so they
        are stored in dipole units. The caller supplies the material
        index mapping (e.g., 1 = plasmonic, 2 = dielectric).

        Parameters
        ----------
        dipole_size : float
            Physical size of one dipole cell used for normalization.
        material_idx : int
            Integer code representing the material family.

        Returns
        -------
        dict
            Dictionary with keys: ``shape``, ``params`` (list),
            ``volume_fraction``, ``material`` (string name), and
            ``material_idx``.
        """
        idx = self.shape_parameter.currentIndex()
        if idx == 0:  # Sphere
            r   = float(self.sphere_radius_input.text()) / dipole_size
            vf  = float(self.sphere_volume_fraction.text())
            mat = self.sphere_material_input.text()
            return {
                    "shape": "sphere",
                    "params": [r],
                    "volume_fraction": vf,
                    "material": mat,
                    "material_idx": material_idx
                }
        else:         # Rod
            r   = float(self.rod_radius_input.text()) / dipole_size
            L   = float(self.rod_length_input.text()) / dipole_size
            vf  = float(self.rod_volume_fraction.text())
            mat = self.rod_material_input.text()
            return {
                "shape": "rod",
                "params": [r, L],
                "volume_fraction": vf,
                "material": mat,
                "material_idx": material_idx
            }


class ParameterWindow(QWidget):
    """
    Main parameter collection and execution window.

    Aggregates two material input forms, system parameters (cloud radius,
    dipole size, number of ensembles, wavelength), ensemble generation
    mode, and checkboxes selecting which computations to run. For each
    requested ensemble it creates the directory structure, persists the
    ensemble via :class:`Storer`, and conditionally invokes
    :class:`Runner` and :class:`Executer` methods.

    Environment paths (output, DDSCAT, materials) are loaded from
    ``QSettings`` on construction.
    """
    def __init__(self):
        super().__init__()
        settings     = QSettings("LogicLorenzo", "PTTool")
        self.paths = {
            "outputDir": settings.value("outputDir", "", type=str),
            "DDSCATDir": settings.value("DDSCATDir", "", type=str),
            "materialDir": settings.value("materialDir", "", type=str)
        }
        self.setWindowTitle("Object Parameter Input")
        self.setGeometry(100, 100, 400, 500)
        layout = QVBoxLayout()

        params_box = QHBoxLayout()
        self.PNS = ObjectInputForm("Plasmonic"); params_box.addWidget(self.PNS)
        self.DNR = ObjectInputForm("Dielectric"); params_box.addWidget(self.DNR)
        layout.addLayout(params_box)


        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_program)

        system_box = QGroupBox("System Parameters")
        system_layout = QFormLayout()
        self.ensemble_size = QLineEdit(); self.ensemble_size.setPlaceholderText("Radius of enclosing volume (in nm)")
        system_layout.addRow("Ensemble Size:", self.ensemble_size)
        self.dipole_input = QLineEdit(); self.dipole_input.setPlaceholderText("Dipole size (in nm)")
        system_layout.addRow("Dipole Size:", self.dipole_input)
        self.number_ensembles = QLineEdit(); self.number_ensembles.setPlaceholderText("Number of ensembles")
        system_layout.addRow("Number of Ensembles:", self.number_ensembles)
        self.wavelength = QLineEdit(); self.wavelength.setPlaceholderText("Wavelength (in nm)")
        system_layout.addRow("Wavelength:", self.wavelength)
        system_box.setLayout(system_layout)
        layout.addWidget(system_box)

        self.ensemble_type = QComboBox(); self.ensemble_type.addItems(["Cell-to-Ensemble", "Volume-to-Ensemble"])
        layout.addWidget(QLabel("Ensemble Generation:")); layout.addWidget(self.ensemble_type)

        options_layout = QHBoxLayout()
        self.ensemble_data_checkbox = QCheckBox("Ensemble Data")
        self.dda_checkbox = QCheckBox("DDA")
        self.ddpost_checkbox = QCheckBox("DDPostprocessing")
        options_layout.addWidget(self.ensemble_data_checkbox)
        options_layout.addWidget(self.dda_checkbox)
        options_layout.addWidget(self.ddpost_checkbox)
        options_layout.addStretch()
        options_layout.addWidget(self.run_button)
        layout.addLayout(options_layout)
        
        layout.addStretch()
        self.setLayout(layout)

    
    def run_program(self):
        """
        Generate one or more ensembles and execute selected tasks.

        Reads all user inputs, constructs the configuration dictionary
        passed to :meth:`CloudGenerator.generate_cloud`, persists each
        ensemble, and executes ensemble data generation, DDA, and/or
        post‑processing based on the state of the corresponding checkboxes.
        Database status flags are updated after each successful task.
        """
        dipole_size = float(self.dipole_input.text()) if hasattr(self, 'dipole_input') else 1
        ensemble_size = float(self.ensemble_size.text()) if hasattr(self, 'ensemble_size') else 25
        
        plasmonic_data = self.PNS.get_data(dipole_size, 1)
        dielectric_data = self.DNR.get_data(dipole_size, 2)
        plasmonic_data["type"] = "plasmonic"
        dielectric_data["type"] = "dielectric"
        ensembe_type = "c2e" if self.ensemble_type.currentText() == "Cell-to-Ensemble" else "v2e"
        ensemble_data = {"data": {"plasmonic": plasmonic_data, "dielectric": dielectric_data}, 
                    "cloud_radius": ensemble_size / dipole_size, 
                    "dipole_size": dipole_size}
        materials = {"plasmonic": plasmonic_data["material"], "dielectric": dielectric_data["material"]}
        wavelength = float(self.wavelength.text()) if hasattr(self, 'wavelength') else 800
        num_ensembles = int(self.number_ensembles.text()) if hasattr(self, 'number_ensembles') else 1
        for _ in range(num_ensembles):
            storer = Storer()
            ensemble = CloudGenerator().generate_cloud(ensemble_data, materials, option=ensembe_type)
            ensemble.ensemble_id = storer.store_new_ensemble(ensemble)
            
            runner = Runner(ensemble)
            executer = Executer(ensemble, wavelength=wavelength)
            print(f"'{ensemble.ensemble_id}'")

            ensemble_dir = os.path.join(self.paths["outputDir"], "ensembles", ensemble.ensemble_id)
            os.makedirs(ensemble_dir, exist_ok=True)

            if self.ensemble_data_checkbox.isChecked():
                runner.generate_ensemble_data()
                storer.update_ensembe_info(ensemble.ensemble_id, "ensemble_data")

            if self.dda_checkbox.isChecked():
                executer.run_ddscat()
                storer.update_ensembe_info(ensemble.ensemble_id, "ddscat_run")

            if self.ddpost_checkbox.isChecked():
                executer.run_ddpostprocess()
                storer.update_ensembe_info(ensemble.ensemble_id, "postprocessing_run")
                

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParameterWindow()
    window.show()
    sys.exit(app.exec_())
