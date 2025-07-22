"""
Persistent storage utilities for ensemble simulations.

This module defines the :class:`Storer` class, which manages creation and
updates of a lightweight SQLite schema for ensembles, their constituent
particles, and scattering results. A small shelve database is used to
generate unique ensemble identifiers.

Tables
------
ensembles
    One row per generated ensemble and high‑level metadata/flags.
ensemble_particles
    Per‑particle geometric/physical properties for an ensemble.
ensemble_scattering
    Scattering / absorption efficiencies indexed by wavelength and number
    of orientations.

Functions
---------
generate_new_key(key_db, n_bytes=5)
    Allocate a new unique hexadecimal identifier and persist it inside a
    shelve file so keys are never reused across sessions.
"""

import secrets, shelve, sqlite3, os

class Storer:
    """
    CRUD interface over the ensemble SQLite database.

    Parameters
    ----------
    settings : QSettings, optional
        If provided, can be used to derive on‑disk locations for the
        shelve file and SQLite database. Currently unused; the class
        defaults to local filenames ``keys`` and ``ensembles.db``.

    Attributes
    ----------
    key_db : str
        Path/prefix of the shelve file holding allocated keys.
    data_db : str
        Path to the SQLite database file.
    """

    def __init__(self, settings=None):
        """Initialize (or migrate) the database schema if not present."""
        
        self.key_db = os.path.join(settings.value("outputDir"), "keys")
        self.data_db = os.path.join(settings.value("outputDir"), "ensembles.db")
        db = sqlite3.connect(self.data_db)
        c  = db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS ensembles (
        ensemble_id             TEXT        PRIMARY KEY,
        ensemble_type           TEXT        NOT NULL,
        dipole_size             FLOAT        NOT NULL,
        cloud_radius            FLOAT        NOT NULL,
        plasmonic_fv            FLOAT        NOT NULL,
        dielectric_fv           FLOAT        NOT NULL,
        pdi                     FLOAT,
        ensemble_data           INTEGER     DEFAULT 0,
        ddscat_run              INTEGER     DEFAULT 0,
        postprocessing_run      INTEGER     DEFAULT 0,
        created_at              DATETIME    DEFAULT CURRENT_TIMESTAMP
        ); """)

        c.execute("""CREATE TABLE IF NOT EXISTS ensemble_particles (
        ensemble_id   TEXT     NOT NULL,
        particle_idx  INTEGER  NOT NULL,
        material_idx  INTEGER  NOT NULL,
        material      TEXT     NOT NULL,
        shape         TEXT     NOT NULL,
        radius        FLOAT     NOT NULL,
        length        FLOAT,
        volume        FLOAT     NOT NULL,       
        cx            FLOAT     NOT NULL,
        cy            FLOAT     NOT NULL,
        cz            FLOAT     NOT NULL,
        rx            FLOAT,
        ry            FLOAT,
        rz            FLOAT,
        PRIMARY KEY (ensemble_id, particle_idx),
        FOREIGN KEY (ensemble_id) REFERENCES ensembles(ensemble_id)
        ); """)

        c.execute("""CREATE TABLE IF NOT EXISTS ensemble_scattering (
        ensemble_id     TEXT        NOT NULL,
        wavelength      FLOAT        NOT NULL,
        num_ori         INTEGER     NOT NULL,
        abs_eff         FLOAT        NOT NULL,
        sca_eff         FLOAT        NOT NULL,
        abs_enh         FLOAT,
        PRIMARY KEY (ensemble_id, wavelength, num_ori),
        FOREIGN KEY (ensemble_id) REFERENCES ensembles(ensemble_id)
        );""")     

        db.commit()
        c.close(), db.close()

    def store_new_ensemble(self, ensemble):
        """
        Persist a newly generated ensemble and its particles.

        A unique ``ensemble_id`` is allocated, the ensemble row inserted,
        and then all particle records are bulk‑inserted. Numeric values
        stored in simulation units are converted back to physical units
        using the ensemble's ``dipole_size``.

        Parameters
        ----------
        ensemble : object
            Object exposing ``option``, ``dipole_size``, ``cloud_radius``,
            ``particle_data`` (dict with plasmonic/dielectric volume
            fractions), ``polydispersity`` and an iterable ``bodies`` of
            particle objects (with attributes ``material_idx``,
            ``material``, ``shape``, ``radius``, ``height`` (optional),
            ``volume``, ``position``, ``rotation`` (optional)).

        Returns
        -------
        str
            The generated unique ``ensemble_id``.
        """
        ensemble_id = generate_new_key(self.key_db)
        ensemble_db = sqlite3.connect(self.data_db)
        c = ensemble_db.cursor()
        c.execute("""INSERT INTO ensembles (
            ensemble_id, ensemble_type, dipole_size, cloud_radius, plasmonic_fv, dielectric_fv, pdi
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                ensemble_id,
                ensemble.option,
                ensemble.dipole_size,
                ensemble.cloud_radius * ensemble.dipole_size,
                ensemble.particle_data["plasmonic"]["volume_fraction"],
                ensemble.particle_data["dielectric"]["volume_fraction"],
                ensemble.polydispersity,
            )
        )
        for idx, particle in enumerate(ensemble.bodies):
            c.execute("""INSERT INTO ensemble_particles (
                ensemble_id, particle_idx, material_idx, material, shape, radius, length, volume, cx, cy, cz, rx, ry, rz
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ensemble_id,
                    idx,
                    particle.material_idx,
                    particle.material,
                    particle.shape,
                    particle.radius * ensemble.dipole_size,
                    particle.height * ensemble.dipole_size if hasattr(particle, 'height') else None,  # length is only for rods
                    particle.volume * ensemble.dipole_size**3,
                    *(particle.position) * ensemble.dipole_size,
                    *(particle.rotation if hasattr(particle, 'rotation') else (None, None, None))
                )
            )
        ensemble_db.commit()
        c.close(), ensemble_db.close()
        return ensemble_id
    
    def update_ensembe_info(self, ensemble_id, calculation_type):
        """
        Mark a calculation flag as completed for an ensemble.

        Sets one of the integer flag columns (``ensemble_data``,
        ``ddscat_run`` or ``postprocessing_run``) to 1.

        Parameters
        ----------
        ensemble_id : str
            Identifier of the target ensemble.
        calculation_type : {'ensemble_data', 'ddscat_run', 'postprocessing_run'}
            Name of the flag to update.
        """
        ensemble_db = sqlite3.connect(self.data_db)
        c = ensemble_db.cursor()
        if calculation_type == "ensemble_data":
            c.execute("UPDATE ensembles SET ensemble_data = 1 WHERE ensemble_id = ?", (ensemble_id,))
        elif calculation_type == "ddscat_run":
            c.execute("UPDATE ensembles SET ddscat_run = 1 WHERE ensemble_id = ?", (ensemble_id,))
        elif calculation_type == "postprocessing_run":
            c.execute("UPDATE ensembles SET postprocessing_run = 1 WHERE ensemble_id = ?", (ensemble_id,))
        ensemble_db.commit()
        c.close(), ensemble_db.close()


def generate_new_key(key_db, n_bytes=5):
    """
    Allocate and persist a new unique hexadecimal key.

    Keys are stored inside a shelve file so future allocations avoid
    collisions across application runs.

    Parameters
    ----------
    key_db : str
        Path/prefix of the shelve database used for key storage.
    n_bytes : int, default=5
        Number of random bytes to generate; the resulting key length will
        be ``2 * n_bytes`` hexadecimal characters.

    Returns
    -------
    str
        Newly generated unique key.
    """
    db = shelve.open(key_db, writeback=False)
    while True:
        token = secrets.token_hex(n_bytes)
        if token in db:
            continue
        db[token] = True
        db.sync()
        return token
    
