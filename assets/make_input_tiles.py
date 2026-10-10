"""実験に入力した2件（請求書のJSON、写真）の中身がわかるタイル画像（assets/inputs-overview.jpg）を作る。

写真の元ファイルはこのリポジトリに含めていない。Hugging Faceの公開ドキュメント用画像なので、
作り直すときは次のURLから取得し、そのパスを引数で渡す。ヘッドレスChromeとPillowが要る。
https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG

使い方（リポジトリ直下で）: python assets/make_input_tiles.py <candy.JPGのパス>
"""
import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get('CHROME', 'C:/Program Files/Google/Chrome/Application/chrome.exe')
INK, SUB, GRID, TRACK, ACCENT = '#111827', '#6B7280', '#D1D5DB', '#F3F4F6', '#D9660A'
W, H = 1760, 1010

contract = json.loads((ROOT / 'experiment/contract.json').read_text(encoding='utf-8'))
cases = {c['case_id']: c for c in contract['cases']}
text, image = cases['text-invoice-01'], cases['image-hand-holding-candy-01']

# モデルに渡したのと同じ前処理（RGB化し、長辺を1024ピクセルへ縮小）をした写真を一時ファイルにする
tmp = Path(tempfile.mkdtemp())
with Image.open(sys.argv[1]) as src:
    rgb = src.convert('RGB')
scale = min(1.0, 1024 / max(rgb.size))
small = rgb.resize((round(rgb.width * scale), round(rgb.height * scale)), Image.Resampling.LANCZOS)
small.save(tmp / 'photo.jpg', quality=90)


def questions(case):
    rows = []
    for qid, q in case['input']['questions'].items():
        kind = {'choice': '候補から1つ選ぶ', 'noul': '真である確率を返す'}[q['type']]
        rows.append(f'<div class="q"><span class="qid">{qid}</span><span class="type">{q["type"]}　{kind}</span>'
                    f'<div class="ask">{html.escape(q["instructions"])}</div>')
        for key, desc in q.get('criteria', {}).items():
            rows.append(f'<div class="opt"><b>{key}</b>{html.escape(desc)}</div>')
        rows.append('</div>')
    return ''.join(rows)


state = html.escape(json.dumps(text['input']['state'], ensure_ascii=False, indent=2))
page = f"""<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0}}
body{{width:{W}px;background:#fff;font-family:'Segoe UI','Hiragino Sans','Yu Gothic UI','Meiryo','Noto Sans JP',sans-serif;color:{INK}}}
.card{{width:{W}px;height:{H}px;border:1px solid {GRID};border-radius:16px;padding:0 32px 32px;overflow:hidden}}
.head{{height:100px;padding-top:26px}}
h1{{font-size:28px;font-weight:700}}
.sub{{font-size:17px;color:{SUB};margin-top:6px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;height:{H - 134}px}}
.tile{{border:1px solid {GRID};border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
.label{{height:46px;flex:none;display:flex;align-items:center;gap:10px;padding:0 12px;border-bottom:1px solid {GRID};white-space:nowrap}}
.chip{{font:700 13px ui-monospace,Consolas,monospace;color:#fff;background:{ACCENT};border-radius:6px;padding:3px 8px}}
.name{{font-size:16px;font-weight:700}}
.note{{font-size:13.5px;color:{SUB}}}
.part{{padding:16px 20px}}
.cap{{font-size:13.5px;font-weight:700;color:{ACCENT};margin-bottom:8px}}
pre{{font:17px/1.5 ui-monospace,Consolas,monospace;background:{TRACK};border-radius:8px;padding:14px 18px}}
.pic{{background:{TRACK};border-radius:8px;height:430px;display:flex;justify-content:center}}
.pic img{{height:100%}}
.q{{border-top:1px solid {GRID};padding:12px 0}}
.q:first-of-type{{border-top:0;padding-top:0}}
.qid{{font:700 15px ui-monospace,Consolas,monospace}}
.type{{font-size:13px;color:{SUB};margin-left:12px}}
.ask{{font-size:18px;margin-top:4px}}
.opt{{font-size:15px;color:{SUB};margin-top:3px}}
.opt b{{font:700 14px ui-monospace,Consolas,monospace;color:{INK};display:inline-block;width:92px}}
</style><div class="card"><div class="head"><h1>Clef-flashに入力した2件</h1>
<div class="sub">入力（state）と質問（questions）を1回の要求で渡す。質問と候補は英語のまま渡した</div></div>
<div class="grid">
<div class="tile"><div class="label"><span class="chip">text-invoice-01</span><span class="name">請求書</span><span class="note">テキスト（JSON）　質問2つ</span></div>
<div class="part"><div class="cap">入力（state）</div><pre>{state}</pre></div>
<div class="part"><div class="cap">質問（questions）</div>{questions(text)}</div></div>
<div class="tile"><div class="label"><span class="chip">image-hand-holding-candy-01</span><span class="name">写真</span><span class="note">画像　{small.width}×{small.height}に縮小して入力　質問1つ</span></div>
<div class="part"><div class="cap">入力（state と images）</div><pre>{html.escape(json.dumps(image['input']['state']))}</pre>
<div class="pic" style="margin-top:10px"><img src="{(tmp / 'photo.jpg').as_uri()}"></div></div>
<div class="part"><div class="cap">質問（questions）</div>{questions(image)}</div></div>
</div></div>"""
(tmp / 'page.html').write_text(page, encoding='utf-8')
subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                f'--user-data-dir={tmp / "profile"}', f'--window-size={W},{H}', f'--screenshot={tmp / "page.png"}',
                (tmp / 'page.html').as_uri()], check=True, capture_output=True)
Image.open(tmp / 'page.png').convert('RGB').save(ROOT / 'assets/inputs-overview.jpg', quality=88, optimize=True)
print(f'wrote inputs-overview.jpg ({W}x{H})')
