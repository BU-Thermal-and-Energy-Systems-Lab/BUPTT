"""
GUI views for listing ensembles, inspecting their particles, and launching
post‑processing tasks.

Classes
-------
EnsembleView
    Lightweight PyVista widget used to visualize a single ensemble's
    geometric bodies (spheres and rods) plus its enclosing cloud radius.
EnsembleListWindow
    Top‑level widget presenting the table of stored ensembles. Double‑
    clicking a row opens a :class:`ParticleListWindow`.
ParticleListWindow
    Detail window for a single ensemble: shows its particles in a table,
    a 3‑D visualization, and a multi‑select menu of pending calculations
    (ensemble data generation, DDA, post‑processing) that can be executed.
"""
import sqlite3
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableView, QLabel, QHBoxLayout, 
    QMenu, QListWidget, QListWidgetItem, QToolButton, QWidgetAction
)
from PyQt5.QtSql import QSqlDatabase, QSqlTableModel
from PyQt5.QtCore import Qt
import pyvista as pv
from pyvistaqt import QtInteractor
from generate_ensemble import CloudGenerator
from Storer import Storer
from Runner import Runner
from Executer import Executer


class EnsembleView(QtInteractor):
    """
    Embedded 3‑D viewer for an ensemble.

    Adds axes on construction and exposes :meth:`add_bodies` to populate
    the scene with all particles belonging to a given ``ensemble_id``.

    Parameters
    ----------
    parent : QWidget, optional
        Parent for normal Qt ownership.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_axes()

    def add_bodies(self, ensemble_id):
        """
        Populate the scene with all bodies for an ensemble.

        Spheres are rendered as ``pv.Sphere`` objects. Rods are rendered
        as a central ``pv.Cylinder`` plus two hemispherical caps to
        approximate a spherocylinder. An enclosing transparent sphere
        representing the cloud radius is also added. The camera is reset
        after population.

        Parameters
        ----------
        ensemble_id : str
            Identifier used by :class:`CloudGenerator` to reconstruct the
            ensemble on disk.
        """
        # create a cylinder between p1 and p2
        cloud = CloudGenerator()
        cloud.read_cloud(ensemble_id)
        for body in cloud.bodies:
            colorlist = ["#FFD700", "#ADD8E6"]
            if body.shape == "sphere":
                sphere = pv.Sphere(center=body.center, radius=body.radius)
                self.add_mesh(sphere, color= colorlist[body.material_idx - 1])
            elif body.shape == "rod":
                cylinder = pv.Cylinder(center=np.mean(body.center, axis=0),
                                  direction=np.subtract(body.center[1], body.center[0]),
                                  radius=body.radius, height=body.height - 2 * body.radius)
                self.add_mesh(cylinder, color=colorlist[body.material_idx - 1])
                cap1 = pv.Sphere(center=body.center[0], radius=body.radius)
                self.add_mesh(cap1, color=colorlist[body.material_idx - 1])
                cap2 = pv.Sphere(center=body.center[1], radius=body.radius)
                self.add_mesh(cap2, color=colorlist[body.material_idx - 1])
        enclosing = pv.Sphere(center=(0, 0, 0), radius=cloud.cloud_radius)
        self.add_mesh(enclosing, color="#786E6D8A", opacity=0.1)
        self.reset_camera()


class EnsembleListWindow(QWidget):
    """
    Window listing all stored ensembles.

    Uses a ``QSqlTableModel`` bound to the ``ensembles`` table and sorts
    by creation timestamp descending. Double‑clicking a row launches a
    :class:`ParticleListWindow` for that ensemble. The model is re‑queried
    each time the window is shown to keep the view current.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ensembles")
        self.resize(800, 600)

        # keep references to detail windows alive
        self._detail_windows = []

        # 1) open the SQLite database
        self.db = QSqlDatabase.database("ens_conn")
        if not self.db.open():
            raise RuntimeError(self.db.lastError().text())

        # 2) model for `ensembles` table
        self.model = QSqlTableModel(self, self.db)
        self.model.setTable("ensembles")
        self.model.select()
        self.model.setHeaderData(0, Qt.Horizontal, "ID")
        self.model.setHeaderData(1, Qt.Horizontal, "Type")
        self.model.setHeaderData(2, Qt.Horizontal, "Dipole Size")
        self.model.setSort(10, Qt.DescendingOrder)
        self.model.select()

        # 3) view
        view = QTableView()
        view.setModel(self.model)
        view.setSelectionBehavior(QTableView.SelectRows)
        view.setEditTriggers(QTableView.NoEditTriggers)
        view.doubleClicked.connect(self._on_double_click)

        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Double-click an ensemble to open its particles"))
        layout.addWidget(view)

    def _on_double_click(self, index):
        """
        Open a particle detail window for the double‑clicked ensemble.

        Parameters
        ----------
        index : QModelIndex
            Table index corresponding to the clicked row.
        """
        row = index.row()
        ensemble_id = self.model.data(self.model.index(row, 0))
        # open a new detail window
        detail_win = ParticleListWindow(self.db, ensemble_id)
        self._detail_windows.append(detail_win)  # keep reference
        detail_win.show()

    def showEvent(self, event):
        """
        Re‑select the underlying model whenever the widget becomes visible.

        Ensures newly created or updated ensembles appear without requiring
        a manual refresh.
        """
        super().showEvent(event)
        # every time this widget is shown, re‑query
        self.model.select()
        # if you have filters, you may also want:
        

class ParticleListWindow(QWidget):
    """
    Detail window for a single ensemble.

    Displays a filtered particle table, a 3‑D visualization, and a
    multi‑select dropdown listing computation steps that have not yet
    been performed. The user can select one or more steps and execute
    them via the *Run Selected Options* button.

    Parameters
    ----------
    db : QSqlDatabase
        Open database connection reused for particle queries.
    ensemble_id : str
        Identifier of the ensemble whose particles are displayed.
    """
    def __init__(self, db, ensemble_id):
        super().__init__()
        self.setWindowTitle(f"Particles in Ensemble {ensemble_id}")
        self.resize(600, 400)

        layout = QHBoxLayout(self)
        col1 = QVBoxLayout()
        col1.addWidget(QLabel(f"<b>Ensemble ID:</b> {ensemble_id}"))

        # model filtered to this ensemble_id
        self.model = QSqlTableModel(self, db)
        self.model.setTable("ensemble_particles")
        self.model.setFilter(f"ensemble_id = '{ensemble_id}'")
        self.model.select()
        self.model.setHeaderData(1, Qt.Horizontal, "Particle Index")

        # view
        view = QTableView()
        view.setModel(self.model)
        view.setSelectionBehavior(QTableView.SelectRows)
        view.setEditTriggers(QTableView.NoEditTriggers)
        # Hide the ensemble_id column
        view.setColumnHidden(self.model.record().indexOf("ensemble_id"), True)
        view.setColumnHidden(self.model.record().indexOf("material_idx"), True)
        view.setColumnHidden(self.model.record().indexOf("particle_idx"), True)
        col1.addWidget(view)
        
        layout.addLayout(col1)
        layout.addStretch()

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("<b>Visualization:</b>"))
        view = EnsembleView()
        view.add_bodies(ensemble_id)
        col2.addWidget(view)
        
        conn = sqlite3.connect("ensembles.db")
        # 2) (Optional) so you can access columns by name
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT ensemble_data, ddscat_run, postprocessing_run FROM ensembles WHERE ensemble_id = ?", (ensemble_id,))
        row = c.fetchone()
        conn.close()
        if row:
            ensemble_data = row["ensemble_data"]
            ddscat_run = row["ddscat_run"]
            postprocessing_run = row["postprocessing_run"]
        options = []
        if not ensemble_data:
            options.append("Ensemble data")
        if not ddscat_run:
            options.append("DDA")
        if not postprocessing_run:
            options.append("Postprocessing")

        option_button, option_list = self.make_dropdown(options)
        option_button.setToolTip("Possible calculations")
        row2 = QHBoxLayout()

        row2.addWidget(option_button)

        run_button = QToolButton()
        run_button.setText("Run Selected Options")
        run_button.clicked.connect(lambda: self.run_selected_options(option_list, ensemble_id))
        row2.addWidget(run_button), col2.addLayout(row2), layout.addLayout(col2)

    def make_dropdown(self, options):
        """
        Build a multi‑select dropdown menu.

        Each option is rendered as a checkable item inside a ``QListWidget``
        embedded in a ``QMenu`` attached to a ``QToolButton``.

        Parameters
        ----------
        options : list[str]
            Human‑readable calculation names to present.

        Returns
        -------
        tuple(QToolButton, QListWidget)
            The configured button and the underlying list widget used for
            state inspection.
        """
        multi_select_btn = QToolButton()
        multi_select_btn.setText("List of possible outputs ▼")
        multi_select_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        tag_list = QListWidget()
        for option in options:
            item = QListWidgetItem(option)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            tag_list.addItem(item)

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.addWidget(tag_list)
        container.setLayout(container_layout)

        action = QWidgetAction(self)
        action.setDefaultWidget(container)
        menu.addAction(action)
        multi_select_btn.setMenu(menu)
        return multi_select_btn, tag_list
    
    def get_selected_tags(self, tag_list):
        """
        Return the user‑checked calculation options.

        Parameters
        ----------
        tag_list : QListWidget
            Widget containing checkable items.

        Returns
        -------
        list[str]
            Text of all items whose state is ``Qt.Checked``.
        """
        selected = []
        for i in range(tag_list.count()):
            item = tag_list.item(i)
            if item.checkState():
                selected.append(item.text())
        print(f"Selected options: {selected}")
        return selected
    
    def run_selected_options(self, tag_list, ensemble_id):
        """
        Execute all user‑selected calculations for the ensemble.

        For each selected task the corresponding runner/executer method is
        invoked and the database flag updated via :class:`Storer`.

        Parameters
        ----------
        tag_list : QListWidget
            Source of user selections.
        ensemble_id : str
            Target ensemble identifier.
        """
        selected = self.get_selected_tags(tag_list)
        if not selected:
            print("No options selected")
            return
        
        # Here you would implement the logic to run the selected options
        # For now, we just print them
        print(f"Running: {', '.join(selected)} for ensemble {ensemble_id}")
        ensemble = CloudGenerator().read_cloud(ensemble_id)
        storer = Storer()
        runner = Runner(ensemble)
        executer = Executer(ensemble)
            
        # Example: if "Ensemble data" is selected, you might call a function to process it
        if "Ensemble data" in selected:
            runner.generate_ensemble_data()
            storer.update_ensembe_info(ensemble.ensemble_id, "ensemble_data")

        if "DDA" in selected:
            executer.run_ddscat()
            storer.update_ensembe_info(ensemble.ensemble_id, "ddscat_run")

        if "Postprocessing" in selected:
            executer.run_ddpostprocess()
            storer.update_ensembe_info(ensemble.ensemble_id, "postprocessing_run")