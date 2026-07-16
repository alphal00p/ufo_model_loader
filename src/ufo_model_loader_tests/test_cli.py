import math
import json
from collections.abc import Mapping, Sequence
from os.path import join as pjoin
from ufo_model_loader.common import JSONLook  # type: ignore
from ufo_model_loader.commands import load_model, export_model, JSONLook  # type: ignore
from ufo_model_loader.model import Model, Propagator  # type: ignore
from ufo_model_loader.symbolica_processing import (  # type: ignore
    evaluate_symbolica_expression_safe,
    expression_to_string_safe,
    parse_python_expression_safe,
)
from symbolica import S
from copy import deepcopy

USE_DETAILED_DIFF_COMPARISON = True

SENTINEL = object()


def compare_models(modelA, modelB):
    obj1_dict = dict(modelA.to_serializable_model().to_dict())
    obj2_dict = dict(modelB.to_serializable_model().to_dict())
    # from pprint import pprint
    # pprint(obj1_dict['parameters'])
    # pprint(obj2_dict['parameters'])
    if USE_DETAILED_DIFF_COMPARISON:
        diff = dict_diff(obj1_dict, obj2_dict)
        assert diff is None, f"Difference: {diff}"
    else:
        assert modelA.__dict__ == modelB.__dict__


def compare_dict_objects(obj1, obj2):
    obj1_dict = dict(obj1.__dict__)
    obj2_dict = dict(obj2.__dict__)
    # from pprint import pprint
    # pprint(obj1_dict)
    # pprint(obj2_dict)
    if USE_DETAILED_DIFF_COMPARISON:
        diff = dict_diff(obj1_dict, obj2_dict)
        assert diff is None, f"Difference: {diff}"
    else:
        assert obj1_dict == obj2_dict


def test_ufo_model_loader(tmp_path):

    # First loading the full model
    loaded_full_sm, input_param_card_full = load_model(
        input_model_path='sm',
        restriction_name='full',
        simplify_model=True,
    )
    assert loaded_full_sm is not None
    assert input_param_card_full is not None

    exported_model_path = export_model(
        model=loaded_full_sm,
        input_param_card=input_param_card_full,
        output_model_path=pjoin(tmp_path, 'sm_output_model_test.json'),
        json_look=JSONLook.COMPACT,
        allow_overwrite=True,
    )
    assert exported_model_path is not None

    # Now try re-loading the exported model again
    reloaded_sm_full, reloaded_param_card_full = load_model(
        input_model_path=exported_model_path,
        restriction_name='full',
        simplify_model=True,
    )
    assert reloaded_sm_full is not None
    assert reloaded_param_card_full is not None
    compare_models(reloaded_sm_full, loaded_full_sm)
    compare_dict_objects(reloaded_param_card_full, input_param_card_full)

    # Now test restrictions
    loaded_sm_no_b_mass_non_simplified, input_param_card_no_b_mass_non_simplified = load_model(
        input_model_path='sm',
        restriction_name='no_b_mass',
        simplify_model=False,
    )
    assert loaded_sm_no_b_mass_non_simplified is not None
    assert input_param_card_no_b_mass_non_simplified is not None

    with open(pjoin(tmp_path, 'restrict_no_b_mass.json'), 'w', encoding='utf-8') as f:
        f.write(input_param_card_no_b_mass_non_simplified.to_json(JSONLook.VERBOSE))

    loaded_sm_no_b_mass, input_param_card_no_b_mass = load_model(
        input_model_path='sm',
        restriction_name='no_b_mass',
        simplify_model=True,
    )
    assert loaded_sm_no_b_mass is not None
    assert input_param_card_no_b_mass is not None

    re_loaded_sm_no_b_mass, re_loaded_input_param_card_no_b_mass = load_model(
        input_model_path=pjoin(tmp_path, 'sm_output_model_test.json'),
        restriction_name='no_b_mass',
        simplify_model=True,
    )
    assert re_loaded_sm_no_b_mass is not None
    assert re_loaded_input_param_card_no_b_mass is not None

    compare_models(re_loaded_sm_no_b_mass, loaded_sm_no_b_mass)
    compare_dict_objects(
        re_loaded_input_param_card_no_b_mass, input_param_card_no_b_mass)


def test_symbolica_2_complex_evaluation_and_standard_ufo_functions():
    expression = parse_python_expression_safe(
        'tan(x) + complexconjugate(y) + cond(c, 3, 5) + Theta(t) + reglogp(r)'
    )
    values = {
        S('UFO::x'): complex(0.25, 0.5),
        S('UFO::y'): complex(1.5, -2.0),
        S('UFO::c'): 0j,
        S('UFO::t'): complex(-2.0, 0.0),
        S('UFO::r'): complex(-2.0, -0.5),
    }

    result = evaluate_symbolica_expression_safe(
        expression,
        values,
        Model.get_model_functions(),
    )

    # cmath is used explicitly because the test point is complex.
    import cmath
    expected = (
        cmath.tan(values[S('UFO::x')])
        + values[S('UFO::y')].conjugate()
        + 3
        + Model.model_function_reglogp([values[S('UFO::r')]])
    )
    assert abs(result - expected) < 1.0e-14
    assert 'UFO::x' in expression_to_string_safe(expression, canonical=False)


def test_default_json_restriction_and_extended_metadata_round_trip(tmp_path):
    model, input_card = load_model(
        input_model_path='scalars',
        restriction_name='full',
        simplify_model=True,
    )
    particle = model.particles[0]
    particle.propagating = False
    particle.goldstoneboson = True
    custom = Propagator(
        'custom_scalar_propagator',
        particle,
        'complex(0,1)',
        'P(1)**2',
    )
    model.propagators[0] = custom
    particle.propagator = custom.name

    output_path = export_model(
        model=model,
        input_param_card=input_card,
        output_model_path=pjoin(tmp_path, 'scalars.json'),
        json_look=JSONLook.COMPACT,
        allow_overwrite=True,
    )
    assert output_path is not None
    with open(pjoin(tmp_path, 'restrict_default.json'), 'w', encoding='utf-8') as stream:
        json.dump({name: [value.real, value.imag] for name, value in input_card.items()}, stream)

    reloaded, _ = load_model(
        input_model_path=output_path,
        restriction_name=None,
        simplify_model=False,
    )

    reloaded_particle = reloaded.get_particle(particle.name)
    assert reloaded.restriction == 'default'
    assert reloaded_particle.propagating is False
    assert reloaded_particle.goldstoneboson is True
    assert reloaded_particle.propagator == custom.name
    assert reloaded.get_propagator(custom.name).particle.name == particle.name
    assert [function.name for function in reloaded.functions] == [
        function.name for function in model.functions
    ]


def test_complete_json_restriction_matches_ufo_restriction(tmp_path):
    full_model, full_card = load_model(
        input_model_path='sm',
        restriction_name='full',
        simplify_model=True,
    )
    output_path = export_model(
        model=full_model,
        input_param_card=full_card,
        output_model_path=pjoin(tmp_path, 'sm.json'),
        json_look=JSONLook.COMPACT,
        allow_overwrite=True,
    )
    assert output_path is not None

    restricted_ufo, _ = load_model(
        input_model_path='sm',
        restriction_name=None,
        simplify_model=True,
    )
    _, complete_card = load_model(
        input_model_path='sm',
        restriction_name=None,
        simplify_model=False,
    )
    with open(
        pjoin(tmp_path, 'restrict_default.json'),
        'w',
        encoding='utf-8',
    ) as stream:
        stream.write(complete_card.to_json(JSONLook.COMPACT))

    restricted_json, _ = load_model(
        input_model_path=output_path,
        restriction_name=None,
        simplify_model=True,
    )

    compare_models(restricted_json, restricted_ufo)


def test_sparse_json_restriction_preserves_omitted_model_defaults(tmp_path):
    full_model, full_card = load_model(
        input_model_path='sm',
        restriction_name='full',
        simplify_model=True,
    )
    output_path = export_model(
        model=full_model,
        input_param_card=full_card,
        output_model_path=pjoin(tmp_path, 'sm.json'),
        json_look=JSONLook.COMPACT,
        allow_overwrite=True,
    )
    assert output_path is not None

    with open(
        pjoin(tmp_path, 'restrict_sparse.json'),
        'w',
        encoding='utf-8',
    ) as stream:
        json.dump({'MB': [0.0, 0.0]}, stream)

    restricted, _ = load_model(
        input_model_path=output_path,
        restriction_name='sparse',
        simplify_model=True,
    )

    assert restricted.get_parameter('MB').value == 0j
    assert restricted.get_parameter('MC').value == full_model.get_parameter('MC').value
    assert restricted.get_parameter('lamWS').value == full_model.get_parameter('lamWS').value


def test_unrestricted_json_load_evaluates_missing_coupling_values(tmp_path):
    model, input_card = load_model(
        input_model_path='sm',
        restriction_name='full',
        simplify_model=True,
    )
    payload = model.to_serializable_model().to_dict()
    for coupling in payload['couplings']:
        coupling['value'] = None
    model_path = pjoin(tmp_path, 'sm.json')
    with open(model_path, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream)

    reloaded, reloaded_card = load_model(
        input_model_path=model_path,
        restriction_name='full',
        simplify_model=True,
    )

    assert reloaded_card == input_card
    assert all(coupling.value is not None for coupling in reloaded.couplings)


def test_capitalized_ufo_goldstone_metadata_is_preserved():
    model, _ = load_model(
        input_model_path='sm',
        restriction_name='full',
        simplify_model=False,
    )

    assert model.get_particle('G0').goldstoneboson is True
    assert model.get_particle('G+').goldstoneboson is True
    assert model.get_particle('G-').goldstoneboson is True
    assert model.get_particle('Z').goldstoneboson is False


def test_old_serialized_models_default_extended_metadata():
    model, _ = load_model(
        input_model_path='scalars',
        restriction_name='full',
        simplify_model=True,
    )
    payload = model.to_serializable_model().to_dict()
    payload.pop('functions')
    payload.pop('form_factors')
    for particle in payload['particles']:
        particle.pop('propagating')
        particle.pop('goldstoneboson')
        particle.pop('propagator')

    reloaded = Model.from_json(json.dumps(payload))

    assert reloaded.functions == []
    assert reloaded.form_factors == []
    assert all(particle.propagating for particle in reloaded.particles)
    assert all(not particle.goldstoneboson for particle in reloaded.particles)


def dict_diff(a, b, *, path="root", rel_tol=None, abs_tol=None):
    """Return None if a == b (deep), else a string describing the first difference.

    - dicts: missing/extra keys, then recurse into shared keys
    - lists/tuples: length mismatch, then recurse by index
    - sets/frozensets: report first element only-in-one
    - floats: optional tolerance via float_tol
    - treats NaNs as equal if both are NaN
    """

    # Fast path for exact equality including identical objects
    if a is b:
        return None

    # Handle numeric tolerance and NaNs
    if _both_numbers(a, b):
        if _nums_equal(a, b, rel_tol=rel_tol, abs_tol=abs_tol):
            return None
        return f"{path}: {a!r} != {b!r}"

    # Type mismatch (after numeric normalization)
    if type(a) is not type(b):
        # Allow tuple vs list? No: be strict to catch bugs.
        return f"{path}: type mismatch {type(a).__name__} != {type(b).__name__}"

    # Dict-like
    if isinstance(a, Mapping):
        # missing in b
        for k in sorted(set(a) - set(b), key=_kkey):
            return f"{path}[{k!r}] only in a"
        # missing in a
        for k in sorted(set(b) - set(a), key=_kkey):
            return f"{path}[{k!r}] only in b"
        # recurse shared keys in stable order
        for k in sorted(a.keys(), key=_kkey):
            d = dict_diff(a[k], b.get(k, SENTINEL), path=f"{
                          path}[{k!r}]", rel_tol=rel_tol, abs_tol=abs_tol)
            if d:
                return d
        return None

    # Sequence (but not str/bytes)
    if isinstance(a, Sequence) and not isinstance(a, (str, bytes, bytearray)):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (ai, bi) in enumerate(zip(a, b)):
            d = dict_diff(ai, bi, path=f"{
                          path}[{i}]", rel_tol=rel_tol, abs_tol=abs_tol)
            if d:
                return d
        return None

    # Sets
    if isinstance(a, (set, frozenset)):
        if a == b:
            return None
        only_a = sorted(a - b, key=_ekey)
        if only_a:
            return f"{path}: element only in a -> {only_a[0]!r}"
        only_b = sorted(b - a, key=_ekey)
        if only_b:
            return f"{path}: element only in b -> {only_b[0]!r}"
        # Fallback
        return f"{path}: set contents differ"

    # Bytes/bytearray exact compare
    if isinstance(a, (bytes, bytearray)):
        if a == b:
            return None
        return f"{path}: bytes differ (len {len(a)} != {len(b)})" if len(a) != len(b) else f"{path}: bytes differ"

    # Fallback: plain equality
    if a == b:
        return None
    return f"{path}: {a!r} != {b!r}"


def _both_numbers(a, b):
    return isinstance(a, (int, float)) and isinstance(b, (int, float))


def _nums_equal(a, b, *, rel_tol, abs_tol):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if rel_tol is not None or abs_tol is not None:
        return math.isclose(float(a), float(b),
                            rel_tol=0.0 if rel_tol is None else rel_tol,
                            abs_tol=0.0 if abs_tol is None else abs_tol)
    return a == b


def _kkey(k):
    # Sort keys deterministically even if mixed types
    return (str(type(k)), repr(k))


def _ekey(e):
    return (str(type(e)), repr(e))


def test_equal_simple_dicts():
    A = {"a": 1, "b": 2}
    B = {"a": 1, "b": 2}
    assert dict_diff(A, B) is None


def test_missing_key_in_a():
    A = {"a": 1}
    B = {"a": 1, "b": 2}
    msg = dict_diff(A, B)
    assert "only in b" in msg
    assert "root['b']" in msg


def test_missing_key_in_b():
    A = {"a": 1, "b": 2}
    B = {"a": 1}
    msg = dict_diff(A, B)
    assert "only in a" in msg
    assert "root['b']" in msg


def test_nested_difference():
    A = {"a": {"x": 1}}
    B = {"a": {"x": 2}}
    msg = dict_diff(A, B)
    assert msg.startswith("root['a']['x']")


def test_sequence_length_mismatch():
    A = {"a": [1, 2]}
    B = {"a": [1, 2, 3]}
    msg = dict_diff(A, B)
    assert "length" in msg
    assert "root['a']" in msg


def test_sequence_value_mismatch():
    A = [1, 2, 3]
    B = [1, 2, 4]
    msg = dict_diff(A, B)
    assert msg.startswith("root[2]")


def test_set_difference():
    A = {"s": {1, 2}}
    B = {"s": {1, 3}}
    msg = dict_diff(A, B)
    assert "element only" in msg
    assert "root['s']" in msg


def test_type_mismatch():
    A = {"x": [1, 2]}
    B = {"x": (1, 2)}
    msg = dict_diff(A, B)
    assert "type mismatch" in msg
    assert "list" in msg and "tuple" in msg


def test_float_exact_equal():
    A = {"x": 1.0}
    B = {"x": 1.0}
    assert dict_diff(A, B) is None


def test_float_within_abs_tol():
    A = {"x": 1.0001}
    B = {"x": 1.0002}
    assert dict_diff(A, B, abs_tol=1e-3) is None


def test_float_outside_abs_tol():
    A = {"x": 1.0}
    B = {"x": 1.1}
    msg = dict_diff(A, B, abs_tol=1e-3)
    assert msg.startswith("root['x']")


def test_float_nan_equal():
    A = {"x": float("nan")}
    B = {"x": float("nan")}
    assert dict_diff(A, B) is None


def test_bytes_difference():
    A = {"x": b"abc"}
    B = {"x": b"abd"}
    msg = dict_diff(A, B)
    assert "bytes differ" in msg


def test_complex_nested_structure():
    A = {"a": [1, {"b": (2, 3)}]}
    B = {"a": [1, {"b": (2, 4)}]}
    msg = dict_diff(A, B)
    assert msg == "root['a'][1]['b'][1]: 3 != 4"
