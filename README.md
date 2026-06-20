# YouTube Collector — Redpill/Manosfera

Projeto de coleta de dados do YouTube seguindo a metodologia:
1. Busca de vídeos por query → 2. Filtro por palavras-chave → 3. Filtro de canais → 4. Todos os vídeos dos canais → 5. Comentários + replies

## Estrutura

```
.
├── coleta_youtube.ipynb   ← notebook orquestrador (rode este)
├── src/
│   ├── quota_manager.py         Controle de quota diária (10k u/dia)
│   ├── checkpoint.py            Persistência de progresso (CSV + JSON)
│   ├── search_video_by_query.py Busca por query (com paginação)
│   ├── get_video_details.py     Detalhes completos + duração (videos.list)
│   ├── keyword_filter.py        Filtro local por palavras-chave
│   ├── search_channels_details.py Detalhes de canais (channels.list)
│   ├── search_videos_from_channel.py Todos os vídeos de um canal (paginado)
│   ├── get_top_comments.py      Top comentários de um vídeo
│   └── get_replies.py           Replies de um comentário
└── data/
    ├── Palavras-Chave_e_Queries_usadas_para_Coleta.txt  ← suas queries/keywords
    ├── quota_state.json         (gerado) estado da quota do dia
    ├── etapa*_progress.json     (gerado) checkpoint de cada etapa
    ├── videos_raw.csv           (gerado) vídeos brutos das queries
    ├── videos_details.csv       (gerado) vídeos com descrição completa + duração
    ├── videos_aprovados_keywords.csv  (gerado) após filtro de keywords
    ├── canais_detalhes.csv      (gerado) detalhes dos canais
    ├── canais_aprovados.csv     (gerado) canais com >= 5 vídeos
    ├── canal_videos_raw.csv     (gerado) todos os vídeos coletados dos canais
    ├── canal_videos_details.csv (gerado) com duração (para filtrar Shorts)
    ├── canal_videos_finais.csv  (gerado) após remover Shorts (duração ≤ 60s)
    ├── top_comments.csv         (gerado) top 50 comentários por vídeo
    └── replies.csv              (gerado) até 20 replies por comentário
```

## Setup

```bash
pip install google-api-python-client pandas
```

Abra `coleta_youtube.ipynb`, preencha `API_KEY` na célula de configuração e rode as etapas em ordem. Cada etapa salva seu progresso automaticamente — se a quota acabar, basta rodar a célula novamente no dia seguinte.

## Estimativa de quota (10.000 unidades/dia, free tier)

| Etapa | Custo (unidades) | Observação |
|---|---|---|
| 1 — Busca por query | ~6.600 | 66 queries × 100u/página |
| 1b — Detalhes dos vídeos | ~40 | videos.list, 1u/lote de 50 |
| 3 — Detalhes de canais | ~5–12 | channels.list, 1u/lote de 50 |
| 4 — Vídeos dos canais | 100u/página | **variável** (depende de quantos canais e tamanho deles) |
| 5 — Comentários + replies | 1–21u/vídeo | 1u comentários + até 20u replies |

### Dias estimados por cenário

| Cenário | Canais | Vídeos/canal | Total (u) | **Dias** |
|---|---|---|---|---|
| Conservador | ~100 | ~30 | ~80.000 | **~8 dias** |
| Moderado | ~250 | ~60 | ~372.000 | **~37 dias** |
| Amplo | ~400 | ~150 | ~1.387.000 | **~139 dias** |

> **O gargalo real é a Etapa 5 (replies)**, que custa 1 unidade por comentário com replies. Com 50 top comments por vídeo e ~40% tendo replies, cada vídeo consome ~21 unidades — ou seja, a quota de 10.000 unidades cobre ~476 vídeos/dia nessa etapa.

## Comportamento ao esgotar a quota

Cada função retorna `(dados, completo)`. Quando `completo=False`, o notebook:
- Salva tudo o que já foi coletado no CSV correspondente
- NÃO marca a tarefa como concluída no checkpoint
- Para o loop com uma mensagem `⏸️`
- Na próxima execução, retoma automaticamente de onde parou
