import os
from ufo_model_loader.model import Model, InputParamCard, ParamCard  # type: ignore
from ufo_model_loader.common import DATA_PATH, UFOModelLoaderError, UFOMODELLOADER_WARNINGS_ISSUED, JSONLook, logger, Colour  # type: ignore
from os.path import join as pjoin


def load_model(input_model_path: str, restriction_name: str | None, simplify_model: bool) -> tuple[Model, InputParamCard]:

    INPUT_FORMAT = 'JSON' if input_model_path.upper().endswith('.JSON') else 'UFO'

    # Derive the full model path from possible known locations
    if os.path.isabs(input_model_path):
        if not os.path.exists(input_model_path):
            raise UFOModelLoaderError(
                f"Absolute {INPUT_FORMAT} model path {input_model_path} not found. Please check the path.")
        model_base_path = os.path.dirname(input_model_path)
        model_name = os.path.basename(input_model_path)
    else:
        model_full_path = os.path.abspath(pjoin(os.getcwd(), input_model_path))
        if not os.path.exists(model_full_path):
            model_full_path = os.path.abspath(
                pjoin(DATA_PATH, 'models', input_model_path))
            if not os.path.exists(model_full_path):
                raise UFOModelLoaderError(
                    f"Relative {INPUT_FORMAT} model path/name {input_model_path} not found in current working directory or in '{pjoin(DATA_PATH, 'models')}'. Considering providing an absolute path.")
        model_base_path = os.path.dirname(model_full_path)
        model_name = os.path.basename(model_full_path)

    logger.info("Loading %s%s%s model %s%s%s from directory '%s%s%s'",
                Colour.BLUE, INPUT_FORMAT, Colour.END, Colour.GREEN, model_name, Colour.END, Colour.BLUE, model_base_path, Colour.END)

    # Try and load the model
    if INPUT_FORMAT == 'JSON':
        with open(pjoin(model_base_path, model_name), 'r', encoding='utf-8') as f:
            model = Model.from_json(f.read())
    else:
        model = Model.from_ufo_model(pjoin(model_base_path, model_name))

    # Make sure to issue warnings again if they were issued before
    UFOMODELLOADER_WARNINGS_ISSUED.clear()

    # Identify the restriction file path
    restriction_card: InputParamCard | None = None
    if restriction_name is not None:
        if restriction_name.lower() not in ['full', 'none']:
            if INPUT_FORMAT == 'UFO':
                if not os.path.isfile(pjoin(model_base_path, model_name, f'restrict_{restriction_name}.dat')):
                    raise UFOModelLoaderError(
                        f"Restriction file 'restrict_{restriction_name}.dat' not found for UFO model '{model_name}' in directory '{pjoin(model_base_path, model_name)}'.")
                param_card = ParamCard(
                    pjoin(model_base_path, model_name, f'restrict_{restriction_name}.dat'))
                restriction_card = InputParamCard.from_param_card(
                    param_card=param_card, model=model)
            else:
                if not os.path.isfile(pjoin(model_base_path, f'restrict_{restriction_name}.json')):
                    raise UFOModelLoaderError(
                        f"Restriction file 'restrict_{restriction_name}.json' not found for JSON model '{model_name}' in directory '{model_base_path}'.")
                restriction_card = InputParamCard.from_json_file(
                    json_path=pjoin(model_base_path, f'restrict_{restriction_name}.json'))
    else:
        if INPUT_FORMAT == 'UFO':
            if os.path.isfile(pjoin(model_base_path, model_name, 'restrict_default.dat')):
                param_card = ParamCard(
                    pjoin(model_base_path, model_name, 'restrict_default.dat'))
                restriction_card = InputParamCard.from_param_card(
                    param_card=param_card, model=model)
        else:
            if os.path.isfile(pjoin(model_base_path, f'{model_name}_default.json')):
                restriction_card = InputParamCard.from_json_file(
                    json_path=pjoin(model_base_path, f'{model_name}_default.json'))

    if restriction_card is not None:
        if restriction_name is not None:
            logger.info(
                "Applying restriction %s%s%s to model %s%s%s", Colour.BLUE, restriction_name, Colour.END, Colour.GREEN, model_name, Colour.END)
        else:
            logger.info(
                "Applying %sdefault%s restriction to model %s%s%s", Colour.BLUE, Colour.END, Colour.GREEN, model_name, Colour.END)
        if not simplify_model:
            logger.warning(
                "Model simplification from restriction %sdisabled%s, so no removal of zero contributions will be performed.", Colour.RED, Colour.END)
        model.apply_input_param_card(restriction_card, simplify=simplify_model)
    else:
        logger.info("No restriction applied to model '%s%s%s'",
                    Colour.GREEN, model_name, Colour.END)

    input_param_card = InputParamCard.from_model(model)
    if restriction_card is not None:
        for param in input_param_card.keys():
            if param in restriction_card:
                input_param_card[param] = restriction_card[param]

    logger.info("Model %s%s%s successfully loaded (%s%s%s particles, %s%s%s parameters, %s%s%s interactions, %s%s%s couplings, %s%s%s Lorentz structures)",
                Colour.GREEN, model.name, Colour.END,
                Colour.YELLOW, len(model.particles), Colour.END,
                Colour.YELLOW, len(model.parameters), Colour.END,
                Colour.YELLOW, len(model.vertex_rules), Colour.END,
                Colour.YELLOW, len(model.couplings), Colour.END,
                Colour.YELLOW, len(model.lorentz_structures), Colour.END
                )
    return model, input_param_card


def export_model(model: Model, input_param_card: InputParamCard, output_model_path: str | None = None, json_look: JSONLook = JSONLook.VERBOSE, allow_overwrite=False) -> str | None:

    if output_model_path is None:
        output_model_path = os.path.abspath(
            pjoin(os.getcwd(), f"{model.name}.json"))

    if not output_model_path.upper().endswith('.JSON'):
        raise UFOModelLoaderError(
            f"Output model path '{output_model_path}' must end with .json as this is the only format supported for output.")
    model_base_path = os.path.dirname(os.path.abspath(output_model_path))
    model_output_name = os.path.basename(output_model_path[:-5])

    model_output_path = pjoin(model_base_path, f"{model_output_name}.json")
    input_param_card_output_path = pjoin(
        model_base_path, f"{model_output_name}_param_card.json")
    if os.path.isfile(model_output_path) and not allow_overwrite:
        logger.exception(
            "Output model file '%s%s%s' already exists. Use option %s-w%s to allow overwriting it.", Colour.RED, input_param_card_output_path, Colour.END, Colour.GREEN, Colour.END)
        return None
    if os.path.isfile(input_param_card_output_path) and not allow_overwrite:
        logger.critical(
            "Output input parameter card file '%s%s%s' already exists. Use option %s-w%s to allow overwriting it.",
            Colour.RED, input_param_card_output_path, Colour.END, Colour.GREEN, Colour.END)
        return None

    with open(model_output_path, 'w', encoding='utf-8') as f:
        f.write(model.to_json(json_look=json_look))
    with open(input_param_card_output_path, 'w', encoding='utf-8') as f:
        f.write(input_param_card.to_json(json_look=json_look))
    if os.getcwd() == model_base_path:
        logger.info(
            "Successfully exported model in %s%s%s %sJSON%s format to file '%s%s.json%s' and corresponding input parameter card to '%s%s_param_card.json%s'", Colour.YELLOW, json_look, Colour.END, Colour.BLUE, Colour.END, Colour.GREEN, model_output_name, Colour.END, Colour.GREEN, model_output_name, Colour.END)
    else:
        logger.info("Successfully exported model in %s%s%s %sJSON%s format to files '%s%s.json%s' and corresponding input parameter card to '%s%s%s' in directory '%s%s%s'",
                    Colour.YELLOW, json_look, Colour.END, Colour.BLUE, Colour.END, Colour.GREEN, f"{model_output_name}.json", Colour.END, Colour.GREEN, f"{model_output_name}_param_card.json", Colour.END, Colour.GREEN, model_base_path, Colour.END)

    return model_output_path
