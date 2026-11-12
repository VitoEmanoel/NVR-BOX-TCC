
import ipaddress
import re
import socket
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ARQUIVO_ARP = "/proc/net/arp"
ARP_FLAG_COMPLETA = 0x2
MAC_REGEX = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
MACS_INVALIDOS = {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}
PORTA_RTSP_PADRAO = 554
PORTA_ONVIF = 5000
CAMINHOS_ONVIF = ("/onvif/device_service", "/onvif/device_service/")
ENVELOPE_ONVIF = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body>'
    '<GetNetworkInterfaces xmlns="http://www.onvif.org/ver10/device/wsdl"/>'
    '</s:Body></s:Envelope>'
)
HWADDRESS_REGEX = re.compile(r"HwAddress[^>]*>\s*([0-9a-fA-F:-]{17})\s*<")


def normalizar_mac(mac):
    mac = (mac or "").strip().lower().replace("-", ":")
    if not MAC_REGEX.match(mac) or mac in MACS_INVALIDOS:
        return None
    return mac


def _ler_proc_arp():
    tabela = {}
    with open(ARQUIVO_ARP, "r", encoding="utf-8") as arquivo:
        linhas = arquivo.readlines()[1:]
    for linha in linhas:
        partes = linha.split()
        if len(partes) < 4:
            continue
        try:
            completa = int(partes[2], 16) & ARP_FLAG_COMPLETA
        except ValueError:
            continue
        mac = normalizar_mac(partes[3])
        if completa and mac:
            tabela[partes[0]] = mac
    return tabela


def _ler_ip_neigh():
    saida = subprocess.run(
        ["ip", "-4", "neigh", "show"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=5,
        check=True,
    ).stdout
    tabela = {}
    for linha in saida.splitlines():
        partes = linha.split()
        if "lladdr" not in partes or partes[-1] in {"FAILED", "INCOMPLETE"}:
            continue
        mac = normalizar_mac(partes[partes.index("lladdr") + 1])
        if mac:
            tabela[partes[0]] = mac
    return tabela


def ler_tabela_arp():
    try:
        return _ler_proc_arp()
    except OSError:
        pass
    try:
        return _ler_ip_neigh()
    except (OSError, subprocess.SubprocessError):
        return None


def tocar_host(ip, porta=PORTA_RTSP_PADRAO, timeout=0.5):
    try:
        with socket.create_connection((ip, porta), timeout=timeout):
            return True
    except OSError:
        return False


def mac_pelo_onvif(ip, porta=PORTA_ONVIF, timeout=3):
    for caminho in CAMINHOS_ONVIF:
        pedido = urllib.request.Request(
            f"http://{ip}:{porta}{caminho}",
            ENVELOPE_ONVIF.encode("utf-8"),
            {"Content-Type": "application/soap+xml"},
        )
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                texto = resposta.read(65536).decode("utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        achado = HWADDRESS_REGEX.search(texto)
        mac = normalizar_mac(achado.group(1)) if achado else None
        if mac:
            return mac
    return None


def varrer_rede(ip_referencia, porta=PORTA_RTSP_PADRAO, timeout=1.5, workers=64, espera_final=1.0):
    try:
        rede = ipaddress.ip_network(f"{ip_referencia}/24", strict=False)
    except ValueError:
        return ler_tabela_arp()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        enderecos = [str(ip) for ip in rede.hosts()]
        respostas = list(executor.map(lambda ip: tocar_host(ip, porta, timeout), enderecos))
        time.sleep(espera_final)
        tabela = ler_tabela_arp()
        if tabela is not None:
            return tabela
        abertos = [ip for ip, aberto in zip(enderecos, respostas) if aberto]
        macs = list(executor.map(mac_pelo_onvif, abertos))
    return {ip: mac for ip, mac in zip(abertos, macs) if mac}


def mac_do_ip(ip, porta=PORTA_RTSP_PADRAO, ler_arp=ler_tabela_arp, tocar=tocar_host, mac_onvif=mac_pelo_onvif):
    tabela = ler_arp()
    if tabela is None:
        return mac_onvif(ip)
    if ip not in tabela:
        tocar(ip, porta)
        tabela = ler_arp() or {}
    return tabela.get(ip)


def localizar_camera(mac, ip_atual, porta=PORTA_RTSP_PADRAO,
                     ler_arp=ler_tabela_arp, tocar=tocar_host, varrer=varrer_rede,
                     mac_onvif=mac_pelo_onvif):
    mac = normalizar_mac(mac)
    if not mac:
        return ip_atual, "sem_verificacao"
    tabela = ler_arp()
    if tabela is None:
        return _localizar_sem_arp(mac, ip_atual, porta, varrer, mac_onvif)

    if ip_atual not in tabela:
        tocar(ip_atual, porta)
        tabela = ler_arp() or {}
    if tabela.get(ip_atual) == mac:
        return ip_atual, "confirmada"

    for ip, mac_encontrado in tabela.items():
        if mac_encontrado == mac:
            return ip, "mudou"

    tabela = varrer(ip_atual, porta) or {}
    for ip, mac_encontrado in tabela.items():
        if mac_encontrado == mac:
            return ip, ("confirmada" if ip == ip_atual else "mudou")
    return None, "nao_encontrada"


def _localizar_sem_arp(mac, ip_atual, porta, varrer, mac_onvif):
    mac_no_ip = mac_onvif(ip_atual)
    if mac_no_ip == mac:
        return ip_atual, "confirmada"
    tabela = varrer(ip_atual, porta) or {}
    for ip, mac_encontrado in tabela.items():
        if mac_encontrado == mac:
            return ip, ("confirmada" if ip == ip_atual else "mudou")
    if mac_no_ip is None and not tabela:
        return ip_atual, "sem_verificacao"
    return None, "nao_encontrada"
