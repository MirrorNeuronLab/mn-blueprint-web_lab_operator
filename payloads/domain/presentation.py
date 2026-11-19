"""A self-contained, read-only replay of recorded simulation observations."""

import json
from pathlib import Path

from .protocol import WELL_CAPACITY
from .supervision import event_rows

ASSETS = Path(__file__).resolve().parents[1] / 'web_assets'
STYLE = 'style.css'
SCRIPTS = ('vendor/three.min.js', 'equipment.js', 'deck.js', 'app.js')


def render(final, trace, plates):
    page = (ASSETS / 'index.html').read_text(encoding='utf-8')
    frames = [{'after': event['after'], 'passed': event['outcome']['passed'],
               'rows': event_rows([event])} for event in trace['events']]
    data = json.dumps({'result': final, 'initial': trace['initial'], 'frames': frames,
                       'plates': plates, 'well_capacity_ul': WELL_CAPACITY},
                      ensure_ascii=True, allow_nan=False)
    data = data.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    style = (ASSETS / STYLE).read_text(encoding='utf-8')
    page = page.replace(f'<link rel="stylesheet" href="{STYLE}">', f'<style>{style}</style>')
    for name in SCRIPTS:
        code = (ASSETS / name).read_text(encoding='utf-8')
        if '</script' in code.lower():
            raise ValueError(f'The replay script {name} cannot be embedded.')
        page = page.replace(f'<script src="{name}" defer></script>', f'<script>{code}</script>')
    license_text = (ASSETS / 'vendor' / 'three.LICENSE.txt').read_text(encoding='utf-8')
    return page.replace('<body>', f'<body>\n<!--\n{license_text}-->\n'
                        f'<script type="application/json" id="replay-data">{data}</script>', 1)
