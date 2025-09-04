import os
import logging
import sys
import re

from importlib.resources import files, as_file
from pathlib import Path
from typing import Any, TextIO
from enum import StrEnum, Enum
from pprint import pformat
import json


def optionally_lower_external_parameter_name(name: str) -> str:
    # return name.lower()
    return name


JSBEAUTIFIER_AVAILABLE = True
try:
    import jsbeautifier  # type: ignore
except ModuleNotFoundError:
    JSBEAUTIFIER_AVAILABLE = False

ROOT_PATH = Path()
try:
    with as_file(files("ufo_model_loader")) as p:
        ROOT_PATH = p
except ModuleNotFoundError:
    ROOT_PATH = Path(os.path.abspath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.path.pardir, 'ufo_model_loader')))

DATA_PATH = os.path.abspath(os.path.join(ROOT_PATH, 'data'))

logger = logging.getLogger('UFOModelLoader')


class JSONLook(StrEnum):
    VERBOSE = 'verbose'
    PRETTY = 'pretty'
    COMPACT = 'compact'


class UFOModelLoaderError(Exception):
    pass


class UFOModelLoaderWarning(Enum):
    FloatInExpression = 100
    DroppingEpsilonTerms = 101

    def __str__(self):
        if self == UFOModelLoaderWarning.FloatInExpression:
            return "FloatInExpression"
        elif self == UFOModelLoaderWarning.DroppingEpsilonTerms:
            return "DroppingEpsilonTerms"
        else:
            raise UFOModelLoaderError(f"Unknown side: {self}")


UFOMODELLOADER_WARNINGS_ISSUED: set[UFOModelLoaderWarning] = set()


class Colour(StrEnum):
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    GRAY = '\033[21m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class UFOModelLoaderCustomFormatter(logging.Formatter):
    """Logging colored formatter"""

    def __init__(self, fmt: str, datefmt: str | None = None):
        super().__init__(datefmt=datefmt)
        self.fmt = fmt
        self.datefmt = datefmt

    def format(self, record: logging.LogRecord) -> str:
        formatter = logging.Formatter(self.fmt, self.datefmt)
        if record.levelno != logging.DEBUG:
            if record.name.startswith('_gammaloop'):
                record.name = f"rust.{record.name[11:]}"
            if len(record.name) > 20:
                record.name = f"{record.name[:17]}..."
            record.name = f"{record.name:20}"
        match record.levelno:
            case logging.DEBUG:
                record.levelname = f"{Colour.GRAY}{record.levelname:8}{Colour.END}"  # nopep8
            case logging.INFO:
                record.levelname = f"{record.levelname:8}"  # nopep8
            case logging.WARNING:
                record.levelname = f"{Colour.YELLOW}{record.levelname:8}{Colour.END}"  # nopep8
            case logging.ERROR:
                record.levelname = f"{Colour.RED}{record.levelname:8}{Colour.END}"  # nopep8
            case logging.CRITICAL:
                record.levelname = f"{Colour.RED}{Colour.BOLD}{record.levelname:8}{Colour.END}"  # nopep8
            case _:
                record.levelname = f"{record.levelname:8}"
        record.asctime = self.formatTime(record, self.datefmt)
        return formatter.format(record)


def setup_logging(prefix_format) -> logging.StreamHandler[TextIO]:
    match prefix_format:
        case 'none':
            console_format = f'%(message)s'
            time_format = "%H:%M:%S"
        case 'min':
            console_format = f'%(levelname)s: %(message)s'
            time_format = "%H:%M:%S"
        case 'short':
            console_format = f'[{Colour.GREEN}%(asctime)s{Colour.END}] %(levelname)s: %(message)s'  # nopep8
            time_format = "%H:%M:%S"
        case 'long':
            console_format = f'[{Colour.GREEN}%(asctime)s.%(msecs)03d{Colour.END}] @{Colour.BLUE}%(name)s{Colour.END} %(levelname)s: %(message)s'  # nopep8
            time_format = '%Y-%m-%d %H:%M:%S'
        case _:
            raise UFOModelLoaderError(
                "Invalid prefix_format: %s", prefix_format)
    file_format = '[%(asctime)s] %(name)s %(levelname)s: %(message)s'
    console_formatter = UFOModelLoaderCustomFormatter(
        console_format, datefmt=time_format)
    file_formatter = UFOModelLoaderCustomFormatter(file_format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    console_handler.setFormatter(console_formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(console_handler)

    if 'UFO_MODEL_LOADER_ENABLE_FILE_HANDLERS' in os.environ and os.environ['UFO_MODEL_LOADER_ENABLE_FILE_HANDLERS'].upper() != 'FALSE':
        log_file_name = 'ufo_model_loader_debug.log'
        file_handler = logging.FileHandler(log_file_name, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(file_handler)

        error_file_name = 'ufo_model_loader_error.log'
        error_file_handler = logging.FileHandler(error_file_name, mode='w')
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(error_file_handler)

    logging.getLogger().setLevel(logging.DEBUG)

    return console_handler


def verbose_json_dump(obj: Any, json_look: JSONLook = JSONLook.VERBOSE) -> str:
    match json_look:
        case JSONLook.COMPACT:
            return json.dumps(obj, sort_keys=True, ensure_ascii=False)
        case JSONLook.VERBOSE:
            return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
        case JSONLook.PRETTY:
            if not JSBEAUTIFIER_AVAILABLE:
                raise UFOModelLoaderError(
                    "JSBeautifier not available, cannot use 'pretty' JSON look. Install this dependencies with e.g. `pip install jsbeautifier`.")
            json_dump = json.dumps(obj, sort_keys=True, ensure_ascii=False)
            jsbeautifier_options = jsbeautifier.default_options()
            jsbeautifier_options.indent_size = 2
            return jsbeautifier.beautify(json_dump, jsbeautifier_options)
        case _:
            raise UFOModelLoaderError(
                f"JSON look selected not supported: {json_look}")
