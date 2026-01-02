# Computer Use Agent - Docker Environment
# Ubuntu 22.04 with Xvfb, Firefox, and automation tools

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up display environment
ENV DISPLAY=:1
ENV DISPLAY_WIDTH=1024
ENV DISPLAY_HEIGHT=768

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # X11 virtual framebuffer
    xvfb \
    # Window manager
    fluxbox \
    # VNC server for optional live viewing
    x11vnc \
    # Browser
    firefox \
    # Automation tools
    xdotool \
    # Screenshot utilities
    scrot \
    imagemagick \
    # Fonts
    fonts-liberation \
    fonts-dejavu \
    # Utilities
    curl \
    wget \
    ca-certificates \
    dbus-x11 \
    # Python (for running scripts inside container if needed)
    python3 \
    python3-pip \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for running the browser
RUN useradd -m -s /bin/bash agent && \
    mkdir -p /home/agent/.config/firefox && \
    mkdir -p /home/agent/.fluxbox && \
    chown -R agent:agent /home/agent

# Set up working directory
WORKDIR /home/agent

# Copy startup script with execute permissions
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/

# Copy Fluxbox menu configuration
COPY --chown=agent:agent fluxbox-menu /home/agent/.fluxbox/menu

# Switch to non-root user
USER agent

# Expose VNC port for optional live viewing
EXPOSE 5900

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD xdotool getactivewindow || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
