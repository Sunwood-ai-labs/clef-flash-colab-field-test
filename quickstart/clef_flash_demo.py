"""Cloudflare Clef-flash に、自分の入力と質問を渡して確率を受け取る。

GPUメモリが24GBを超えるColabランタイム（実験ではA100 40GB）で、このファイルをそのまま実行する。
先に transformers==5.10.2 を入れ、カーネルを再起動しておく。REQUESTS を書き換えれば自分のデータで試せる。

実験で使った experiment/run_clef.py から、取得・読み込み・判定の部分だけを取り出したもの。
モデルのrevisionと公式コードのSHA-256は、実験と同じ値に固定している。
"""
import hashlib
import io
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import torch
from huggingface_hub import snapshot_download
from PIL import Image

MODEL_ID = "Cloudflare/clef-flash"
REVISION = "8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3"
OFFICIAL_CODE_SHA256 = "0E304CF7C6500E8BB59BEF7E2AFD2C6373F82596DFB3B57D1AA93C175E2DC3A3"
MODEL_DIR = "/content/clef-flash-pinned"
MAX_IMAGE_SIDE = 1024

# ここを書き換える。state が入力、questions が質問。image_url を付けると画像も渡す。
# 質問の型は choice（候補から1つ選ぶ）、noul（真である確率）、score（順序のある段階）の3つ。
REQUESTS = {
    "text-invoice-01": {
        "state": {"invoice": {"vendor": "Acme", "total": 1250.0, "currency": "USD", "status": "overdue"}},
        "questions": {
            "status": {
                "type": "choice",
                "instructions": "What is the invoice status?",
                "criteria": {"paid": "Invoice is paid.", "overdue": "Invoice is past due.", "draft": "Not sent."},
            },
            "large": {"type": "noul", "instructions": "Is the total above 1000 USD?"},
        },
    },
    "image-hand-holding-candy-01": {
        "state": "Inspect the attached photo.",
        "image_url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG",
        "questions": {
            "hand_holding_candy": {
                "type": "noul",
                "instructions": "Is a human hand visibly holding several pieces of candy?",
            },
        },
    },
}


def load_image(url):
    """画像を取得してRGBにし、長辺を MAX_IMAGE_SIDE ピクセルまで縮める（実験と同じ前処理）。"""
    with urlopen(url, timeout=60) as response:
        rgb = Image.open(io.BytesIO(response.read())).convert("RGB")
    scale = min(1.0, MAX_IMAGE_SIDE / max(rgb.size))
    size = (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale)))
    return rgb.resize(size, resample=Image.Resampling.LANCZOS) if size != rgb.size else rgb


if not torch.cuda.is_available():
    raise RuntimeError("CUDAが使えません。GPUランタイムで実行してください。")
gpu = torch.cuda.get_device_properties(0)
print(f"GPU: {gpu.name} / {gpu.total_memory / 2**30:.1f} GiB", flush=True)

started = time.perf_counter()
model_path = snapshot_download(repo_id=MODEL_ID, revision=REVISION, local_dir=MODEL_DIR, max_workers=4, token=False)
print(f"重みの取得: {time.perf_counter() - started:.1f}秒", flush=True)

code_hash = hashlib.sha256((Path(model_path) / "joint_schema_model.py").read_bytes()).hexdigest().upper()
if code_hash != OFFICIAL_CODE_SHA256:
    raise ValueError(f"公式コードのSHA-256が実験時と違います: {code_hash}")

# 通常の pipeline() や generate() ではなく、配布物に入っている公式の判断ヘッドを通す
sys.path.insert(0, str(model_path))
from joint_schema_model import load_release_model, systemone

started = time.perf_counter()
model, processor = load_release_model(model_path, device="cuda")
torch.cuda.synchronize()
print(f"モデルの読み込み: {time.perf_counter() - started:.1f}秒 / "
      f"GPUメモリ {torch.cuda.memory_allocated(0) / 2**30:.2f} GiB", flush=True)

results = {}
for name, spec in REQUESTS.items():
    request = {"model": "clef-flash", "state": spec["state"], "questions": spec["questions"]}
    if spec.get("image_url"):
        request["images"] = [load_image(spec["image_url"])]
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats(0)
    started = time.perf_counter()
    response = systemone(model, processor, request)
    torch.cuda.synchronize()
    results[name] = {
        "response": response,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "cuda_peak_allocated_gib": round(torch.cuda.max_memory_allocated(0) / 2**30, 2),
    }

print("CLEF_RESULT_JSON_BEGIN")
print(json.dumps(results, ensure_ascii=False, indent=2))
print("CLEF_RESULT_JSON_END")
