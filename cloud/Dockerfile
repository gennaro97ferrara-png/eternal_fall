# Eternal Fall — immagine cloud "tutto-in-uno":
#   Chromium GPU (WebGL hardware) + PulseAudio + ffmpeg NVENC + server.js
# Pensata per un host con GPU NVIDIA (es. Hetzner GEX44, RTX 4000 SFF Ada) e
# nvidia-container-toolkit. I file del progetto NON sono copiati nell'immagine:
# vengono montati a runtime in /app (vedi docker-compose.yml), così aggiorni la
# live con un semplice rsync senza ricostruire l'immagine.
# Base Ubuntu liscia: non serve CUDA (usiamo solo NVENC + WebGL via driver).
# nvidia-container-toolkit inietta driver/NVENC/EGL/Vulkan a runtime in base a
# NVIDIA_DRIVER_CAPABILITIES, qualunque sia l'immagine base.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all

# --- base + X virtuale + audio + Node (per server.js) + Vulkan/EGL ---
# NOTA GPU/WebGL: il nvidia-container-toolkit inietta a runtime SOLO le librerie
# *vendor* del driver (libEGL_nvidia, libGLX_nvidia, libnvidia-*). NON inietta i
# loader GLVND vendor-neutral (libEGL.so.1, libGLdispatch.so.0, libOpenGL.so.0,
# libGLX.so.0) né i loader Vulkan/EGL generici: quelli DEVONO stare nell'immagine,
# altrimenti ANGLE gl-egl/EGL non trova nulla e va in segfault o cade in software.
#   - libglvnd0      → libGLdispatch.so.0  (il dispatcher su cui si appoggia tutto)
#   - libopengl0     → libOpenGL.so.0
#   - libegl1        → libEGL.so.1         (loader EGL che legge gli ICD egl_vendor.d)
#   - libgles2       → libGLESv2.so.2      (ANGLE espone GLES → serve il loader)
#   - libglx0        → libGLX.so.0
#   - libvulkan1     → loader Vulkan (legge gli ICD in vulkan/icd.d)
#   - libgbm1/libglx-mesa0 → backend Mesa di scorta (display/EGL surfaceless)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg xz-utils coreutils \
      xvfb x11-utils x11-xserver-utils \
      pulseaudio pulseaudio-utils \
      libvulkan1 vulkan-tools mesa-vulkan-drivers \
      libglvnd0 libopengl0 libegl1 libgles2 libglx0 libgl1 libglu1-mesa \
      libglx-mesa0 libgbm1 mesa-utils \
      fonts-liberation fonts-noto-color-emoji \
      nodejs \
      procps psmisc tini \
    && rm -rf /var/lib/apt/lists/*

# --- ICD di scorta EGL/Vulkan (idempotenti) ---
# Il toolkit DOVREBBE iniettare /usr/share/glvnd/egl_vendor.d/10_nvidia.json e
# /usr/share/vulkan/icd.d/nvidia_icd.json quando la capability "graphics" è attiva
# (NVIDIA_DRIVER_CAPABILITIES include graphics+display). Su molte VM/driver però
# NON lo fa (è il bug storico nvidia-docker#1520 / toolkit#16): la lib vendor c'è,
# ma manca il JSON che dice a libglvnd/Vulkan dove trovarla → fallback software.
# Mettiamo i JSON in /etc/...: ha PRIORITÀ su /usr/share/ nel search-path glvnd e
# non collide con un eventuale file iniettato dal toolkit in /usr/share/.
# Il library_path è solo il SONAME: lo risolve il dynamic linker tra le lib del
# driver montate dal toolkit a runtime; non hard-codiamo percorsi del driver.
RUN install -d /etc/glvnd/egl_vendor.d /etc/vulkan/icd.d && \
    printf '%s\n' \
      '{' \
      '    "file_format_version" : "1.0.0",' \
      '    "ICD" : {' \
      '        "library_path" : "libEGL_nvidia.so.0"' \
      '    }' \
      '}' > /etc/glvnd/egl_vendor.d/10_nvidia.json && \
    printf '%s\n' \
      '{' \
      '    "file_format_version" : "1.0.0",' \
      '    "ICD": {' \
      '        "library_path": "libGLX_nvidia.so.0",' \
      '        "api_version" : "1.3.0"' \
      '    }' \
      '}' > /etc/vulkan/icd.d/nvidia_icd.json

# --- Google Chrome stable (stessi flag di Chromium: --use-angle, --headless=new) ---
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -f /tmp/chrome.deb && rm -rf /var/lib/apt/lists/*

# --- ffmpeg con NVENC dai pacchetti Ubuntu ---
# La versione NVENC dell'ffmpeg di Ubuntu è allineata ai driver NVIDIA stabili
# (535/550/560…); i build "master" di BtbN richiedono invece driver troppo nuovi (610+).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_nvenc && echo "ffmpeg con NVENC OK"

# --- Piano B (4K60 fluido): Xorg+NVIDIA headless + gpu-screen-recorder (cattura NvFBC) ---
# nvidia_drv.so e libnvidia-fbc sono iniettati dal toolkit a runtime; qui serve solo
# il binario Xorg e il permesso per root di avviarlo dentro un container.
RUN apt-get update && apt-get install -y --no-install-recommends \
      xserver-xorg-core xserver-xorg-legacy x11-xkb-utils xkb-data xauth \
    && printf 'allowed_users=anybody\nneeds_root_rights=yes\n' > /etc/X11/Xwrapper.config \
    && rm -rf /var/lib/apt/lists/*

# build di gpu-screen-recorder (NvFBC→NVENC, CPU quasi a zero). NON bloccante: se la
# build fallisce l'immagine si crea lo stesso e l'entrypoint usa il fallback ffmpeg.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates meson ninja-build gcc g++ pkg-config \
      libx11-dev libxcomposite-dev libxrandr-dev libxfixes-dev libxdamage-dev \
      libwayland-dev wayland-protocols libpulse-dev libva-dev libcap-dev libdrm-dev \
      libavcodec-dev libavformat-dev libavutil-dev libswresample-dev libavfilter-dev \
      libglvnd-dev libpipewire-0.3-dev cmake libdbus-1-dev libvulkan-dev \
    ; ( git clone --depth 1 https://repo.dec05eba.com/gpu-screen-recorder /tmp/gsr \
        && sed -i "s/if(geteuid() == 0)/if(0)/" /tmp/gsr/src/main.cpp \
        && cd /tmp/gsr && ./install.sh ) || echo "GSR build FALLITA → fallback ffmpeg" \
    ; rm -rf /tmp/gsr /var/lib/apt/lists/* ; true

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app
EXPOSE 8099
# tini fa da init (reaping zombie); entrypoint orchestra e supervisiona i processi
ENTRYPOINT ["/usr/bin/tini","--","/usr/local/bin/entrypoint.sh"]
