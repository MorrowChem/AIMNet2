from ase.calculators.calculator import Calculator, all_changes
from aimnet2calc import AIMNet2Calculator
from typing import Union
import torch


class AIMNet2ASE(Calculator):
    implemented_properties = ['energy', 'forces', 'free_energy', 'charges', 'stress']
    def __init__(self, base_calc: Union[AIMNet2Calculator, str] = 'aimnet2', charge=0, mult=1):
        super().__init__()
        if isinstance(base_calc, str):
            base_calc = AIMNet2Calculator(base_calc)
        self.base_calc = base_calc
        self.charge = charge
        self.mult = mult
        self.do_reset()

    def do_reset(self):
        self._t_numbers = None
        self._t_charge = None
        self._t_mult = None
        self._t_mol_idx = None
        self.charge = 0.0
        self.mult = 1.0

    def set_atoms(self, atoms):
        self.atoms = atoms
        self.do_reset()

    def set_charge(self, charge):
        self.charge = charge

    def set_mult(self, mult):
        self.mult = mult

    def uptade_tensors(self):
        if self._t_numbers is None:
            self._t_numbers = torch.tensor(self.atoms.numbers, dtype=torch.int64, device=self.base_calc.device)
        if self._t_charge is None:
            self._t_charge = torch.tensor(self.charge, dtype=torch.float32, device=self.base_calc.device)
        if self._t_mult is None:
            self._t_mult = torch.tensor(self.mult, dtype=torch.float32, device=self.base_calc.device)
        if self._t_mol_idx is None:
            self.mol_idx = torch.zeros(len(self.atoms), dtype=torch.int64, device=self.base_calc.device)

    def calculate(self, atoms=None, properties=['energy'], system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        self.uptade_tensors()

        if self.atoms.cell is not None and self.atoms.pbc.any():
            assert self.base_calc.cutoff_lr < float('inf'), 'Long-range cutoff must be finite for PBC'
            cell = self.atoms.cell.array
        else:
            cell = None

        results = self.base_calc({
            'coord': torch.tensor(self.atoms.positions, dtype=torch.float32, device=self.base_calc.device),
            'numbers': self._t_numbers,
            'cell': cell,
            'mol_idx': self._t_mol_idx,
            'charge': self._t_charge,
            'mult': self._t_mult,
        }, forces='forces' in properties, stress='stress' in properties)
        for k, v in results.items():
            results[k] = v.detach().cpu().numpy()

        self.results['energy'] = results['energy']
        self.results['charges'] = results['charges']
        if 'forces' in properties:
            self.results['forces'] = results['forces']
        if 'stress' in properties:
            self.results['stress'] = results['stress']

