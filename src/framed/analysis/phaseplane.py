"""
This module implements the phenotype phase plane analysis.
(Edwards et al. 2001, Characterizing the metabolic phenotype: A phenotype phase plane analysis)

@author: Kai Zhuang

   Copyright 2013 Novo Nordisk Foundation Center for Biosustainability,
   Technical University of Denmark.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
__author__ = 'kaizhuang'

from simulation import FBA
from ..solvers import solver_instance
from ..solvers.solver import Status
import numpy
import matplotlib.pyplot as plt


class PhenotypePhasePlane(object):

    def __init__(self, rxn_x, rxn_y, rxn_x_range, rxn_y_range):
        self.rxn_x = rxn_x
        self.rxn_y = rxn_y

        # converting reaction ranges to numpy array and storing it inside self
        self.x_range = numpy.array(rxn_x_range)
        self.y_range = numpy.array(rxn_y_range)

        # find length of reaction ranges
        len_x = len(self.x_range)
        len_y = len(self.y_range)

        # creating empty arrays for storing analysis results
        self.f_objective = numpy.zeros((len_x, len_y))
        self.shadow_price_x = numpy.zeros((len_x, len_y))
        self.shadow_price_y = numpy.zeros((len_x, len_y))

    def plot_objective_function(self, new_figure=True, show_plot=True):
        """
        new_figure: if set to True, a new matplotlib figure will be created.
        show_plot: if set to True, current figure will be shown
        """

        if new_figure:
            plt.figure()
        f = self.f_objective
        x = self.x_range
        y = self.y_range

        if 'EX_' in self.rxn_x:
            x = x*-1

        if 'EX_' in self.rxn_y:
            y = y*-1

        plt.pcolormesh(x, y, numpy.transpose(f))
        plt.colorbar()
        if show_plot:
            plt.show()

    def plot_shadow_price_x(self, new_figure=True, show_plot=True):
        """
        this method plots the shadow price of metabolites that are associated with reaction x
        new_figure: if set to True, a new matplotlib figure will be created.
        show_plot: if set to True, current figure will be shown
        """

        if new_figure:
            plt.figure()
        sp_x = self.shadow_price_x
        x = self.x_range
        y = self.y_range

        if 'EX_' in self.rxn_x:
            x = x*-1

        if 'EX_' in self.rxn_y:
            y = y*-1

        plt.pcolormesh(x, y, numpy.transpose(sp_x))
        plt.colorbar()
        if show_plot:
            plt.show()

    def plot_shadow_price_y(self, new_figure=True, show_plot=True):
        """
        this method plots the shadow price of metabolites that are associated with reaction x
        new_figure: if set to True, a new matplotlib figure will be created.
        show_plot: if set to True, current figure will be shown
        """

        if new_figure:
            plt.figure()
        sp_y = self.shadow_price_y
        x = self.x_range
        y = self.y_range

        if 'EX_' in self.rxn_x:
            x = x*-1

        if 'EX_' in self.rxn_y:
            y = y*-1

        plt.pcolormesh(x, y, numpy.transpose(sp_y))
        plt.colorbar()
        if show_plot:
            plt.show()

def PhPP(model, rxn_x, rxn_y, rxn_x_range, rxn_y_range, target=None, maximize=True):
    """
    Phenotype Phase Plane Analysis
    analyze the changes in the objective function and the shadow prices

    :param model: ConstraintBasedModel -- the metabolic model
    :param rxn_x: str -- reaction to be plotted along x axis.  must be of a type convertable to numpy.array
    :param rxn_y: str -- reaction to be plotted along y axis.  must be of a type convertable to numpy.array
    :param rxn_x_range: list or array -- the range of the reaction x
    :param rxn_y_range: list or array -- the range of the reaction y
    :param target: str -- the  reaction id of the optimization target.
                   if None is included, it will attempt to detect the biomass function
    :param maximize: True or False. the sense of the optimization
    :return: phaseplane
    """
    solver = solver_instance()
    solver.build_problem(model)

    # find metabolite ids corresponding to reactions x and y
    table = model.reaction_metabolite_lookup_table()
    met_x = table[rxn_x].keys()[0]
    met_y = table[rxn_y].keys()[0]

    # create a PhenotypePhasePlane instance for storing results
    phase_plane = PhenotypePhasePlane(rxn_x, rxn_y, rxn_x_range, rxn_y_range)

    for i, v_x in enumerate(rxn_x_range):
        for j, v_y in enumerate(rxn_y_range):
            constraints = {rxn_x: (v_x, v_x), rxn_y: (v_y, v_y)}
            solution = FBA(model, constraints=constraints, target=target, maximize=maximize, solver=solver,
                           get_shadow_prices=True)

            if solution.status == Status.OPTIMAL:
                phase_plane.f_objective[i, j] = solution.fobj
                phase_plane.shadow_price_x[i, j] = solution.shadow_prices[met_x]
                phase_plane.shadow_price_y[i, j] = solution.shadow_prices[met_y]

    return phase_plane
