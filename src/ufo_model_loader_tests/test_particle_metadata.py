"""Particle metadata compatibility with ordinary UFO use and released HepKit."""

import json
from fractions import Fraction

import pytest
from symbolica.community.hepkit import Model as HepKitModel

from ufo_model_loader.commands import load_model
from ufo_model_loader.model import Model, ParameterNature


def test_existing_antiparticle_and_parameter_negation_are_involutive():
    from ufo_model_loader.data.models.sm import parameters, particles
    from ufo_model_loader.data.models.sm.object_library import Particle, all_particles

    count = len(all_particles)
    try:
        electron = particles.e__plus__.anti()
        assert electron.name == 'e-'
        assert electron.chemical_potential is parameters.mue
        assert (electron.Y, electron.YRight) == (-1, -2)
        positron = electron.anti()
        assert positron.name == 'e+'
        assert positron.chemical_potential is parameters.minus_mue
        assert (positron.Y, positron.YRight) == (2, 1)
        assert -(-parameters.mue) is parameters.mue
        assert -(-parameters.minus_mue) is parameters.minus_mue
        right_only = Particle(999, 'r', 'r~', 2, 1, parameters.ZERO,
                              parameters.ZERO, 'r', 'r~', 1, YRight=2)
        conjugate = right_only.anti()
        assert (conjugate.Y, conjugate.YRight) == (-2, None)
        left_only = Particle(998, 'l', 'l~', 2, 1, parameters.ZERO,
                             parameters.ZERO, 'l', 'l~', 0, Y=-1)
        conjugate = left_only.anti()
        assert (conjugate.Y, conjugate.YRight) == (None, 1)
    finally:
        # UFO construction registers new objects; do not pollute later loads.
        del all_particles[count:]


@pytest.mark.parametrize('restriction,simplify', [('full', False), ('default', True)])
def test_sm_particle_quantum_numbers_match_released_hepkit(restriction, simplify):
    model, _ = load_model('sm', restriction, simplify)
    exported = json.dumps(model.to_serializable_model().to_dict())
    imported = HepKitModel.from_json(exported)
    expected = HepKitModel.standard_model()
    actual_particles = {p['pdg_code']: p for p in json.loads(imported.to_json())['particles']}
    expected_particles = {p['pdg_code']: p for p in json.loads(expected.to_json())['particles']}
    assert len(model.particles) == 43
    for particle in model.particles:
        actual = actual_particles[particle.pdg_code]
        reference = expected_particles[particle.pdg_code]
        for field in ('name', 'antiname', 'spin', 'color', 'charge', 'ghost_number',
                      'lepton_number', 'propagating', 'goldstoneboson',
                      'y_charge', 'y_charge_right'):
            assert actual[field] == reference[field], (particle.name, field)
    assert model.get_particle('u').charge == Fraction(2, 3)
    assert model.get_particle('u~').y_charge == Fraction(-4, 3)
    assert model.get_particle('ve~').y_charge is None
    assert model.get_particle('ve~').y_charge_right == 1
    assert model.get_particle('H').y_charge is None
    assert model.get_particle('G0').y_charge is None
    assert Model.from_json(exported).to_serializable_model().to_dict()['particles'] == json.loads(exported)['particles']


def test_legacy_numeric_json_quantum_numbers_stay_numeric_and_export_exactly():
    model, _ = load_model('sm', 'full', False)
    payload = model.to_serializable_model().to_dict()
    particle = next(p for p in payload['particles'] if p['name'] == 'u')
    particle['charge'] = 0.2  # Legacy numeric JSON, not an inferred 2/3 rational.
    particle.pop('y_charge_right')
    restored = Model.from_json(json.dumps(payload))
    assert 3 * restored.get_particle('u').charge == Fraction(3, 5)
    assert restored.get_particle('u').y_charge_right is None
    output = restored.to_serializable_model().to_dict()
    assert next(p for p in output['particles'] if p['name'] == 'u')['charge'] == '1/5'


def test_explicit_nonzero_chemical_potentials_follow_all_sm_charges():
    model, card = load_model('sm', 'full', False)
    names = ('muB', 'muQ', 'muLe', 'muLmu', 'muLtau')
    assert all(model.get_parameter(name).nature == ParameterNature.EXTERNAL for name in names)
    assert all(card[name] == 0 for name in names)
    original_couplings = [coupling.value for coupling in model.couplings]
    card.update(zip(names, (3, 7, 11, 13, 17)))
    model.apply_input_param_card(card, simplify=False)
    for particle in model.particles:
        pdg = abs(particle.pdg_code)
        sign = 1 if particle.pdg_code > 0 else -1
        expected = float(particle.charge) * 7
        if 1 <= pdg <= 6:
            expected += sign
        if pdg in (11, 12, 13, 14, 15, 16):
            expected += sign * {11: 11, 12: 11, 13: 13, 14: 13, 15: 17, 16: 17}[pdg]
        actual = 0 if particle.chemical_potential is None else particle.chemical_potential.value
        assert actual == pytest.approx(expected), particle.name
    assert [coupling.value for coupling in model.couplings] == original_couplings
