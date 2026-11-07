"""Model-facing protocol steps choose their kind before operation parameters."""

from copy import deepcopy


def response_schema(output_schema):
    """Derive the generation shape from the authoritative block output schema.

    Flat step variants start with different parameter names after canonical key
    sorting. That makes a constrained decoder select a shape before it can
    emit the operation kind. Nesting parameters gives every variant the same
    prefix and puts the discriminator before any operation-specific fields.
    """
    schema = deepcopy(output_schema)
    for variant in schema['properties']['steps']['items']['oneOf']:
        properties = variant['properties']
        common = ('id', 'instruction_lines', 'kind')
        parameters = {key: value for key, value in properties.items() if key not in common}
        variant['properties'] = {key: properties[key] for key in common}
        variant['properties']['parameters'] = {
            'type': 'object', 'properties': parameters,
            'required': [key for key in variant['required'] if key not in common],
            'additionalProperties': False,
        }
        variant['required'] = [*common, 'parameters']
    return schema


def protocol_plan(response):
    """Project validated model parameters into the unchanged execution language."""
    plan = deepcopy(response)
    for step in plan['steps']:
        step.update(step.pop('parameters'))
    return plan
