import csv, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime

PASTA = os.path.expanduser("~/monitoramento")
SAIDA = os.path.join(PASTA, "monitoramento.csv")
GRAVACOES = os.path.expanduser("~/NVR-BOX/gravacoes")
PAINEL = "http://127.0.0.1:5000"
INTERVALO = int(sys.argv[1]) if len(sys.argv) > 1 else 300
TICKS = os.sysconf("SC_CLK_TCK")

CAMPOS = ["hora", "carga_1min", "mem_disponivel_mb", "swap_livre_mb", "disco_livre_gb",
          "gravacoes_mb", "bateria_pct", "bateria_temp_c", "n_ffmpeg", "ffmpeg_cpu_pct",
          "ffmpeg_ram_mb", "n_python", "python_ram_mb", "cameras_gravando", "cameras_total",
          "segmentos_hoje", "tamanho_hoje_mb"]

anterior = {}


def ler(caminho):
    try:
        with open(caminho) as f:
            return f.read()
    except OSError:
        return ""


def nome_programa(pid):
    bruto = ler(f"/proc/{pid}/cmdline")
    for arg in bruto.split("\0")[:2]:
        base = os.path.basename(arg)
        if base in ("ffmpeg", "python3"):
            return base
    return ""


def processos():
    achados = {"ffmpeg": [], "python3": []}
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        nome = nome_programa(d)
        if nome not in achados:
            continue
        stat = ler(f"/proc/{d}/stat")
        if ")" not in stat:
            continue
        campos = stat.rsplit(")", 1)[1].split()
        try:
            cpu = (int(campos[11]) + int(campos[12])) / TICKS
        except (IndexError, ValueError):
            continue
        mm = re.search(r"VmRSS:\s+(\d+)", ler(f"/proc/{d}/status"))
        ram = int(mm.group(1)) / 1024 if mm else 0.0
        achados[nome].append((int(d), cpu, ram))
    return achados


def painel(caminho):
    try:
        with urllib.request.urlopen(PAINEL + caminho, timeout=10) as r:
            return r.read().decode()
    except Exception:
        return ""


def tamanho_pasta(caminho):
    total = 0
    for raiz, _, arqs in os.walk(caminho):
        for a in arqs:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return total / 1024**2


def bateria():
    try:
        r = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout)
        return d.get("percentage", ""), d.get("temperature", "")
    except Exception:
        pass
    pct = ler("/sys/class/power_supply/battery/capacity").strip()
    temp = ler("/sys/class/power_supply/battery/temp").strip()
    return pct, (int(temp) / 10 if temp.lstrip("-").isdigit() else "")


def amostra():
    agora = time.time()
    linha = {c: "" for c in CAMPOS}
    up = ler("/proc/loadavg").split()
    if up:
        linha["carga_1min"] = up[0]
    mem = ler("/proc/meminfo")
    for chave, campo in (("MemAvailable", "mem_disponivel_mb"), ("SwapFree", "swap_livre_mb")):
        mm = re.search(chave + r":\s+(\d+)", mem)
        if mm:
            linha[campo] = round(int(mm.group(1)) / 1024)
    try:
        s = os.statvfs(os.path.expanduser("~"))
        linha["disco_livre_gb"] = round(s.f_bavail * s.f_frsize / 1024**3, 1)
    except OSError:
        pass
    if os.path.isdir(GRAVACOES):
        linha["gravacoes_mb"] = round(tamanho_pasta(GRAVACOES))
    linha["bateria_pct"], linha["bateria_temp_c"] = bateria()

    proc = processos()
    for nome, pref in (("ffmpeg", "ffmpeg"), ("python3", "python")):
        lista = proc[nome]
        linha[f"n_{pref}"] = len(lista)
        linha[f"{pref}_ram_mb"] = round(sum(p[2] for p in lista), 1)
        if nome == "ffmpeg":
            cpu = 0.0; ok = False
            for pid, t, _ in lista:
                if pid in anterior and agora > anterior[pid][1]:
                    cpu += 100 * (t - anterior[pid][0]) / (agora - anterior[pid][1]); ok = True
            linha["ffmpeg_cpu_pct"] = round(cpu, 1) if ok else ""
    novos = {p[0]: (p[1], agora) for lista in proc.values() for p in lista}
    anterior.clear(); anterior.update(novos)

    slugs = sorted(set(re.findall(r'href="/camera/([^"]+)"', painel("/"))))
    gravando = segs = 0; tam = 0.0
    for s in slugs:
        try:
            st = json.loads(painel(f"/api/camera/{s}/status") or "{}")
            if st.get("gravacao", {}).get("codigo") == "gravando":
                gravando += 1
            for v in json.loads(painel(f"/api/camera/{s}/videos") or "{}").get("videos", []):
                segs += 1
                n, u = v["tamanho"].split()
                tam += float(n) * (1024 if u == "GB" else 1)
        except Exception:
            pass
    linha.update(cameras_gravando=gravando, cameras_total=len(slugs),
                 segmentos_hoje=segs, tamanho_hoje_mb=round(tam))
    linha["hora"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return linha


def main():
    os.makedirs(PASTA, exist_ok=True)
    with open(os.path.join(PASTA, "monitor.pid"), "w") as f:
        f.write(str(os.getpid()))
    novo = not os.path.exists(SAIDA) or os.path.getsize(SAIDA) == 0
    with open(SAIDA, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        while True:
            inicio = time.time()
            try:
                w.writerow(amostra()); f.flush()
            except Exception as erro:
                print("erro na amostra:", erro, flush=True)
            time.sleep(max(5, INTERVALO - (time.time() - inicio)))


if __name__ == "__main__":
    main()
