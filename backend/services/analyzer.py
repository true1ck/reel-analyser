"""
Vision analysis service — wraps Qwen2.5-VL or NVIDIA NIM API.
Supports MLX (Mac), Transformers (Windows), and NVIDIA API (Cloud).
"""
from __future__ import annotations
import sys
import os
import json
import base64
import requests
import httpx
import asyncio
import importlib.util
from pathlib import Path

from qwen_vl_utils import process_vision_info
from backend.config import (
    VISION_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    REPETITION_PENALTY,
    VIDEO_FPS,
    MAX_PIXELS,
    USE_NVIDIA_API,
    NVIDIA_API_KEY,
)

# Detect if MLX is available
MLX_AVAILABLE = importlib.util.find_spec("mlx") is not None

if not USE_NVIDIA_API:
    if MLX_AVAILABLE:
        from mlx_vlm import load, generate
    else:
        import torch
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor


# ─── GLOBAL MODEL (loaded once, reused across all jobs) ──────────────────────
_model = None
_processor = None


def get_model():
    """Lazy-load and cache the vision model based on platform."""
    if USE_NVIDIA_API:
        return None, None # API doesn't need local loading

    global _model, _processor
    if _model is None:
        print(f"[->] Loading {VISION_MODEL}...")
        
        if MLX_AVAILABLE:
            _model, _processor = load(VISION_MODEL)
            print(f"[OK] Model loaded using MLX")
        else:
            # Windows / Linux / CUDA / CPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            load_kwargs = {
                "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
                "device_map": "auto",
            }
            if device == "cuda":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                VISION_MODEL, **load_kwargs
            )
            _processor = AutoProcessor.from_pretrained(VISION_MODEL)
            print(f"[OK] Model loaded using Transformers on {device}")
            
    return _model, _processor


ANALYSIS_PROMPT = """You are an absolute expert video analyst and meticulous note-taker. I am providing you with an educational/tutorial Instagram Reel video file and its audio transcript. 

If the transcript is in Hindi, Urdu, or another language, TRANSLATE it mentally and write your final notes ENTIRELY IN ENGLISH.

Reel title/metadata: {title}{transcript_section}

Please provide a highly practical, step-by-step breakdown of the tutorial so the user does NOT have to watch the video again.

You MUST use exactly this Markdown structure:

### 🗣️ English Transcript Translation
- Provide a full, clean English translation of the spoken audio transcript.

### 🛠️ Tools & Resources Mentioned
- List all software, websites, AI tools, or plugins shown or spoken about (e.g., Playwright, Claude, MCP, specific folders).

### 🪜 Exact Step-by-Step Tutorial
1. **[Action Name]**: Detailed explanation of the action. (e.g., "Install Playwright MCP inside Claude", "Open the Reference Folder").
2. **[Action Name]**: ...
(Make sure to chronologically list every single action the creator takes or instructs the viewer to take).

### 💻 Prompts / Code Used
- Write out any specific text prompts, commands, or code snippets the creator pastes or types in the video.

### 💡 Key Notes & Takeaways
- Any important warnings, background contexts, or tips the creator shares to make it work.

Be precise, highly specific, and output only the required markdown structure."""


async def analyze_video_via_api(transcript: str, title: str) -> str:
    """Analyze video using NVIDIA NIM API with robust error handling."""
    print(f"[->] Analyzing via NVIDIA API ({VISION_MODEL})...")
    
    # Try different possible NIM endpoints
    endpoints = [
        "https://integrate.api.nvidia.com/v1/chat/completions",
        "https://ai.api.nvidia.com/v1/chat/completions"
    ]
    
    transcript_section = (
        f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
    )
    prompt_text = ANALYSIS_PROMPT.format(
        title=title, transcript_section=transcript_section
    )
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": 1.0,
    }
    
    # No additional payload params for now

    for url in endpoints:
        try:
            print(f"    Trying cloud endpoint: {url}...")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
            if response.status_code == 200:
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"]
                if not content:
                    print(f"    [WARN] API returned empty content for {url}")
                else:
                    print(f"    [OK] Analysis successful ({len(content)} chars)")
                return content
            else:
                print(f"    [!] API Error {response.status_code} from {url}: {response.text}")
        except Exception as e:
            print(f"    Connection error with {url}: {e}")
            
    return f"API Error: Failed to connect to any NVIDIA endpoint."


def analyze_video(video_path: Path, transcript: str, title: str) -> str:
    """
    Analyze a video file with API attempt and local fallback.
    """
    if USE_NVIDIA_API:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(analyze_video_via_api(transcript, title))
            else:
                return asyncio.run(analyze_video_via_api(transcript, title))
        except Exception as e:
            print(f"[WARN] NVIDIA Vision API Failed: {e}. Falling back to local...")

    # Local fallback
    model, processor = get_model()

    transcript_section = (
        f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
    )
    prompt_text = ANALYSIS_PROMPT.format(
        title=title, transcript_section=transcript_section
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": str(video_path.absolute()) if not MLX_AVAILABLE else f"file://{video_path.absolute()}",
                    "max_pixels": MAX_PIXELS,
                    "fps": VIDEO_FPS,
                },
                {"type": "text", "text": prompt_text},
            ],
        }
    ]

    if MLX_AVAILABLE:
        # MLX Vision Pipeline
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        output = generate(
            model=model,
            processor=processor,
            prompt=text,
            images=image_inputs,
            videos=video_inputs,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            repetition_penalty=REPETITION_PENALTY,
            verbose=False,
        )
        return output
    else:
        # Transformers Vision Pipeline
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        generated_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            do_sample=True if TEMPERATURE > 0 else False,
        )
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return output_text[0]
