"""Model/JSON keeps authoritative source NLO records beside the tree view."""

import json
import shutil
from pathlib import Path

import pytest

from ufo_model_loader.commands import load_model
from ufo_model_loader.common import DATA_PATH
from ufo_model_loader.model import Model
from ufo_model_loader.raw import load_raw_ufo_model


def _nlo_sm(tmp_path):
    source = tmp_path / 'synthetic_nlo_sm'
    shutil.copytree(Path(DATA_PATH) / 'models' / 'sm', source,
                    ignore=shutil.ignore_patterns('__pycache__'))
    with (source / '__init__.py').open('a') as stream:
        stream.write('''
from types import SimpleNamespace
from .object_library import Coupling
class CTVertex:
    def __init__(self, **fields):
        self.__dict__.update(fields)
dZ = SimpleNamespace(name='dZ', nature='internal', type='real',
                     value={-2: 'G**2', -1: '-3*G**2', 0: '2*G**2'})
all_CTparameters = [dZ]
GC_test_UV = Coupling(name='GC_test_UV', value='G*dZ', order={'QCD': 3})
GC_test_R2 = Coupling(name='GC_test_R2', value={0: 'G**3', 1: '-G**3'}, order={'QCD': 3})
all_CTvertices = [
    CTVertex(name='duplicate', type='UV', particles=[particles.g]*3,
             color=['f(1,2,3)'], lorentz=[all_lorentz[0]],
             loop_particles=[[[particles.g]], [[particles.g, particles.g]]],
             couplings={(0,0,0): GC_test_UV, (0,0,1): GC_test_R2}),
    CTVertex(name='duplicate', type='R2', particles=[particles.g]*3,
             color=['f(1,2,3)'], lorentz=[all_lorentz[0]],
             loop_particles=[[[particles.g]]], couplings={(0,0,0): GC_test_R2}),
]
all_vertices.extend(all_CTvertices)
regularization = {'spin': 'declared-test-only', 'gamma5': 'undeclared'}
''')
    return source


def test_normalized_model_and_json_keep_full_nlo_source(tmp_path):
    source = _nlo_sm(tmp_path)
    model, _ = load_model(str(source), 'full', False)
    raw = model.raw_ufo
    assert raw is not None and model.raw_ufo_error is None
    assert model.get_parameter('dZ').value == pytest.approx(2 * model.get_parameter('G').value**2)
    assert model.get_coupling('GC_test_UV').value == pytest.approx(2 * model.get_parameter('G').value**3)
    assert not any(vertex.name == 'duplicate' for vertex in model.vertex_rules)
    assert raw.record('counterterm_parameters', 'dZ')['fields']['value']['terms'] == (
        (-2, 'G**2'), (-1, '-3*G**2'), (0, '2*G**2'))
    assert raw.record('couplings', 'GC_test_UV')['fields']['value']['expression'] == 'G*dZ'
    assert raw.record('couplings', 'GC_test_R2')['fields']['value']['terms'] == (
        (0, 'G**3'), (1, '-G**3'))
    assert [raw.record('counterterm_vertices', i)['fields']['type'] for i in range(2)] == ['UV', 'R2']
    assert len(raw.record('counterterm_vertices', 0)['fields']['loop_particles']) == 2
    with pytest.raises(ValueError, match='ambiguous'):
        raw.record('counterterm_vertices', 'duplicate')
    with pytest.raises(KeyError):
        raw.record('counterterm_vertices', -1)
    restored = Model.from_json(model.to_json())
    assert restored.raw_ufo.to_dict() == raw.to_dict()
    assert restored.to_serializable_model().to_dict() == model.to_serializable_model().to_dict()
    # Existing JSON remains accepted without an NLO claim.
    legacy = model.to_serializable_model().to_dict()
    legacy.pop('raw_ufo')
    assert Model.from_json(json.dumps(legacy)).raw_ufo is None


def test_restriction_is_retained_as_unapplied_source_and_survives_tree_update(tmp_path):
    source = _nlo_sm(tmp_path)
    card = (source / 'restrict_default.dat').read_text()
    model, parameters = load_model(str(source), None, True)
    assert model.raw_ufo is not None
    assert model.raw_ufo.metadata['restriction'] == {
        'applied': False, 'name': 'default', 'card': card,
    }
    source_before = model.raw_ufo.to_dict()
    parameters['aS'] = 0.14
    model.apply_input_param_card(parameters, simplify=False)
    assert model.raw_ufo.to_dict() == source_before
    assert Model.from_json(model.to_json()).raw_ufo.to_dict() == source_before


def test_extra_metadata_failure_is_explicit_but_tree_loading_still_works(tmp_path):
    source = _nlo_sm(tmp_path)
    with (source / '__init__.py').open('a') as stream:
        stream.write('\nextra_metadata = object()\n')
    model, _ = load_model(str(source), 'full', False)
    assert model.raw_ufo is None
    assert 'model.extra_metadata' in model.raw_ufo_error
    assert Model.from_json(model.to_json()).raw_ufo_error == model.raw_ufo_error
    with pytest.raises(ValueError, match=r'model\.extra_metadata'):
        load_raw_ufo_model(source, restriction='full')


@pytest.mark.parametrize('value', [False, [], {'kind': 'wrong'}])
def test_malformed_json_source_is_never_silently_dropped(value):
    payload = Model('empty').to_serializable_model().to_dict()
    payload['raw_ufo'] = value
    with pytest.raises(ValueError, match='raw|schema'):
        Model.from_json(json.dumps(payload))


@pytest.mark.parametrize('restriction', ['FULL', 'NONE'])
def test_uppercase_unrestricted_sentinels_preserve_tree_loading(restriction):
    model, _ = load_model('sm', restriction, False)
    assert model.restriction is None
    assert model.raw_ufo.metadata['restriction'] == {
        'applied': False, 'name': None, 'card': None,
    }


def test_true_tree_projection_avoids_ct_only_parser_and_retains_full_source(tmp_path):
    source = _nlo_sm(tmp_path)
    text = (source / '__init__.py').read_text().replace(
        "0: '2*G**2'", "0: '2*G**2 if G != 0 and aS > 0 else 0'")
    (source / '__init__.py').write_text(text)
    model, _ = load_model(str(source), 'full', False,
                          include_counterterm_finite_parts=False)
    assert 'dZ' not in model.name_to_position['parameters']
    assert 'GC_test_UV' not in model.name_to_position['couplings']
    assert len(model.raw_ufo.collections['counterterm_vertices']) == 2
    assert model.raw_ufo.record('counterterm_parameters', 'dZ')['fields']['value']['terms'][-1] == (
        0, '2*G**2 if G != 0 and aS > 0 else 0')
    assert Model.from_json(model.to_json()).raw_ufo.to_dict() == model.raw_ufo.to_dict()
    from ufo_model_loader.cli import parser
    args = parser.parse_args(['-i', str(source), '--no-include-counterterm-finite-parts'])
    assert args.include_counterterm_finite_parts is False


def test_true_tree_dependency_on_ct_parameter_is_diagnosed(tmp_path):
    from ufo_model_loader.common import UFOModelLoaderError
    source = _nlo_sm(tmp_path)
    with (source / '__init__.py').open('a') as stream:
        stream.write("\nall_vertices[0].couplings[(0, 0)] = GC_test_UV\n")
    with pytest.raises(UFOModelLoaderError, match='GC_test_UV references counterterm'):
        load_model(str(source), 'full', False, include_counterterm_finite_parts=False)


def test_raw_json_roundtrip_and_override_rejection(tmp_path):
    source = _nlo_sm(tmp_path)
    raw = load_raw_ufo_model(source, restriction='full')
    path = tmp_path / 'raw.json'
    path.write_text(raw.to_json())
    assert load_raw_ufo_model(path) == raw
    assert type(raw).from_json(raw.to_json()) == raw
    with pytest.raises(ValueError, match='require the original UFO directory'):
        load_raw_ufo_model(path, restriction='full')
    with pytest.raises(ValueError, match='require the original UFO directory'):
        load_raw_ufo_model(path, value_overrides={})
