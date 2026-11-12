#!/data/data/com.termux/files/usr/bin/bash
if [ -f ~/vigia.pid ] && kill -0 "$(cat ~/vigia.pid)" 2>/dev/null; then exit 0; fi
echo $$ > ~/vigia.pid
cd ~/NVR-BOX
vivo() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null && tr '\0' ' ' < /proc/$(cat "$1")/cmdline | grep -q "$2"; }
while true; do
  if ! vivo .run/servidor.pid nvrbox || ! vivo .run/captura.pid nvrbox || ! vivo .run/limpeza.pid nvrbox; then
    nohup bash ./iniciar_nvr.sh >> .run/iniciar.log 2>&1 &
    sleep 30
  fi
  if ! vivo ~/monitoramento/monitor.pid monitor_nvr; then
    nohup python3 ~/NVR-BOX/termux/monitor_nvr_celular.py >> ~/monitoramento/monitor.log 2>&1 &
  fi
  sleep 60
done
