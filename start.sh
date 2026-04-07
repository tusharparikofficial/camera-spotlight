#!/bin/sh
echo "Starting Camera Spotlight on http://localhost:8000"
echo "Press Ctrl+C to stop the server."
echo ""
python3 -m http.server 8000 &
PID=$!
sleep 1
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:8000
elif command -v open >/dev/null 2>&1; then
    open http://localhost:8000
fi
wait $PID
