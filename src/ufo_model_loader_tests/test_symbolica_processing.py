import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_sqrt_rewrite_terminates_at_a_canonical_fixed_point():
    # Run the termination control in a child so a repeated identity rewrite
    # fails with a timeout instead of hanging the complete test suite.
    code = textwrap.dedent('''
        from symbolica import Expression
        from ufo_model_loader.symbolica_processing import (
            parse_python_expression_safe,
            replace_from_sqrt,
        )

        for source, expected in [
            ('cmath.sqrt(aS)', 'sqrt(aS)'),
            ('cmath.sqrt(1+cmath.sqrt(aS))', 'sqrt(1+sqrt(aS))'),
            ('2*cmath.sqrt(aS)*cmath.sqrt(2)', '2*sqrt(aS)*sqrt(2)'),
            ('cmath.sqrt(-1)', 'sqrt(-1)'),
        ]:
            result = parse_python_expression_safe(source)
            assert result == Expression.parse(expected, default_namespace='UFO')
            assert replace_from_sqrt(result) == result
    ''')
    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
