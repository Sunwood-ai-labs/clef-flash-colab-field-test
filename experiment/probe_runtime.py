import importlib.metadata
import json
import platform
import subprocess
import sys


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


result = {
    "python": sys.version,
    "platform": platform.platform(),
    "packages": {
        name: package_version(name)
        for name in ("torch", "transformers", "huggingface-hub", "accelerate", "safetensors", "pillow")
    },
}

try:
    import psutil

    memory = psutil.virtual_memory()
    result["host_memory"] = {
        "total_bytes": memory.total,
        "available_bytes": memory.available,
    }
except Exception as exc:
    result["host_memory_error"] = f"{type(exc).__name__}: {exc}"

try:
    import torch

    result["torch_cuda"] = {
        "torch_cuda_version": torch.version.cuda,
        "available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        result["torch_cuda"].update(
            {
                "device_name": props.name,
                "total_memory_bytes": props.total_memory,
                "capability": list(torch.cuda.get_device_capability(0)),
            }
        )
except Exception as exc:
    result["torch_cuda_error"] = f"{type(exc).__name__}: {exc}"

try:
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

    result["transformers_model_classes"] = {
        "AutoProcessor": AutoProcessor.__name__,
        "Qwen3_5ForConditionalGeneration": Qwen3_5ForConditionalGeneration.__name__,
    }
except Exception as exc:
    result["transformers_model_classes_error"] = f"{type(exc).__name__}: {exc}"

try:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,driver_version",
            "--format=csv,noheader",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    result["nvidia_smi_exit_code"] = completed.returncode
    result["nvidia_smi_stdout"] = completed.stdout.strip()
    if completed.stderr.strip():
        result["nvidia_smi_stderr"] = completed.stderr.strip()
except Exception as exc:
    result["nvidia_smi_error"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(result, indent=2, sort_keys=True))
