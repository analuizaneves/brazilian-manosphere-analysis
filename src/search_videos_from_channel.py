"""
search_videos_from_channel.py

Busca TODOS os vídeos publicados por um canal (com paginação completa).

MUDANÇAS em relação à versão original:
  - Paginação completa via nextPageToken (a versão original buscava só
    a primeira página, até 50 vídeos, mesmo que o canal tivesse mais).
  - Integração com QuotaManager (cada página custa 100 unidades).
  - Suporta um "orçamento de páginas" (max_pages) para parar a coleta de
    um canal específico antes de esgotar toda a quota do dia nele.
"""

import time
from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


def search_videos_from_channel(channel_id, youtube, quota_manager=None,
                                 published_after="2022-01-01T00:00:00Z",
                                 published_before="2025-12-01T00:00:00Z",
                                 relevance_language="pt", region_code="BR",
                                 max_pages=None, sleep_between_pages=0.1):
    """
    Retorna (videos, completo) onde:
      - videos: lista de vídeos (snippet básico) já coletados até agora
      - completo: True se TODAS as páginas do canal foram coletadas,
                  False se a coleta foi interrompida (ex: quota esgotada)
                  antes de terminar o canal.

    Paginação completa até esgotar os resultados ou até `max_pages`
    páginas (cada página custa 100 unidades de quota). IMPORTANTE: se a
    quota se esgotar no meio da paginação de um canal grande, os vídeos
    já coletados nas páginas anteriores são retornados (não se perdem),
    e `completo=False` sinaliza ao chamador para NÃO marcar o canal como
    concluído no checkpoint (ele será retomado, refazendo a paginação
    do início, pois a API não permite retomar de uma página arbitrária
    sem o nextPageToken da execução anterior).

    max_pages=None -> sem limite (coleta tudo que o canal tiver).
    """
    videos = []
    next_page_token = None
    page_count = 0

    while True:
        if max_pages is not None and page_count >= max_pages:
            return videos, False

        if quota_manager is not None and not quota_manager.can_spend(100):
            # Quota insuficiente para mais uma página: para AQUI, sem
            # tentar a chamada (que lançaria QuotaExceededError), e
            # devolve o que já foi coletado deste canal até agora.
            return videos, False

        try:
            request = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                maxResults=50,
                type="video",
                publishedAfter=published_after,
                publishedBefore=published_before,
                relevanceLanguage=relevance_language,
                regionCode=region_code,
                pageToken=next_page_token,
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("search.list", pages=1, note=f"channel={channel_id}")

        except QuotaExceededError:
            return videos, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar vídeos do canal {channel_id}: {e}")
            return videos, False

        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            videos.append({
                "channelId": channel_id,
                "id_video": video_id,
                "title": snippet.get("title"),
                "published_at": snippet.get("publishedAt"),
            })

        page_count += 1
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            return videos, True

        time.sleep(sleep_between_pages)
