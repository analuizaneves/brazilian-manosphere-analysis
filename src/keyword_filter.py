"""
keyword_filter.py

NOVO MÓDULO (não existia explicitamente no código original, era o próximo
passo manual da metodologia).

Filtra uma lista/DataFrame de vídeos, mantendo apenas os que têm pelo menos
uma palavra-chave (da lista pré-definida) no título OU na descrição.

Filtro: case-insensitive simples (decisão confirmada com o usuário).
Como a lista de keywords já inclui várias variações de capitalização e
algumas variações "leetspeak" manualmente, não fazemos normalização de
acentos/leet automática - comparamos exatamente o que está na lista,
ignorando apenas case.
"""

import re


def compile_keyword_pattern(key_words):
    """
    Compila um único regex com todas as keywords (escapadas), usando
    boundary de palavra onde fizer sentido. Operação única e reaproveitável
    para não recompilar a cada vídeo (mais rápido para milhares de vídeos).
    """
    # Remove duplicatas (case-insensitive já cobre várias formas repetidas na lista original)
    keywords_unicas = sorted(set(key_words), key=len, reverse=True)
    escaped = [re.escape(k) for k in keywords_unicas]
    pattern = "|".join(escaped)
    return re.compile(pattern, flags=re.IGNORECASE)


def video_matches_keywords(title, description, compiled_pattern):
    texto = f"{title or ''} {description or ''}"
    return bool(compiled_pattern.search(texto))


def filter_videos_by_keywords(videos, key_words, title_field="title", description_field="description"):
    """
    videos: lista de dicts (cada um representando um vídeo)
    key_words: lista de palavras-chave
    Retorna: (videos_aprovados, videos_reprovados)
    """
    pattern = compile_keyword_pattern(key_words)

    aprovados, reprovados = [], []
    for v in videos:
        titulo = v.get(title_field, "") or ""
        descricao = v.get(description_field, "") or ""
        if video_matches_keywords(titulo, descricao, pattern):
            aprovados.append(v)
        else:
            reprovados.append(v)

    return aprovados, reprovados
