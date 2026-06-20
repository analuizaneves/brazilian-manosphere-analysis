"""
get_top_comments.py

Busca os top comentários (mais relevantes) de um vídeo, paginando até
atingir max_comments ou esgotar os resultados.

MUDANÇAS em relação à versão original:
  - Integração com QuotaManager (1 unidade por página de até 100 resultados;
    como max_comments=50 < 100, normalmente cabe em 1 página/chamada).
  - Tratamento de erro mais explícito para o caso comum de comentários
    desativados (não trata como falha grave, apenas retorna lista vazia
    e marca o vídeo como "sem comentários" para não tentar de novo).
  - Pequeno ajuste: maxResults agora é min(100, max_comments) ao invés de
    sempre pedir 100 (mais eficiente quando max_comments for pequeno).
"""

from googleapiclient.errors import HttpError

try:
    from quota_manager import QuotaExceededError
except ImportError:
    class QuotaExceededError(Exception):
        pass


class CommentsDisabledError(Exception):
    """Sinaliza que o vídeo tem comentários desativados (não é um erro real,
    apenas informação a ser registrada no checkpoint para não tentar de novo)."""
    pass


def get_top_comments(video_id, youtube, quota_manager=None, max_comments=50):
    """
    Retorna (comments, completo): comments é a lista coletada até agora;
    completo=True se terminou de coletar (atingiu max_comments ou esgotou
    os resultados) sem interrupção por quota, False se a quota impediu
    buscar mais páginas.

    Lança CommentsDisabledError se comentários estiverem desativados
    (para o chamador decidir como registrar isso no checkpoint).
    """
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        page_size = min(100, max_comments - len(comments))

        if quota_manager is not None and not quota_manager.can_spend(1):
            return comments, False

        try:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=page_size,
                order="relevance",
                pageToken=next_page_token,
                textFormat="plainText",
            )
            response = request.execute()

            if quota_manager is not None:
                quota_manager.register("commentThreads.list", pages=1, note=f"video={video_id}")

        except QuotaExceededError:
            return comments, False
        except HttpError as e:
            content = str(e.content)
            if e.resp.status == 403 and "commentsDisabled" in content:
                raise CommentsDisabledError(video_id)
            print(f"  ❌ Erro inesperado no vídeo {video_id}: {e}")
            return comments, False

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id": item["snippet"]["topLevelComment"]["id"],
                "video_id": video_id,
                "author": snippet.get("authorDisplayName"),
                "text": snippet.get("textDisplay"),
                "likes": snippet.get("likeCount"),
                "published_at": snippet.get("publishedAt"),
                "reply_count": item["snippet"].get("totalReplyCount", 0),
            })
            if len(comments) >= max_comments:
                break

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            return comments, True

    return comments, True
