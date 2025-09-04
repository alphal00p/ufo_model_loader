import re
import os
from pprint import pformat
from typing import Callable

from ufo_model_loader.common import UFOModelLoaderError, UFOModelLoaderWarning, UFOMODELLOADER_WARNINGS_ISSUED, logger  # type: ignore

SYMBOLICA_AVAILABLE = True
try:
    os.environ["SYMBOLICA_HIDE_BANNER"] = "1"
    import symbolica  # type: ignore
    from symbolica import Expression, E, S  # type: ignore
    _ = Expression.parse("1")  # Just to trigger the banner
    del os.environ["SYMBOLICA_HIDE_BANNER"]
except BaseException as e:
    logger.critical(
        "Symbolica could not be imported and is currently mandatory in UFOModelLoader: %s", e)
    raise UFOModelLoaderError(
        "Symbolica could not be imported and is currently mandatory in UFOModelLoader: %s", e)
    SYMBOLICA_AVAILABLE = False


def expression_to_string_safe(expr: Expression, canonical=True) -> str:
    try:
        if canonical:
            return expr.to_canonical_string()
        else:
            return expr.format(
                terms_on_new_line=False,
                color_top_level_sum=False,
                color_builtin_symbols=False,
                print_finite_field=False,
                explicit_rational_polynomial=False,
                number_thousands_separator=None,
                multiplication_operator='*',
                square_brackets_for_function=False,
                num_exp_as_superscript=False,
            )
    except Exception as exception:  # pylint: disable=broad-except
        raise UFOModelLoaderError(
            "Symbolica (@%s)failed to cast expression to string:\n%s\nwith exception:\n%s", symbolica.__file__, expr, exception)


def expression_to_string(expr: Expression | None, canonical=True) -> str | None:
    if expr is None:
        return None
    try:
        return expression_to_string_safe(expr, canonical)
    except Exception as exception:  # pylint: disable=broad-except
        logger.critical("%s", exception)
        return None


def replace_from_sqrt(expr: Expression) -> Expression:
    expr = expr.replace(Expression.parse(
        'sqrt(x__)'), Expression.parse('x__^(1/2)'), repeat=True)
    str_expr = expression_to_string(expr)
    if str_expr is None or re.match(r'\^\(\d+/\d+\)', str_expr):
        raise UFOModelLoaderError(
            "Exponentiation with real arguments not supported in model expressions: %s", str_expr)
    return expr


def replace_pseudo_floats(expression: str) -> str:

    def rationalize_float(fl: re.Match[str]) -> Expression:
        fl_eval: float = eval(fl.group())
        # Work around a bug for 0.0 in symbolica
        rationalized_fl = Expression.num(
            fl_eval, 1e-13) if fl_eval != 0. else SBE.num(0)  # type: ignore
        rationalized_fl_eval: float = eval(str(rationalized_fl)+'.')
        if UFOModelLoaderWarning.FloatInExpression not in UFOMODELLOADER_WARNINGS_ISSUED:
            UFOMODELLOADER_WARNINGS_ISSUED.add(
                UFOModelLoaderWarning.FloatInExpression)
            logger.warning(
                f"Expression contains the following floating point values in the expression: {fl.group()} (mapped to {rationalized_fl})")
            logger.warning(
                "It is typically best for the UFO model to be adjusted and declare these floats as internal constant parameters instead, or have them written as a fraction.")
        valid_cast = True
        if abs(rationalized_fl_eval-fl_eval) != 0.:
            if abs(fl_eval) != 0.:
                if abs(rationalized_fl_eval-fl_eval)/abs(fl_eval) > 1.0e-12:
                    valid_cast = False
            else:
                if abs(rationalized_fl_eval-fl_eval) > 1.0e-12:
                    valid_cast = False
        if not valid_cast:
            raise UFOModelLoaderError(
                "The float value %s in the expression could not be cast to a rational number %s = %.16e", fl.group(), rationalized_fl, rationalized_fl_eval)

        return rationalized_fl

    modified_expression = re.sub(
        r'(\d+\.\d+e[+-]?\d+)', lambda x: f'({rationalize_float(x)})', expression)
    modified_expression = re.sub(
        r'(\d+\.\d+)', lambda x: f'({rationalize_float(x)})', expression)
    modified_expression = re.sub(r'(\d+)\.', r'\1', modified_expression)

    return modified_expression


def parse_python_expression_safe(expr: str) -> Expression:

    sanitized_expr = expr.replace('**', '^')\
        .replace('cmath.sqrt', 'sqrt')\
        .replace('cmath.pi', '𝜋')\
        .replace('math.sqrt', 'sqrt')\
        .replace('math.pi', '𝜋')
    sanitized_expr = replace_pseudo_floats(sanitized_expr)
    try:
        sb_expr = Expression.parse(sanitized_expr, default_namespace='UFO')
        sb_expr = sb_expr.replace(
            E('UFO::complex(x_,y_)'), E('x_+y_ 1𝑖'), repeat=True)
    except Exception as exception:  # pylint: disable=broad-except
        raise UFOModelLoaderError(
            "Symbolica (@%s) failed to parse expression:\n%s\nwith exception:\n%s", symbolica.__file__, sanitized_expr, exception)

    # sb_expr_processed = replace_to_sqrt(sb_expr)
    sb_expr_processed = replace_from_sqrt(sb_expr)

    return sb_expr_processed


def parse_python_expression(expr: str | None) -> Expression | None:
    if expr is None:
        return None
    try:
        return parse_python_expression_safe(expr)
    except Exception as exception:  # pylint: disable=broad-except
        logger.critical("%s", exception)
        return None


def evaluate_symbolica_expression(expr: Expression, evaluation_variables: dict[Expression, complex], evaluation_functions: dict[Callable[[Expression], Expression], Callable[[list[complex]], complex]]) -> complex | None:
    try:
        return evaluate_symbolica_expression_safe(expr, evaluation_variables, evaluation_functions)
    except UFOModelLoaderError:
        return None


def evaluate_symbolica_expression_safe(expr: Expression, evaluation_variables: dict[Expression, complex], evaluation_functions: dict[Callable[[Expression], Expression], Callable[[list[complex]], complex]]) -> complex:
    try:
        res: complex = expr.evaluate_complex(  # type: ignore
            evaluation_variables, evaluation_functions)  # type: ignore
        # Small adjustment to avoid havin -0. in either the real or imaginary part
        return complex(0 if abs(res.real) == 0. else res.real,  # type: ignore
                       0 if abs(res.imag) == 0. else res.imag)  # type: ignore
    except BaseException as e:
        err_msg = "Symbolica (@%s) failed to evaluate expression:\n%s\nwith exception:\n%s.\nVariables:\n%s\nFunctions:\n%s" % (
            symbolica.__file__,
            expression_to_string(expr), e,
            pformat({expression_to_string(k): v for k,
                    v in evaluation_variables.items()}),
            pformat([expression_to_string(k()).replace('()', '')  # type: ignore
                    for k in evaluation_functions.keys()])  # type: ignore
        )
        logger.exception("%s", err_msg)
        raise UFOModelLoaderError(err_msg)
