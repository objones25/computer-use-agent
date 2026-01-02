#!/bin/bash
set -e

# Start Xvfb (X Virtual Framebuffer)
echo "Starting Xvfb on display :1..."
Xvfb :1 -screen 0 ${DISPLAY_WIDTH:-1024}x${DISPLAY_HEIGHT:-768}x24 &
XVFB_PID=$!

# Wait for Xvfb to start
sleep 2

# Start Fluxbox window manager
echo "Starting Fluxbox window manager..."
fluxbox &
FLUXBOX_PID=$!

# Wait for window manager
sleep 1

# Optionally start VNC server for live viewing
if [ "${ENABLE_VNC:-false}" = "true" ]; then
    echo "Starting VNC server on port 5900..."
    x11vnc -display :1 -forever -shared -rfbport 5900 -nopw &
    VNC_PID=$!
fi

echo "Desktop environment ready!"
echo "Display: $DISPLAY"
echo "Resolution: ${DISPLAY_WIDTH:-1024}x${DISPLAY_HEIGHT:-768}"

# Keep container running and handle signals
cleanup() {
    echo "Shutting down..."
    [ -n "$VNC_PID" ] && kill $VNC_PID 2>/dev/null
    [ -n "$FLUXBOX_PID" ] && kill $FLUXBOX_PID 2>/dev/null
    [ -n "$XVFB_PID" ] && kill $XVFB_PID 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# If a command was passed, execute it
if [ $# -gt 0 ]; then
    exec "$@"
else
    # Otherwise, keep container running
    echo "Container ready. Waiting for commands..."
    wait $XVFB_PID
fi
