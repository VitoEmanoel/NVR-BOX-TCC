# Dados do TCC

Dados usados no artigo "Implementacao de um sistema de gravacao de video em rede de baixo custo utilizando cameras IP, hardware reaproveitado e software livre" (Victor Emanoel Lima Silva e Dario Brito Calcada, UESPI, 2026).

O NVR-BOX rodou em um celular Xiaomi Redmi Note 11 (Android 13, Termux) com tres cameras Wi-Fi do mesmo fabricante. Os horarios estao no horario de Brasilia; os do monitor e da conferencia vem do relogio do celular, e os do ensaio do roteador, do relogio do computador. MB e GB estao em base 1024.

## Arquivos

| Arquivo | Conteudo |
| --- | --- |
| `monitoramento_celular.csv` | Uma amostra a cada 5 minutos, de 2026-10-30 16:01:31 a 2026-11-07 04:26:34 (2166 amostras, 180,4 h). Coletado por `termux/monitor_nvr_celular.py`. |
| `conferencia_videos.csv` | 60 segmentos de video do periodo (20 por camera, sorteados em 2026-11-09 entre os que ainda estavam armazenados), baixados pelo painel e decodificados por inteiro com o FFmpeg. |
| `recuperacao_roteador.csv` | Ensaio de 2026-11-09: o roteador foi desligado 3 vezes e um script no computador mediu quando cada camera voltou a rede e quando voltou a gravar. |
| `gerar_figuras.py` | Gera as figuras de disponibilidade e de recursos e imprime os numeros da secao de estabilidade do artigo: `python gerar_figuras.py monitoramento_celular.csv <pasta de saida>` (precisa de `matplotlib`). |
| `verificacao_requisitos.csv` | Resultado do roteiro que testou por HTTP as operacoes do painel em 2026-11-12 (18 de 18 verificacoes com o resultado esperado). |
| `verificar_requisitos.py` | O roteiro: cadastra uma camera simulada, confere estado, ao vivo, gravacao, segmentos, lista, reproducao, conversao, download, edicao, exclusao, armazenamento e remocao. |
| `servidor_teste_isolado.py` | Inicia o painel para o teste sem procurar discos externos (`python servidor_teste_isolado.py <pasta do NVR-BOX>`), para nao criar pastas nos discos do computador. |

## monitoramento_celular.csv

| Coluna | Significado |
| --- | --- |
| `hora` | Momento da amostra. |
| `carga_1min`, `bateria_pct`, `bateria_temp_c` | Vazias: o Android nao deixa o Termux ler esses valores. |
| `mem_disponivel_mb` | Memoria disponivel do celular (`MemAvailable`). |
| `swap_livre_mb` | Swap livre. |
| `disco_livre_gb` | Espaco livre na particao do Termux. |
| `gravacoes_mb` | Tamanho da pasta de gravacoes. |
| `n_ffmpeg`, `n_python` | Quantidade de processos FFmpeg e Python do sistema. |
| `ffmpeg_cpu_pct` | CPU dos processos FFmpeg somados, em % de um nucleo, media do intervalo desde a amostra anterior. Vazia quando nao havia amostra anterior do mesmo processo. |
| `ffmpeg_ram_mb`, `python_ram_mb` | Memoria residente somada dos processos. |
| `cameras_gravando` | Cameras com estado "gravando" no painel (arquivo de video crescendo). |
| `cameras_total` | Cameras cadastradas. |
| `segmentos_hoje`, `tamanho_hoje_mb` | Segmentos e tamanho gravados no dia. |

Numeros do artigo: 2107 das 2166 amostras com `cameras_gravando = 3` (97,3%). As 59 restantes estao todas dentro da queda de rede de 2026-11-05, de 03:53 a 08:47, causada pelo travamento do roteador; fora dela, 100%. A CPU (media de 71,4%, maximo de 88,8%) e a memoria (1211 a 1876 MB, media de 1618 MB) usam as amostras com as tres cameras gravando.

## conferencia_videos.csv

| Coluna | Significado |
| --- | --- |
| `camera`, `arquivo`, `dia` | Camera e nome do segmento (o nome traz o horario de inicio). |
| `tamanho_bytes` | Tamanho do arquivo. |
| `duracao_painel_s` | Duracao informada pelo painel (data de modificacao menos o horario do nome). |
| `duracao_container_s` | Duracao lida pelo `ffprobe`. |
| `quadros`, `tempo_decodificado_s` | Quadros e tempo decodificados pelo FFmpeg. |
| `diferenca_s` | `duracao_painel_s` menos `tempo_decodificado_s`. |
| `leu_ate_o_fim` | Verdadeiro quando a diferenca e de ate 10 s. |
| `codec_video`, `largura`, `altura`, `tem_audio` | Formato do video. |
| `codigo_saida` | Codigo de saida do FFmpeg. |
| `erros_decodificacao` | Linhas de mensagem de erro emitidas pelo FFmpeg (um bloco danificado costuma gerar 2 ou 3 linhas). |
| `avisos_tempo` | Avisos de marcacao de tempo (DTS), que nao impedem a leitura. |
| `mensagens` | As mensagens mais frequentes, com numeros trocados por N. |
| `situacao` | `ok`, `com_erros_pontuais`, `terminou_antes` ou `ilegivel`. |
| `segundos_download`, `segundos_decodificacao` | Tempo gasto em cada etapa. |

Resultado: os 60 segmentos (14,9 h) foram lidos ate o fim; 55 sem mensagem de erro, 5 com 1 a 9 e 38 com avisos de tempo.

## recuperacao_roteador.csv

| Coluna | Significado |
| --- | --- |
| `rodada`, `camera` | Rodada (1 a 3) e camera. |
| `queda_inicio` | Quando o computador deixou de alcancar o painel. |
| `camera_voltou` | Primeira vez que a porta RTSP da camera respondeu depois da queda (verificado a cada segundo). |
| `ip_mudou` | Se a camera voltou com outro endereco IP. |
| `primeiro_segmento_novo` | Inicio do primeiro segmento gravado depois da volta, lido no nome do arquivo. |
| `recuperacao_s` | `primeiro_segmento_novo` menos `camera_voltou`. |
| `fim_ultimo_segmento`, `lacuna_s` | Fim do ultimo segmento antes da queda e tempo total sem gravar. |
| `tamanho_primeiro_segmento` | Tamanho do primeiro segmento novo no momento em que foi visto. |
| `estado_apos_espera` | Estado da camera no painel 45 s depois. |
| `defasagem_relogio_s` | Relogio do celular menos relogio do computador; os horarios do celular ja estao corrigidos por ela. |

Resultado: 9 de 9 recuperacoes automaticas; de 41 a 75 s (media de 54 s) quando o IP nao mudou e de 98 a 166 s (media de 130 s) quando mudou.

## verificacao_requisitos.csv

Ensaio feito em um computador, com uma camera simulada (MediaMTX e FFmpeg gerando imagem e som de teste em `rtsp://127.0.0.1:8554/onvif1`), segmentos de 300 s e o codigo deste repositorio. O roteiro confere as respostas do painel, e nao a exibicao no navegador.

| Coluna | Significado |
| --- | --- |
| `hora` | Momento da verificacao. |
| `requisito` | Requisito funcional verificado (RF01 a RF16; o RF17, limpeza automatica, e coberto pelos testes automatizados e pelos dados do celular). |
| `verificacao` | O que o roteiro fez. |
| `esperado`, `obtido` | Resultado esperado e resultado observado. |
| `ok` | `sim` quando o obtido corresponde ao esperado. |

Para repetir: suba o MediaMTX e a camera simulada, inicie o painel com `servidor_teste_isolado.py` e a captura (`python -m nvrbox.captura`) com `NVRBOX_CAMERAS`, `NVRBOX_GRAVACOES`, `NVRBOX_ESTADO_CAPTURA` e `NVRBOX_TEMPO_SEGMENTO=300` apontando para uma pasta de teste, e rode `python verificar_requisitos.py --cameras <cameras.json> --gravacoes <pasta> --saida <csv>`. Leva cerca de 8 minutos.
