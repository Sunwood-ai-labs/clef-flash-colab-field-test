import copy
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from PIL import Image


IMAGE_REMOTE_PATH = Path("/content/candy-source.JPG")
MODEL_DIR = Path("/content/clef-flash-pinned")
OUTPUT_DIR = Path("/content/clef-output")
CONTRACT_PATH = Path("/content/clef-contract.json")
RESULT_PATH = OUTPUT_DIR / "run-result.json"
PROGRESS_PATH = OUTPUT_DIR / "download-progress.jsonl"
RAW_DIR = OUTPUT_DIR / "raw"
EXPECTED_SOURCE_HASH = "0E304CF7C6500E8BB59BEF7E2AFD2C6373F82596DFB3B57D1AA93C175E2DC3A3"


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest().upper()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, path)


def event(name, **fields):
    row = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": name, **fields}
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)


def tree_stats(root):
    file_count = 0
    byte_count = 0
    if not root.exists():
        return file_count, byte_count
    for current, _, filenames in os.walk(root):
        for filename in filenames:
            path = Path(current) / filename
            try:
                if path.is_file():
                    file_count += 1
                    byte_count += path.stat().st_size
            except OSError:
                pass
    return file_count, byte_count


def download_monitor(stop_event, expected_bytes):
    started = time.monotonic()
    while not stop_event.wait(15):
        count, size = tree_stats(MODEL_DIR)
        event(
            "snapshot_download_progress",
            elapsed_seconds=round(time.monotonic() - started, 1),
            files_seen=count,
            bytes_seen=size,
            expected_bytes=expected_bytes,
        )


def save_result():
    write_json(RESULT_PATH, result)


def emit_result():
    print("RUN_RESULT_JSON_BEGIN", flush=True)
    print(RESULT_PATH.read_text(encoding="utf-8"), flush=True)
    print("RUN_RESULT_JSON_END", flush=True)


def answer_values(response, question_id):
    return (response.get("answers") or {}).get(question_id) or {}


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
if not CONTRACT_PATH.is_file():
    raise FileNotFoundError(f"Bootstrap contract is missing: {CONTRACT_PATH}.")
contract_bytes = CONTRACT_PATH.read_bytes()
contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
target = contract["target"]
execution = contract["execution_contract"]
model_id = target["model_id"]
revision = target["release_revision"]
run_id = f"{contract['experiment_id']}-{datetime.now(timezone.utc).strftime('%H%M%S')}Z"

result = {
    "status": "running",
    "phase": "runtime_preflight",
    "run_id": run_id,
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "contract_sha256": sha256_bytes(contract_bytes),
    "model": model_id,
    "revision": revision,
    "gpu": {"requested": execution["gpu_requested"], "actual": None},
    "environment": {
        "colab_cli_version": execution["cli_version"],
        "colab_session": execution["session_name"],
        "colab_runtime_id": execution.get("session_runtime_id"),
        "python": sys.version,
        "platform": platform.platform(),
        "torch": package_version("torch"),
        "transformers": package_version("transformers"),
        "huggingface_hub": package_version("huggingface-hub"),
        "accelerate": package_version("accelerate"),
        "safetensors": package_version("safetensors"),
        "pillow": package_version("pillow"),
        "cuda_runtime": torch.version.cuda,
    },
    "command": (
        f"colab --auth=adc --config {execution['session_config']} exec -s "
        f"{execution['session_name']} -f "
        "experiment/bootstrap_clef.py; "
        "then colab --auth=adc --config "
        f"{execution['session_config']} exec -s {execution['session_name']} "
        "--timeout 1800 -f "
        "experiment/run_clef.py"
    ),
    "inference_path": execution["inference_path"],
    "snapshot_download": {
        "started": False,
        "revision_pinned": revision,
        "expected_file_count": target["snapshot_file_count"],
        "expected_total_bytes": target["snapshot_total_bytes"],
        "local_path": str(MODEL_DIR),
        "download_seconds": None,
        "actual_file_count": None,
        "actual_total_bytes": None,
    },
    "cases": [],
    "model_load_seconds": None,
    "cuda_allocated_bytes_after_load": None,
    "cuda_reserved_bytes_after_load": None,
    "total_wall_seconds": None,
    "error": None,
    "unexecuted_cases": [case["case_id"] for case in contract["cases"]],
}
save_result()
overall_started = time.perf_counter()

try:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable in the allocated Colab runtime.")
    device_properties = torch.cuda.get_device_properties(0)
    result["gpu"].update(
        {
            "actual": device_properties.name,
            "total_memory_bytes": device_properties.total_memory,
            "capability": list(torch.cuda.get_device_capability(0)),
        }
    )
    try:
        import psutil

        memory = psutil.virtual_memory()
        result["environment"]["host_memory_total_bytes"] = memory.total
        result["environment"]["host_memory_available_bytes"] = memory.available
    except Exception:
        pass
    try:
        result["gpu"]["nvidia_smi"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except Exception:
        pass

    image_case = next(case for case in contract["cases"] if case["modality"] == "image")
    image_contract = image_case["input"]["image"]
    if not IMAGE_REMOTE_PATH.is_file():
        raise FileNotFoundError(f"Bootstrap image is missing: {IMAGE_REMOTE_PATH}.")
    source_image_bytes = IMAGE_REMOTE_PATH.read_bytes()
    actual_image_hash = sha256_bytes(source_image_bytes)
    expected_image_hash = image_contract["source_sha256"]
    if actual_image_hash != expected_image_hash:
        raise ValueError(f"Source image hash mismatch: expected {expected_image_hash}, got {actual_image_hash}.")
    with Image.open(io.BytesIO(source_image_bytes)) as source_image:
        source_dimensions = list(source_image.size)
        rgb_image = source_image.convert("RGB")
    max_side = 1024
    resize_scale = min(1.0, max_side / max(rgb_image.size))
    processed_dimensions = [
        max(1, round(rgb_image.width * resize_scale)),
        max(1, round(rgb_image.height * resize_scale)),
    ]
    processed_image = (
        rgb_image.resize(tuple(processed_dimensions), resample=Image.Resampling.LANCZOS)
        if tuple(processed_dimensions) != rgb_image.size
        else rgb_image
    )
    processed_rgb_hash = sha256_bytes(processed_image.tobytes())
    event(
        "image_source_verified_and_preprocessed",
        source_bytes=len(source_image_bytes),
        source_sha256=actual_image_hash,
        source_dimensions=source_dimensions,
        processed_dimensions=processed_dimensions,
        processed_rgb_sha256=processed_rgb_hash,
    )
    result["image_input"] = {
        "remote_path": str(IMAGE_REMOTE_PATH),
        "source_url": image_contract["source"],
        "source_sha256": actual_image_hash,
        "source_bytes": len(source_image_bytes),
        "source_dimensions": source_dimensions,
        "preprocessing": image_contract["preprocessing"],
        "processed_dimensions": processed_dimensions,
        "processed_rgb_sha256": processed_rgb_hash,
    }

    result["phase"] = "snapshot_download"
    result["snapshot_download"]["started"] = True
    save_result()
    event(
        "snapshot_download_started",
        model=model_id,
        revision=revision,
        expected_file_count=target["snapshot_file_count"],
        expected_total_bytes=target["snapshot_total_bytes"],
    )
    monitor_stop = threading.Event()
    monitor_thread = threading.Thread(
        target=download_monitor,
        args=(monitor_stop, target["snapshot_total_bytes"]),
        daemon=True,
    )
    monitor_thread.start()
    download_started = time.perf_counter()
    try:
        model_path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(MODEL_DIR),
            max_workers=4,
            token=False,
        )
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=20)
    result["snapshot_download"]["download_seconds"] = round(time.perf_counter() - download_started, 3)
    result["snapshot_download"]["local_path"] = str(model_path)
    file_count, total_bytes = tree_stats(Path(model_path))
    result["snapshot_download"]["actual_file_count"] = file_count
    result["snapshot_download"]["actual_total_bytes"] = total_bytes
    event(
        "snapshot_download_completed",
        download_seconds=result["snapshot_download"]["download_seconds"],
        files_seen=file_count,
        bytes_seen=total_bytes,
    )

    code_path = Path(model_path) / "joint_schema_model.py"
    actual_code_hash = sha256_file(code_path)
    if actual_code_hash != EXPECTED_SOURCE_HASH:
        raise ValueError(f"Official code SHA-256 mismatch: expected {EXPECTED_SOURCE_HASH}, got {actual_code_hash}.")
    for filename in ("model.safetensors.index.json", "joint_head.safetensors", "joint_head_config.json", "processor_config.json"):
        if not (Path(model_path) / filename).is_file():
            raise FileNotFoundError(f"Pinned snapshot is missing required file: {filename}")
    result["official_source_sha256"] = actual_code_hash

    sys.path.insert(0, str(model_path))
    from joint_schema_model import load_release_model, systemone

    result["phase"] = "load_release_model"
    save_result()
    event("load_release_model_started", dtype="torch.bfloat16 (official function default)", device="cuda")
    load_started = time.perf_counter()
    model, processor = load_release_model(model_path, device="cuda")
    torch.cuda.synchronize()
    result["model_load_seconds"] = round(time.perf_counter() - load_started, 3)
    first_parameter = next(model.parameters())
    result["loaded_model"] = {
        "first_parameter_device": str(first_parameter.device),
        "first_parameter_dtype": str(first_parameter.dtype),
        "all_parameters_cuda": all(parameter.device.type == "cuda" for parameter in model.parameters()),
    }
    result["cuda_allocated_bytes_after_load"] = torch.cuda.memory_allocated(0)
    result["cuda_reserved_bytes_after_load"] = torch.cuda.memory_reserved(0)
    event(
        "load_release_model_completed",
        model_load_seconds=result["model_load_seconds"],
        cuda_allocated_bytes=result["cuda_allocated_bytes_after_load"],
        cuda_reserved_bytes=result["cuda_reserved_bytes_after_load"],
    )
    save_result()

    result["phase"] = "inference"
    for case in contract["cases"]:
        case_id = case["case_id"]
        request_input = case["input"]
        request = {key: copy.deepcopy(request_input[key]) for key in ("model", "state", "questions")}
        stored_input = copy.deepcopy(request)
        opened_image = None
        if case["modality"] == "image":
            opened_image = processed_image.copy()
            request["images"] = [opened_image]
            stored_input["image"] = {
                **request_input["image"],
                "remote_path": str(IMAGE_REMOTE_PATH),
                "source_bytes": len(source_image_bytes),
                "source_dimensions": source_dimensions,
                "processed_dimensions": list(opened_image.size),
                "processed_rgb_sha256": processed_rgb_hash,
            }

        event("systemone_started", case_id=case_id, modality=case["modality"])
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(0)
        case_started = time.perf_counter()
        response = systemone(model, processor, request)
        torch.cuda.synchronize()
        elapsed = round(time.perf_counter() - case_started, 6)
        answers = response.get("answers") or {}

        if case_id == "text-invoice-01":
            status_answer = answer_values(response, "status")
            large_answer = answer_values(response, "large")
            predicted = {
                "status.choice": status_answer.get("choice"),
                "large.noul": large_answer.get("noul"),
            }
            passed = (
                predicted["status.choice"] == case["expected"]["status.choice"]
                and isinstance(predicted["large.noul"], (int, float))
                and predicted["large.noul"] > case["expected"]["large.noul_minimum"]
            )
        else:
            answer = answer_values(response, "hand_holding_candy")
            predicted = {"hand_holding_candy.noul": answer.get("noul")}
            passed = (
                isinstance(predicted["hand_holding_candy.noul"], (int, float))
                and predicted["hand_holding_candy.noul"] > case["expected"]["hand_holding_candy.noul_minimum"]
            )

        case_result = {
            "case_id": case_id,
            "modality": case["modality"],
            "input": stored_input,
            "expected": case["expected"],
            "raw_response": response,
            "predicted": predicted,
            "elapsed_seconds": elapsed,
            "input_tokens": (response.get("usage") or {}).get("input_tokens"),
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(0),
            "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(0),
            "passed": passed,
            "status": "completed",
        }
        result["cases"].append(case_result)
        result["unexecuted_cases"] = [
            pending["case_id"] for pending in contract["cases"] if pending["case_id"] not in {done["case_id"] for done in result["cases"]}
        ]
        write_json(RAW_DIR / f"{case_id}.json", response)
        save_result()
        event(
            "systemone_completed",
            case_id=case_id,
            elapsed_seconds=elapsed,
            input_tokens=case_result["input_tokens"],
            predicted=predicted,
            passed=passed,
            cuda_peak_allocated_bytes=case_result["cuda_peak_allocated_bytes"],
            cuda_peak_reserved_bytes=case_result["cuda_peak_reserved_bytes"],
        )
        if opened_image is not None:
            opened_image.close()

    result["total_wall_seconds"] = round(time.perf_counter() - overall_started, 3)
    result["status"] = "completed"
    result["phase"] = "complete"
    result["outcome"] = "PASS" if all(case["passed"] for case in result["cases"]) else "FAIL"
    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    event("run_completed", outcome=result["outcome"], total_wall_seconds=result["total_wall_seconds"])
    save_result()
    emit_result()
except Exception as exc:
    result["total_wall_seconds"] = round(time.perf_counter() - overall_started, 3)
    result["status"] = "blocked" if not result["cases"] else "error"
    result["phase"] = result.get("phase", "unknown")
    result["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    result["failed_at_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        event("run_error", error_type=type(exc).__name__, message=str(exc), phase=result["phase"])
    except Exception:
        pass
    save_result()
    emit_result()
    raise
