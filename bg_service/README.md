# GPU Background Removal Service

RMBG-1.4 model running on CUDA via ONNX Runtime. Much better quality than MediaPipe Selfie Segmentation.

## Setup (one-time)

```bash
cd bg_service
python3.12 -m venv venv
./venv/bin/pip install websockets onnxruntime-gpu pillow numpy nvidia-cudnn-cu12 nvidia-cublas-cu12

# Download model (168MB)
mkdir -p models
curl -sL -o models/rmbg-1.4.onnx https://huggingface.co/briaai/RMBG-1.4/resolve/main/onnx/model.onnx
```

## Run locally

```bash
./run.sh
# Listens on ws://localhost:8083
```

## Deploy as service

```bash
sudo bash ../setup-bg-service.sh
# Creates systemd service + cloudflared tunnel entry for bg.jarvis.tuxy.online
```

## Protocol

WebSocket binary messages:
- Client → Server: JPEG bytes
- Server → Client: PNG bytes (grayscale mask, white = person, black = background)

## Performance

RTX 3060: ~17 FPS at 1024x1024 (~60ms per frame inference).
Network adds ~30-50ms round-trip. Realistic throughput: 10-15 effective FPS.
