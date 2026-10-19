# UFO Model Loader

**UFO Model Loader** is a Python CLI and library to work with High-Energy Physics models in the [UFO format](https://arxiv.org/pdf/2304.09883).  
It can:

- Load UFO models or pre-exported JSON models
- Apply restrictions from parameter cards
- Evaluate all dependent parameters from input parameters using [Symbolica](https://symbolica.io/)
- Simplify couplings and disable zero contributions
- Preserve propagating/Goldstone flags, custom propagators, particle chemical potentials, declared functions, and form-factor metadata
- Preserve lossless NLO source records, including UV/R2 vertices and Laurent-valued parameters/couplings
- Export the finite tree view and optional source records in one JSON model

Limitations:

- Normalized `Model.parameters`, `couplings` and `vertex_rules` remain a finite tree view; NLO consumers use `Model.raw_ufo`. The loader preserves NLO data but does not evaluate loops or certify a model’s renormalization completeness.
- Current version only supports export of model expression in the [Symbolica](https://symbolica.io/) notation

---

## Installation

Version 1.0.1 requires Python 3.11 or newer and Symbolica 3.0.0 or newer.
Symbolica is available on PyPI and is installed automatically as a dependency;
no separate Git-source installation is needed.

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
    output_model_path = 'sm_no_b_mass_simplified_flat.json',
    json_look = JSONLook.VERBOSE,
    allow_overwrite = True
)
```

## NLO and exact source data

Since 1.0.1, normal UFO import captures a public immutable `RawUFOModel` before
finite projection or restriction. It is available as `Model.raw_ufo` and survives
`Model.to_json()` / `Model.from_json()` and CLI export. Existing tree fields keep
their meaning. Older JSON without `raw_ufo` loads with `model.raw_ufo is None`.
Do not use the finite `Model.couplings` expressions to reconstruct counterterms.

For a loop UFO, `include_counterterm_finite_parts=False` selects a true tree view:
CT parameters and couplings used only by CT vertices are excluded **only from the
normalized view**, while `raw_ufo` still retains all UV/R2 information. This avoids
parsing NLO-only expressions (such as complex-mass conditional CT formulas) just
to obtain the tree model. The default `True` preserves historical access to
finite CT parameters/couplings. A genuine tree dependency on an excluded CT
parameter raises. This keyword affects UFO import; a normalized JSON model keeps
its already stored projection. The CLI exposes the same choice as
`--no-include-counterterm-finite-parts`.

```python
from ufo_model_loader.commands import load_model
from ufo_model_loader.raw import RawUFOModel, load_raw_ufo_model

model, card = load_model(
    "/path/to/loop_ufo", "full", False,
    include_counterterm_finite_parts=False,
)
source = model.raw_ufo
if source is None:
    raise ValueError(model.raw_ufo_error or "JSON contains no source UFO data")

for vertex in source.collections["counterterm_vertices"]:
    fields = vertex["fields"]
    print(vertex["id"], vertex["name"], fields["type"])  # UV, UVmass, R2, ...
    print(fields["couplings"], fields["loop_particles"])

# Lookup by unique name or stable collection-local integer ID.
first = source.record("counterterm_vertices", 0)
# Strict source-only import needs no normalized tree model or loop evaluator.
source_only = load_raw_ufo_model("/path/to/loop_ufo", restriction="full")
restored = RawUFOModel.from_json(source_only.to_json())
```

The versioned `ufo-model-source` schema preserves ordered collections for ordinary
and CT parameters, particles, couplings, ordinary and CT vertices, Lorentz
structures, coupling orders, functions, propagators and form factors. Each record
has `id`, `name`, `ufo_type` and unnormalized `fields`. References carry collection,
ID and name, so duplicate names cannot merge distinct CT vertices. A nonunique
name lookup raises; indexed lookup remains available.

Expression values retain UFO strings verbatim. Laurent values have
`{"kind": "laurent", "terms": [[epsilon_power, expression], ...]}`. A scalar
coupling such as `"g*dZ"` remains a scalar expression referencing the full Laurent
parameter `dZ`, **not** an inferred epsilon-zero coefficient. Sparse maps use
`{"kind": "mapping", "entries": [[key, value], ...]}`; tuple keys use
`{"kind": "tuple", "items": [...]}`. Thus colour × Lorentz × loop-particle-group
keys, nested alternatives, particle counterterms and directed particle ordering
survive JSON without projection. Declared model conventions use the same generic
encoding. Presence diagnostics in `source.capabilities` are an inventory, not a
physics certificate or a statement that UV/R2 rules are complete.

`source.exact_value(collection, id)` returns a value only when its exact origin
is established. Direct numeric literals retain their original decimal spelling;
string expressions and supported compositions of source strings retain their
contents. Computed or mutated Python values are retained with explicit unproven
source status, and `exact_value` raises. It never promotes rounded Python floats
to arbitrary-precision inputs. Explicit exact overrides are available through
`capture_raw_ufo_model` and `load_raw_ufo_model` without changing the imported
model objects.

`source.metadata["restriction"]` records the selected original UFO card text and
`applied=False`: source records are deliberately unrestricted. Later normalized
parameter updates, simplification, or loading a different JSON parameter card do
not rewrite this snapshot. NLO consumers must apply their intended restriction
and parameter state explicitly. `load_raw_ufo_model` uses an optional default
card when `restriction=None`, no card for `"full"`/`"none"`, and requires a named
card to exist. Raw source JSON can also be read by `load_raw_ufo_model(path)`;
restriction or value overrides require the original UFO directory and are
rejected for this snapshot format.

If extra custom metadata cannot be represented, ordinary tree loading remains
available with `raw_ufo=None` and an explicit `raw_ufo_error`; strict source-only
import raises. Malformed `raw_ufo` supplied in JSON raises rather than falling
back to tree-only data. UFO Python modules are executable code and must be
trusted. Scoped source import serializes loader imports and restores Python
module, path, profiler and bytecode state on success and failure.

## Built-in models

UFO Model Loader comes with the following built-in models: `sm`, `scalars`, and `scalar_gravity`, which can be specified as input models directly from their names (the corresponding UFO directories are shipped with the Python package).

The `sm` model attaches a chemical potential to every particle that carries baryon number, electric charge, or lepton flavour. The independent chemical potentials are the external parameters `muB`, `muQ`, `muLe`, `muLmu`, and `muLtau` in the `CHEMICALPOTENTIAL` block. All default to zero for ordinary vacuum use. Since restriction with simplification freezes zero-valued external parameters, load with `simplify_model=False` to vary these inputs, or provide an explicit nonzero parameter card before simplification. Each particle's chemical potential is derived from its charges, and antiparticles carry the opposite value through the corresponding `minus_<name>` parameter. Chemical potentials do not enter vacuum couplings.

Particle electric charges are numeric inside the loader and exported exactly as JSON integers or rational strings such as `"2/3"`. Hypercharges use `Q = T3 + Y/2`: `y_charge` is left-handed for fermions, and the optional `y_charge_right` is right-handed. Charge conjugation swaps these chiralities and negates their values. Missing/undefined hypercharge is `null`, not zero; in particular the real neutral `H` and `G0` fields have no definite hypercharge. The bundled SM metadata matches Symbolica 3.0.0 HepKit's `Model.standard_model()`. Models without these optional fields remain supported, and older numeric JSON charges can still be loaded. Consumers of the 1.0.0 JSON format must accept rational strings and optional hypercharges.

The `scalars` model is a purely scalar toy model, with a number of scalars controlled by the environment variable `UFO_SCALARS_MODEL_N_SCALARS`, and all possible n-point interactions mixing these scalars, with `n` given by the environment variable `UFO_SCALARS_MODEL_N_POINT_INTERACTIONS`.
By default, `UFO_SCALARS_MODEL_N_SCALARS="3"` and `UFO_SCALARS_MODEL_N_POINT_INTERACTIONS="3,4,5,6,7,8,9,10"`.

The `scalar_gravity` model couples a configurable number of scalar fields to a massless spin-2 graviton. The number of scalars is controlled by `UFO_GRAVITY_MODEL_N_SCALARS` and defaults to three.

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

Install the test dependencies and test your installation with

```bash
python -m pip install "ufo-model-loader[dev,prettyjson]"
python -m pytest --pyargs ufo_model_loader_tests
```

## Main options

- `--input_model, -i`  
  UFO directory or JSON file path to load.

- `--restriction_name, -r`  
  Restriction to apply (`restrict_<restriction_name>.dat` in UFO or `restrict_<restriction_name>.json` beside a JSON model). Without this option, `restrict_default.dat` or `restrict_default.json` is applied when present. Legacy `<model>_default.json` cards remain accepted.

- `--simplify / --no-simplify`  
  Remove zero contributions in the model given specified restriction. Default: enabled.

- `--wrap_indices_in_lorentz_structures`
  Wrap indices in Lorentz structures when exporting. This is particularly useful for spin-2 models, mapping `<1 or 2>00<p_id>` conventions to `idx(1 or 2, p_id)`. Default: disabled.

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
python -m pip install --upgrade -e ".[dev,prettyjson]"
python -m pytest
```

### Release dry run

From the repository root, build the source distribution and wheel, then check
their PyPI metadata without uploading anything:

```bash
python -m build
python -m twine check dist/*
```

The `pypi_publish.sh` helper runs these same two steps with `python3`. Activate
the intended development or release environment before running it. It does not
delete existing artifacts or upload to PyPI or TestPyPI.

### Publish to PyPI

The manually triggered [Publish to PyPI workflow](https://github.com/alphal00p/ufo_model_loader/actions/workflows/publish.yml)
builds the wheel and source distribution on `main`, checks their metadata, and
publishes them using GitHub's OIDC identity. Only the publishing job can request
an identity token; no PyPI password or API token is stored in the repository.

One-time setup for an owner of the existing PyPI project:

1. Open [the project's Publishing settings](https://pypi.org/manage/project/ufo-model-loader/settings/publishing/).
2. Add a GitHub trusted publisher with owner `alphal00p`, repository
   `ufo_model_loader`, workflow filename `publish.yml`, and environment `pypi`.
   The workflow field takes the filename, not `.github/workflows/publish.yml`.
3. Ensure the repository has a GitHub environment named `pypi`.

For a release, commit the new `project.version` in `pyproject.toml` to `main` and
run the workflow with that exact version. For example:

```bash
gh workflow run publish.yml --repo alphal00p/ufo_model_loader --ref main -f version=1.0.1
```

The workflow checks the requested version against the source before building.
Ordinary pushes and pull requests do not trigger publishing. PyPI rejects an
attempt to replace an already published distribution.

See the [PyPI trusted-publisher setup guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
for the project-owner registration step.
