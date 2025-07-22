"""Settings management UI components.

This module provides two PyQt5 widgets used to persist and display
application directory paths via ``QSettings``.

Classes
-------
DirectoryDialog
    Modal dialog that lets the user browse for three required folders
    (output, DDSCAT executable, and materials) and saves them into
    ``QSettings`` when accepted.
SettingsWindow
    Read‑only summary panel that shows the currently stored folders and
    exposes a button allowing the user to reopen ``DirectoryDialog`` to
    change them. Emits ``settingsSaved`` after every dialog dismissal
    (whether or not the user actually changed values) so the rest of the
    application can refresh its state.

Design Notes
------------
* All persistent state is handled exclusively through ``QSettings`` using
  organization ``LogicLorenzo`` and application ``PTTool`` so these
  widgets can be dropped into any main window without additional glue.
* The dialog stores references to each editable ``QLineEdit`` together
  with the corresponding settings key in ``self.rows`` to avoid parallel
  lists.
* ``SettingsWindow`` keeps local copies of the three directory paths
  (``self.output_dir`` etc.) that other parts of the application can
  query directly after the signal ``settingsSaved`` is emitted.
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QDialog, QFileDialog
)
from PyQt5.QtCore import QSettings, pyqtSignal

class DirectoryDialog(QDialog):
    """Modal dialog to pick and persist required folder paths.

    The dialog presents three rows, each with a label, a line edit, and a
    *Browse…* button. When the dialog is accepted the current contents of
    each line edit are written back to ``QSettings``.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget for modality / ownership.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Folders")
        self.resize(500, 200)

        # Load stored paths (or "" if not set)
        settings     = QSettings("LogicLorenzo", "PTTool")
        out_dir  = settings.value("outputDir",  "")
        ddscat_dir = settings.value("DDSCATDir", "")
        mat_dir = settings.value("materialDir",    "")

        layout = QVBoxLayout(self)

        # helper to make a row of (label, edit, browse)
        def make_row(label_text, init_text, key):
            """Create one (label, line edit, browse button) row.

            Returns
            -------
            tuple(QLineEdit, str)
                The created line edit and the settings key; both are
                stored so we can iterate later when saving.
            """
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            edit = QLineEdit(init_text)
            btn  = QPushButton("Browse…")
            def on_browse():
                d = QFileDialog.getExistingDirectory(self, f"Select {label_text}", edit.text())
                if d:
                    edit.setText(d)
            btn.clicked.connect(on_browse)
            row.addWidget(lbl)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            layout.addLayout(row)
            return edit, key

        # build the three rows
        self.rows = []
        self.rows.append(make_row("Output Directory:",  out_dir,  "outputDir"))
        self.rows.append(make_row("DDSCAT Directory:", ddscat_dir, "DDSCATDir"))
        self.rows.append(make_row("Materials Directory:",    mat_dir, "materialDir"))

        # OK / Cancel
        btns = QHBoxLayout()
        ok  = QPushButton("OK");     ok.clicked.connect(self.accept)
        can = QPushButton("Cancel"); can.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(can)
        layout.addLayout(btns)

    def accept(self):
        """Persist current edits into ``QSettings`` then close.

        Overridden to ensure data is saved prior to emitting the standard
        ``accepted`` signal via ``super().accept()``.
        """
        # save current edits back to QSettings
        settings = QSettings("LogicLorenzo", "PTTool")
        for edit, key in self.rows:
            settings.setValue(key, edit.text())
        super().accept()

    def get_paths(self):
        """Return the current text of all three directory fields.

        Returns
        -------
        list[str]
            Ordered list ``[output_dir, ddscat_dir, materials_dir]``.
        """
        return [edit.text() for edit, _ in self.rows]

class SettingsWindow(QWidget):
    """Widget showing stored directory settings and allowing edits.

    The window displays the three persisted directories in read‑only
    ``QLineEdit`` widgets along with a *Change Folders…* button. When the
    user clicks the button a :class:`DirectoryDialog` is shown. After the
    dialog closes (regardless of acceptance) the ``settingsSaved`` signal
    is emitted so other components (e.g., tab enablers) can refresh their
    state.

    Attributes
    ----------
    settingsSaved : pyqtSignal()
        Emitted whenever the dialog is dismissed. Listeners should read
        the updated path attributes ``output_dir``, ``ddscat_dir`` and
        ``mat_dir`` directly from this instance.
    """
    settingsSaved = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Main Application")
        self.resize(400,300)

        # load the saved dirs so far
        settings     = QSettings("LogicLorenzo", "PTTool")
        self.output_dir  = settings.value("outputDir",  "")
        self.ddscat_dir = settings.value("DDSCATDir", "")
        self.mat_dir    = settings.value("materialDir",    "")

        layout = QVBoxLayout(self)

        # show them in read-only fields (optional)
        self.out_edit  = QLineEdit(self.output_dir);  self.out_edit.setReadOnly(True)
        self.ddscat_edit = QLineEdit(self.ddscat_dir); self.ddscat_edit.setReadOnly(True)
        self.mat_edit = QLineEdit(self.mat_dir);    self.mat_edit.setReadOnly(True)
        for lbl_text, edit in [("Output Directory:",self.out_edit),
                               ("DDSCAT Directory:",self.ddscat_edit),
                               ("Materials Directory:",   self.mat_edit)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(lbl_text))
            row.addWidget(edit, 1)
            layout.addLayout(row)

        # Button to re-open the folder-picker at any time
        btn = QPushButton("Change Folders…")
        btn.clicked.connect(self.change_folders)
        layout.addWidget(btn)

        layout.addStretch()

    def change_folders(self):
        """Open the directory dialog and update internal state.

        If the dialog is accepted the three path attributes and their
        corresponding read‑only fields are updated. The ``settingsSaved``
        signal is emitted unconditionally so any listener can decide how
        to handle cancellation vs. acceptance.
        """
        dlg = DirectoryDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            # pull back the new paths
            self.output_dir, self.ddscat_dir, self.mat_dir = dlg.get_paths()
            # update display
            self.out_edit.setText(self.output_dir)
            self.ddscat_edit.setText(self.ddscat_dir)
            self.mat_edit.setText(self.mat_dir)
            # now any part of your app can use self.input_dir, etc.
        self.settingsSaved.emit()


