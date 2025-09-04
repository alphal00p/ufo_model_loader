import math
from collections.abc import Mapping, Sequence
from os.path import join as pjoin
from ufo_model_loader.common import JSONLook  # type: ignore
from ufo_model_loader.commands import load_model, export_model, JSONLook  # type: ignore
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
