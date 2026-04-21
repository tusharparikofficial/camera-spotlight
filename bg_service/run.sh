#!/bin/bash
# Wrapper that sets up LD_LIBRARY_PATH for pip-installed CUDA libs
cd "$(dirname "$0")"
VENV=./venv
SITE=$VENV/lib/python3.12/site-packages
export LD_LIBRARY_PATH="$SITE/nvidia/cudnn/lib:$SITE/nvidia/cublas/lib:$SITE/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH}"
exec $VENV/bin/python bg_server.py "$@"
