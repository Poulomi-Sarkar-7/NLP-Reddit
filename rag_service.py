import os
import re
import json
import sqlite3
from urllib import request, error
from urllib.parse import quote_plus
from env_utils import load_env_file


load_env_file()


RAG_DB = 'career_rag.db'
SOURCE_DB = 'career.db'
MAX_CHUNK_CHARS = 700
CHUNK_OVERLAP = 120
RETRIEVAL_STOPWORDS = {
    'what', 'are', 'is', 'the', 'a', 'an', 'about', 'on', 'in', 'of', 'to', 'for',
    'people', 'saying', 'say', 'do', 'does', 'did', 'and', 'or', 'with', 'from', 'this',
    'that', 'it', 'they', 'we', 'you', 'me', 'my', 'our', 'their', 'at', 'by', 'as',
    'be', 'been', 'being', 'can', 'could', 'should', 'would', 'any', 'all'
}
GRAPH_STOPWORDS = RETRIEVAL_STOPWORDS.union({
    'about', 'reddit', 'question', 'system', 'using', 'used', 'use', 'also', 'into',
    'very', 'more', 'most', 'some', 'many', 'much', 'still', 'even', 'than'
})


def _chunk_text(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP):
    if not text:
        return []
    text = str(text).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks = []
    for para in paragraphs if paragraphs else [text]:
        if len(para) <= max_chars:
            chunks.append(para)
            continue

        start = 0
        while start < len(para):
            end = min(start + max_chars, len(para))
            part = para[start:end].strip()
            if part:
                chunks.append(part)
            if end >= len(para):
                break
            start = end - overlap
            if start < 0:
                start = 0
    return chunks


def _connect_rag():
    conn = sqlite3.connect(RAG_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn):
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS rag_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT,
            body TEXT NOT NULL,
            created_utc INTEGER
        )
        '''
    )
    conn.execute(
        '''
        CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
        USING fts5(
            title,
            body,
            content='rag_chunks',
            content_rowid='id'
        )
        '''
    )
    conn.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS rag_chunks_ai AFTER INSERT ON rag_chunks BEGIN
          INSERT INTO rag_chunks_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;
        '''
    )
    conn.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS rag_chunks_ad AFTER DELETE ON rag_chunks BEGIN
          INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, title, body)
          VALUES ('delete', old.id, old.title, old.body);
        END;
        '''
    )
    conn.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS rag_chunks_au AFTER UPDATE ON rag_chunks BEGIN
          INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, title, body)
          VALUES ('delete', old.id, old.title, old.body);
          INSERT INTO rag_chunks_fts(rowid, title, body)
          VALUES (new.id, new.title, new.body);
        END;
        '''
    )
    conn.commit()


def _set_meta(conn, key, value):
    conn.execute(
        'INSERT INTO rag_meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        (key, value),
    )


def _get_meta(conn, key):
    row = conn.execute('SELECT value FROM rag_meta WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else None


def build_or_refresh_index(force=False):
    rag_conn = _connect_rag()
    _init_schema(rag_conn)

    if not force and rag_conn.execute('SELECT COUNT(*) AS c FROM rag_chunks').fetchone()['c'] > 0:
        rag_conn.close()
        return

    rag_conn.execute('DELETE FROM rag_chunks')
    rag_conn.execute("INSERT INTO rag_chunks_fts(rag_chunks_fts) VALUES('rebuild')")

    src_conn = sqlite3.connect(SOURCE_DB)
    src_conn.row_factory = sqlite3.Row

    post_rows = src_conn.execute(
        '''
        SELECT id, title, selftext, created_utc
        FROM posts
        WHERE COALESCE(selftext, '') NOT IN ('[removed]', '[deleted]')
        '''
    ).fetchall()
    comment_rows = src_conn.execute(
        '''
        SELECT id, post_id, body, created_utc
        FROM comments
        WHERE COALESCE(body, '') NOT IN ('[removed]', '[deleted]')
        '''
    ).fetchall()

    for p in post_rows:
        title = (p['title'] or '').strip()
        content = ((p['title'] or '') + '\n' + (p['selftext'] or '')).strip()
        for idx, chunk in enumerate(_chunk_text(content)):
            source_id = f"{p['id']}#p{idx + 1}"
            rag_conn.execute(
                '''
                INSERT INTO rag_chunks(source_type, source_id, title, body, created_utc)
                VALUES (?, ?, ?, ?, ?)
                ''',
                ('post', source_id, title, chunk, p['created_utc']),
            )

    for c in comment_rows:
        body = (c['body'] or '').strip()
        for idx, chunk in enumerate(_chunk_text(body)):
            source_id = f"{c['id']}#c{idx + 1}"
            rag_conn.execute(
                '''
                INSERT INTO rag_chunks(source_type, source_id, title, body, created_utc)
                VALUES (?, ?, ?, ?, ?)
                ''',
                ('comment', source_id, f"Comment on post {c['post_id']}", chunk, c['created_utc']),
            )

    _set_meta(rag_conn, 'built_from', SOURCE_DB)
    _set_meta(rag_conn, 'build_complete', '1')
    rag_conn.commit()
    src_conn.close()
    rag_conn.close()


def retrieve_context(query, top_k=8):
    build_or_refresh_index(force=False)
    conn = _connect_rag()
    _init_schema(conn)

    base_sql = '''
        SELECT
            c.id,
            c.source_type,
            c.source_id,
            c.title,
            c.body,
            c.created_utc,
            bm25(rag_chunks_fts) AS score
        FROM rag_chunks_fts
        JOIN rag_chunks c ON c.id = rag_chunks_fts.rowid
        WHERE rag_chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?
    '''

    def _run(match_query):
        if not match_query:
            return []
        return conn.execute(base_sql, (match_query, int(top_k))).fetchall()

    # Strategy 1: keyword OR + prefix search (much better for natural-language questions).
    tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', query or '')]
    tokens = [t for t in tokens if t not in RETRIEVAL_STOPWORDS]
    if not tokens:
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{2,}\b', query or '')]
    token_query = ' OR '.join([f'{t}*' for t in tokens[:10]])
    rows = _run(token_query)

    # Strategy 2: relaxed raw query fallback.
    if not rows:
        safe_query = re.sub(r'["\'():]', ' ', query or '').strip()
        rows = _run(safe_query)

    # Strategy 3: broad LIKE fallback so user never gets zero due FTS query syntax quirks.
    if not rows and tokens:
        like_sql = '''
            SELECT
                id, source_type, source_id, title, body, created_utc, 999.0 AS score
            FROM rag_chunks
            WHERE body LIKE ? OR title LIKE ?
            LIMIT ?
        '''
        like_term = f"%{tokens[0]}%"
        rows = conn.execute(like_sql, (like_term, like_term, int(top_k))).fetchall()

    conn.close()

    contexts = []
    for r in rows:
        contexts.append(
            {
                'id': r['id'],
                'source_type': r['source_type'],
                'source_id': r['source_id'],
                'title': r['title'] or '',
                'body': r['body'] or '',
                'created_utc': r['created_utc'],
                'score': float(r['score']) if r['score'] is not None else None,
            }
        )
    return contexts


def build_knowledge_graph(user_query, contexts, max_nodes=12, max_edges=18):
    token_freq = {}
    cooccur = {}

    def _tokens(text):
        words = [w.lower() for w in re.findall(r'\b[a-zA-Z][a-zA-Z0-9+\-]{2,}\b', text or '')]
        return [w for w in words if w not in GRAPH_STOPWORDS and not w.isdigit()]

    for ctx in contexts:
        combined = f"{ctx.get('title', '')} {ctx.get('body', '')}"
        toks = _tokens(combined)
        if not toks:
            continue

        seen = []
        for t in toks:
            token_freq[t] = token_freq.get(t, 0) + 1
            if t not in seen:
                seen.append(t)

        # co-occurrence within each retrieved chunk
        for i in range(len(seen)):
            for j in range(i + 1, len(seen)):
                a, b = sorted((seen[i], seen[j]))
                key = (a, b)
                cooccur[key] = cooccur.get(key, 0) + 1

    top_tokens = [k for k, _ in sorted(token_freq.items(), key=lambda x: x[1], reverse=True)[:max_nodes - 1]]
    token_set = set(top_tokens)

    nodes = [{'id': 'query', 'label': user_query.strip()[:60], 'size': 32}]
    for t in top_tokens:
        nodes.append({
            'id': t,
            'label': t,
            'size': int(max(12, min(26, 10 + token_freq.get(t, 1) * 1.3)))
        })

    edges = []
    # connect all important terms to query node
    for t in top_tokens:
        edges.append({'source': 'query', 'target': t, 'weight': token_freq.get(t, 1)})

    pair_edges = []
    for (a, b), w in cooccur.items():
        if a in token_set and b in token_set:
            pair_edges.append((a, b, w))
    pair_edges.sort(key=lambda x: x[2], reverse=True)

    for a, b, w in pair_edges[:max_edges]:
        edges.append({'source': a, 'target': b, 'weight': w})

    return {'nodes': nodes, 'edges': edges}


def _normalize_token(text):
    return (text or '').strip().lower()


def _extract_tokens(text):
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z][a-zA-Z0-9+\-]{2,}\b', text or '')]
    return [w for w in words if w not in GRAPH_STOPWORDS and not w.isdigit()]


def _external_related_terms(term, max_terms=10):
    # Free external lexical association source (no API key needed).
    # Uses Datamuse "ml" (means-like) endpoint.
    url = f'https://api.datamuse.com/words?ml={quote_plus(term)}&max={int(max_terms)}'
    req = request.Request(
        url,
        headers={
            'Accept': 'application/json',
            'User-Agent': 'NLP-Reddit-RAG/1.0 (+local-dev)',
        },
        method='GET'
    )
    try:
        with request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode('utf-8')
            data = json.loads(body)
            results = []
            for row in data:
                w = (row.get('word') or '').strip().lower()
                if not w:
                    continue
                if w in GRAPH_STOPWORDS:
                    continue
                if len(w) < 3:
                    continue
                results.append(w)
            return results[:max_terms]
    except Exception:
        # Silent fallback: graph still works from local data.
        return []


def expand_knowledge_graph(center_term, contexts, query_text=None, max_neighbors=10):
    center = _normalize_token(center_term)
    if not center:
        return {'nodes': [], 'edges': [], 'center': ''}

    local_counts = {}
    pair_counts = {}

    for ctx in contexts or []:
        combined = f"{ctx.get('title', '')} {ctx.get('body', '')}"
        toks = _extract_tokens(combined)
        if not toks:
            continue
        unique = list(dict.fromkeys(toks))
        if center not in unique:
            continue

        for t in unique:
            if t == center:
                continue
            local_counts[t] = local_counts.get(t, 0) + 1

        # neighbor-neighbor links (within center-containing chunks)
        neighbors_in_chunk = [t for t in unique if t != center]
        for i in range(len(neighbors_in_chunk)):
            for j in range(i + 1, len(neighbors_in_chunk)):
                a, b = sorted((neighbors_in_chunk[i], neighbors_in_chunk[j]))
                key = (a, b)
                pair_counts[key] = pair_counts.get(key, 0) + 1

    top_local = [k for k, _ in sorted(local_counts.items(), key=lambda x: x[1], reverse=True)[:max_neighbors]]
    ext = _external_related_terms(center, max_terms=max_neighbors)

    merged_neighbors = []
    seen = set()
    for w in top_local + ext:
        if w == center or w in seen:
            continue
        seen.add(w)
        merged_neighbors.append(w)
    merged_neighbors = merged_neighbors[: max_neighbors * 2]

    nodes = []
    edges = []

    center_label = center_term.strip() if (center_term or '').strip() else center
    nodes.append({'id': center, 'label': center_label, 'size': 34, 'type': 'center'})

    if query_text:
        nodes.append({'id': 'query', 'label': query_text[:60], 'size': 24, 'type': 'query'})
        edges.append({'source': 'query', 'target': center, 'weight': 1, 'kind': 'query'})

    local_set = set(top_local)
    ext_set = set(ext)
    for w in merged_neighbors:
        score = local_counts.get(w, 0)
        base_size = 14 + min(12, score * 2)
        n_type = 'local_external' if (w in local_set and w in ext_set) else ('local' if w in local_set else 'external')
        nodes.append({
            'id': w,
            'label': w,
            'size': base_size,
            'type': n_type
        })
        weight = max(1, score)
        if w in ext_set:
            weight += 1
        edges.append({'source': center, 'target': w, 'weight': weight, 'kind': n_type})

    neighbor_set = set(merged_neighbors)
    bridge_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)
    added = 0
    for (a, b), w in bridge_pairs:
        if a in neighbor_set and b in neighbor_set:
            edges.append({'source': a, 'target': b, 'weight': w, 'kind': 'local_bridge'})
            added += 1
            if added >= 14:
                break

    return {'nodes': nodes, 'edges': edges, 'center': center}


def build_prompt(user_query, contexts):
    context_lines = []
    for idx, item in enumerate(contexts, start=1):
        short_body = re.sub(r'\s+', ' ', item['body']).strip()
        context_lines.append(
            f"[{idx}] ({item['source_type']}:{item['source_id']}) {item['title']} :: {short_body}"
        )

    context_block = '\n'.join(context_lines)
    return f"""You are an assistant answering questions about a Reddit dataset.
Use ONLY the retrieved context below. If context is insufficient, say what is missing.

User question:
{user_query}

Retrieved context:
{context_block}

Instructions:
1) Answer directly and concisely.
2) Include 2-6 bullet points with evidence.
3) End with a short "Sources" line citing [numbers] used.
"""


def available_providers():
    return {
        'groq': bool(os.getenv('GROQ_API_KEY')),
        'google': bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')),
    }


def _call_openai_compatible(url, api_key, model, prompt):
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You answer from provided context only.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'User-Agent': 'NLP-Reddit-RAG/1.0 (+local-dev)',
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8')
            data = json.loads(body)
            return data['choices'][0]['message']['content']
    except error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        if e.code == 403 and '1010' in detail:
            raise RuntimeError(
                'LLM endpoint error (403:1010): request blocked by upstream gateway/firewall. '
                'This is usually due to network policy, VPN/proxy, or missing/blocked client headers. '
                'Try switching provider (Groq <-> Together), disabling VPN, and retrying.'
            ) from e
        raise RuntimeError(f"LLM endpoint error ({e.code}): {detail}") from e
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {e}") from e


def _call_gemini(api_key, model, prompt):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    payload = {
        'contents': [
            {
                'parts': [{'text': prompt}]
            }
        ],
        'generationConfig': {
            'temperature': 0.2
        }
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key,
            'Accept': 'application/json',
            'User-Agent': 'NLP-Reddit-RAG/1.0 (+local-dev)',
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8')
            data = json.loads(body)
            candidates = data.get('candidates') or []
            if not candidates:
                raise RuntimeError(f'No candidate returned from Gemini: {data}')
            parts = (((candidates[0] or {}).get('content') or {}).get('parts') or [])
            text_parts = [p.get('text', '') for p in parts if isinstance(p, dict)]
            text = '\n'.join([t for t in text_parts if t.strip()]).strip()
            if not text:
                raise RuntimeError(f'Gemini returned empty text: {data}')
            return text
    except error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        if e.code == 403 and '1010' in detail:
            raise RuntimeError(
                'LLM endpoint error (403:1010): request blocked by upstream gateway/firewall. '
                'Try disabling VPN/proxy and retrying.'
            ) from e
        raise RuntimeError(f"LLM endpoint error ({e.code}): {detail}") from e
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {e}") from e


def generate_answer(user_query, contexts, provider='groq', model=None):
    prompt = build_prompt(user_query, contexts)
    provider = (provider or 'groq').lower().strip()

    if provider == 'groq':
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise RuntimeError('Missing GROQ_API_KEY in environment.')
        model = model or 'llama-3.3-70b-versatile'
        return _call_openai_compatible(
            'https://api.groq.com/openai/v1/chat/completions',
            api_key,
            model,
            prompt,
        )

    if provider == 'google':
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('Missing GOOGLE_API_KEY (or GEMINI_API_KEY) in environment.')
        model = model or 'gemini-2.5-flash'
        return _call_gemini(api_key, model, prompt)

    raise RuntimeError("Unsupported provider. Use 'groq' or 'google'.")
