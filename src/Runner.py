"""
Computation runner for ensemble post‑processing.

This module provides the :class:`Runner` class, a thin orchestration layer
that evaluates distribution statistics for a single ensemble, writes the
resulting histograms to CSV, and updates the persistent database flags.

Classes
-------
Runner
    Owns references to ``Storer`` and ``Calculator`` instances and exposes
    a single public method to generate and persist ensemble‑level data.
"""
import os, csv
from Storer import Storer
from Calculator import Calculator

class Runner:
    """
    Orchestrates generation and persistence of ensemble data.

    Parameters
    ----------
    ensemble : object
        In‑memory ensemble object exposing ``ensemble_id`` and geometry
        required by :meth:`Calculator.evaluate_distribution`.
    """
    def __init__(self, ensemble):
        """Store collaborators used throughout the run."""
        self.ensemble = ensemble
        self.storer = Storer()
        self.calculator = Calculator()

    def generate_ensemble_data(self):
        """
        Compute and persist all histogram distributions for the ensemble.

        Invokes :meth:`Calculator.evaluate_distribution` to obtain a
        mapping of labels to histogram data structures and writes each one
        to CSV via :meth:`write_to_csv`. Finally marks the ensemble's
        ``ensemble_data`` flag as complete in the database.
        """
        ensemble_dist = self.calculator.evaluate_distribution(self.ensemble)
        for keys in ensemble_dist.keys():
            self.write_to_csv(ensemble_dist[keys], keys)
        self.storer.update_ensembe_info(self.ensemble.ensemble_id, "ensemble_data")

    def write_to_csv(self, data, label):
        """
        Serialize a single histogram to disk.

        Each CSV contains three rows: bin counts, lower bin edges, and
        upper bin edges. Empty inputs are ignored.

        Parameters
        ----------
        data : dict
            Dictionary with keys ``\"dist\"`` (counts) and ``\"bins\"``
            (array of bin edges).
        label : str
            Label used to construct the output filename
            ``<label>_dist.csv``.
        """
        if len(data) == 0:
            return
        filename = os.path.join(self.paths["outputDir"], "ensembles", self.ensemble.ensemble_id, f"{label}_dist.csv")
        with open(filename, 'w+', newline='') as csvfile:
            writer = csv.writer(csvfile)
            data_edit = [data["dist"], data["bins"][:-1], data["bins"][1:]]
            for row in data_edit:
                writer.writerow(row)
               