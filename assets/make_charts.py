"""results/ の実測値から、記事・README用のグラフ（SVGとPNG）を作る。

使い方（リポジトリ直下で）: python assets/make_charts.py
PNGの書き出しにはヘッドレスChromeを使う。場所が違うときは環境変数 CHROME で指定する。
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get('CHROME', 'C:/Program Files/Google/Chrome/Application/chrome.exe')


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


INK, SUB, GRID, TRACK, ACCENT, CARD = '#111827', '#6B7280', '#D1D5DB', '#EEF0F2', '#D9660A', '#FFFFFF'
FONT = "font-family=\"'Segoe UI','Hiragino Sans','Yu Gothic UI','Meiryo','Noto Sans JP',sans-serif\""
W = 880
GIB = 2 ** 30


def frame(h, title, subtitle, body):
    return '\n'.join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-label="{title}" {FONT}>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="12" fill="{CARD}" stroke="{GRID}"/>',
        f'<text x="32" y="44" font-size="20" font-weight="700" fill="{INK}">{title}</text>',
        f'<text x="32" y="70" font-size="13.5" fill="{SUB}">{subtitle}</text>',
        *body, '</svg>'])


def write(name, h, svg):
    path = ROOT / 'assets' / f'{name}.svg'
    path.write_text(svg, encoding='utf-8', newline='\n')
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                    f'--user-data-dir={tempfile.mkdtemp()}',
                    '--default-background-color=00000000', f'--window-size={W},{h}',
                    f'--screenshot={ROOT / "assets" / (name + ".png")}', path.as_uri()], check=True, capture_output=True)
    print('wrote', name)


run = load('results/run-result.json')
fail = load('results/run-result-l4-failure.json')
cases = {c['case_id']: c for c in run['cases']}
text, image = cases['text-invoice-01'], cases['image-hand-holding-candy-01']

# ---- 1. 3つの質問に付いた確率 ----
status = text['raw_response']['answers']['status']
expected_choice = text['expected']['status.choice']
rows = [('請求書', '状態はどれか（3択）', key, p, key == expected_choice, None)
        for key, p in sorted(status['probabilities'].items(), key=lambda kv: -kv[1])]
rows += [
    ('請求書', '合計は1,000ドルを超えるか', '真である確率', text['predicted']['large.noul'], True, text['expected']['large.noul_minimum']),
    ('写真', '手が複数のキャンディを持っているか', '真である確率', image['predicted']['hand_holding_candy.noul'], True,
     image['expected']['hand_holding_candy.noul_minimum']),
]
x0, bw, y0, rh = 420, 340, 118, 44
body = [
    f'<text x="32" y="100" font-size="12.5" fill="{SUB}">入力と質問</text>',
    f'<text x="288" y="100" font-size="12.5" fill="{SUB}">答えの候補</text>',
    f'<text x="{x0}" y="100" font-size="12.5" fill="{SUB}">Clef-flashが返した確率（0〜1）</text>',
]
prev = None
for i, (src, question, label, p, expected, threshold) in enumerate(rows):
    y = y0 + i * rh + (10 if i >= 3 else 0) + (10 if i >= 4 else 0)
    if (src, question) != prev:
        body += [
            f'<text x="32" y="{y + 12}" font-size="14" font-weight="700" fill="{INK}">{src}</text>',
            f'<text x="32" y="{y + 30}" font-size="12" fill="{SUB}">{question}</text>',
        ]
        prev = (src, question)
    w = p * bw
    body += [
        f'<text x="288" y="{y + 16}" font-size="13.5" fill="{INK}" {"font-weight=\"700\"" if expected else ""}>{label}</text>',
        f'<rect x="{x0}" y="{y}" width="{bw}" height="22" rx="4" fill="{TRACK}"/>',
    ]
    if expected:
        body.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="22" rx="4" fill="{ACCENT}"><title>{label}: {p}</title></rect>')
    else:
        body.append(f'<rect x="{x0 + 0.75}" y="{y + 0.75}" width="{max(w, 4):.1f}" height="20.5" rx="3" fill="{CARD}" stroke="{INK}" stroke-width="1.5"><title>{label}: {p}</title></rect>')
    body.append(f'<text x="{x0 + max(w, 4) + 10:.1f}" y="{y + 16}" font-size="14" font-weight="700" fill="{INK}">{p:.4f}</text>')
    if threshold is not None:
        tx = x0 + threshold * bw
        body += [
            f'<line x1="{tx}" x2="{tx}" y1="{y - 5}" y2="{y + 27}" stroke="{INK}" stroke-dasharray="4 3" stroke-width="1.5"/>',
            f'<text x="{tx}" y="{y + 40}" font-size="11.5" text-anchor="middle" fill="{SUB}">合格の基準 {threshold} 超</text>',
        ]
yb = y0 + len(rows) * rh + 20
lx, ly = 32, yb + 26
body += [
    f'<rect x="{lx}" y="{ly - 10}" width="26" height="12" rx="3" fill="{ACCENT}"/>',
    f'<text x="{lx + 34}" y="{ly + 1}" font-size="12.5" fill="{INK}">実験前に決めた期待どおりの答え</text>',
    f'<rect x="{lx + 250.75}" y="{ly - 9.25}" width="24.5" height="10.5" rx="3" fill="{CARD}" stroke="{INK}" stroke-width="1.5"/>',
    f'<text x="{lx + 284}" y="{ly + 1}" font-size="12.5" fill="{INK}">それ以外の候補</text>',
]
low = min(r[3] for r in rows if r[4])
write('chart-answers', yb + 50, frame(
    yb + 50, f'3つの質問すべてで、期待した答えに{int(low * 100) / 100:.2f}以上の確率が付いた',
    f'Cloudflare Clef-flash。請求書のJSON（質問2つ）と写真（質問1つ）の2例。{run["gpu"]["actual"]}、BF16', body))

# ---- 2. GPUメモリ：L4の失敗とA100の成功 ----
msg = fail['error']['message']
l4_total = float(re.search(r'total capacity of ([\d.]+) GiB', msg).group(1))
l4_used = float(re.search(r'([\d.]+) GiB is allocated by PyTorch', msg).group(1))
l4_want = float(re.search(r'Tried to allocate ([\d.]+) GiB', msg).group(1))
a100_total = run['gpu']['total_memory_bytes'] / GIB
mem_rows = [
    ('L4', '読み込みの途中で停止', l4_total, l4_used, l4_want),
    ('A100', '読み込み直後', a100_total, run['cuda_allocated_bytes_after_load'] / GIB, 0),
    ('A100', '請求書の判定中（最大）', a100_total, text['cuda_peak_allocated_bytes'] / GIB, 0),
    ('A100', '写真の判定中（最大）', a100_total, image['cuda_peak_allocated_bytes'] / GIB, 0),
]
x0, bw, y0, rh, top = 250, 560, 124, 52, 42.0
sx = lambda v: v / top * bw
body = [
    f'<text x="32" y="104" font-size="12.5" fill="{SUB}">GPUと場面</text>',
    f'<text x="{x0}" y="104" font-size="12.5" fill="{SUB}">GPUメモリ（GiB）。灰色の帯がそのGPUの全容量</text>',
]
for i, (gpu, scene, total, used, want) in enumerate(mem_rows):
    y = y0 + i * rh
    body += [
        f'<text x="32" y="{y + 13}" font-size="14" font-weight="700" fill="{INK}">{gpu}<tspan font-weight="400" fill="{SUB}" font-size="12">　全{total:.1f} GiB</tspan></text>',
        f'<text x="32" y="{y + 31}" font-size="12" fill="{SUB}">{scene}</text>',
        f'<rect x="{x0}" y="{y}" width="{sx(total):.1f}" height="24" rx="4" fill="{TRACK}"/>',
    ]
    if want:
        body += [
            f'<rect x="{x0}" y="{y}" width="{sx(used):.1f}" height="24" rx="4" fill="{SUB}"><title>使用中 {used} GiB</title></rect>',
            f'<rect x="{x0 + sx(used) + 0.75:.1f}" y="{y + 0.75}" width="{sx(want) - 1.5:.1f}" height="22.5" rx="3" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="5 4"><title>追加で要求 {want} GiB</title></rect>',
            f'<path d="M{x0 + sx(used + want) + 10:.1f} {y + 6}l12 12M{x0 + sx(used + want) + 22:.1f} {y + 6}l-12 12" stroke="{INK}" stroke-width="2.5"/>',
            f'<text x="{x0 + 8}" y="{y + 17}" font-size="12.5" font-weight="700" fill="{CARD}">使用中 {used:.2f}</text>',
            f'<text x="{x0 + sx(total) + 10:.1f}" y="{y + 17}" font-size="12.5" font-weight="700" fill="{INK}">追加で要求 {want:.2f}</text>',
            f'<text x="{x0 + sx(used + want) + 34:.1f}" y="{y + 17}" font-size="12.5" font-weight="700" fill="{INK}">不足</text>',
            f'<line x1="{x0 + sx(total):.1f}" x2="{x0 + sx(total):.1f}" y1="{y - 6}" y2="{y + 30}" stroke="{INK}" stroke-width="1.5"/>',
            f'<text x="{x0 + sx(total):.1f}" y="{y + 44}" font-size="11.5" text-anchor="middle" fill="{SUB}">L4の上限 {total:.2f}</text>',
        ]
    else:
        body += [
            f'<rect x="{x0}" y="{y}" width="{sx(used):.1f}" height="24" rx="4" fill="{ACCENT}"><title>{scene}: {used:.2f} GiB</title></rect>',
            f'<text x="{x0 + sx(used) + 10:.1f}" y="{y + 17}" font-size="14" font-weight="700" fill="{INK}">{used:.2f}<tspan font-weight="400" fill="{SUB}"> GiB</tspan></text>',
        ]
yb = y0 + len(mem_rows) * rh
peak = max(text['cuda_peak_allocated_bytes'], image['cuda_peak_allocated_bytes']) / GIB
write('chart-memory', yb + 14, frame(
    yb + 14, f'L4の{l4_total:.0f} GiBでは読み込みで不足。A100では最大{peak:.1f} GiBで動いた',
    '同じモデル、同じ入力、同じ読み込み手順（BF16）。変えたのはGPUだけ。PyTorchが確保した量', body))

# ---- 3. 74秒の内訳 ----
total = run['total_wall_seconds']
dl, ld = run['snapshot_download']['download_seconds'], run['model_load_seconds']
t1, t2 = text['elapsed_seconds'], image['elapsed_seconds']
parts = [
    ('重みの取得（約19.1 GB）', dl, INK),
    ('モデルの読み込み', ld, SUB),
    ('請求書の判定', t1, ACCENT),
    ('写真の判定', t2, ACCENT),
    ('そのほか', total - dl - ld - t1 - t2, GRID),
]
x0, bw, y0 = 32, W - 64, 150
body, x = [], x0
for i, (label, sec, color) in enumerate(parts):
    w = sec / total * bw
    body.append(f'<rect x="{x:.1f}" y="{y0}" width="{max(w - 2, 1):.1f}" height="44" rx="4" fill="{color}"><title>{label}: {sec:.3f}秒</title></rect>')
    cx = x + w / 2
    if i < 2:
        body += [
            f'<text x="{cx:.1f}" y="{y0 - 28}" font-size="13.5" text-anchor="middle" fill="{INK}">{label}</text>',
            f'<text x="{cx:.1f}" y="{y0 - 9}" font-size="15" font-weight="700" text-anchor="middle" fill="{INK}">{sec:.1f}秒</text>',
        ]
    x += w
ix = x0 + (dl + ld) / total * bw
iw = (t1 + t2) / total * bw
body += [
    f'<path d="M{ix:.1f} {y0 + 52}v8h{iw:.1f}v-8" fill="none" stroke="{INK}" stroke-width="1.5"/>',
    f'<text x="{ix + iw / 2:.1f}" y="{y0 + 80}" font-size="13.5" text-anchor="end" fill="{INK}">判定2回 <tspan font-weight="700" font-size="15">{t1 + t2:.1f}秒</tspan>（請求書 {t1:.2f}秒 ＋ 写真 {t2:.2f}秒）</text>',
    f'<text x="{x0}" y="{y0 + 80}" font-size="12.5" fill="{SUB}">0秒</text>',
    f'<text x="{x0 + bw}" y="{y0 + 104}" font-size="12.5" text-anchor="end" fill="{SUB}">合計 {total:.1f}秒</text>',
]
write('chart-time', y0 + 124, frame(
    y0 + 124, f'全体{total:.0f}秒のうち、判定そのものは{t1 + t2:.1f}秒。残りは準備',
    f'{run["gpu"]["actual"]}での1回の実行。判定時間はそれぞれ1回だけ測った値で、反復した平均ではない', body))

# ---- 4. 試せたこと、試せなかったこと ----
h100 = (ROOT / 'results/h100-request.log').read_text(encoding='utf-8')
assert 'Backend rejected accelerator' in h100
cover = [
    ('Clef-flash・テキスト', f'A100で実行。期待どおり（{t1:.2f}秒）', 'ok'),
    ('Clef-flash・画像', f'A100で実行。期待どおり（{t2:.2f}秒）', 'ok'),
    ('Clef-flash・L4での実行', 'モデルの読み込みでGPUメモリ不足', 'ng'),
    ('Clef-omni・音声と動画', 'H100の割り当てを拒否され、未実行', 'none'),
    ('Workers AIのホスト版API', '未実行。料金と速度は公式の発表値のみ', 'none'),
    ('正解率や速度の比較評価', '未実施。今回は2例の動作確認', 'none'),
]
y0, rh = 108, 42
body = []
for i, (label, note, kind) in enumerate(cover):
    y = y0 + i * rh
    cx, cy = 48, y + 12
    if kind == 'ok':
        body.append(f'<circle cx="{cx}" cy="{cy}" r="10" fill="{ACCENT}"/><path d="M{cx - 5} {cy}l4 4l6 -8" fill="none" stroke="{CARD}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    elif kind == 'ng':
        body.append(f'<circle cx="{cx}" cy="{cy}" r="9.25" fill="{CARD}" stroke="{INK}" stroke-width="1.5"/><path d="M{cx - 4} {cy - 4}l8 8M{cx + 4} {cy - 4}l-8 8" stroke="{INK}" stroke-width="2"/>')
    else:
        body.append(f'<circle cx="{cx}" cy="{cy}" r="9.25" fill="{CARD}" stroke="{SUB}" stroke-width="1.5" stroke-dasharray="3 3"/>')
    body += [
        f'<text x="72" y="{y + 17}" font-size="15" font-weight="700" fill="{INK}">{label}</text>',
        f'<text x="330" y="{y + 17}" font-size="14" fill="{INK if kind != "none" else SUB}">{note}</text>',
    ]
yb = y0 + len(cover) * rh
write('chart-coverage', yb + 8, frame(
    yb + 8, '動いたのはClef-flashの2例。Clef-omniとホスト版は試せていない',
    '塗りつぶしの丸は実行して期待どおり、×は実行して失敗、点線の丸は未実行', body))
