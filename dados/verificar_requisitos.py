import argparse
import csv
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

NOME = "Camera Teste"
NOME_EDITADO = "Camera Teste Editada"


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


abridor = urllib.request.build_opener(SemRedirecionar)


def pedir(url, dados=None, cabecalhos=None, timeout=60, ler=None):
    corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos or {})
    try:
        resposta = abridor.open(pedido, timeout=timeout)
    except urllib.error.HTTPError as erro:
        return erro.code, dict(erro.headers), erro.read()
    with resposta:
        conteudo = resposta.read(ler) if ler else resposta.read()
        return resposta.status, dict(resposta.headers), conteudo


def jpeg_completo(dados):
    inicio = dados.find(b"\xff\xd8")
    return inicio >= 0 and dados.find(b"\xff\xd9", inicio + 2) >= 0


def ler_stream(url, limite_bytes, limite_s, completo=None):
    inicio = time.monotonic()
    pedido = urllib.request.Request(url)
    with abridor.open(pedido, timeout=limite_s) as resposta:
        tipo = resposta.headers.get("Content-Type", "")
        dados = b""
        while len(dados) < limite_bytes and time.monotonic() - inicio < limite_s:
            bloco = resposta.read1(65536)
            if not bloco:
                break
            dados += bloco
            if completo and completo(dados):
                break
        return resposta.status, tipo, dados, round(time.monotonic() - inicio, 2)


class Verificacao:
    def __init__(self, painel, cameras, gravacoes, saida):
        self.painel = painel.rstrip("/")
        self.cameras = Path(cameras)
        self.gravacoes = Path(gravacoes)
        self.saida = saida
        self.linhas = []
        self.origem = {"Origin": self.painel}

    def registrar(self, requisito, verificacao, esperado, obtido, ok):
        linha = {
            "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "requisito": requisito,
            "verificacao": verificacao,
            "esperado": esperado,
            "obtido": obtido,
            "ok": "sim" if ok else "nao",
        }
        self.linhas.append(linha)
        print(f"[{linha['ok']}] {requisito}: {verificacao} -> {obtido}", flush=True)

    def cadastro(self):
        return json.loads(self.cameras.read_text(encoding="utf-8"))

    def formulario(self, porta, nome=NOME, senha="teste"):
        return {
            "nome": nome, "ip": "127.0.0.1", "senha": senha, "perfil": "onvif1",
            "usuario": "admin", "porta": str(porta), "mac": "", "protocolo": "tcp",
        }

    def segmentos(self, slug):
        return sorted(p for p in self.gravacoes.glob(f"{slug}_*.mp4"))

    def esperar(self, condicao, limite_s, passo=2):
        fim = time.monotonic() + limite_s
        while time.monotonic() < fim:
            valor = condicao()
            if valor:
                return valor
            time.sleep(passo)
        return None

    def rodar(self):
        status, _, html = pedir(f"{self.painel}/")
        texto = html.decode("utf-8", "replace")
        self.registrar("RF01", "abrir o painel pelo navegador (GET /)", "200 e titulo do painel",
                       f"{status}, titulo {'presente' if 'Painel de Seguran' in texto else 'ausente'}",
                       status == 200 and "Painel de Seguran" in texto)
        self.registrar("RF02", "indicadores de armazenamento na pagina inicial", "uso do HD exibido",
                       "presente" if "Uso do HD" in texto or "USO DO HD" in texto.upper() else "ausente",
                       "USO DO HD" in texto.upper())

        status, _, html = pedir(f"{self.painel}/adicionar_camera", self.formulario(8555), self.origem, timeout=120)
        recusado = status != 302 and not self.cadastro()
        self.registrar("RF08", "cadastrar camera em porta sem RTSP (8555)", "cadastro recusado com mensagem",
                       f"HTTP {status}, cameras cadastradas: {len(self.cadastro())}", recusado)

        status, _, _ = pedir(f"{self.painel}/adicionar_camera", self.formulario(8554), self.origem, timeout=120)
        cadastro = self.cadastro()
        slug = cadastro[0].get("slug") if cadastro else None
        self.registrar("RF05", "cadastrar camera simulada (RTSP na porta 8554)", "302 e camera salva",
                       f"HTTP {status}, slug {slug}", status == 302 and bool(slug))
        self.registrar("RF08", "teste de conexao RTSP aceito no cadastro valido", "cadastro aceito apos teste",
                       f"HTTP {status}", status == 302)
        if not slug:
            return

        def gravando():
            _, _, corpo = pedir(f"{self.painel}/api/camera/{slug}/status")
            dados = json.loads(corpo or b"{}")
            return dados if dados.get("gravacao", {}).get("codigo") == "gravando" else None

        dados = self.esperar(gravando, 180)
        self.registrar("RF02", "consultar estado da camera (API de status)", "online e gravando",
                       f"online={dados.get('online') if dados else None}, gravacao={dados.get('gravacao', {}).get('codigo') if dados else None}",
                       bool(dados) and dados.get("online") is True)

        status, tipo, dados_vivo, segundos = ler_stream(f"{self.painel}/live/{slug}", 2000000, 30, jpeg_completo)
        tem_jpeg = jpeg_completo(dados_vivo)
        self.registrar("RF03", "abrir o ao vivo (/live)", "fluxo MJPEG com um quadro JPEG completo",
                       f"HTTP {status}, {tipo.split(';')[0]}, primeiro quadro completo {'recebido' if tem_jpeg else 'ausente'} em {segundos} s",
                       status == 200 and "multipart" in tipo and tem_jpeg)

        primeiro = self.esperar(lambda: self.segmentos(slug), 120)
        tamanho_1 = primeiro[0].stat().st_size if primeiro else 0
        time.sleep(15)
        tamanho_2 = self.segmentos(slug)[-1].stat().st_size if primeiro else 0
        self.registrar("RF09", "gravacao continua: arquivo crescendo", "tamanho aumenta em 15 s",
                       f"{tamanho_1} -> {tamanho_2} bytes", tamanho_2 > tamanho_1 > 0)

        dois = self.esperar(lambda: self.segmentos(slug) if len(self.segmentos(slug)) >= 2 else None, 420, passo=5)
        self.registrar("RF10", "segmentacao (segmento configurado em 300 s)", "segundo arquivo criado",
                       f"{len(dois) if dois else len(self.segmentos(slug))} segmentos", bool(dois))
        if not dois:
            return
        alvo = dois[0].name
        tamanho_alvo = dois[0].stat().st_size

        hoje = datetime.now().strftime("%Y-%m-%d")
        _, _, corpo = pedir(f"{self.painel}/api/camera/{slug}/videos?data={hoje}")
        lista = json.loads(corpo)
        _, _, corpo = pedir(f"{self.painel}/api/camera/{slug}/calendario")
        calendario = json.loads(corpo)
        dia = next((d for d in calendario.get("dias", []) if d.get("data") == hoje), {})
        self.registrar("RF12", "listar gravacoes filtrando pela data e calendario", "lista do dia e contagem no calendario",
                       f"{len(lista.get('videos', []))} videos em {hoje}; calendario {dia.get('total')}",
                       len(lista.get("videos", [])) >= 2 and (dia.get("total") or 0) >= 2)

        status, cab, corpo = pedir(f"{self.painel}/video/{alvo}", cabecalhos={"Range": "bytes=0-1023"})
        self.registrar("RF13", "entrega parcial do video ao player (/video com Range)", "206, video/mp4, 1024 bytes",
                       f"HTTP {status}, {cab.get('Content-Type')}, {len(corpo)} bytes",
                       status == 206 and "video/mp4" in (cab.get("Content-Type") or "") and len(corpo) == 1024)

        status, tipo, dados_webm, segundos = ler_stream(f"{self.painel}/video_compativel/{alvo}", 65536, 60)
        webm = dados_webm[:4] == b"\x1a\x45\xdf\xa3"
        self.registrar("RF14", "inicio da conversao para formato compativel (/video_compativel)", "fluxo WebM",
                       f"HTTP {status}, {tipo.split(';')[0]}, cabecalho WebM {'sim' if webm else 'nao'}, {len(dados_webm)} bytes em {segundos} s",
                       status == 200 and webm)

        status, cab, corpo = pedir(f"{self.painel}/download/{alvo}", timeout=120)
        with tempfile.NamedTemporaryFile(suffix=".mp4") as arquivo:
            arquivo.write(corpo)
            arquivo.flush()
            sonda = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arquivo.name],
                capture_output=True, text=True,
            ).stdout.strip()
        self.registrar("RF15", "baixar o arquivo (/download)", "200, anexo, mesmo tamanho e duracao reconhecida pelo ffprobe",
                       f"HTTP {status}, {cab.get('Content-Disposition', '')[:30]}, {len(corpo)}/{tamanho_alvo} bytes, duracao {sonda} s",
                       status == 200 and "attachment" in cab.get("Content-Disposition", "") and len(corpo) == tamanho_alvo and bool(sonda))

        editar = self.formulario(8554, nome=NOME_EDITADO, senha="")
        status, _, _ = pedir(f"{self.painel}/editar_camera/{slug}", editar, self.origem, timeout=120)
        nomes = [c.get("nome") for c in self.cadastro()]
        self.registrar("RF06", "editar o nome da camera", "302 e nome alterado",
                       f"HTTP {status}, nomes {nomes}", status == 302 and NOME_EDITADO in nomes)

        recente = self.segmentos(slug)[-1].name
        status, _, _ = pedir(f"{self.painel}/camera/{slug}/video/{recente}/apagar", {}, self.origem)
        self.registrar("RF11", "tentar apagar o segmento que esta sendo gravado", "exclusao recusada",
                       f"HTTP {status}, arquivo {'mantido' if (self.gravacoes / recente).exists() else 'removido'}",
                       (self.gravacoes / recente).exists())

        self.esperar(lambda: time.time() - (self.gravacoes / alvo).stat().st_mtime >= 65, 180)
        status, _, _ = pedir(f"{self.painel}/camera/{slug}/video/{alvo}/apagar", {}, self.origem)
        self.registrar("RF11", "apagar uma gravacao fechada pelo painel", "302 e arquivo removido",
                       f"HTTP {status}, arquivo {'removido' if not (self.gravacoes / alvo).exists() else 'ainda existe'}",
                       status == 302 and not (self.gravacoes / alvo).exists())

        status, _, html = pedir(f"{self.painel}/")
        opcoes = html.decode("utf-8", "replace").count('name="caminho_videos"')
        status_ruim, _, _ = pedir(f"{self.painel}/configurar_armazenamento",
                                  {"caminho_videos": "/run/media/disco_inexistente/gravacoes"}, self.origem)
        status_bom, _, _ = pedir(f"{self.painel}/configurar_armazenamento",
                                 {"caminho_videos": str(self.gravacoes)}, self.origem)
        self.registrar("RF16", "escolher local de armazenamento", "disco ausente recusado e pasta valida aceita",
                       f"disco ausente HTTP {status_ruim}, pasta valida HTTP {status_bom}",
                       status_ruim == 400 and status_bom == 302 and opcoes >= 1)

        status, _, _ = pedir(f"{self.painel}/apagar_camera/{slug}", {}, self.origem)
        self.registrar("RF07", "remover a camera", "302 e cadastro vazio",
                       f"HTTP {status}, cameras restantes {len(self.cadastro())}", status == 302 and not self.cadastro())

    def salvar(self):
        with open(self.saida, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(self.linhas[0].keys()))
            escritor.writeheader()
            escritor.writerows(self.linhas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--painel", default="http://127.0.0.1:5000")
    parser.add_argument("--cameras", required=True)
    parser.add_argument("--gravacoes", required=True)
    parser.add_argument("--saida", required=True)
    args = parser.parse_args()
    verificacao = Verificacao(args.painel, args.cameras, args.gravacoes, args.saida)
    try:
        verificacao.rodar()
    finally:
        if verificacao.linhas:
            verificacao.salvar()
    print("FIM", sum(1 for l in verificacao.linhas if l["ok"] == "sim"), "de", len(verificacao.linhas), "ok", flush=True)


if __name__ == "__main__":
    main()
