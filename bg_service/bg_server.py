#!/usr/bin/env python3
"""
GPU-accelerated background removal WebSocket service.

Uses BRIA RMBG-1.4 (state-of-the-art) via ONNX Runtime with CUDA.
Accepts JPEG frames over WebSocket, returns PNG mask (single alpha channel).

Protocol:
  - Client sends binary JPEG image frame
  - Server returns binary PNG with grayscale mask (white=person, black=bg)
  - Single connection per client, frames processed one at a time
"""
import asyncio
import io
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import websockets
from PIL import Image

HERE = Path(__file__).parent
MODEL_PATH = HERE / "models" / "rmbg-1.4.onnx"
HOST = os.environ.get("BG_HOST", "0.0.0.0")
PORT = int(os.environ.get("BG_PORT", "8083"))
MODEL_SIZE = 1024  # RMBG-1.4 expects 1024x1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bg_server")


def load_model():
    providers = [
        ("CUDAExecutionProvider", {"device_id": 0}),
        "CPUExecutionProvider",
    ]
    sess_opts = ort.SessionOptions()
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess = ort.InferenceSession(str(MODEL_PATH), sess_options=sess_opts, providers=providers)
    log.info("Model loaded with providers: %s", sess.get_providers())
    # Warm up
    dummy = np.zeros((1, 3, MODEL_SIZE, MODEL_SIZE), dtype=np.float32)
    for _ in range(3):
        sess.run(None, {"input": dummy})
    log.info("Model warmed up")
    return sess


def preprocess(img: Image.Image) -> tuple[np.ndarray, tuple[int, int]]:
    """Resize to 1024x1024, normalize to float32 CHW."""
    orig_size = img.size  # (w, h)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img_resized = img.resize((MODEL_SIZE, MODEL_SIZE), Image.BILINEAR)
    arr = np.array(img_resized, dtype=np.float32) / 255.0
    # RMBG-1.4 expects normalization
    arr = (arr - 0.5) / 1.0
    arr = arr.transpose(2, 0, 1)  # HWC -> CHW
    arr = arr[None, ...]  # add batch dim
    return arr, orig_size


def postprocess(mask: np.ndarray, orig_size: tuple[int, int]) -> bytes:
    """Convert 1024x1024 mask output to RGBA PNG where alpha = mask value.

    Canvas API requires actual alpha channel for source-in compositing to work.
    A grayscale PNG has alpha=255 everywhere (opaque black/white), which
    breaks source-in. So we encode the mask into the alpha channel of white
    RGBA pixels: where mask is high, alpha=255 (keep video); where low,
    alpha=0 (transparent).
    """
    m = mask[0, 0]
    m = (m - m.min()) / max(m.max() - m.min(), 1e-8)
    m = (m * 255).clip(0, 255).astype(np.uint8)

    h, w = m.shape
    # Build RGBA: RGB=white, A=mask
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 255  # R
    rgba[..., 1] = 255  # G
    rgba[..., 2] = 255  # B
    rgba[..., 3] = m    # A = mask

    pil = Image.fromarray(rgba, mode="RGBA").resize(orig_size, Image.BILINEAR)
    buf = io.BytesIO()
    pil.save(buf, format="PNG", optimize=False, compress_level=1)
    return buf.getvalue()


async def handle_client(ws, sess):
    peer = ws.remote_address
    log.info("Client connected: %s", peer)
    frame_count = 0
    start = time.time()
    try:
        async for msg in ws:
            if isinstance(msg, str):
                # Ignore text frames (e.g. ping)
                continue
            t0 = time.time()
            try:
                img = Image.open(io.BytesIO(msg))
                arr, orig_size = preprocess(img)
                out = sess.run(None, {"input": arr})
                mask_png = postprocess(out[0], orig_size)
                await ws.send(mask_png)
                frame_count += 1
                dt = time.time() - t0
                if frame_count % 30 == 0:
                    avg_fps = frame_count / (time.time() - start)
                    log.info("Client %s: %d frames, %.1fms last, %.1f avg FPS",
                            peer, frame_count, dt * 1000, avg_fps)
            except Exception as e:
                log.warning("Frame processing error: %s", e)
                # Send empty response so client can continue
                try:
                    await ws.send(b"")
                except Exception:
                    break
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        log.error("Client handler error: %s", e)
    finally:
        log.info("Client disconnected: %s (%d frames in %.1fs)",
                 peer, frame_count, time.time() - start)


async def main():
    if not MODEL_PATH.exists():
        log.error("Model not found at %s", MODEL_PATH)
        sys.exit(1)

    sess = load_model()

    # Use closure to pass sess
    async def handler(ws):
        await handle_client(ws, sess)

    log.info("Listening on ws://%s:%d", HOST, PORT)
    async with websockets.serve(
        handler, HOST, PORT,
        max_size=16 * 1024 * 1024,  # 16MB max frame
        ping_interval=20, ping_timeout=60,
    ):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
