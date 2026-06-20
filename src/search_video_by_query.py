"""
search_video_by_query.py

Busca vídeos no YouTube a partir de uma query textual.

MUDANÇAS em relação à versão original:
  - Paginação: agora respeita o `max_results` solicitado buscando várias
    páginas se necessário (a API retorna no máximo 50 por página).
  - Integração com QuotaManager: cada página custa 100 unidades
    (search.list tem custo fixo de 100, independente de maxResults).
  - Tratamento de HttpError para não quebrar a coleta inteira por causa
    de uma query problemática.
"""

import time
from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


def search_videos(query, youtube, quota_manager=None, max_results=50,
                   published_after="2024-01-01T00:00:00Z",
                   published_before="2025-12-01T00:00:00Z",
                   relevance_language="pt", region_code="BR",
                   sleep_between_pages=0.1):
    """
    Busca vídeos para uma query, paginando até atingir max_results
    (ou esgotar os resultados disponíveis).

    Retorna (items, completo): items é a lista coletada até agora;
    completo=True se terminou de coletar todas as páginas necessárias
    sem interrupção por falta de quota, False caso a quota tenha
    impedido buscar mais páginas (o chamador deve então NÃO marcar essa
    query como concluída no checkpoint).
    """
    items_coletados = []
    next_page_token = None

    while len(items_coletados) < max_results:
        page_size = min(50, max_results - len(items_coletados))

        if quota_manager is not None and not quota_manager.can_spend(100):
            return items_coletados, False

        try:
            request = youtube.search().list(
                part="snippet",
                q=query,
                maxResults=page_size,
                type="video",
                publishedAfter=published_after,
                publishedBefore=published_before,
                relevanceLanguage=relevance_language,
                regionCode=region_code,
                pageToken=next_page_token,
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("search.list", pages=1, note=f"query='{query}'")

        except QuotaExceededError:
            return items_coletados, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar query '{query}': {e}")
            return items_coletados, False

        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            items_coletados.append({
                "query": query,
                "id_video": video_id,
                "title": snippet.get("title"),
                "description_snippet": snippet.get("description"),
                "channelId": snippet.get("channelId"),
                "published_at": snippet.get("publishedAt"),
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            return items_coletados, True

        time.sleep(sleep_between_pages)

    return items_coletados, True
