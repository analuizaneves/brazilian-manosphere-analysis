"""
get_video_details.py

NOVO MÓDULO (não existia no código original).

O endpoint search.list NÃO retorna a descrição completa do vídeo (vem
truncada) nem a duração. Como a metodologia exige checar título E descrição
contra a lista de palavras-chave, e também precisamos excluir Shorts
(<=60s) da etapa de "todos os vídeos do canal", precisamos do videos.list.

Custo: 1 unidade por chamada, processando até 50 IDs por vez (extremamente
mais barato que repetir o search.list).
"""

import time
from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


def _chunks(lista, tamanho=50):
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


def get_videos_details(video_ids, youtube, quota_manager=None, sleep_between_calls=0.05):
    """
    Recebe uma lista de video_ids (pode ter milhares) e retorna
    (detalhes, completo), onde:
      - detalhes: dict {video_id: {title, description, duration_iso,
                  duration_seconds, channelId, viewCount, likeCount,
                  commentCount}} já coletado até agora
      - completo: True se TODOS os lotes foram processados; False se a
                  quota impediu processar algum lote (os lotes já feitos
                  continuam no retorno, nada se perde)

    Processa em lotes de até 50 IDs (limite da API), gastando 1 unidade
    de quota por lote. O chamador deve usar `completo` para decidir quais
    video_ids marcar como concluídos no checkpoint (idealmente, marcar
    apenas os que aparecem nas chaves de `detalhes`).
    """
    detalhes = {}
    video_ids_unicos = list(dict.fromkeys(video_ids))  # remove duplicatas preservando ordem

    for lote in _chunks(video_ids_unicos, 50):
        if quota_manager is not None and not quota_manager.can_spend(1):
            return detalhes, False

        try:
            request = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(lote),
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("videos.list", pages=1, note=f"{len(lote)} ids")

        except QuotaExceededError:
            return detalhes, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar detalhes de vídeos: {e}")
            continue

        for item in response.get("items", []):
            vid = item["id"]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            stats = item.get("statistics", {})

            duration_iso = content_details.get("duration")
            duration_seconds = _parse_iso8601_duration(duration_iso) if duration_iso else None

            detalhes[vid] = {
                "video_id": vid,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "channelId": snippet.get("channelId"),
                "published_at": snippet.get("publishedAt"),
                "duration_iso": duration_iso,
                "duration_seconds": duration_seconds,
                "is_short": (duration_seconds is not None and duration_seconds <= 60),
                "view_count": int(stats["viewCount"]) if "viewCount" in stats else None,
                "like_count": int(stats["likeCount"]) if "likeCount" in stats else None,
                "comment_count": int(stats["commentCount"]) if "commentCount" in stats else None,
            }

        time.sleep(sleep_between_calls)

    return detalhes, True


def _parse_iso8601_duration(duration_str):
    """Converte 'PT1H2M10S' em segundos totais (int). Sem dependências externas."""
    import re
    match = re.match(
        r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        duration_str
    )
    if not match:
        return None
    parts = match.groupdict()
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds
