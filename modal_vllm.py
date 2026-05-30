import os
import shlex
import subprocess

import modal

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv()


APP_NAME = os.getenv("MODAL_APP_NAME", "agentic-red-team-vllm")
MODEL_NAME = os.getenv("MODAL_MODEL_NAME", "Qwen/Qwen3.5-9B")
MODEL_REVISION = os.getenv("MODAL_MODEL_REVISION", "")
SERVED_MODEL_NAME = os.getenv("MODAL_SERVED_MODEL_NAME", "qwen3.5-9b")
GPU = os.getenv("MODAL_GPU", "L40S")
MAX_MODEL_LEN = os.getenv("MODAL_MAX_MODEL_LEN", "4096")
GPU_MEMORY_UTILIZATION = os.getenv("MODAL_GPU_MEMORY_UTILIZATION", "0.90")
DTYPE = os.getenv("MODAL_DTYPE", "auto")
QUANTIZATION = os.getenv("MODAL_QUANTIZATION", "")
VLLM_VERSION = os.getenv("MODAL_VLLM_VERSION", "0.21.0")
REQUIRE_PROXY_AUTH = os.getenv("MODAL_REQUIRE_PROXY_AUTH", "1") != "0"
VLLM_API_KEY = os.getenv("MODAL_VLLM_API_KEY", "")
TRUST_REMOTE_CODE = os.getenv("MODAL_TRUST_REMOTE_CODE", "0") == "1"
HF_SECRET_NAME = os.getenv("MODAL_HF_SECRET_NAME", "")
EXTRA_VLLM_ARGS = os.getenv("MODAL_EXTRA_VLLM_ARGS", "")

MINUTES = 60
VLLM_PORT = 8000


def _gpu_count(gpu_spec: str) -> str:
    if ":" not in gpu_spec:
        return "1"
    return gpu_spec.rsplit(":", 1)[1]


TENSOR_PARALLEL_SIZE = os.getenv("MODAL_TENSOR_PARALLEL_SIZE", _gpu_count(GPU))

RUNTIME_ENV = {
    "MODAL_MODEL_NAME": MODEL_NAME,
    "MODAL_MODEL_REVISION": MODEL_REVISION,
    "MODAL_SERVED_MODEL_NAME": SERVED_MODEL_NAME,
    "MODAL_GPU": GPU,
    "MODAL_MAX_MODEL_LEN": MAX_MODEL_LEN,
    "MODAL_GPU_MEMORY_UTILIZATION": GPU_MEMORY_UTILIZATION,
    "MODAL_DTYPE": DTYPE,
    "MODAL_QUANTIZATION": QUANTIZATION,
    "MODAL_VLLM_VERSION": VLLM_VERSION,
    "MODAL_TRUST_REMOTE_CODE": "1" if TRUST_REMOTE_CODE else "0",
    "MODAL_EXTRA_VLLM_ARGS": EXTRA_VLLM_ARGS,
    "MODAL_TENSOR_PARALLEL_SIZE": TENSOR_PARALLEL_SIZE,
}


vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}", "openai>=1.76.0")
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VLLM_LOG_STATS_INTERVAL": "1",
            **RUNTIME_ENV,
        }
    )
)

hf_cache_vol = modal.Volume.from_name("agentic-red-team-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("agentic-red-team-vllm-cache", create_if_missing=True)
secrets = [modal.Secret.from_name(HF_SECRET_NAME)] if HF_SECRET_NAME else []
if VLLM_API_KEY:
    secrets.append(modal.Secret.from_dict({"MODAL_VLLM_API_KEY": VLLM_API_KEY}))

app = modal.App(APP_NAME)


def _modal_proxy_headers() -> dict[str, str]:
    token_id = os.getenv("MODAL_PROXY_TOKEN_ID") or os.getenv("MODAL_KEY")
    token_secret = os.getenv("MODAL_PROXY_TOKEN_SECRET") or os.getenv("MODAL_SECRET")
    if token_id and token_secret:
        return {"Modal-Key": token_id, "Modal-Secret": token_secret}
    return {}


@app.function(
    image=vllm_image,
    gpu=GPU,
    timeout=15 * MINUTES,
    scaledown_window=15 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=secrets,
)
@modal.concurrent(max_inputs=20)
@modal.web_server(
    port=VLLM_PORT,
    startup_timeout=15 * MINUTES,
    requires_proxy_auth=REQUIRE_PROXY_AUTH,
)
def serve():
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--host",
        "0.0.0.0",
        "--port",
        str(VLLM_PORT),
        "--max-model-len",
        MAX_MODEL_LEN,
        "--gpu-memory-utilization",
        GPU_MEMORY_UTILIZATION,
        "--dtype",
        DTYPE,
        "--tensor-parallel-size",
        TENSOR_PARALLEL_SIZE,
        "--uvicorn-log-level",
        "info",
    ]

    if MODEL_REVISION:
        cmd += ["--revision", MODEL_REVISION]
    if QUANTIZATION:
        cmd += ["--quantization", QUANTIZATION]
    if VLLM_API_KEY:
        cmd += ["--api-key", VLLM_API_KEY]
    if TRUST_REMOTE_CODE:
        cmd += ["--trust-remote-code"]
    if EXTRA_VLLM_ARGS:
        cmd += shlex.split(EXTRA_VLLM_ARGS)

    printable_cmd = ["<redacted>" if item == VLLM_API_KEY else item for item in cmd]
    print("Starting vLLM:", " ".join(printable_cmd))
    subprocess.Popen(cmd)


@app.local_entrypoint()
async def test(prompt: str = "Reply with READY in one short sentence."):
    url = await serve.get_web_url.aio()
    print(f"Configured HF model: {MODEL_NAME}")
    print(f"Configured GPU: {GPU}")
    print(f"Modal vLLM URL: {url}")
    print(f"OpenAI-compatible base URL: {url.rstrip('/')}/v1")
    print(f"Served model name: {SERVED_MODEL_NAME}")

    headers = _modal_proxy_headers()
    if REQUIRE_PROXY_AUTH and not headers:
        print(
            "Skipping chat smoke test because proxy auth is enabled. "
            "Set MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET, then rerun."
        )
        return

    from openai import OpenAI

    client = OpenAI(
        base_url=f"{url.rstrip('/')}/v1",
        api_key=VLLM_API_KEY or "EMPTY",
        default_headers=headers,
        timeout=120,
    )
    response = client.chat.completions.create(
        model=SERVED_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
    )
    print("Smoke test response:")
    print(response.choices[0].message.content)
