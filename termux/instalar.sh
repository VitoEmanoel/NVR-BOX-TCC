#!/data/data/com.termux/files/usr/bin/bash
mkdir -p ~/.termux/boot ~/monitoramento
cp ~/NVR-BOX/termux/boot_nvrbox.sh ~/.termux/boot/nvrbox.sh
chmod +x ~/.termux/boot/nvrbox.sh ~/NVR-BOX/termux/*.sh
echo "Instalado. Reinicie o celular ou rode: nohup bash ~/NVR-BOX/termux/vigia_nvr.sh > ~/vigia.log 2>&1 &"
