"""Modal GPU specialist — private. Not a public HTTP API.

Deploy:
  modal deploy src/underprice/modal/gpu_pricer.py

Web/CPU image must never import torch; Ensemble calls price_one via Modal .remote().
"""

from __future__ import annotations

import os
import re

import modal

app = modal.App("underprice")

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "transformers",
        "peft",
        "bitsandbytes",
        "accelerate",
        "huggingface-hub",
        "sentencepiece",
        "protobuf",
    )
)

MODEL_STATE: dict = {}

_DEFAULT_PROMPT = (
    "What does this cost to the nearest dollar?\n\n"
    "Sony WH-1000XM5\n\n"
    "Price is $"
)


def _parse_price(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d{1,2})?)", text.replace(",", ""))
    if not match:
        raise ValueError(f"no price in model output: {text!r}")
    value = float(match.group(1))
    return max(1.0, min(999.0, value))


@app.function(
    image=gpu_image,
    gpu="T4",
    timeout=600,
    secrets=[modal.Secret.from_name("underprice-secrets")],
    scaledown_window=60,
)
def price_one(prompt: str) -> float:
    """Run list-price completion for one prompt. Scale-to-zero (no min containers)."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    base = os.environ.get("UNDERPRICE_BASE_MODEL", "meta-llama/Llama-3.2-3B")
    adapter = os.environ.get("UNDERPRICE_ADAPTER_ID", "benifa/list-price-qlora")
    revision = os.environ.get("UNDERPRICE_ADAPTER_REVISION", "v0.1.0")

    if "model" not in MODEL_STATE:
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        )
        tok = AutoTokenizer.from_pretrained(base)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            base,
            quantization_config=quant,
            device_map="auto",
        )
        model = PeftModel.from_pretrained(model, adapter, revision=revision)
        model.eval()
        MODEL_STATE["model"] = model
        MODEL_STATE["tok"] = tok

    model = MODEL_STATE["model"]
    tok = MODEL_STATE["tok"]
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=8,
            do_sample=False,
            pad_token_id=tok.eos_token_id,
        )
    completion = tok.decode(out[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
    return _parse_price(completion)


@app.function(
    image=gpu_image,
    gpu="T4",
    timeout=900,
    secrets=[modal.Secret.from_name("underprice-secrets")],
    scaledown_window=60,
)
def price_batch(prompts: list[str]) -> list[float]:
    return [price_one.local(p) for p in prompts]


@app.local_entrypoint()
def main(prompt: str = _DEFAULT_PROMPT) -> None:
    print(price_one.remote(prompt))
