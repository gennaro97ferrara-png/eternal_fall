#!/bin/bash
pkill -9 -x Xorg 2>/dev/null; sleep 1
rm -f /tmp/.X11-unix/X0 /tmp/.X0-lock 2>/dev/null
exec Xorg :0 -config /etc/X11/xorg-4k.conf -noreset -novtswitch -sharevts -nolisten tcp
