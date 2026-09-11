import cmath

import pytest
from symbolica import E
from ufo_model_loader.commands import load_model
from ufo_model_loader.symbolica_processing import (
    parse_python_expression_safe,
    replace_from_sqrt,
    wrap_indices,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("cmath.sqrt(4)", 2),
        ("cmath.sqrt(16) + cmath.sqrt(9)", 7),
        ("cmath.sqrt(cmath.sqrt(16))", 2),
        ("cmath.sqrt(x)", 4),
        ("cmath.sqrt(cmath.sqrt(x))", 2),
    ),
)
def test_square_root_parsing_is_finite_and_idempotent(source, expected):
    expression = parse_python_expression_safe(source)
    assert replace_from_sqrt(expression).matches(expression)
    assert complex(expression.evaluate({E("UFO::x"): 16.0})) == expected


@pytest.mark.parametrize("prefix", ("cmath.", ""))
def test_standard_trigonometric_functions_use_builtin_heads(prefix):
    expression = parse_python_expression_safe(
        f"{prefix}sin(x) + {prefix}cos(x) + {prefix}asin(y) + {prefix}acos(y)"
    )
    actual = complex(expression.evaluate({E("UFO::x"): 0.3, E("UFO::y"): 0.25}))
    expected = cmath.sin(0.3) + cmath.cos(0.3) + cmath.asin(0.25) + cmath.acos(0.25)
    assert abs(actual - expected) < 1e-14
    assert "cmath" not in expression.to_canonical_string()


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("1", "1"),
        ("P(3,2)", "P(UFO::idx(1,3),UFO::idx(1,2))"),
        ("ProjM(1,2)", "ProjM(UFO::idx(1,1),UFO::idx(1,2))"),
        (
            "Gamma(3,1,-1)*ProjM(-1,2)",
            "Gamma(UFO::idx(1,3),UFO::idx(1,1),UFO::dummy(1))"
            "*ProjM(UFO::dummy(1),UFO::idx(1,2))",
        ),
    ),
)
def test_lorentz_indices_are_wrapped_once(source, expected):
    wrapped = wrap_indices(E(source))
    assert wrapped.matches(E(expected))
    assert wrap_indices(wrapped).matches(wrapped)


def test_bundled_sm_loads_with_restriction_and_wrapped_indices():
    model, _card = load_model(
        "sm",
        restriction_name="no_b_mass",
        simplify_model=True,
        wrap_indices_in_lorentz_structures=True,
    )
    assert len(model.vertex_rules) == 117
    assert len(model.lorentz_structures) == 22
