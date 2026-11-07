"""Plan the simulated procedure while its empty native deck is visible."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from mn_sdk.blueprint.context import source_manifest
from mn_sdk.blueprint.models import model_request

from .planning_schema import protocol_plan, response_schema
from .planning_ui import planning_view
from .protocol import validate_plan


def run(block, inputs):
    with planning_view(block, 'planning'):
        declaration = source_manifest(__file__, env=block.environment)
        schema = declaration['metadata']['mn_blocks']['steps'][block.step_id]['output_schema']
        value = _plan(block, inputs, schema)
        Draft202012Validator(schema).validate(value)
        return validate_plan(value, inputs['procedure']['markdown'])


def _plan(block, inputs, schema):
    schema = response_schema(schema)
    llm = block.config['llm']
    settings = llm['configs'][llm['default_config']]
    prompt = (Path(__file__).resolve().parents[1] / 'prompts/plan.md').read_text(encoding='utf-8')
    prompt += '\nReturn compact JSON matching this response schema:\n' + json.dumps(
        schema, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    response = model_request(block, {
        'purpose': 'web_lab_operator', 'model': llm['model'], 'path': '/chat/completions',
        'payload': {'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(inputs, ensure_ascii=False, allow_nan=False)}],
            'max_tokens': settings['max_tokens'], 'temperature': 0,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'web_lab_plan', 'strict': True, 'schema': schema}}},
        'options': {'provider': llm['provider'], 'backend': llm['backend'],
                    'timeout_seconds': settings['timeout_seconds'], 'structured_output': True},
    }, key='procedure-plan')
    choices = response.get('choices')
    if isinstance(choices, list) and choices and choices[0].get('finish_reason') == 'length':
        raise ValueError('The model reached the lab plan output token limit. No simulation actions were started.')
    if not isinstance(choices, list) or not choices or choices[0].get('finish_reason') != 'stop':
        raise ValueError('The model did not return a complete lab plan.')
    content = choices[0].get('message', {}).get('content')
    if not isinstance(content, str) or len(content.encode()) > 256000:
        raise ValueError('The lab plan exceeds its text limit.')
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError('The model returned invalid JSON for the lab plan. No simulation actions were started.') from error
    Draft202012Validator(schema).validate(value)
    return protocol_plan(value)
