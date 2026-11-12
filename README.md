# NVR-BOX

Codigo do NVR-BOX, sistema desenvolvido no Trabalho de Conclusao de Curso "Implementacao de um sistema de gravacao de video em rede de baixo custo utilizando cameras IP, hardware reaproveitado e software livre" (Victor Emanoel Lima Silva, Tecnologia em Sistemas de Computacao, UESPI, 2026, orientador Prof. Dr. Dario Brito Calcada). Os dados coletados para o artigo estao na pasta [`dados/`](dados/).

NVRBox e um NVR residencial simples para uso local. Ele usa Flask para o painel web, FFmpeg para capturar cameras RTSP e arquivos `.mp4` segmentados e fragmentados para armazenar as gravacoes.

O uso previsto e em `localhost`, rede local confiavel ou Tailscale. Por padrao, o painel continua sem login para manter o uso local simples; existe autenticacao opcional por variaveis de ambiente. O sistema nao deve ser exposto em IP publico, dominio publico ou porta aberta no roteador sem autenticacao e protecao de rede.

Se precisar colocar o painel em uma rede onde outras pessoas tenham acesso, ative a autenticacao HTTP basica com variaveis de ambiente:

```bash
export NVRBOX_AUTH_USUARIO="admin"
export NVRBOX_AUTH_SENHA="troque-esta-senha"
```

Sem essas duas variaveis, o painel continua sem login para manter o uso local simples.

Mesmo sem login, as acoes do painel (cadastrar, editar e apagar cameras, apagar gravacoes, trocar o armazenamento e o tamanho dos segmentos) so sao aceitas quando o pedido vem das proprias telas do painel. O servidor confere os cabecalhos `Origin` e `Referer` (esquema, endereco e porta) e recusa com 403 o que vier de outro site ou sem origem. Isso protege contra CSRF, quando uma pagina aberta no navegador tenta mandar comandos ao painel sem o usuario perceber.

## Funcionalidades atuais

- Painel web em Flask.
- Cadastro simplificado de cameras por nome, IP, senha e perfil RTSP.
- Perfis RTSP conhecidos para ONVIF/Intelbras, Hikvision, Dahua, XM/Yoosee e generico.
- Modo avancado para usuario, porta, MAC, protocolo UDP/TCP e caminho RTSP manual.
- Live view via MJPEG.
- Gravacao por FFmpeg em segmentos `.mp4`.
- Segmentos `.mp4` fragmentados para preservar reproducao mesmo em paradas antes dos 10 minutos.
- Historico de gravacoes por camera.
- Calendario interativo de gravacoes por camera, com contador por dia.
- Filtro por data.
- Reproducao de gravacoes no proprio painel.
- Acoes explicitas de player e download na lista de gravacoes.
- Rota de reproducao compativel com navegador usando FFmpeg/WebM quando o `.mp4` original nao toca diretamente.
- Download de videos.
- Remocao de cameras por `POST`.
- Edicao de cameras pela tela de detalhe, mantendo o slug e as gravacoes antigas.
- Mascaramento de senha RTSP na interface.
- Escolha da memoria de gravacao pelo painel.
- Limpeza automatica quando o disco passa do limite configurado.
- Configuracao real de cameras em arquivo local ignorado pelo Git.
- Slugs seguros para rotas, nomes de arquivos e logs.
- Mensagens de erro e sucesso exibidas no painel.
- Teste real de stream RTSP antes de salvar uma nova camera.
- Autenticacao opcional por variaveis de ambiente.
- Rotacao simples dos logs do FFmpeg.
- Identificacao da camera pelo MAC: quando o roteador troca o IP, o sistema procura a camera na rede local e atualiza o cadastro sozinho.
- Deteccao de gravacao parada: se o arquivo nao cresce por 60 s, a captura reinicia o FFmpeg daquela camera; o painel mostra se cada camera esta gravando.
- Mosaico com todas as cameras ao vivo (botao `Ver todas`).
- Exclusao de gravacoes pelo painel, uma a uma ou todas da camera; arquivos modificados no ultimo minuto (o segmento em gravacao) nao sao apagados.
- Escolha do tamanho dos segmentos pelo painel (5, 10 ou 15 minutos).
- Protecao contra CSRF nas acoes do painel.
- Scripts para rodar sozinho em celular Android com Termux (pasta `termux/`).

## Requisitos

- Python 3.
- FFmpeg instalado no sistema.
- Flask.

Instale as dependencias Python:

```bash
pip install -r requirements.txt
```

## Execucao

Para iniciar o sistema completo:

```bash
./iniciar_nvr.sh
```

Ou rode os processos separadamente:

```bash
python3 -m nvrbox.limpeza
python3 -m nvrbox.captura
python3 -m nvrbox.servidor
```

Depois acesse:

```text
http://127.0.0.1:5000
```

Em outro dispositivo da rede ou via Tailscale, use o IP da maquina onde o servidor esta rodando.

## Armazenamento

O usuario pode escolher a memoria de gravacao no painel principal. A escolha fica salva em `sistema.json`, que e um arquivo local da maquina e nao deve ser versionado.

A ordem de resolucao do armazenamento e:

1. Variavel de ambiente `NVRBOX_GRAVACOES`, se existir.
2. Caminho salvo em `sistema.json`.
3. Memorias gravaveis detectadas em caminhos comuns de Linux e Android.
4. Fallback local em `gravacoes/`.

Ao trocar a memoria pelo painel, a captura reinicia os processos FFmpeg para gravar no novo caminho. As gravacoes antigas permanecem na memoria anterior.

## Ao vivo e gravacoes

O painel principal mostra as cameras cadastradas, o status online/offline e a quantidade de gravacoes por camera. Para ver o video ao vivo, abra a camera pelo botao `Abrir Camera`; o stream MJPEG e carregado na tela de detalhe.

Na tela da camera, a lista `Gravacoes` mostra os arquivos encontrados no armazenamento ativo. O calendario destaca dias com gravacoes, mostra a quantidade de videos por dia e permite clicar em uma data para filtrar a lista. O filtro manual por data continua disponivel como fallback. Ao abrir uma gravacao, o painel interrompe o stream ao vivo, mostra o player de video e usa uma rota compativel com navegador (`/video_compativel/<arquivo>`) para converter o trecho sob demanda para WebM quando necessario. O download continua entregando o arquivo `.mp4` original.

Arquivos com menos de 64 KB que nao estao sendo gravados aparecem como incompletos na lista.

## Gravacoes curtas e queda de energia

Cada segmento tem duracao alvo de 10 minutos por padrao. Se a energia cair, o processo for encerrado ou a camera parar antes disso, o trecho ja gravado deve continuar reproduzivel. Para isso, a captura usa MP4 fragmentado (`frag_keyframe`, `empty_moov` e `default_base_moof`), que escreve metadados no inicio e ao longo do arquivo em vez de depender apenas do fechamento final.

Arquivos antigos gravados antes dessa configuracao podem continuar aparecendo como incompletos se perderam o indice final do MP4.

## Configuracao de cameras

O cadastro principal pede:

- nome da camera;
- IP da camera;
- senha;
- perfil/modelo RTSP.

As opcoes avancadas permitem ajustar:

- usuario, padrao `admin`;
- porta RTSP, padrao `554`;
- MAC;
- protocolo UDP/TCP;
- caminho RTSP manual.

As cameras ficam salvas em `cameras.local.json`, que e um arquivo local da maquina e nao deve ser versionado. O repositorio mantem `cameras.example.json` apenas como modelo sem credenciais reais. Cameras ja cadastradas podem ser editadas pela tela de detalhe; se a senha ficar em branco, a senha atual e mantida.

Ao editar IP, perfil, porta, usuario, senha ou protocolo, o slug da camera e preservado para manter o historico de gravacoes. A captura detecta a alteracao e reinicia o FFmpeg daquela camera no proximo ciclo do watchdog.

Para criar uma configuracao inicial manualmente, copie o exemplo e ajuste os dados:

```bash
cp cameras.example.json cameras.local.json
```

Por padrao, o sistema testa o stream RTSP com `ffprobe` antes de salvar uma nova camera. Para ambientes onde a camera so fica acessivel depois de ajustes externos, esse teste pode ser desligado:

```bash
export NVRBOX_TESTAR_RTSP_CADASTRO=0
```

## Quando a camera muda de IP

Cameras Wi-Fi recebem IP por DHCP, e o endereco pode mudar quando o roteador reinicia. Por isso cada camera e identificada pelo MAC, preenchido no cadastro ou aprendido sozinho pela captura. A captura confere se o IP salvo ainda pertence a camera; se nao pertencer, varre a rede local (/24) atras da porta RTSP, confirma o MAC e atualiza o cadastro, sem perder o historico de gravacoes. Entre uma varredura e outra ha um intervalo minimo de 60 segundos.

Em Linux, o MAC vem da tabela ARP. No Android, que bloqueia a tabela ARP para aplicativos, o MAC e obtido pelo ONVIF (porta 5000), que as cameras testadas respondem sem senha.

## Rodar em um celular Android (Termux)

O sistema roda em um celular antigo com o Termux, sem acesso de administrador (root).

1. Instale o Termux e o Termux:Boot pelo GitHub ou pelo F-Droid. A versao da Play Store nao funciona com o Termux:Boot.
2. No Termux, instale as dependencias e baixe o projeto para `~/NVR-BOX`, que e o caminho usado pelos scripts:

```bash
pkg install python ffmpeg git openssh
git clone https://github.com/VitoEmanoel/NVR-BOX-TCC.git ~/NVR-BOX
pip install -r ~/NVR-BOX/requirements.txt
bash ~/NVR-BOX/termux/instalar.sh
```

3. Abra o Termux:Boot uma vez. Nas configuracoes do Android, deixe o Termux e o Termux:Boot sem restricao de bateria; em aparelhos Xiaomi, libere tambem o inicio automatico (Autostart). Configure o Wi-Fi do celular para usar o MAC do aparelho, e nao um MAC aleatorio, para o endereco nao mudar a cada reinicio.
4. Reinicie o celular. O sistema sobe sozinho, sem abrir o Termux.

O que cada arquivo da pasta `termux/` faz:

- `boot_nvrbox.sh`: roda no boot do celular; impede o Android de suspender o Termux (`termux-wake-lock`), liga o SSH (`sshd`, porta 8022) e inicia o vigia.
- `vigia_nvr.sh`: a cada 60 segundos confere se o servidor, a captura, a limpeza e o monitor estao vivos e religa o que tiver parado.
- `monitor_nvr_celular.py`: a cada 5 minutos grava em `~/monitoramento/monitoramento.csv` a memoria livre, o disco livre, a CPU dos FFmpeg e quantas cameras estao gravando.
- `instalar.sh`: copia o script de boot para `~/.termux/boot/` e cria a pasta do monitor.

## Acesso remoto pelo Tailscale

Para ver o painel fora de casa sem abrir portas no roteador, instale o Tailscale no aparelho que roda o NVR-BOX e no celular ou computador de onde vai acessar, entre com a mesma conta nos dois e abra `http://<IP do Tailscale do aparelho>:5000`. O Tailscale cria uma rede privada criptografada entre os seus aparelhos e funciona mesmo atras de CGNAT; o painel nao fica exposto na internet.

## Variaveis de ambiente uteis

- `NVRBOX_AUTH_USUARIO` e `NVRBOX_AUTH_SENHA`: ativam autenticacao HTTP basica.
- `NVRBOX_GRAVACOES`: forca o caminho de gravacao.
- `NVRBOX_CAMERAS`: muda o arquivo JSON de cameras.
- `NVRBOX_LIMITE_DISCO`: limite de uso do disco para limpeza automatica, padrao `90`.
- `NVRBOX_TEMPO_SEGMENTO`: duracao de cada segmento em segundos, padrao `600`. Quando definida, tem prioridade sobre a escolha feita no painel.
- `NVRBOX_RTSP_TRANSPORTE`: transporte padrao `udp` ou `tcp`, padrao `udp`.
- `NVRBOX_TESTAR_RTSP_CADASTRO`: liga/desliga o teste RTSP no cadastro, padrao `1`.
- `NVRBOX_TIMEOUT_TESTE_RTSP`: tempo maximo do teste RTSP em segundos, padrao `20`.
- `NVRBOX_FFMPEG_LOG_MAX_BYTES`: tamanho maximo de cada log FFmpeg antes da rotacao, padrao `2097152`.
- `NVRBOX_LIMITE_SEM_GRAVACAO`: segundos sem o arquivo crescer para considerar a gravacao parada e reiniciar o FFmpeg, padrao `60`.
- `NVRBOX_TIMEOUT_RTSP`: segundos sem resposta da camera antes de o FFmpeg desistir da conexao RTSP, padrao `15`.
- `NVRBOX_ESTADO_CAPTURA`: arquivo onde a captura grava o estado de cada camera, padrao `.run/estado_captura.json`.

## Verificacoes

Antes de considerar uma alteracao concluida, rode:

```bash
python3 -m py_compile nvrbox/*.py
python3 -m unittest
python3 -m json.tool cameras.example.json
test ! -f cameras.local.json || python3 -m json.tool cameras.local.json
bash -n iniciar_nvr.sh
```

## Limitacoes conhecidas

- O painel nao exige senha por padrao. Se outras pessoas tiverem acesso a rede, ative a autenticacao opcional.
- A limpeza automatica apaga arquivos `.mp4` da pasta de gravacoes modificados ha mais de 15 minutos, mesmo que nao tenham sido gravados pelo NVR-BOX. Use uma pasta so para as gravacoes.
- Abrir a pagina inicial em um computador com discos montados em `/mnt` ou `/run/media` pode criar uma pasta `gravacoes` vazia em cada disco, por causa do teste de escrita feito ao listar os armazenamentos.
- O sistema foi validado com cameras de um unico fabricante, que oferecem RTSP e ONVIF no perfil S.

## Onde foi testado

- Celular Xiaomi Redmi Note 11 (Android 13, Termux) com tres cameras Wi-Fi de um mesmo fabricante, em operacao continua por 180 horas.
- Computador com Arch Linux, nos testes automatizados e nos ensaios com camera real e com camera simulada.

Os dados e os resultados desses ensaios estao na pasta [`dados/`](dados/).

## Licenca

MIT. Veja o arquivo [`LICENSE`](LICENSE).
