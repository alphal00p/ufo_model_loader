from importlib.resources import files, as_file
import logging
from ufo_model_loader.common import setup_logging, JSONLook, UFOModelLoaderError
from ufo_model_loader.commands import load_model, export_model
import argparse

# create the top-level parser
parser = argparse.ArgumentParser(prog='ufo_model_loader')

# Add options common to all subcommands
parser.add_argument('--verbosity', '-v', type=str, choices=[
                    'debug', 'info', 'critical'], default='info', help='Set verbosity level')
parser.add_argument('--debug', '-d', action='store_true', default=False,
                    help='Shortcut for --verbosity debug')
parser.add_argument('--quiet', '-q', action='store_true', default=False,
                    help='Shortcut for --verbosity critical')
parser.add_argument('--input_model', '-i', metavar='input_model_path', type=str, required=True,
                    help='UFO directory model name <UFO_directory> or or JSON file path <JSON_file_path>.json to load.')
parser.add_argument('--restriction_name', '-r', metavar='restriction_name', type=str, default=None,
                    help="""Restriction name to consider. For UFO, it will look for a file restrict_<restriction_name>.dat in the UFO model directory. If not given, it will look for restrict_default.dat and if not found, it will use no restriction. 
                            For JSON it will use the param card called <JSON_model_file_name>_<restriction_name>.json file and if not specified, then <JSON_model_file_name>_default.json, and nothing if not found.""")
parser.add_argument('--simplify', '-s', metavar='simplify', action=argparse.BooleanOptionalAction, default=True,
                    help='Simplify the model given the restriction by merging identical couplings and disabling zero contributions. Default = %(default)s')
parser.add_argument('--output_model_path', '-o', metavar='output_model_path', type=str, default=None,
                    help='Output JSON file path <output_model_path>.json to write the model to, with input param card written as <output_model_path>_param_card.json. If not given, it will be written to the current working directory with the name of the input model.')
parser.add_argument('--json_look', '-j', metavar='json_look', type=str, default='verbose', choices=['compact', 'pretty', 'verbose'],
                    help="JSON look to use when writing JSON files. One of 'compact', 'pretty' or 'verbose'. Default = %(default)s")
parser.add_argument('--logging_format', '-l', metavar='logging_format', type=str, default='short', choices=['none', 'min', 'short', 'long'],
                    help="Logging prefix format. One of 'none', 'min', 'short' or 'long'. Default = %(default)s")
parser.add_argument('--overwrite', '-w', action=argparse.BooleanOptionalAction, default=False,
                    help='Allow overwrite of the output files if they exist. Default = %(default)s')


def main():
    args = parser.parse_args()

    console_handler = setup_logging(args.logging_format)
    match args.verbosity.lower():
        case 'debug':
            console_handler.setLevel(logging.DEBUG)
        case 'info':
            console_handler.setLevel(logging.INFO)
        case 'critical':
            console_handler.setLevel(logging.CRITICAL)
        case _:
            raise UFOModelLoaderError(
                f"Invalid verbosity level: {args.verbosity}")

    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    if args.quiet:
        console_handler.setLevel(logging.CRITICAL)

    match args.json_look.lower():
        case 'compact':
            json_look = JSONLook.COMPACT
        case 'pretty':
            json_look = JSONLook.PRETTY
        case 'verbose':
            json_look = JSONLook.VERBOSE
        case _:
            raise UFOModelLoaderError(f"Invalid JSON look: {args.json_look}")

    # Load the model
    model, input_param_card = load_model(
        input_model_path=args.input_model,
        restriction_name=args.restriction_name,
        simplify_model=args.simplify,
    )
    # Export the model
    export_model(
        model=model,
        input_param_card=input_param_card,
        output_model_path=args.output_model_path,
        json_look=json_look,
        allow_overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
