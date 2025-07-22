"""
Primitive geometric shapes (sphere, rod) with dipole discretization.

This module defines simple 3‑D shape classes used to build ensembles for
discrete dipole simulations. Shapes can be translated, randomly or
explicitly rotated (rods), and discretized into integer lattice
coordinates suitable for DDSCAT input.

Functions
---------
rotate(points, rotation)
    Apply successive x/y/z Euler‑angle rotations (degrees) to a set of
    3‑D points.

Classes
-------
ShapeFactory
    Simple factory that instantiates the appropriate shape based on a
    parameter dictionary.
Sphere
    Solid sphere centered at the origin; supports translation and volume
    / dipole discretization queries.
Rod
    Spherocylinder composed of a cylinder segment with two hemispherical
    caps; supports arbitrary 3‑D rotation, translation, and dipole
    discretization.
"""
import numpy as np


def rotate(points, rotation):
    """
    Rotate an array of points by three Euler angles (degrees).

    Rotations are applied in X→Y→Z order using the right‑hand rule.

    Parameters
    ----------
    points : array_like, shape (N, 3) or (2, 3)
        Input coordinates to transform.
    rotation : sequence[float]
        Three angles in degrees (rx, ry, rz).

    Returns
    -------
    numpy.ndarray
        Rotated coordinates with the same leading shape as ``points``.
    """
    rotation_angle_x = np.deg2rad(rotation[0])
    rotation_angle_y = np.deg2rad(rotation[1])
    rotation_angle_z = np.deg2rad(rotation[2])

    rotation_matrix_x = np.array(
        [
            [1, 0, 0],
            [0, np.cos(rotation_angle_x), -np.sin(rotation_angle_x)],
            [0, np.sin(rotation_angle_x), np.cos(rotation_angle_x)],
        ]
    )

    rotation_matrix_y = np.array(
        [
            [np.cos(rotation_angle_y), 0, np.sin(rotation_angle_y)],
            [0, 1, 0],
            [-np.sin(rotation_angle_y), 0, np.cos(rotation_angle_y)],
        ]
    )

    rotation_matrix_z = np.array(
        [
            [np.cos(rotation_angle_z), -np.sin(rotation_angle_z), 0],
            [np.sin(rotation_angle_z), np.cos(rotation_angle_z), 0],
            [0, 0, 1],
        ]
    )

    # Combine the three rotations by multiplying the matrices in the desired order
    rotation_matrix = np.dot(
        rotation_matrix_x, np.dot(rotation_matrix_y, rotation_matrix_z)
    )

    return np.dot(points, rotation_matrix)


class ShapeFactory:
    """
    Factory for constructing shape instances.

    Methods
    -------
    shape_selector(parameters, rotation=[None, None, None])
        Create either a :class:`Sphere` or :class:`Rod` based on the
        ``parameters['shape']`` field.
    """
    @staticmethod
    def shape_selector(parameters, rotation=[None, None, None]):
        """
        Instantiate a shape from a parameter dictionary.

        Parameters
        ----------
        parameters : dict
            Must contain at least ``'shape'`` and a ``'params'`` list.
        rotation : list[float] or list[None], optional
            Explicit Euler angles for rods; if all ``None`` a random
            rotation is chosen.

        Returns
        -------
        Sphere or Rod
            Newly created shape instance.
        """
        if parameters["shape"] == "sphere":
            body = Sphere(parameters)
        if parameters["shape"] == "rod":
            body = Rod(parameters, rotation=rotation)
        return body


class Sphere:
    """
    Solid sphere centered at the origin.

    Parameters
    ----------
    data : dict
        Dictionary with key ``'params'`` whose first element is the
        sphere radius.

    Attributes
    ----------
    radius : float
        Sphere radius in dipole units.
    center : numpy.ndarray, shape (3,)
        Current center position (updated by :meth:`move`).
    """

    def __init__(self, data):
        self.shape = "sphere"
        self.radius = data["params"][0]
        self.center = np.array([0.0, 0.0, 0.0])
        self.dipoles = []

    @property
    def volume(self):
        """
        Continuous geometric volume of the sphere.

        Returns
        -------
        float
            ``4/3 * pi * r^3``.
        """
        return 4 / 3 * np.pi * self.radius**3

    def move(self, position):
        """
        Translate the sphere by a vector.

        Parameters
        ----------
        position : sequence[float]
            Displacement to add to the current center.
        """
        self.position = np.array(position)
        self.center += self.position
        
    def point_inside(self, point):
        """
        Test if a lattice point lies inside the sphere.

        Parameters
        ----------
        point : array_like, shape (3,)
            Candidate point relative to the current center.

        Returns
        -------
        bool
            True if the point is within the radius.
        """
        distance = np.linalg.norm(point)
        # Check if point is inside the sphere
        return distance <= self.radius

    def discretize(self):
        """
        Generate integer lattice dipoles filling the sphere volume.

        Returns
        -------
        numpy.ndarray, shape (M, 3)
            Unique integer coordinates belonging to the sphere.
        """
        rad_array = np.ceil([self.radius, self.radius, self.radius])
        min_position = -rad_array.astype(int)
        max_position = rad_array.astype(int)

        dipoles = []
        for x in range(min_position[0], max_position[0] + 1):
            for y in range(min_position[1], max_position[1] + 1):
                for z in range(min_position[2], max_position[2] + 1):
                    point = np.array([x, y, z])
                    if self.point_inside(point):
                        dipoles.append(point)
        dipoles = np.array(dipoles + np.array(self.center))
        dipoles = np.unique(np.around(dipoles).astype(int), axis=0)
        return dipoles


class Rod:
    """
    Spherocylinder (capped cylinder) oriented by Euler angles.

    The rod consists of a cylindrical segment of height
    ``height - 2*radius`` plus two hemispherical caps. The internal
    ``center`` array stores the endpoints of the cylindrical segment
    after rotation.

    Parameters
    ----------
    data : dict
        Dictionary with key ``'params'`` = ``[radius, height]``.
    rotation : list[float] or list[None], optional
        Three Euler angles in degrees. If all ``None`` a random rotation
        in [0, 360)° for each axis is generated.

    Attributes
    ----------
    radius : float
        Rod radius.
    height : float
        Total end‑to‑end length including caps.
    rotation : numpy.ndarray, shape (3,)
        Euler angles applied to the canonical orientation.
    center : numpy.ndarray, shape (2, 3)
        Rotated endpoints of the cylindrical segment.
    """

    def __init__(self, data, rotation=[None, None, None]):
        self.shape = "rod"
        self.radius = data["params"][0]
        self.height = data["params"][1]
        if rotation == [None, None, None]:
            self.rotation = np.random.uniform(0, 360, size=3)
        else:
            self.rotation = np.array(rotation)
        center = np.array(
            [
                [0, 0, self.height / 2 - self.radius],
                [0, 0, -(self.height / 2 - self.radius)],
            ]
        )
        self.center = rotate(center, self.rotation)

    @property
    def volume(self):
        """
        Translate the rod by a vector.

        Parameters
        ----------
        position : sequence[float]
            Displacement added to both endpoints.
        """
        tip_volume = 4 / 3 * np.pi * self.radius**3
        rod_volume = np.pi * self.radius**2 * (self.height - 2 * self.radius)
        return tip_volume + rod_volume

    def move(self, position):
        
        self.center += np.array(position)
        self.position = np.array(position)
        

    def point_inside_rod(self, point):
        """
        Test if a point lies inside the cylindrical segment.

        Parameters
        ----------
        point : array_like, shape (3,)
            Candidate point in the rod's local (unrotated) frame.

        Returns
        -------
        bool
            True if within radius and interior height.
        """
        distance_xy = np.linalg.norm(point[:2])
        # Check if the point is within the cylinder's radius and height
        return distance_xy <= self.radius and abs(point[2]) <= (
            self.height / 2 - self.radius
        )

    def point_inside_tip(self, point):
        """
        Test if a point lies inside either hemispherical cap.

        Parameters
        ----------
        point : array_like, shape (3,)
            Candidate point in the rod's local frame.

        Returns
        -------
        bool
            True if inside either spherical tip.
        """
        rod_height = np.array([0, 0, self.height / 2 - self.radius])
        distance_pos = np.linalg.norm(point - rod_height)
        distance_neg = np.linalg.norm(point + rod_height)
        return distance_pos <= self.radius or distance_neg <= self.radius

    def discretize(self):
        """
        Generate integer lattice dipoles filling the rod volume.

        Returns
        -------
        numpy.ndarray, shape (M, 3)
            Unique integer coordinates for the rotated rod.
        """
        bounds = np.array([np.ceil(self.radius), np.ceil(self.radius), np.ceil(self.height / 2)])

        rod_points = []
        for x in np.linspace(-bounds[0], bounds[0], int(2 * bounds[0] + 1)):
            for y in np.linspace(-bounds[1], bounds[1], int(2 * bounds[1] + 1)):
                for z in np.linspace(-bounds[2], bounds[2], int(2 * bounds[2] + 1)):
                    point = np.round([x, y, z])
                    if self.point_inside_rod(point) or self.point_inside_tip(point):
                        rod_points.append(point)
        rotated_points = rotate(np.array(rod_points), self.rotation)
        rod_points = rotated_points + np.average(self.center, axis=0)
        dipoles = np.unique(np.around(rod_points).astype(int), axis=0)
        return dipoles
        

if __name__ == "__main__":
    rod = Rod([10, 45], rotation=[0, 0, 0])
    sphere = Sphere([10])
    
    r = np.arange(20, 210, 10)
    theta = np.arange(0, 95, 5)

    visualize = False
    print((3 * (sphere.volume + rod.volume)/(4 * np.pi)) ** (1/3)/1e3)
    sphere_dipoles = sphere.discretize()
    rod_dipoles = np.rint(rod.discretize()).astype(int)
    results = np.zeros((len(sphere_dipoles), len(rod_dipoles)))
    for r_idx in range(len(r)):
        for t_idx in range(len(theta)):
            sphere_dipoles = sphere.discretize()
            location = [0, r[r_idx] * np.cos(np.deg2rad(theta[t_idx])), r[r_idx] * np.sin(np.deg2rad(theta[t_idx]))]
            if location[1] < 22 and location[2] < 35:
                continue
            else:
                sphere_dipoles += location
                sphere_dipoles = np.unique(np.rint(sphere_dipoles), axis=0).astype(int)
                total_dipoles = len(sphere_dipoles) + len(rod_dipoles)
                row_count = 1          
                with open("shape.dat", "w") as f:
                    pre = [ f"R = {r[r_idx]}, theta = {theta[t_idx]}\n",
                            f"{total_dipoles} = NAT \n",
                            "1.000000  0.000000  0.000000 = A_1 vector\n",
                            "0.000000  1.000000  0.000000 = A_2 vector\n",
                            "1.000000  1.000000  1.000000 = lattice spacings (d_x,d_y,d_z)/d\n",
                            "0.000000  0.000000  0.000000 = lattice offset x0(1-3) = (x_TF,y_TF,z_TF)/d for dipole 0 0 0\n",
                            "JA  IX  IY  IZ ICOMP(x,y,z)\n"]
                    f.writelines(pre)
                    for row in sphere_dipoles:
                        f.write(f"{row_count} {row[0]} {row[1]} {row[2]} 1 1 1\n")
                        row_count += 1
                    for row in rod_dipoles:
                        f.write(f"{row_count} {row[0]} {row[1]} {row[2]} 2 2 2\n")
                        row_count += 1
                
    
    if visualize:
        import pyvista as pv

        sphere_vis = pv.Sphere(radius=10,
                        center=location,
                        theta_resolution=60,
                        phi_resolution=60)

        # Create a cylinder (rod) of length 4, radius 0.2, oriented along the y–axis
        rod_vis = pv.Cylinder(center=np.average(rod.center, axis=0),
                        direction=rod.center[1] - rod.center[0],
                        radius=10,
                        height=25,
                        resolution=60)
        cap1 = pv.Sphere(radius=10,
                        theta_resolution=60,
                        phi_resolution=60)
        

        cap2 = pv.Sphere(radius=10,
                        center=rod.center[1],
                        theta_resolution=60,
                        phi_resolution=60)
        # Set up the plotter
        p = pv.Plotter()
        p.add_mesh(sphere_vis, color='gold',     label='Sphere')
        p.add_mesh(rod_vis,    color='steelblue',  label='Rod')
        p.add_mesh(cap1,    color='steelblue')
        p.add_mesh(cap2,    color='steelblue')

        # Add a legend, grid, and axes
        p.camera_position = "yz"
        
        # Render!
        p.show(window_size=[800, 600])
