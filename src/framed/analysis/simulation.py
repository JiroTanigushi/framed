''' This module implements common constraint-based simulation methods.

@author: Daniel Machado

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
   
'''

from framed.experimental.mathutils import nullspace
from ..solvers import solver_instance
from ..solvers.solver import Status, VarType


def FBA(model, objective=None, minimize=False, constraints=None, solver=None, get_shadow_prices=False,
        get_reduced_costs=False):
    """ Run a Flux Balance Analysis (FBA) simulation:
    
    Arguments:
        model : CBModel -- a constraint-based model
        objective : dict (of str to float) -- objective coefficients (optional)
        minimize : bool (False) -- sense of optimization (maximize by default)
        constraints: dict (of str to (float, float)) -- environmental or additional constraints (optional)
        solver : Solver -- solver instance instantiated with the model, for speed (optional)
        get_shadow_prices : Bool -- retrieve shadow prices (default: False)
        get_reduced_costs : Bool -- retrieve reduced costs (default: False)
       
    Returns:
        Solution -- solution
    """

    if not objective:
        objective = model.objective

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    solution = solver.solve_lp(objective, minimize, None, constraints, get_shadow_prices, get_reduced_costs)
    return solution


def pFBA(model, objective=None, minimize=False, constraints=None, reactions=None, solver=None):
    """ Run a parsimonious Flux Balance Analysis (pFBA) simulation:
    
    Arguments:
        model : CBModel -- a constraint-based model
        objective : dict (of str to float) -- objective coefficients (optional)
        minimize : bool (False) -- sense of optimization (maximize by default)
        constraints: dict (of str to (float, float)) -- environmental or additional constraints (optional)
        reactions: list of str -- list of reactions to be minimized (optional, default: all)
        solver : Solver -- solver instance instantiated with the model, for speed (optional)
       
    Returns:
        Solution -- solution
    """

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    if not objective:
        objective = model.objective

    pre_solution = FBA(model, objective, minimize, constraints, solver)

    if pre_solution.status != Status.OPTIMAL:
        return pre_solution

    solver.add_constraint('obj', objective.items(), '=', pre_solution.fobj)

    if not reactions:
        reactions = model.reactions.keys()
       
    if not hasattr(solver, 'pFBA_flag'): #for speed (about 3x faster)
        solver.pFBA_flag = True
        for r_id in reactions:
            if model.reactions[r_id].reversible:
                pos, neg = r_id + '+', r_id + '-'
                solver.add_variable(pos, 0, None, persistent=False, update_problem=False)
                solver.add_variable(neg, 0, None, persistent=False, update_problem=False)
        solver.update()        
        for r_id in reactions:
            if model.reactions[r_id].reversible:
                pos, neg = r_id + '+', r_id + '-'
                solver.add_constraint('c' + pos, [(r_id, -1), (pos, 1)], '>', 0, persistent=False, update_problem=False)
                solver.add_constraint('c' + neg, [(r_id, 1), (neg, 1)], '>', 0, persistent=False, update_problem=False)
        solver.update()

    objective = dict()
    for r_id in reactions:
        if model.reactions[r_id].reversible:
            pos, neg = r_id + '+', r_id + '-'
            objective[pos] = 1
            objective[neg] = 1
        else:
            objective[r_id] = 1

    solution = solver.solve_lp(objective, minimize=True, constraints=constraints)

    #post process
    
    solver.remove_constraint('obj')
    solution.pre_solution = pre_solution
                      
    if solution.status == Status.OPTIMAL:
        for r_id in reactions:
            if model.reactions[r_id].reversible:
                pos, neg = r_id + '+', r_id + '-'
                del solution.values[pos]
                del solution.values[neg]

    return solution


def looplessFBA(model, objective=None, minimize=False, constraints=None, internal=None, solver=None):

    M = 1e4

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    if not objective:
        objective = model.objective

    if not hasattr(solver, 'll_FBA_flag'):
        solver.ll_FBA_flag = True

        if not internal:
            internal = [r_id for r_id, reaction in model.reactions.items()
                        if len(reaction.stoichiometry) > 1]

        Sint = [[model.reactions[r_id].stoichiometry[m_id]
                 if m_id in model.reactions[r_id].stoichiometry else 0
                 for r_id in internal]
                for m_id in model.metabolites]

        Nint = nullspace(Sint)

        for r_id in internal:
            a, g = 'a' + r_id, 'g' + r_id
            solver.add_variable(g, persistent=False, update_problem=False)
            solver.add_variable(a, 0, 1, vartype=VarType.BINARY, persistent=False, update_problem=False)
        solver.update()

        for r_id in internal:
            a, g = 'a' + r_id, 'g' + r_id
            solver.add_constraint('c1_' + r_id, [(a, M), (r_id, -1)], '<', M, persistent=False, update_problem=False)
            solver.add_constraint('c2_' + r_id, [(a, -M), (r_id, 1)], '<', 0, persistent=False, update_problem=False)
            solver.add_constraint('c3_' + r_id, [(a, M+1), (g, 1)], '>', 1, persistent=False, update_problem=False)
            solver.add_constraint('c4_' + r_id, [(a, M+1), (g, 1)], '<', M, persistent=False, update_problem=False)
        solver.update()


        for i, row in enumerate(Nint):
            expr = [('g' + r_id, coeff) for r_id, coeff in zip(internal, row) if abs(coeff) > 1e-12]
            solver.add_constraint('n{}'.format(i), expr, '=', 0, persistent=False, update_problem=False)

        solver.update()

    if not constraints:
        constraints = dict()

    solution = solver.solve_lp(objective, minimize=minimize, constraints=constraints)

    return solution


def MOMA(model, reference=None, constraints=None, solver=None):
    """ Run a Minimization Of Metabolic Adjustment (MOMA) simulation:
    
    Arguments:
        model : CBModel -- a constraint-based model
        reference : dict (of str to float) -- reference flux distribution (optional)
        constraints: dict (of str to (float, float)) -- environmental or additional constraints (optional)
        solver : Solver -- solver instance instantiated with the model, for speed (optional)
       
    Returns:
        Solution -- solution
    """

    if not reference:
        wt_solution = pFBA(model)
        reference = wt_solution.values

    quad_obj = {(r_id, r_id): 1 for r_id in reference.keys()}
    lin_obj = {r_id: -2 * x for r_id, x in reference.items()}

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    solution = solver.solve_qp(quad_obj, lin_obj, minimize=True, constraints=constraints)

    return solution


def lMOMA(model, reference=None, constraints=None, solver=None):
    """ Run a (linear version of) Minimization Of Metabolic Adjustment (lMOMA) simulation:
    
    Arguments:
        model : CBModel -- a constraint-based model
        reference : dict (of str to float) -- reference flux distribution (optional)
        constraints: dict (of str to (float, float)) -- environmental or additional constraints (optional)
        solver : Solver -- solver instance instantiated with the model, for speed (optional)
       
    Returns:
        Solution -- solution
    """

    if not reference:
        wt_solution = pFBA(model)
        reference = wt_solution.values

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    if not hasattr(solver, 'lMOMA_flag'): #for speed (about 3x faster)
        solver.lMOMA_flag = True
        for r_id in reference.keys():
            d_pos, d_neg = r_id + '_d+', r_id + '_d-'
            solver.add_variable(d_pos, 0, None, persistent=False, update_problem=False)
            solver.add_variable(d_neg, 0, None, persistent=False, update_problem=False)
        solver.update()
        for r_id in reference.keys():
            d_pos, d_neg = r_id + '_d+', r_id + '_d-'
            solver.add_constraint('c' + d_pos, [(r_id, -1), (d_pos, 1)], '>', -reference[r_id], persistent=False, update_problem=False)
            solver.add_constraint('c' + d_neg, [(r_id, 1), (d_neg, 1)], '>', reference[r_id], persistent=False, update_problem=False)
        solver.update()
        
    objective = dict()
    for r_id in reference.keys():
        d_pos, d_neg = r_id + '_d+', r_id + '_d-'
        objective[d_pos] = 1
        objective[d_neg] = 1

    solution = solver.solve_lp(objective, minimize=True, constraints=constraints)

    #post process
    if solution.status == Status.OPTIMAL:
        for r_id in reference.keys():
            d_pos, d_neg = r_id + '_d+', r_id + '_d-'
            del solution.values[d_pos]
            del solution.values[d_neg]

    return solution


def ROOM(model, reference=None, constraints=None, solver=None, delta=0.03, epsilon=0.001):
    """ Run a Regulatory On/Off Minimization (ROOM) simulation:
    
    Arguments:
        model : CBModel -- a constraint-based model
        reference : dict (of str to float) -- reference flux distribution (optional)
        constraints: dict (of str to (float, float)) -- environmental or additional constraints (optional)
        solver : Solver -- solver instance instantiated with the model, for speed (optional)
        delta : float -- relative tolerance (default: 0.03)
        epsilon : float -- absolute tolerance (default: 0.001)
       
    Returns:
        Solution -- solution
    """

    U = 1e6;
    L = -1e6;
    
    if not reference:
        wt_solution = pFBA(model)
        reference = wt_solution.values

    if not solver:
        solver = solver_instance()
        solver.build_problem(model)

    objective = dict()
    if not hasattr(solver, 'ROOM_flag'): #for speed (a LOT faster)
        solver.ROOM_flag = True

        for r_id in model.reactions.keys():
            y_i = 'y_' + r_id
            solver.add_variable(y_i, 0, 1, vartype=VarType.BINARY, persistent=False, update_problem=False)
            objective[y_i] = 1
        solver.update()

        for r_id in model.reactions.keys():
            y_i = 'y_' + r_id
            w_i = reference[r_id]
            w_u = w_i + delta*abs(w_i) + epsilon
            w_l = w_i - delta*abs(w_i) - epsilon
            solver.add_constraint('c' + r_id + '_u', [(r_id, 1), (y_i, (w_u - U))], '<', w_u, persistent=False, update_problem=False)
            solver.add_constraint('c' + r_id + '_l', [(r_id, 1), (y_i, (w_l - L))], '>', w_l, persistent=False, update_problem=False)
        solver.update()

    solution = solver.solve_lp(objective, minimize=True, constraints=constraints)
    
    #post process
    if solution.status == Status.OPTIMAL:
        for r_id in model.reactions.keys():
            y_i = 'y_' + r_id
            del solution.values[y_i]

    return solution
                