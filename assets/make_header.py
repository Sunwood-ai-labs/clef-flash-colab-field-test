"""READMEのヘッダー画像（assets/header.svg）を、results/ の実測値から作る。

使い方（リポジトリ直下で）: python assets/make_header.py
"""
import json
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
run = json.loads((ROOT / 'results/run-result.json').read_text(encoding='utf-8'))
cases = {c['case_id']: c for c in run['cases']}
text, image = cases['text-invoice-01'], cases['image-hand-holding-candy-01']
probs = text['raw_response']['answers']['status']['probabilities']
large = text['predicted']['large.noul']
candy = image['predicted']['hand_holding_candy.noul']
peak = max(c['cuda_peak_allocated_bytes'] for c in run['cases']) / 2 ** 30
low = int(min(probs['overdue'], large, candy) * 100) / 100

ACC, SANS = '#F38020', "font-family=\"'Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif\""
MONO = 'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'

out = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 420" width="1280" height="420" role="img" '
    'aria-label="Cloudflare Clef-flash on Google Colab A100: text and image decision field test">',
    '<defs>',
    '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B0F14"/><stop offset="0.6" stop-color="#11151B"/><stop offset="1" stop-color="#1C140C"/></linearGradient>',
    f'<radialGradient id="glow" cx="0.82" cy="0.25" r="0.6"><stop offset="0" stop-color="{ACC}" stop-opacity="0.20"/><stop offset="1" stop-color="{ACC}" stop-opacity="0"/></radialGradient>',
    '<linearGradient id="title" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#FBC38D"/></linearGradient>',
    '<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#FFFFFF" stroke-opacity="0.035"/></pattern>',
    '<clipPath id="r"><rect width="1280" height="420" rx="20"/></clipPath>',
    '</defs>',
    '<g clip-path="url(#r)">',
    '<rect width="1280" height="420" fill="url(#bg)"/><rect width="1280" height="420" fill="url(#grid)"/><rect width="1280" height="420" fill="url(#glow)"/>',
    f'<g {SANS}>',
    f'<rect x="64" y="70" width="278" height="30" rx="15" fill="{ACC}" fill-opacity="0.14" stroke="{ACC}" stroke-opacity="0.55"/>',
    '<text x="203" y="90" text-anchor="middle" font-size="13" font-weight="700" letter-spacing="2" fill="#FBAD41">DECISION MODEL FIELD TEST</text>',
    '<text x="64" y="158" font-size="54" font-weight="800" fill="url(#title)" letter-spacing="-1">Cloudflare</text>',
    '<text x="64" y="216" font-size="54" font-weight="800" fill="url(#title)" letter-spacing="-1">Clef-flash</text>',
    f'<text x="64" y="262" font-size="24" font-weight="600" fill="#9CA3AF"><tspan fill="{ACC}">×</tspan> Google Colab A100 <tspan fill="#6B7280" font-weight="400">— text + image</tspan></text>',
    '</g>',
]
chips = [(f'{low:.2f}+', 'on expected answers'), (f'{peak:.1f} GiB', 'peak GPU memory'),
         (f'{text["elapsed_seconds"]:.1f}–{image["elapsed_seconds"]:.1f} s', 'per decision call')]
for i, (value, label) in enumerate(chips):
    x = 64 + i * 200
    out.append(f'<g {SANS}><rect x="{x}" y="304" width="186" height="64" rx="12" fill="#FFFFFF" fill-opacity="0.04" stroke="#FFFFFF" stroke-opacity="0.10"/>'
               f'<text x="{x + 18}" y="332" font-size="22" font-weight="800" fill="#F9FAFB">{value}</text>'
               f'<text x="{x + 18}" y="354" font-size="12.5" fill="#9CA3AF" letter-spacing="0.4">{label}</text></g>')

# 右側：質問ごとに、候補と確率の棒を並べる（実験で返ってきた値そのもの）
out += [
    '<rect x="676" y="52" width="556" height="316" rx="16" fill="#000000" fill-opacity="0.28" stroke="#FFFFFF" stroke-opacity="0.08"/>',
    f'<text x="698" y="82" {MONO} font-size="12" fill="#6B7280" letter-spacing="1">QUESTIONS IN, PROBABILITIES OUT</text>',
]
bx, bw = 850, 290
groups = [
    ('invoice · status (choice)', [('overdue', probs['overdue']), ('paid', probs['paid']), ('draft', probs['draft'])]),
    ('invoice · total above 1000 USD? (noul)', [('true', large)]),
    ('photo · hand holding candy? (noul)', [('true', candy)]),
]
y = 112
for title, rows in groups:
    out.append(f'<text x="698" y="{y}" {MONO} font-size="12.5" fill="#D1D5DB">{title}</text>')
    y += 12
    for name, p in rows:
        top = p > 0.5
        out += [
            f'<text x="718" y="{y + 12}" {MONO} font-size="12" fill="{"#FBAD41" if top else "#6B7280"}">{name}</text>',
            f'<rect x="{bx}" y="{y}" width="{bw}" height="14" rx="7" fill="#FFFFFF" fill-opacity="0.06"/>',
            f'<rect x="{bx}" y="{y}" width="{max(p * bw, 14):.1f}" height="14" rx="7" fill="{ACC if top else "#6B7280"}"/>',
            f'<text x="{bx + bw + 12}" y="{y + 12}" {MONO} font-size="12" fill="{"#F9FAFB" if top else "#6B7280"}">{p:.4f}</text>',
        ]
        y += 24
    y += 22
out += [f'<rect x="0" y="0" width="6" height="420" fill="{ACC}"/>', '</g></svg>']
svg = '\n'.join(out)
xml.dom.minidom.parseString(svg)
(ROOT / 'assets/header.svg').write_text(svg, encoding='utf-8', newline='\n')
print('wrote header.svg')
