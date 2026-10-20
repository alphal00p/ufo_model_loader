"""Goldstone aliases agree in source metadata and the normalized tree view."""

import json
from types import MappingProxyType, ModuleType, SimpleNamespace

import pytest

from ufo_model_loader.model import Model
from ufo_model_loader.raw import RawUFOModel, is_goldstone_particle


def _source(flags):
    module = ModuleType('goldstone_alias_fixture')
    zero = SimpleNamespace(name='ZERO', nature='internal', type='real', value='0')
    module.all_parameters = [zero]
    module.all_particles = [
        SimpleNamespace(
            pdg_code=251 * sign, name=name, antiname=antiname, spin=1, color=1,
            mass=zero, width=zero, texname=name, antitexname=antiname,
            charge=sign, GhostNumber=0, LeptonNumber=0, **values,
        )
        for sign, name, antiname, values in (
            (1, 'G+', 'G-', flags[0]), (-1, 'G-', 'G+', flags[1]),
        )
    ]
    module.all_orders = []
    module.all_couplings = []
    module.all_lorentz = []
    module.all_vertices = []
    module.gauge = [0, 1]
    return module


@pytest.mark.parametrize('flags,expected', [
    ({}, False),
    ({'GoldstoneBoson': False, 'goldstoneboson': False, 'goldstone': 0}, False),
    ({'GoldstoneBoson': True, 'goldstoneboson': False}, True),
    ({'GoldstoneBoson': False, 'goldstoneboson': True}, True),
    ({'goldstoneboson': False, 'goldstone': True}, True),
    ({'GoldstoneBoson': False, 'goldstoneboson': False, 'goldstone': -1}, True),
    ({'goldstone': True}, True),
])
def test_aliases_match_normalized_and_raw_round_trips(flags, expected):
    for value in (flags, MappingProxyType(flags), SimpleNamespace(**flags)):
        assert is_goldstone_particle(value) is expected
    source = _source((flags, flags))
    originals = [vars(p).copy() for p in source.all_particles]
    model = Model.from_ufo_module(source)
    assert [p.goldstoneboson for p in model.particles] == [expected, expected]
    assert model.raw_ufo is not None
    raw = model.raw_ufo.to_dict()
    assert raw['capabilities']['goldstone_particles'] == (['G+', 'G-'] if expected else [])
    for record in raw['collections']['particles']:
        for key, value in flags.items():
            assert record['fields'][key] == value
        for key in {'GoldstoneBoson', 'goldstoneboson', 'goldstone'} - flags.keys():
            assert key not in record['fields']
    assert RawUFOModel.from_dict(json.loads(json.dumps(raw))).to_dict() == raw
    reloaded = Model.from_json(model.to_json())
    assert [p.goldstoneboson for p in reloaded.particles] == [expected, expected]
    assert reloaded.raw_ufo.to_dict() == raw
    assert [vars(p) for p in source.all_particles] == originals


def test_legacy_antiparticle_numeric_flag_is_preserved():
    source = _source((
        {'goldstoneboson': False, 'goldstone': True},
        {'goldstoneboson': False, 'goldstone': -1},
    ))
    model = Model.from_ufo_module(source)
    assert all(p.goldstoneboson for p in model.particles)
    assert model.raw_ufo.capabilities['goldstone_particles'] == ('G+', 'G-')
    for particle, value in zip(source.all_particles, (True, -1), strict=True):
        fields = model.raw_ufo.record('particles', particle.name)['fields']
        assert fields['goldstoneboson'] is False
        assert fields['goldstone'] == value
        assert type(fields['goldstone']) is type(value)
        assert particle.goldstone == value
    reloaded = Model.from_json(model.to_json())
    assert all(p.goldstoneboson for p in reloaded.particles)
    assert reloaded.raw_ufo.to_dict() == model.raw_ufo.to_dict()


@pytest.mark.parametrize('flags,expected', [
    ({}, True),
    ({'propagating': False}, False),
    ({'Propagating': False, 'propagating': True}, False),
    ({'Propagating': True, 'propagating': False}, True),
])
def test_propagating_precedence_is_unchanged(flags, expected):
    source = _source(({**flags, 'goldstone': True}, {**flags, 'goldstone': -1}))
    model = Model.from_ufo_module(source)
    assert all(p.goldstoneboson for p in model.particles)
    assert [p.propagating for p in model.particles] == [expected, expected]
