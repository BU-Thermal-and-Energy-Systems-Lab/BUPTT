"""
Application entry point and top‑level tabbed interface.

Classes
-------
MainWindow
    QMainWindow subclass that wires together the setup, run, and storage
    pages, manages a shared SQLite connection, and enables/disables tabs
    based on persisted configuration state.
"""

import run_page, store_page, setup_page
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
import sys
from PyQt5.QtCore import Qt, QSettings, QDir
from PyQt5.QtSql import QSqlDatabase

class MainWindow(QMainWindow):
    """
    Primary window hosting the application workflow.

    On construction a shared SQLite connection (named ``ens_conn``) is
    opened and three tabs are created:

    * **Generate New Ensembles** – user input form for creating ensembles.
    * **Old Ensembles** – table/visualization of previously stored ensembles.
    * **Setup Program** – directory configuration page.

    The first two tabs remain disabled until all required directories
    (output, DDSCAT, materials) exist. Whenever the setup page emits
    ``settingsSaved`` the tab lock state is recomputed.
    """
    def __init__(self):
        super().__init__()
        settings = QSettings("LogicLorenzo", "PTTool")
        self.setWindowTitle("Cloud Generation Tool")
        self.resize(1000, 600)

        self.db = QSqlDatabase.addDatabase("QSQLITE", "ens_conn")
        self.db.setDatabaseName("ensembles.db")
        if not self.db.open():
            raise RuntimeError(self.db.lastError().text())

        # Create a central widget and set the layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create a tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Add tabs for each page
        self.setup_page = setup_page.SettingsWindow()
        self.run_page = run_page.ParameterWindow()
        self.store_page = store_page.EnsembleListWindow()
        self.tabs.addTab(self.run_page, "Generate New Ensembles")
        self.tabs.addTab(self.store_page, "Old Ensembles")
        self.tabs.addTab(self.setup_page, "Setup Program")
        self.setup_page.settingsSaved.connect(self.update_tab_lock)
        self.update_tab_lock()

    def update_tab_lock(self):
        """
        Enable or disable tabs based on configured directory paths.

        Reads ``outputDir``, ``DDSCATDir``, and ``materialDir`` from
        ``QSettings``. If all exist, the generation/storage tabs are
        enabled and the first tab is shown; otherwise only the setup tab
        is accessible.
        """
        settings = QSettings("LogicLorenzo", "PTTool")
        output_dir = settings.value("outputDir", "", type=str)
        has_output = bool(output_dir and QDir(output_dir).exists())
        
        dds_dir = settings.value("DDSCATDir", "", type=str)
        has_dds = bool(dds_dir and QDir(dds_dir).exists())
        
        mat_dir = settings.value("materialDir", "", type=str)
        has_mat = bool(mat_dir and QDir(mat_dir).exists())

        has_all = has_output and has_dds and has_mat
        # enable the first two tabs only if we've got an outputDir
        for i in (0,1):
            self.tabs.setTabEnabled(i, has_all)
        # choose the page to show
        if has_all:
            self.tabs.setCurrentIndex(0)
        else:
            self.tabs.setCurrentIndex(2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())