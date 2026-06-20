"""
search_channels_details.py

Busca detalhes (snippet + statistics + topicDetails + brandingSettings)
de canais a partir de uma lista de channelIds.

MUDANÇAS nesta versão:
  - Adicionados os parts 'topicDetails' e 'brandingSettings' para trazer:
      * topic_categories: lista de categorias legíveis (ex: "Society",
        "Entertainment") extraídas dos URLs da Wikipedia que a API retorna.
        É o substituto oficial do campo "category" desde 2016.
      * channel_keywords: tags livres definidas pelo próprio criador do canal.
  - Novo campo 'relevance_score': razão entre os vídeos do canal que
    apareceram nas queries (já encontrados na Etapa 1) e o total de vídeos
    do canal — permite filtrar canais onde o tema é incidental, não central.
  - Custo de quota inalterado: channels.list custa 1u por chamada
    independente de quantos 'parts' forem pedidos.
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


def _extrair_categorias(topic_categories):
    """
    Converte lista de URLs da Wikipedia em nomes legíveis.
    Ex: "https://en.wikipedia.org/wiki/Society" → "Society"
    """
    if not topic_categories:
        return []
    return [url.rstrip("/").split("/")[-1].replace("_", " ")
            for url in topic_categories]


def search_channels(lista_canais, youtube, quota_manager=None,
                    videos_por_canal=None, sleep_between_calls=0.05):
    """
    lista_canais: lista de channelIds (qualquer tamanho)
    videos_por_canal: dict opcional {channelId: n_videos_encontrados_nas_queries}
                      usado para calcular o 'relevance_score' de cada canal.

    Retorna (detalhes, completo) onde:
      - detalhes: dict {channelId: {...}} com os campos abaixo
      - completo: True se todos os lotes foram processados

    Campos retornados por canal:
      channelId, channel_title, subscribers, video_count, view_count,
      topic_categories (lista), topic_categories_str (string separada por |),
      channel_keywords,
      videos_found_in_queries (n de vídeos deste canal encontrados nas queries),
      relevance_score (videos_found / video_count — proxy de foco no tema)
    """
    detalhes = {}
    lista_canais_unicos = list(dict.fromkeys(lista_canais))
    videos_por_canal = videos_por_canal or {}

    for lote in _chunks(lista_canais_unicos, 50):
        if quota_manager is not None and not quota_manager.can_spend(1):
            return detalhes, False

        try:
            request = youtube.channels().list(
                part="snippet,statistics,topicDetails,brandingSettings",
                id=",".join(lote),
                maxResults=50,
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("channels.list", pages=1,
                                       note=f"{len(lote)} ids")

        except QuotaExceededError:
            return detalhes, False
        except HttpError as e:
            print(f"  ❌ Erro ao buscar detalhes de canais: {e}")
            continue

        for item in response.get("items", []):
            channel_id = item["id"]
            snippet    = item.get("snippet", {})
            stats      = item.get("statistics", {})
            topics     = item.get("topicDetails", {})
            branding   = item.get("brandingSettings", {}).get("channel", {})

            video_count = int(stats["videoCount"]) if "videoCount" in stats else None
            found       = videos_por_canal.get(channel_id, 0)

            # relevance_score: proporção de vídeos do canal que apareceram
            # nas queries. Canal com score alto → tema é central para ele.
            # Canal com score próximo de zero → passou só por acidente.
            if video_count and video_count > 0:
                relevance_score = round(found / video_count, 4)
            else:
                relevance_score = None

            categorias = _extrair_categorias(
                topics.get("topicCategories", [])
            )

            detalhes[channel_id] = {
                "channelId":              channel_id,
                "channel_title":          snippet.get("title"),
                "country":                snippet.get("country"),
                "subscribers":            int(stats["subscriberCount"]) if "subscriberCount" in stats else None,
                "video_count":            video_count,
                "view_count":             int(stats["viewCount"]) if "viewCount" in stats else None,
                # Categorias do canal (topicDetails)
                "topic_categories":       categorias,
                "topic_categories_str":   " | ".join(categorias) if categorias else None,
                # Tags livres do criador (brandingSettings)
                "channel_keywords":       branding.get("keywords"),
                # Relevância temática
                "videos_found_in_queries": found,
                "relevance_score":        relevance_score,
            }

        time.sleep(sleep_between_calls)

    return detalhes, True
