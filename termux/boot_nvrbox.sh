#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
sshd
nohup bash ~/NVR-BOX/termux/vigia_nvr.sh > ~/vigia.log 2>&1 &
