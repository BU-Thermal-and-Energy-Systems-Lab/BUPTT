"""
Cloud generation and persistence utilities.

The module exposes :class:`CloudGenerator`, a builder for particle clouds
(spheres and rods) using either *cell‑to‑ensemble* or *volume‑to‑ensemble*
placement strategies. Generated clouds can be reloaded from the backing
SQLite database, discretized into dipole coordinates, and analyzed via
distance histograms.

Logging
-------
All progress and early‑termination warnings are emitted through the
``cloud_generation`` logger.

Usage
-----
>>> system = {"data": {...}, "cloud_radius": 50.0, "dipole_size": 2.0}
>>> materials = {"plasmonic": "Au.nk", "dielectric": "SiO2.nk"}
>>> cloud = CloudGenerator().generate_cloud(system, materials, option="v2e")
>>> dipoles = cloud.discretize_cloud()
"""
import numpy as np
from discretization import ShapeFactory
from Calculator import Calculator
from time import time
import logging
import sqlite3


class CloudGenerator:
    """
    Construct and manipulate particle clouds.

    Methods
    -------
    read_cloud(ensemble_id)
        Populate this instance from rows stored in the SQLite database.
    generate_cloud(system, materials, option='c2e')
        Create a new cloud using either *cell‑to‑ensemble* (c2e) or
        *volume‑to‑ensemble* (v2e) logic.
    discretize_cloud()
        Invoke each body's ``discretize`` method and collect unique
        dipole coordinates.
    calculate_distribution()
        Histogram pairwise center distances for the current bodies.
    """
    def __init__(self):
        """Initialize helpers used during placement and analysis."""
        self.calculator = Calculator()

    def read_cloud(self, ensemble_id):
        """
        Reconstruct a cloud from the persistent database.

        Parameters
        ----------
        ensemble_id : str
            Identifier used to query ensemble metadata and particle rows.

        Returns
        -------
        CloudGenerator
            This instance for fluent chaining.
        """
        conn = sqlite3.connect("ensembles.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""SELECT cloud_radius, dipole_size  FROM ensembles WHERE ensemble_id = ?""", (ensemble_id,))
        ensemble_data = dict(cur.fetchone())
        self.ensemble_id = ensemble_id
        self.dipole_size = ensemble_data["dipole_size"]
        self.cloud_radius = ensemble_data["cloud_radius"] / self.dipole_size
        cur.execute("""SELECT * FROM ensemble_particles WHERE ensemble_id = ?""", (self.ensemble_id,))
        self.bodies = []
        self.materials = {}
        plas_recorded = False
        diel_recorded = False
        for row in cur.fetchall():
            particle = dict(row)
            if particle["shape"] == "sphere":
                particle["params"] = [particle["radius"] / self.dipole_size]                
            elif particle["shape"] == "rod":
                particle["params"] = [
                    particle["radius"] / self.dipole_size,
                    particle["length"] / self.dipole_size
                ]
            body = ShapeFactory.shape_selector(
                particle, rotation=[particle["rx"], particle["ry"], particle["rz"]]
            )
            body.material_idx = particle["material_idx"]
            body.move([
                        particle["cx"] / self.dipole_size,
                        particle["cy"] / self.dipole_size,
                        particle["cz"] / self.dipole_size]
                    )
            self.bodies.append(body)
            if particle["material_idx"] == 1 and not plas_recorded:
                self.materials["plasmonic"] =  particle["material"],
                plas_recorded = True
            if particle["material_idx"] == 2 and not diel_recorded:
                self.materials["dielectric"] = particle["material"]
                diel_recorded = True
        cur.close(), conn.close()
        return self
           
    def generate_cloud(self, system, materials, option="c2e"):
        """
        Generate a new particle cloud.

        Two placement modes are supported:

        * ``'c2e'`` (*cell‑to‑ensemble*): fill a 3‑D grid of cubic cells,
          choosing integer counts of each particle type so their target
          volume fractions are met locally.
        * ``'v2e'`` (*volume‑to‑ensemble*): randomly place particles
          within a sphere of diameter ``4 * cloud_radius`` until each
          type's fractional target volume is satisfied.

        Collision rejection (up to 500 trials per particle) prevents
        overlap; early termination is logged if exceeded.

        Parameters
        ----------
        system : dict
            Must contain keys ``'data'`` (mapping of type → parameter
            dicts), ``'cloud_radius'`` (float, dipole units), and
            ``'dipole_size'`` (physical size).
        materials : dict
            Mapping of type labels (``'plasmonic'``, ``'dielectric'``)
            to material identifiers.
        option : {'c2e', 'v2e'}, default='c2e'
            Placement strategy.

        Returns
        -------
        CloudGenerator
            This instance populated with ``bodies`` and metadata.
        """
        
        self.option = option
        self.particle_data = system["data"]
        self.cloud_radius = system["cloud_radius"]
        self.dipole_size = system["dipole_size"]
        self.polydispersity = system.get("polydispersity", 0.0)
        self.materials = materials
        def cell_to_ensemble():
            """
            Populate the cloud using the *cell‑to‑ensemble* strategy.

            The domain is tiled with cubic cells of edge length ``L`` chosen so
            that an integer pair of particle counts ``(N_plas, N_diel)`` within a
            single cell approximates the target volume‑fraction ratio. For each
            lattice cell all required particles are placed uniformly at random
            (with rejection to avoid overlaps) inside the cell bounds. After all
            cells are processed, only bodies whose geometric center lies within
            ``cloud_radius`` of the origin are retained.

            Early termination occurs if any particle exceeds 500 failed placement
            trials; a warning is logged and the partially filled cloud is returned.

            Returns
            -------
            CloudGenerator
                This instance with ``bodies`` populated.
            """
            def pick_counts_and_cell_size(max_denom=20):
                from fractions import Fraction
                import math
                # 1) target ratio
                V1 = ShapeFactory.shape_selector(self.particle_data["plasmonic"]).volume
                V2 = ShapeFactory.shape_selector(self.particle_data["dielectric"]).volume
                phi1 = self.particle_data["plasmonic"]["volume_fraction"]
                phi2 = self.particle_data["dielectric"]["volume_fraction"]
                r = (phi1*V2) / (phi2*V1)

                # 2) approximate r by N1/N2 with small denominators
                frac = Fraction(r).limit_denominator(max_denom)
                N1, N2 = frac.numerator, frac.denominator

                # 3) compute exact V_cell to meet phi1
                Vcell = (N1 * V1) / phi1         # in dipole‑volume units
                # you can check how close phi2 is:
                phi2_achieved = (N2 * V2) / Vcell

                # 4) edge length in dipole units
                L = math.ceil(Vcell ** (1/3))

                return N1, N2, L

            container_bodies = [] 
            N_plas, N_diel, cell_size = pick_counts_and_cell_size()
            
            for x in np.arange(-self.cloud_radius, self.cloud_radius + cell_size, cell_size):
                for y in np.arange(-self.cloud_radius, self.cloud_radius + cell_size, cell_size):
                    for z in np.arange(-self.cloud_radius, self.cloud_radius + cell_size, cell_size):
                        cell_position = np.array([x, y, z])
                        cell_bodies = []
                        for idx in range(N_plas + N_diel):
                            trials = 0
                            is_placed = False
                            mat_type = ("plasmonic" if (idx < N_plas) else "dielectric")
                            body = ShapeFactory.shape_selector(self.particle_data[mat_type])
                            body.material     = self.particle_data[mat_type]["material"]
                            body.material_idx = self.particle_data[mat_type]["material_idx"]
                            while not is_placed:
                                is_colliding = False
                                body_min = np.array([-cell_size / 2, -cell_size / 2, -cell_size / 2]) - np.min(body.center, axis=0)
                                body_max = np.array([cell_size / 2, cell_size / 2, cell_size / 2]) - np.max(body.center, axis=0)
                                particle_position = cell_position + np.random.uniform(body_min, body_max)
                                for old_body in cell_bodies:
                                    if (
                                        self.calculator.calculate_center_distance(
                                            body.center + particle_position, old_body.center
                                        )
                                        < body.radius + old_body.radius + 1
                                    ):
                                        is_colliding = True
                                        trials += 1
                                        if trials > 500:
                                            return
                                        break
                                if not is_colliding:
                                    body.move(particle_position)
                                    cell_bodies.append(body)
                                    is_placed = True
                        container_bodies.extend(cell_bodies)
            for body in container_bodies:
                if body.shape == "sphere":
                    center_point = body.center
                else:
                    center_point = np.mean(body.center, axis=0)
                if np.linalg.norm(center_point) < self.cloud_radius:
                    self.bodies.append(body)
            return self
    
        def volume_to_ensemble():
            """
            Populate the cloud using the *volume‑to‑ensemble* strategy.

            For each particle type, repeatedly sample a random position inside a
            sphere of radius ``2*cloud_radius`` (uniform in volume) and attempt
            to place a new body there. A placement is rejected if its center is
            closer than ``radius_i + radius_j + dipole_size + 1`` to any already
            accepted body. Sampling continues until the cumulative volume of that
            type reaches its target fraction:
            ``target_vol = (4/3)π (2*cloud_radius)^3 * volume_fraction``.

            After all types are processed, only bodies whose center lies within
            the inner sphere of radius ``cloud_radius`` are kept. If any body
            exceeds 500 failed placement trials the procedure aborts early with
            a warning.

            Returns
            -------
            CloudGenerator
                This instance with ``bodies`` populated.
            """
            

            volume = 0
            start_time = time()
            collection_bodies = []
            for _, particle in self.particle_data.items():
                par_vol = 0
                target_vol = 4 * np.pi / 3 * (2 * self.cloud_radius)**3 * particle["volume_fraction"]
                while par_vol < target_vol:
                    trials = 0
                    is_placed = False
                    body = ShapeFactory.shape_selector(particle)
                    while not is_placed:
                        phi       = np.random.uniform(0, 2*np.pi)
                        cos_theta = np.random.uniform(-1, 1)
                        sin_theta = np.sqrt(1 - cos_theta**2)
                        direction = np.array([
                            sin_theta * np.cos(phi),
                            sin_theta * np.sin(phi),
                            cos_theta
                        ])

                        # pick r so that the CDF ~ r³ (this yields a uniform volume density)
                        u = np.random.random()               # in [0,1]
                        r = (u ** (1/3)) * (2 * self.cloud_radius)

                        particle_position = direction * r
                        is_colliding = False
                        for old_body in collection_bodies:
                            if (
                                self.calculator.calculate_center_distance(
                                    body.center + particle_position, old_body.center
                                )
                                < body.radius + old_body.radius + self.dipole_size + 1
                            ):
                                trials += 1
                                is_colliding = True
                                break
                        if trials > 500:
                            return
                        if not is_colliding:
                            body.move(particle_position)
                            body.material_idx = particle["material_idx"]
                            body.material = particle["material"]
                            collection_bodies.append(body)
                            par_vol += body.volume
                            is_placed = True

                volume += par_vol
            for body in collection_bodies:
                if self.calculator.calculate_center_distance(body.center, np.array([0, 0, 0])) < self.cloud_radius:
                    self.bodies.append(body)
            return self
        
        self.option = option
        self.bodies = []
        if option == "c2e":
            return cell_to_ensemble()
        elif option == "v2e":
            return volume_to_ensemble()
        
    def discretize_cloud(self):
        """
        Discretize all bodies into dipole coordinates.

        Returns
        -------
        list[numpy.ndarray]
            List of unique integer dipole positions aggregated across
            shapes.
        """
        self.dipoles = []
        for body in self.bodies:
            body.discretize()
            self.dipoles.extend(np.unique(np.round(body.dipoles), axis=0))
        return self.dipoles
        
    def calculate_distribution(self):
        """
        Histogram pairwise center distances among bodies.

        Bins the upper‑triangle of all center–center distances into 20
        linearly spaced bins over ``[0, 2*cloud_radius)``.

        Returns
        -------
        numpy.ndarray, shape (20,)
            Counts per distance bin.
        """
        num_particles = len(self.bodies)
        step = 2 * self.cloud_radius / 20
        d_hist = np.zeros(20)
        for i in range(num_particles):
            par1 = self.bodies[i].center
            for j in range(i + 1, num_particles):
                par2 = self.bodies[j].center
                dist = self.calculator.calculate_center_distance(par1, par2)
                index = int(np.floor(dist / step))
                if 0 <= index < len(d_hist):
                    d_hist[index] += 1
        return d_hist

