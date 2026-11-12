import csv
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

CSV = sys.argv[1]
SAIDA = sys.argv[2]
INICIO = datetime(2026, 10, 30, 16, 0, 0)
FIM = datetime(2026, 11, 7, 4, 26, 34)
QUEDA = (datetime(2026, 11, 5, 3, 53, 15), datetime(2026, 11, 5, 8, 47, 36))

AZUL = "#2a78d6"
LARANJA = "#eb6834"
TEXTO = "#0b0b0b"
SECUNDARIO = "#52514e"
GRADE = "#e1e0dc"
FUNDO = "#fcfcfb"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.edgecolor": SECUNDARIO,
    "axes.labelcolor": SECUNDARIO,
    "xtick.color": SECUNDARIO,
    "ytick.color": SECUNDARIO,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": FUNDO,
    "figure.facecolor": FUNDO,
    "savefig.facecolor": FUNDO,
})


def numero(valor):
    return float(valor) if valor not in ("", None) else None


linhas = []
with open(CSV, newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        hora = datetime.strptime(linha["hora"], "%Y-%m-%d %H:%M:%S")
        if INICIO <= hora <= FIM:
            linhas.append((hora, linha))

horas = [h for h, _ in linhas]
gravando = [int(l["cameras_gravando"]) for _, l in linhas]
cpu = [numero(l["ffmpeg_cpu_pct"]) for _, l in linhas]
ram = [numero(l["mem_disponivel_mb"]) for _, l in linhas]
disco = [numero(l["disco_livre_gb"]) for _, l in linhas]

total = len(linhas)
com_tres = sum(1 for g in gravando if g == 3)
disponibilidade = 100 * com_tres / total
fora_da_queda = [g for h, g in zip(horas, gravando) if not QUEDA[0] <= h <= QUEDA[1]]
disponibilidade_com_rede = 100 * sum(1 for g in fora_da_queda if g == 3) / len(fora_da_queda)
duracao_h = (horas[-1] - horas[0]).total_seconds() / 3600


def formatar_tempo(eixo):
    eixo.xaxis.set_major_locator(mdates.DayLocator())
    eixo.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    eixo.grid(axis="y", color=GRADE, linewidth=0.6)
    eixo.set_axisbelow(True)
    eixo.set_xlim(horas[0], horas[-1])


fig, eixo = plt.subplots(figsize=(6.8, 2.3))
eixo.fill_between(horas, gravando, step="post", color=AZUL, alpha=0.18, linewidth=0)
eixo.step(horas, gravando, where="post", color=AZUL, linewidth=1.4)
eixo.axvspan(*QUEDA, color=LARANJA, alpha=0.18, linewidth=0)
eixo.text(
    QUEDA[0] - (QUEDA[1] - QUEDA[0]) * 0.15, 1.5, "queda de rede\n4 h 54 min",
    ha="right", va="center", color=TEXTO, fontsize=8,
)
eixo.set_ylim(0, 3.4)
eixo.set_yticks([0, 1, 2, 3])
eixo.set_ylabel("Câmeras gravando")
formatar_tempo(eixo)
eixo.set_xlabel("Data (2026)")
eixo.text(
    0.01, 0.96,
    f"3 câmeras gravando em {disponibilidade:.1f}% das amostras de {duracao_h:.0f} h "
    f"({disponibilidade_com_rede:.0f}% com a rede local funcionando)".replace(".", ","),
    transform=eixo.transAxes, ha="left", va="top", color=TEXTO, fontsize=8,
)
fig.tight_layout()
fig.savefig(f"{SAIDA}/fig_disponibilidade.png", dpi=300)
fig.savefig(f"{SAIDA}/fig_disponibilidade.pdf")
plt.close(fig)


LIMITE_BURACO_MIN = 12


def serie_com_buracos(valores):
    xs, ys = [], []
    anterior = None
    for h, v in zip(horas, valores):
        if v is None:
            continue
        if anterior is not None and (h - anterior).total_seconds() / 60 > LIMITE_BURACO_MIN:
            xs.append(anterior + (h - anterior) / 2)
            ys.append(float("nan"))
        xs.append(h)
        ys.append(v)
        anterior = h
    return xs, ys


fig, eixos = plt.subplots(3, 1, figsize=(6.8, 5.0), sharex=True)
paineis = (
    (eixos[0], cpu, "CPU dos FFmpeg\n(% de 1 núcleo)", AZUL, 0, None),
    (eixos[1], ram, "RAM disponível\n(MB)", AZUL, 0, None),
    (eixos[2], disco, "Disco livre\n(GB)", AZUL, 0, None),
)
for eixo, valores, rotulo, cor, minimo, maximo in paineis:
    xs, ys = serie_com_buracos(valores)
    eixo.plot(xs, ys, color=cor, linewidth=0.8)
    eixo.axvspan(*QUEDA, color=LARANJA, alpha=0.18, linewidth=0)
    eixo.set_ylabel(rotulo)
    eixo.set_ylim(bottom=minimo)
    formatar_tempo(eixo)
eixos[2].text(
    QUEDA[0] - (QUEDA[1] - QUEDA[0]) * 0.15, 45, "queda de rede",
    ha="right", va="center", color=TEXTO, fontsize=8,
)
eixos[2].annotate(
    "limpeza automática\n(disco a 90% de uso)",
    xy=(datetime(2026, 11, 2, 20, 0), 10.5),
    xytext=(datetime(2026, 11, 2, 22, 0), 38),
    ha="center", va="center", color=TEXTO, fontsize=8,
    arrowprops=dict(arrowstyle="-", color=SECUNDARIO, linewidth=0.8),
)
eixos[2].set_xlabel("Data (2026)")
fig.align_ylabels(eixos)
fig.tight_layout()
fig.savefig(f"{SAIDA}/fig_recursos.png", dpi=300)
fig.savefig(f"{SAIDA}/fig_recursos.pdf")
plt.close(fig)

ativos = [c for c, g in zip(cpu, gravando) if c is not None and g == 3]
ram_ativa = [r for r, g in zip(ram, gravando) if r is not None and g == 3]
resumo = {
    "amostras": total,
    "amostras_com_tres": com_tres,
    "amostras_fora_da_queda": len(fora_da_queda),
    "duracao_h": round(duracao_h, 1),
    "disponibilidade_pct": round(disponibilidade, 1),
    "disponibilidade_com_rede_pct": round(disponibilidade_com_rede, 1),
    "amostras_cpu": len(ativos),
    "cpu_media_pct": round(sum(ativos) / len(ativos), 1),
    "cpu_max_pct": max(ativos),
    "ram_min_mb": min(ram_ativa),
    "ram_media_mb": round(sum(ram_ativa) / len(ram_ativa)),
    "ram_max_mb": max(ram_ativa),
    "disco_min_gb": min(d for d in disco if d is not None),
    "disco_max_gb": max(d for d in disco if d is not None),
}
for chave, valor in resumo.items():
    print(chave, valor)
