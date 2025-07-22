"""
Geometric distance/angle calculations and ensemble distribution histograms.

The :class:`Calculator` class groups static helpers for computing pairwise
distances and angles between particles (spheres and rods) and for
aggregating those measurements into histogram distributions used in
ensemble‑level analysis.
"""
import numpy as np

class Calculator:
    """
    Collection of static geometry utilities.

    Methods
    -------
    calculate_center_distance(new_center, old_center)
        Distance between two centers: point–point, point–segment, or
        segment–segment depending on array dimensionality.
    point_to_segment_distance(point, segment)
        Shortest distance between a point and a line segment.
    segment_to_segment_distance(seg1, seg2)
        Shortest distance between two line segments.
    calculate_center_angle(sphere_center, rod_center)
        Angle (degrees) between the rod axis and the sphere–closest‑end
        vector.
    evaluate_distribution(ensemble)
        Build histograms of angles / distances for all sphere–rod,
        sphere–sphere, and rod–rod pairs present in an ensemble.
    """
    @staticmethod
    def calculate_center_distance(new_center, old_center):
        """
        Distance between two geometric centers.

        Parameters
        ----------
        new_center, old_center : numpy.ndarray
            Either a 1‑D array of shape ``(3,)`` representing a point or a
            2‑D array of shape ``(2, 3)`` representing a line segment
            (rod endpoints).

        Returns
        -------
        float
            Euclidean distance (point–point), point–segment distance, or
            segment–segment distance as appropriate.
        """
        
        if new_center.ndim == 1 and old_center.ndim == 1:
            return np.linalg.norm(new_center - old_center)

        # sphere–rod
        if new_center.ndim == 1 and old_center.shape == (2,3):
            return Calculator.point_to_segment_distance(new_center, old_center)
        if old_center.ndim == 1 and new_center.shape == (2,3):
            return Calculator.point_to_segment_distance(old_center, new_center)

        # rod–rod
        if new_center.shape == (2,3) and old_center.shape == (2,3):
            return Calculator.segment_to_segment_distance(new_center, old_center)

    @staticmethod
    def point_to_segment_distance(point, segment):
        """
        Shortest distance between a point and a finite segment.

        Parameters
        ----------
        point : numpy.ndarray, shape (3,)
            Query point.
        segment : numpy.ndarray, shape (2, 3)
            Segment endpoints.

        Returns
        -------
        float
            Euclidean distance from the point to the closest location on
            the segment.
        """
        p1, p2 = segment
        d = p2 - p1
        a = point - p1
        t = np.dot(a, d) / np.dot(d, d)
        t = np.clip(t, 0, 1)
        closest = p1 + t * d
        return np.linalg.norm(point - closest)

    @staticmethod
    def segment_to_segment_distance(seg1, seg2):
        """
        Shortest distance between two finite segments.

        Parameters
        ----------
        seg1, seg2 : numpy.ndarray, shape (2, 3)
            Segment endpoint coordinates.

        Returns
        -------
        float
            Distance between the closest pair of points, one on each
            segment.
        """
        p1, p2 = seg1
        q1, q2 = seg2

        u = p2 - p1
        v = q2 - q1
        w0 = p1 - q1

        a = np.dot(u, u)
        b = np.dot(u, v)
        c = np.dot(v, v)
        d = np.dot(u, w0)
        e = np.dot(v, w0)

        denom = a * c - b * b
        if denom == 0:
            sc = 0
            tc = np.dot(v, w0) / c if c != 0 else 0
        else:
            sc = (b * e - c * d) / denom
            tc = (a * e - b * d) / denom

        sc = np.clip(sc, 0, 1)
        tc = np.clip(tc, 0, 1)

        point_on_seg1 = p1 + sc * u
        point_on_seg2 = q1 + tc * v

        return np.linalg.norm(point_on_seg1 - point_on_seg2)

    @staticmethod
    def calculate_center_angle(sphere_center, rod_center):
        """
        Angle between a rod axis and the sphere vector to its nearest end.

        Parameters
        ----------
        sphere_center : numpy.ndarray, shape (3,)
            Sphere center.
        rod_center : numpy.ndarray, shape (2, 3)
            Rod endpoints.

        Returns
        -------
        float
            Absolute angle in degrees.
        """
        if np.linalg.norm(sphere_center - rod_center[0]) > np.linalg.norm(
            sphere_center - rod_center[1]
        ):
            d = rod_center[0] - rod_center[1]
            a = rod_center[1] - sphere_center
        else:
            d = rod_center[1] - rod_center[0]
            a = rod_center[0] - sphere_center

        cos_angle = np.dot(a, d) / (np.linalg.norm(a) * np.linalg.norm(d))

        # Distance from the point to the closest point on the segment
        return np.abs(np.rad2deg(np.arccos(cos_angle)))

    @staticmethod
    def evaluate_distribution(ensemble):
        """
        Histogram angle and distance distributions for an ensemble.

        For each available particle type the relevant pairwise distances
        (sphere–rod, sphere–sphere, rod–rod) and sphere–rod angles are
        accumulated and binned. Histogram ranges scale with the average
        sphere radius. Empty categories are omitted.

        Parameters
        ----------
        ensemble : object
            Object exposing ``bodies`` (iterable of sphere/rod objects).

        Returns
        -------
        dict
            Mapping of distribution labels to ``{\"dist\": counts,
            \"bins\": edges}`` dictionaries.
        """
        rods, spheres = [], []
        i, j, k, radii = 0, 0, 0, 0
        for body in ensemble.bodies:
            center = body.center
            if body.shape == "sphere":
                radii += body.radius
                spheres.append(center)
            if body.shape == "rod":
                rods.append(center)
        radius = radii / len(spheres)

        angle   = np.zeros((len(rods), len(spheres)))       # Initialize as 2D array
        dist_sr = np.zeros((len(rods), len(spheres)))       # Initialize as 2D array
        dist_ss = np.zeros((len(spheres), len(spheres)))    # Initialize as 2D array
        dist_rr = np.zeros((len(rods), len(rods)))          # Initialize as 2D array
        
        for j in range(len(spheres)):
            for i in range(len(rods)):
                angle[i, j] = Calculator.calculate_center_angle(spheres[j], rods[i])
                dist_sr[i, j] = Calculator.calculate_center_distance(
                    spheres[j], rods[i]
                )

            for k in range(j+1, len(spheres)):
                dist_ss[k, j] = Calculator.calculate_center_distance(
                    spheres[j], spheres[k]
                    )
        # csv formatting
        for i in range(len(rods)):
            for j in range(i+1, len(rods)):
                dist_rr[i, j] = Calculator.calculate_center_distance(
                    rods[i], rods[j]
                    )
        if len(spheres) > 0 and len(rods) > 0:
            angle, angle_bins = np.histogram(angle, range=(0, 180), bins= 36)  # Convert to 2D array
            dist_sr, dsr_bins = np.histogram(dist_sr, range=(2 * radius, 80 * radius), bins= 78)  # Convert to 2D array
            dist_ss, dss_bins = np.histogram(dist_ss, range=(2 * radius, 80 * radius), bins= 78)  # Convert to 2D array
            dist_rr, drr_bins = np.histogram(dist_rr, range=(2 * radius, 80 * radius), bins= 78)  # Convert to 2D array
            bins = {"angle": {"dist": angle, "bins": angle_bins}, 
                    "dist_sr": {"dist": dist_sr, "bins": dsr_bins},
                    "dist_ss": {"dist": dist_ss, "bins": dss_bins},
                    "dist_rr": {"dist": dist_rr, "bins": drr_bins}}
        elif len(spheres) > 0:
            dist_ss, dss_bins = np.histogram(dist_ss, range=(2* radius, 80 * radius), bins= 78)  # Convert to 2D array
            bins = {"dist_ss": {"dist": dist_ss, "bins": dss_bins}}
        elif len(rods) > 0:
            dist_rr, drr_bins = np.histogram(dist_rr, range=(2 * radius, 80 * radius), bins= 78)  # Convert to 2D array
            bins = {"dist_rr": {"dist": dist_rr, "bins": drr_bins}}            
        return bins

