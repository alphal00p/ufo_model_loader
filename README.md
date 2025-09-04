# UFO Model Loader

**UFO Model Loader** is a Python CLI and library to work with High-Energy Physics models in the [UFO format](https://arxiv.org/pdf/2304.09883).  
It can:

- Load UFO models or pre-exported JSON models
- Apply restrictions from parameter cards
- Evaluates all dependent parameters from input parameters using [Symbolica](https://symbolica.io/)
- Simplify couplings and disable zero contributions
- Export the result as a flat JSON model

Limitations:

- Only tree-level information is being retained and exported
- Current version only supports export of model expression in the [Symbolica](https://symbolica.io/) notation

---

## Installation

From PyPI:

```bash
pip install ufo-model-loader
```

From GitHub:

```bash
pip install "git+https://github.com/alphal00p/ufo_model_loader.git"
```

---

## Command Line Usage

```bash
ufo_model_loader --help
```

Example:

```bash
ufo_model_loader -i sm -r no_b_mass -o sm_flat.json
```

This will:

1. Load the default UFO sm model shipped with this python module
2. Apply restrictions from `restrict_no_b_mass.dat`
3. Simplify the model by removing zero contributions and parameters set to zero.
4. Write the model `sm_flat.json` and its corresponding parameter card `sm_flat_param_card.json` to the current directory.

## Library Usage


When using UFO Model Loader as a library, you can import the main functions:

```python
from ufo_model_loader.commands import load_model, export_model, JSONLook

loaded_sm_no_b_mass, input_param_card_no_b_mass = load_model(
    input_model_path = 'sm',
    restriction_name = 'no_b_mass',
    simplify_model = True,
)

exported_model_path = export_model(
    model = loaded_sm_no_b_mass,
    input_param_card = input_param_card_no_b_mass,
    output_model_path = 'sm_no_b_mass_simplified_flat.json'),
    json_look = JSONLook.VERBOSE,
    allow_overwrite = True
)
```

## Built-in models

UFO Model Loader comes with the following built-in models: `sm` and `scalars`, which can be specified as input model directly from their names (the corresponding UFO directories are shipped with the python package).

The `scalars` model is a purely scalar toy model, with a number of scalars controlled by the environment variable `UFO_SCALARS_MODEL_N_SCALARS`, and all possible n-point interactions mixing these scalars, with `n` given by the environment variable `UFO_SCALARS_MODEL_N_POINT_INTERACTIONS`.
By default, `UFO_SCALARS_MODEL_N_SCALARS="3"` and `UFO_SCALARS_MODEL_N_POINT_INTERACTIONS="3,4,5,6,7,8,9,10"`.

For example, the following:
```bash
UFO_SCALARS_MODEL_N_SCALARS=7 UFO_SCALARS_MODEL_N_POINT_INTERACTIONS="3,4,5,6,7,8" ufo_model_loader -j compact -i scalars -o scalars_big_model.json; du -hc scalars_big_model.json
```
yields a pretty big model :)
```
[23:34:27] INFO    : Loading UFO model scalars from directory '[...]/ufo_model_loader/src/ufo_model_loader/data/models'
Loading UFO scalars model with 7 scalars
Loading UFO scalars model with n-point interactions, n=[3|4|5|6|7|8]
[23:34:28] INFO    : Applying default restriction to model scalars
[23:34:28] INFO    : The following 6 external parameters were forced to zero by the restriction card:
width_scalar_1, width_scalar_2, width_scalar_3, width_scalar_4, width_scalar_5, width_scalar_6
[23:34:28] INFO    : Model scalars successfully loaded (7 particles, 20 parameters, 6399 interactions, 1 couplings, 6 Lorentz structures)
[23:34:28] INFO    : Successfully exported model in compact JSON format to file 'scalars_big_model.json' and corresponding input parameter card to 'scalars_big_model_param_card.json'
1.5M	scalars_big_model.json
1.5M	total
```

## Tests

Test your installation with

```bash
pytest --pyargs ufo_model_loader_tests
```

## Main options

- `--input_model, -i`  
  UFO directory or JSON file path to load.

- `--restriction_name, -r`  
  Restriction to apply (`restrict_<restriction_name>.dat` in UFO or `<model>_<restriction_name>.json`).

- `--simplify / --no-simplify`  
  Remove zero contributions in the model given specified restriction. Default: enabled.

- `--output_model_path, -o`  
  Output path for the JSON model. Defaults to current directory.

- `--json_look, -j`  
  Output format: `compact`, `pretty`, or `verbose`. Default: `verbose`.
  Note: `pretty` requires the optional python package `jsbeautifier`.

- `--verbosity, -v`  
  Logging level: `debug`, `info`, `critical`.

- `--overwrite, -w`  
  Allow overwriting existing output files.

---

## Development

Clone the repo and install in editable mode:

```bash
git clone https://github.com/alphal00p/ufo_model_loader.git
cd ufo_model_loader
pip install -e .[dev]
pytest
```
