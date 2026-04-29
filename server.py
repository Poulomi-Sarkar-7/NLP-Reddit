from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import re
import os
import json
from collections import Counter
from urllib import request as urlrequest, error as urlerror
from rag_service import (
    build_or_refresh_index,
    retrieve_context,
    generate_answer,
    available_providers,
    build_knowledge_graph,
    expand_knowledge_graph,
)

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

KEYWORD_STOPWORDS = {
    'make', 'makes', 'made', 'the', 'a', 'an', 'and', 'or', 'like', 'just', 'know', 'people',
    'thread', 'post', 'posts', 'comment', 'comments', 'www', 'http', 'https', 'com', 've', 'don',
    'got', 'getting'
}
AI_TERMS = {'ai', 'machine', 'learning', 'ml', 'llm', 'llms', 'gpt', 'chatgpt', 'automation'}
ANALYSIS_STOPWORDS = KEYWORD_STOPWORDS.union({
    'this', 'that', 'with', 'from', 'have', 'has', 'had', 'were', 'been', 'being', 'also',
    'about', 'into', 'through', 'where', 'when', 'while', 'your', 'their', 'would', 'could',
    'should', 'very', 'much', 'many', 'more', 'most', 'than', 'then', 'there', 'here'
})
PROFANITY_WORDS = {
    'fuck', 'fucking', 'shit', 'bullshit', 'bitch', 'asshole', 'bastard', 'damn', 'crap',
    'dick', 'piss', 'prick', 'slut', 'whore', 'idiot', 'moron', 'stupid', 'sucks', 'wtf'
}
PROFANITY_REGEX = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in sorted(PROFANITY_WORDS, key=len, reverse=True)) + r')\b',
    flags=re.IGNORECASE
)
GENERIC_NOISE_WORDS = {
    'for', 'you', 'it', 'its', 'they', 'them', 'theirs', 'ours', 'mine', 'myself', 'yourself',
    'him', 'her', 'hers', 'his', 'who', 'whom', 'whose', 'which', 'what', 'why', 'how',
    'any', 'some', 'every', 'each', 'either', 'neither', 'both', 'few', 'lot', 'lots',
    'able', 'cannot', 'cant', 'dont', 'doesnt', 'didnt', 'isnt', 'arent', 'wasnt', 'werent',
    'am', 'is', 'are', 'was', 'were', 'be', 'being', 'been', 'do', 'does', 'did', 'doing',
    'have', 'has', 'had', 'having', 'go', 'goes', 'went', 'gone', 'get', 'gets', 'got',
    'make', 'makes', 'made', 'take', 'takes', 'took', 'taken', 'put', 'puts', 'say', 'says',
    'said', 'tell', 'tells', 'told', 'see', 'seen', 'seeing', 'look', 'looks', 'looking',
    'know', 'knows', 'knew', 'known', 'think', 'thinks', 'thought', 'feel', 'feels', 'felt',
    'want', 'wants', 'wanted', 'need', 'needs', 'needed', 'work', 'works', 'working',
    'really', 'actually', 'basically', 'literally', 'probably', 'maybe', 'perhaps',
    'just', 'also', 'still', 'even', 'ever', 'never', 'always', 'sometimes', 'often',
    'today', 'tomorrow', 'yesterday', 'now', 'then', 'there', 'here', 'anyone', 'someone',
    'everyone', 'nobody', 'something', 'anything', 'everything', 'nothing',
    'reddit', 'thread', 'post', 'posts', 'comment', 'comments', 'title', 'selftext',
    'https', 'http', 'www', 'com', 'org', 'net'
}


def clean_keywords(keywords_str):
    cleaned = []
    for raw in (keywords_str or '').split(','):
        kw = raw.strip().lower()
        if (
            not kw
            or kw in KEYWORD_STOPWORDS
            or kw.isnumeric()
            or len(kw) <= 2
            or kw.startswith('http')
            or '_' in kw
        ):
            continue
        if kw not in cleaned:
            cleaned.append(kw)
    return cleaned


def sentence_split(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text or '') if s.strip()]


def summarize_comments(comment_rows):
    sentences = []
    for row in comment_rows:
        for sent in sentence_split(row['body']):
            if 35 <= len(sent) <= 220:
                sentences.append(sent)

    if not sentences:
        return "Not enough high-quality comments were available to generate a summary."

    token_counts = Counter()
    tokenized = []
    for sent in sentences:
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', sent)]
        tokens = [t for t in tokens if t not in KEYWORD_STOPWORDS]
        tokenized.append(tokens)
        token_counts.update(tokens)

    scored = []
    for i, tokens in enumerate(tokenized):
        if not tokens:
            continue
        score = sum(token_counts[t] for t in tokens) / len(tokens)
        scored.append((i, score))

    if not scored:
        return "Comments exist, but they were too noisy for a reliable summary."

    scored.sort(key=lambda x: x[1], reverse=True)
    picked = []
    seen = set()
    for idx, _ in scored:
        text = sentences[idx]
        norm = text.lower()
        if norm in seen:
            continue
        seen.add(norm)
        picked.append(text)
        if len(picked) == 2:
            break

    return ' '.join(picked) if picked else "No clear repeated argument was detected."


def build_topic_overview(label, keywords, support_rows, oppose_rows, neutral_rows):
    all_comments = support_rows + oppose_rows + neutral_rows
    if not all_comments:
        base = label.lower()
        key_txt = ', '.join(keywords[:4]) if keywords else 'career questions'
        return f"This topic focuses on {base}, with frequent terms like {key_txt}."

    text_blob = ' '.join((r['body'] or '') for r in all_comments).lower()
    focus_map = [
        ('job applications and interview preparation', {'interview', 'leetcode', 'apply', 'resume', 'offer'}),
        ('career growth, role expectations, and workplace tradeoffs', {'manager', 'team', 'work', 'promotion', 'role'}),
        ('market conditions, layoffs, and hiring uncertainty', {'layoff', 'market', 'hiring', 'fired', 'recession'}),
        ('AI tools, automation, and how they affect software careers', AI_TERMS),
        ('education paths and degree-related decisions', {'degree', 'college', 'university', 'masters', 'study'}),
    ]
    matched = [desc for desc, token_set in focus_map if any(token in text_blob for token in token_set)]
    key_txt = ', '.join(keywords[:5]) if keywords else 'practical career themes'

    if matched:
        if len(matched) == 1:
            main_focus = matched[0]
        else:
            main_focus = ', '.join(matched[:-1]) + f", and {matched[-1]}"
        return (
            f"People are mainly talking about {main_focus}. "
            f"Common keywords include {key_txt}, and discussion includes both first-hand experiences and actionable advice."
        )

    return (
        f"People are discussing {label.lower()} from multiple angles. "
        f"Common keywords include {key_txt}, with a mix of opinions, questions, and practical suggestions."
    )


def score_comment(text, token_counts):
    tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', text or '')]
    tokens = [t for t in tokens if t not in KEYWORD_STOPWORDS]
    if not tokens:
        return 0
    return sum(token_counts[t] for t in tokens) / len(tokens)


def pick_top_comments(comment_rows, limit=5):
    if not comment_rows:
        return []
    token_counts = Counter()
    for row in comment_rows:
        token_counts.update(
            t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', row['body'] or '')
            if t.lower() not in KEYWORD_STOPWORDS
        )
    ranked = sorted(comment_rows, key=lambda r: score_comment(r['body'], token_counts), reverse=True)
    selected = []
    seen = set()
    for row in ranked:
        body = (row['body'] or '').strip()
        if not body:
            continue
        norm = body.lower()
        if norm in seen:
            continue
        seen.add(norm)
        selected.append(body)
        if len(selected) == limit:
            break
    return selected


def ranked_comments_with_profanity(comment_rows):
    scored = []
    for row in comment_rows:
        body = (row['body'] or '').strip()
        if not body:
            continue
        hits = [m.group(0).lower() for m in PROFANITY_REGEX.finditer(body)]
        if not hits:
            continue
        scored.append({
            'body': body,
            'hits': hits,
            'hit_count': len(hits)
        })
    scored.sort(key=lambda x: (x['hit_count'], len(x['body'])), reverse=True)
    return scored


def profanity_frequency(comment_rows):
    freq = Counter()
    for row in comment_rows:
        body = row['body'] or ''
        for m in PROFANITY_REGEX.finditer(body):
            freq[m.group(0).lower()] += 1
    return [{'word': w, 'count': int(c)} for w, c in freq.most_common(20)]


def count_non_english_tokens(text):
    # Heuristic: tokens with non a-z letters after punctuation cleanup.
    count = 0
    for tok in re.findall(r'\b[^\s]+\b', text or ''):
        t = tok.strip(".,!?;:\"'()[]{}<>").lower()
        if not t:
            continue
        if re.search(r'[^a-z]', t):
            count += 1
    return count


def llm_translate_to_bengali(text, provider='groq', model=None):
    prompt = (
        "Translate the following English text to Bengali script.\n"
        "Keep meaning faithful, preserve formatting where possible, and return only Bengali output.\n\n"
        f"English text:\n{text}"
    )
    provider = (provider or 'groq').strip().lower()

    if provider == 'groq':
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise RuntimeError('Missing GROQ_API_KEY in environment.')
        model = model or 'llama-3.3-70b-versatile'
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'You are a professional translator to Bengali script.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.2
        }
        req = urlrequest.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
                'User-Agent': 'NLP-Reddit-Translation/1.0'
            },
            method='POST'
        )
        with urlrequest.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']

    if provider == 'google':
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('Missing GOOGLE_API_KEY (or GEMINI_API_KEY) in environment.')
        model = model or 'gemini-2.5-flash'
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.2}
        }
        req = urlrequest.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key,
                'Accept': 'application/json',
                'User-Agent': 'NLP-Reddit-Translation/1.0'
            },
            method='POST'
        )
        with urlrequest.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates') or []
            parts = (((candidates[0] or {}).get('content') or {}).get('parts') or []) if candidates else []
            text_parts = [p.get('text', '') for p in parts if isinstance(p, dict)]
            out = '\n'.join([t for t in text_parts if t.strip()]).strip()
            if not out:
                raise RuntimeError('Gemini returned empty translation.')
            return out

    raise RuntimeError("Unsupported provider. Use 'groq' or 'google'.")


def with_single_ai_topic(topics_rows):
    topics = [dict(row) for row in topics_rows]
    ai_scored = []
    for idx, topic in enumerate(topics):
        kws = clean_keywords(topic.get('keywords', ''))
        score = sum(1 for kw in kws if kw in AI_TERMS)
        if 'ai' in (topic.get('label', '') or '').lower():
            score += 2
        ai_scored.append((idx, score))

    if not ai_scored:
        return topics

    best_idx, best_score = max(ai_scored, key=lambda x: x[1])
    if best_score > 0:
        topics[best_idx]['label'] = 'AI Careers & Impact'

    return topics


def get_ai_topic_id(topics_rows):
    topics = [dict(row) for row in topics_rows]
    ai_scored = []
    for topic in topics:
        kws = clean_keywords(topic.get('keywords', ''))
        score = sum(1 for kw in kws if kw in AI_TERMS)
        if 'ai' in (topic.get('label', '') or '').lower():
            score += 2
        ai_scored.append((topic.get('topic_id'), score))
    if not ai_scored:
        return None
    best_topic_id, best_score = max(ai_scored, key=lambda x: x[1])
    return best_topic_id if best_score > 0 else None


def get_db_connection():
    conn = sqlite3.connect('career_processed3.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_raw_db_connection():
    conn = sqlite3.connect('career.db')
    conn.row_factory = sqlite3.Row
    return conn


def tokenize_text(text):
    tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z][a-zA-Z0-9+\-]{2,}\b', text or '')]
    return [
        t for t in tokens
        if t not in ANALYSIS_STOPWORDS
        and t not in GENERIC_NOISE_WORDS
        and not t.isdigit()
    ]


def keyword_pattern(keyword):
    return re.compile(rf'\b{re.escape(keyword.lower())}\b', flags=re.IGNORECASE)


@app.route('/api/dashboard')
def dashboard():
    # Show original scraped totals (before cleaning), as requested.
    raw_conn = sqlite3.connect('career.db')
    raw_conn.row_factory = sqlite3.Row
    total_posts = raw_conn.execute('SELECT COUNT(*) AS c FROM posts').fetchone()['c']
    total_comments = raw_conn.execute('SELECT COUNT(*) AS c FROM comments').fetchone()['c']
    total_users = raw_conn.execute('''
        SELECT COUNT(DISTINCT author) AS c
        FROM (
            SELECT author FROM posts
            UNION ALL
            SELECT author FROM comments
        )
    ''').fetchone()['c']
    raw_conn.close()

    return jsonify({
        'total_posts': total_posts,
        'total_users': total_users,
        'total_comments': total_comments
    })

@app.route('/api/topics')
def topics():
    conn = get_db_connection()
    topics_rows = conn.execute('SELECT * FROM topics').fetchall()
    conn.close()

    topics_payload = with_single_ai_topic(topics_rows)
    for topic in topics_payload:
        topic['keywords'] = ', '.join(clean_keywords(topic.get('keywords', '')))
    return jsonify(topics_payload)

@app.route('/api/topic/<int:topic_id>')
def topic_details(topic_id):
    conn = get_db_connection()
    
    topic_row = conn.execute('SELECT * FROM topics WHERE topic_id = ?', (topic_id,)).fetchone()
    all_topics_rows = conn.execute('SELECT topic_id, label, keywords FROM topics').fetchall()
    ai_topic_id = get_ai_topic_id(all_topics_rows)
    if topic_row is None:
        conn.close()
        return jsonify({'error': 'Topic not found'}), 404
    topic_info = dict(topic_row)
    if ai_topic_id == topic_id:
        topic_info['label'] = 'AI Careers & Impact'
    topic_info['keywords'] = ', '.join(clean_keywords(topic_info.get('keywords', '')))
    
    monthly_rows = []
    try:
        monthly_rows = conn.execute(
            '''
            SELECT year_month_str, count
            FROM topic_volumes_monthly
            WHERE topic = ?
            ORDER BY year_month
            ''',
            (topic_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        monthly_rows = []
    if monthly_rows:
        timeline = [{'period': r['year_month_str'], 'count': r['count']} for r in monthly_rows]
    else:
        timeline_rows = conn.execute(
            'SELECT year, count FROM topic_volumes WHERE topic = ? ORDER BY year',
            (topic_id,)
        ).fetchall()
        timeline = [{'period': str(r['year']), 'count': r['count']} for r in timeline_rows]
    
    stances = conn.execute('SELECT stance, count(*) as count FROM comment_stances WHERE topic = ? GROUP BY stance', (topic_id,)).fetchall()
    stance_data = {r['stance']: r['count'] for r in stances}
    
    comments_support = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = "Support" AND body IS NOT NULL
    ''', (topic_id,)).fetchall()
    
    comments_oppose = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = "Oppose" AND body IS NOT NULL
    ''', (topic_id,)).fetchall()
    comments_neutral = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = "Neutral" AND body IS NOT NULL
    ''', (topic_id,)).fetchall()
    all_topic_comments = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND body IS NOT NULL
    ''', (topic_id,)).fetchall()
    
    conn.close()

    support_summary = summarize_comments(comments_support)
    oppose_summary = summarize_comments(comments_oppose)
    neutral_summary = summarize_comments(comments_neutral)
    topic_info['support_summary'] = support_summary
    topic_info['oppose_summary'] = oppose_summary
    topic_info['neutral_summary'] = neutral_summary
    topic_info['description'] = build_topic_overview(
        topic_info.get('label', 'this topic'),
        clean_keywords(topic_info.get('keywords', '')),
        comments_support,
        comments_oppose,
        comments_neutral
    )
    profanity_words = profanity_frequency(all_topic_comments)
    profanity_ranked = ranked_comments_with_profanity(all_topic_comments)
    
    return jsonify({
        'info': topic_info,
        'timeline': timeline,
        'stance_counts': stance_data,
        'top_comments': {
            'support': pick_top_comments(comments_support, limit=5),
            'oppose': pick_top_comments(comments_oppose, limit=5),
            'neutral': pick_top_comments(comments_neutral, limit=5)
        },
        'profanity': {
            'top_words': profanity_words[:10],
            'comments': [r['body'] for r in profanity_ranked[:5]],
            'total_comments_with_profanity': len(profanity_ranked),
            'has_more': len(profanity_ranked) > 5
        }
    })


@app.route('/api/topic/<int:topic_id>/comments')
def topic_comments_paginated(topic_id):
    stance = (request.args.get('stance') or '').strip().capitalize()
    offset = int(request.args.get('offset') or 0)
    limit = int(request.args.get('limit') or 5)

    if stance not in ('Support', 'Oppose', 'Neutral'):
        return jsonify({'ok': False, 'error': 'stance must be Support, Oppose, or Neutral'}), 400

    offset = max(0, offset)
    limit = max(1, min(20, limit))

    conn = get_db_connection()
    topic_exists = conn.execute('SELECT 1 FROM topics WHERE topic_id = ? LIMIT 1', (topic_id,)).fetchone()
    if not topic_exists:
        conn.close()
        return jsonify({'ok': False, 'error': 'topic not found'}), 404

    rows = conn.execute(
        '''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = ? AND body IS NOT NULL
        ''',
        (topic_id, stance)
    ).fetchall()
    conn.close()

    ranked = pick_top_comments(rows, limit=5000)
    total = len(ranked)
    items = ranked[offset: offset + limit]
    next_offset = offset + len(items)
    return jsonify({
        'ok': True,
        'topic_id': topic_id,
        'stance': stance,
        'offset': offset,
        'limit': limit,
        'next_offset': next_offset,
        'total': total,
        'has_more': next_offset < total,
        'items': items
    })


@app.route('/api/topic/<int:topic_id>/profanity')
def topic_profanity_paginated(topic_id):
    offset = int(request.args.get('offset') or 0)
    limit = int(request.args.get('limit') or 5)
    offset = max(0, offset)
    limit = max(1, min(20, limit))

    conn = get_db_connection()
    topic_exists = conn.execute('SELECT 1 FROM topics WHERE topic_id = ? LIMIT 1', (topic_id,)).fetchone()
    if not topic_exists:
        conn.close()
        return jsonify({'ok': False, 'error': 'topic not found'}), 404

    rows = conn.execute(
        '''
        SELECT body FROM comment_stances
        WHERE topic = ? AND body IS NOT NULL
        ''',
        (topic_id,)
    ).fetchall()
    conn.close()

    ranked = ranked_comments_with_profanity(rows)
    freq = profanity_frequency(rows)[:10]

    total = len(ranked)
    sliced = ranked[offset: offset + limit]
    items = [r['body'] for r in sliced]
    next_offset = offset + len(items)
    return jsonify({
        'ok': True,
        'topic_id': topic_id,
        'offset': offset,
        'limit': limit,
        'next_offset': next_offset,
        'total': total,
        'has_more': next_offset < total,
        'top_words': freq,
        'items': items
    })


@app.route('/api/sorting/topics')
def sorting_topics():
    metric = (request.args.get('metric') or 'most_comments').strip()
    order = (request.args.get('order') or 'desc').strip().lower()
    if order not in ('asc', 'desc'):
        order = 'desc'

    valid_metrics = {
        'most_comments': 'Most Comments',
        'avg_comment_length': 'Average Comment Length',
        'mean_positive_sentiment': 'Mean Positive Sentiment',
        'mean_negative_sentiment': 'Mean Negative Sentiment',
        'mean_neutral_sentiment': 'Mean Neutral Sentiment',
        'profanity': 'Profanity Frequency',
        'non_english_words': 'Number of Non-English Words',
    }
    if metric not in valid_metrics:
        return jsonify({'ok': False, 'error': 'Invalid metric'}), 400

    conn = get_db_connection()
    topics_rows = conn.execute('SELECT topic_id, label, status FROM topics ORDER BY topic_id').fetchall()
    comment_rows = conn.execute(
        '''
        SELECT topic, stance, body
        FROM comment_stances
        WHERE body IS NOT NULL
        '''
    ).fetchall()
    conn.close()

    agg = {}
    for t in topics_rows:
        agg[t['topic_id']] = {
            'topic_id': t['topic_id'],
            'label': t['label'],
            'status': t['status'],
            'comment_count': 0,
            'total_len': 0,
            'support_count': 0,
            'oppose_count': 0,
            'neutral_count': 0,
            'profanity_hits': 0,
            'non_english_words': 0
        }

    for r in comment_rows:
        topic_id = r['topic']
        row = agg.get(topic_id)
        if not row:
            continue
        body = r['body'] or ''
        row['comment_count'] += 1
        row['total_len'] += len(body)
        stance = (r['stance'] or '').strip()
        if stance == 'Support':
            row['support_count'] += 1
        elif stance == 'Oppose':
            row['oppose_count'] += 1
        else:
            row['neutral_count'] += 1
        row['profanity_hits'] += len(PROFANITY_REGEX.findall(body))
        row['non_english_words'] += count_non_english_tokens(body)

    enriched = []
    for topic_id, row in agg.items():
        total_comments = row['comment_count']
        avg_len = (row['total_len'] / total_comments) if total_comments else 0.0
        pos_mean = (row['support_count'] / total_comments) if total_comments else 0.0
        neg_mean = (row['oppose_count'] / total_comments) if total_comments else 0.0
        neu_mean = (row['neutral_count'] / total_comments) if total_comments else 0.0

        metric_value_map = {
            'most_comments': float(total_comments),
            'avg_comment_length': float(avg_len),
            'mean_positive_sentiment': float(pos_mean),
            'mean_negative_sentiment': float(neg_mean),
            'mean_neutral_sentiment': float(neu_mean),
            'profanity': float(row['profanity_hits']),
            'non_english_words': float(row['non_english_words']),
        }
        metric_value = metric_value_map[metric]
        if metric in ('mean_positive_sentiment', 'mean_negative_sentiment', 'mean_neutral_sentiment'):
            metric_display = f"{metric_value:.3f}"
        elif metric == 'avg_comment_length':
            metric_display = f"{metric_value:.2f}"
        else:
            metric_display = str(int(metric_value))

        enriched.append({
            'topic_id': row['topic_id'],
            'label': row['label'],
            'status': row['status'],
            'metric_key': metric,
            'metric_label': valid_metrics[metric],
            'metric_value': metric_value,
            'metric_display': metric_display,
            'comment_count': total_comments,
        })

    reverse = order == 'desc'
    enriched.sort(key=lambda x: (x['metric_value'], x['comment_count']), reverse=reverse)
    for idx, item in enumerate(enriched, start=1):
        item['rank'] = idx

    return jsonify({
        'ok': True,
        'metric': metric,
        'metric_label': valid_metrics[metric],
        'order': order,
        'topics': enriched
    })


@app.route('/api/translation/translate', methods=['POST'])
def translation_translate():
    payload = request.get_json(silent=True) or {}
    query = (payload.get('query') or '').strip()
    provider = (payload.get('provider') or 'groq').strip().lower()
    model = (payload.get('model') or '').strip() or None

    if not query:
        return jsonify({'ok': False, 'error': 'query is required'}), 400

    conn = get_raw_db_connection()

    # Query strategy: exact post id first, then title/selftext search.
    row = conn.execute(
        '''
        SELECT id, title, selftext
        FROM posts
        WHERE id = ?
        LIMIT 1
        ''',
        (query,)
    ).fetchone()
    if row is None:
        row = conn.execute(
            '''
            SELECT id, title, selftext
            FROM posts
            WHERE LOWER(COALESCE(title, '') || ' ' || COALESCE(selftext, '')) LIKE ?
            ORDER BY created_utc DESC
            LIMIT 1
            ''',
            (f'%{query.lower()}%',)
        ).fetchone()
    conn.close()

    if row is None:
        return jsonify({'ok': True, 'found': False, 'query': query, 'message': 'No matching post found.'})

    english_text = f"Title: {row['title'] or ''}\n\nBody: {row['selftext'] or ''}".strip()
    if provider == 'both':
        try:
            groq_out = llm_translate_to_bengali(english_text, provider='groq', model=model)
            google_out = llm_translate_to_bengali(english_text, provider='google', model=model)
            return jsonify({
                'ok': True,
                'found': True,
                'post_id': row['id'],
                'english_text': english_text,
                'translations': {
                    'groq': groq_out,
                    'google': google_out
                }
            })
        except urlerror.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')
            return jsonify({'ok': False, 'error': f'LLM endpoint error ({e.code}): {detail}'}), 500
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    try:
        translated = llm_translate_to_bengali(english_text, provider=provider, model=model)
        return jsonify({
            'ok': True,
            'found': True,
            'post_id': row['id'],
            'english_text': english_text,
            'translation': translated,
            'provider': provider
        })
    except urlerror.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        return jsonify({'ok': False, 'error': f'LLM endpoint error ({e.code}): {detail}'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/reports/list')
def reports_list():
    items = [
        {'id': 'part1', 'label': 'Part 1 Documentation'},
        {'id': 'rag_eval', 'label': 'RAG Evaluation'},
        {'id': 'translation_eval', 'label': 'Translation Evaluation'},
        {'id': 'bias_detection', 'label': 'Bias Detection'},
        {'id': 'ethics_note', 'label': 'Ethics Note'},
        {'id': 'final_report', 'label': 'Final Report'},
    ]
    return jsonify({'reports': items})


@app.route('/api/reports/file/<report_id>')
def reports_file(report_id):
    mapping = {
        'part1': 'Part1_Documentation and Dashboard.pdf',
        'rag_eval': 'rag_evaluation_report.pdf',
        'translation_eval': 'bengali_translation_evaluation_report.pdf',
        'bias_detection': 'bias_detection_report.pdf',
        'ethics_note': 'ethics_note.pdf',
        'final_report': 'FullFinalReport.pdf',
    }
    filename = mapping.get(report_id)
    if not filename:
        return jsonify({'ok': False, 'error': 'Unknown report id'}), 404
    if not os.path.exists(os.path.join(REPORTS_DIR, filename)):
        return jsonify({'ok': False, 'error': 'Report file not found'}), 404
    return send_from_directory(REPORTS_DIR, filename)

@app.route('/api/timeline_consolidated')
def timeline_consolidated():
    conn = get_db_connection()
    
    # We will fetch 'year' (which we stored in topic_volumes) for each topic
    # and pivot it so each year is a row like: { year: 2020, topic1: 15, topic2: 50...}
    # For UI, doing this on backend saves compute.
    
    # Actually, the pipeline saved 'year' in 'topic_volumes'. 
    # Let's get distinct years
    years = [row['year'] for row in conn.execute('SELECT DISTINCT year FROM topic_volumes ORDER BY year').fetchall()]
    topics_list = conn.execute('SELECT topic_id, label, status FROM topics ORDER BY topic_id').fetchall()
    
    # Initialize response array
    res = []
    
    for y in years:
        # fetch all topics for this year
        counts = conn.execute('SELECT topic, count FROM topic_volumes WHERE year = ?', (y,)).fetchall()
        point = {'year': str(y)}
        # fill defaults
        for t in topics_list:
            point[f"Topic {t['topic_id']}"] = 0
            
        for c in counts:
            point[f"Topic {c['topic']}"] = c['count']
            
        res.append(point)
        
    conn.close()
    
    topics_payload = with_single_ai_topic(topics_list)
    return jsonify({
        'timeline': res,
        'topics': [{'id': t['topic_id'], 'label': t['label'], 'status': t['status']} for t in topics_payload]
    })


@app.route('/api/conversation/providers')
def conversation_providers():
    return jsonify({'providers': available_providers()})


@app.route('/api/conversation/rebuild', methods=['POST'])
def conversation_rebuild():
    try:
        build_or_refresh_index(force=True)
        return jsonify({'ok': True, 'message': 'RAG index rebuilt successfully.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/conversation/ask', methods=['POST'])
def conversation_ask():
    payload = request.get_json(silent=True) or {}
    query = (payload.get('query') or '').strip()
    provider = (payload.get('provider') or 'groq').strip().lower()
    model = (payload.get('model') or '').strip() or None
    top_k = int(payload.get('top_k') or 8)

    if not query:
        return jsonify({'ok': False, 'error': 'Query cannot be empty.'}), 400

    try:
        contexts = retrieve_context(query, top_k=top_k)
        if not contexts:
            return jsonify({
                'ok': True,
                'answer': 'I could not find relevant context in the Reddit repository for this question.',
                'contexts': [],
                'knowledge_graph': {'nodes': [], 'edges': []},
                'provider': provider,
                'model': model
            })

        answer = generate_answer(query, contexts, provider=provider, model=model)
        kg = build_knowledge_graph(query, contexts)
        return jsonify({
            'ok': True,
            'answer': answer,
            'contexts': contexts,
            'knowledge_graph': kg,
            'provider': provider,
            'model': model
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e),
            'contexts': []
        }), 500


@app.route('/api/conversation/expand_node', methods=['POST'])
def conversation_expand_node():
    payload = request.get_json(silent=True) or {}
    term = (payload.get('term') or '').strip()
    query = (payload.get('query') or '').strip()
    contexts = payload.get('contexts') or []
    max_neighbors = int(payload.get('max_neighbors') or 10)

    if not term:
        return jsonify({'ok': False, 'error': 'term is required'}), 400

    try:
        graph = expand_knowledge_graph(
            center_term=term,
            contexts=contexts,
            query_text=query if query else None,
            max_neighbors=max_neighbors
        )
        return jsonify({'ok': True, 'graph': graph})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'graph': {'nodes': [], 'edges': []}}), 500


@app.route('/api/users/top')
def users_top():
    limit = int(request.args.get('limit', 20))
    limit = max(5, min(50, limit))

    conn = get_raw_db_connection()
    rows = conn.execute(
        '''
        SELECT
            author,
            SUM(posts_count) AS posts_count,
            SUM(comments_count) AS comments_count,
            SUM(posts_count + comments_count) AS total_activity
        FROM (
            SELECT author, COUNT(*) AS posts_count, 0 AS comments_count
            FROM posts
            WHERE author IS NOT NULL AND author NOT IN ('[deleted]', 'AutoModerator')
            GROUP BY author
            UNION ALL
            SELECT author, 0 AS posts_count, COUNT(*) AS comments_count
            FROM comments
            WHERE author IS NOT NULL AND author NOT IN ('[deleted]', 'AutoModerator')
            GROUP BY author
        ) u
        GROUP BY author
        ORDER BY total_activity DESC
        LIMIT ?
        ''',
        (limit,)
    ).fetchall()
    conn.close()

    payload = []
    for idx, r in enumerate(rows, start=1):
        payload.append({
            'rank': idx,
            'author': r['author'],
            'posts_count': int(r['posts_count'] or 0),
            'comments_count': int(r['comments_count'] or 0),
            'total_activity': int(r['total_activity'] or 0),
            'bar_label': f'U{idx}'
        })
    return jsonify({'users': payload})


@app.route('/api/users/query')
def users_query():
    username = (request.args.get('username') or '').strip()
    if not username:
        return jsonify({'ok': False, 'error': 'username is required'}), 400

    conn = get_raw_db_connection()
    user_exists = conn.execute(
        '''
        SELECT 1
        FROM (
            SELECT author FROM posts
            UNION ALL
            SELECT author FROM comments
        )
        WHERE LOWER(author) = LOWER(?)
        LIMIT 1
        ''',
        (username,)
    ).fetchone() is not None

    if not user_exists:
        conn.close()
        return jsonify({'ok': True, 'found': False, 'username': username, 'posts': [], 'comments': []})

    posts = conn.execute(
        '''
        SELECT id, title, selftext, created_utc, num_comments
        FROM posts
        WHERE LOWER(author) = LOWER(?)
        ORDER BY created_utc DESC
        LIMIT 200
        ''',
        (username,)
    ).fetchall()

    comments = conn.execute(
        '''
        SELECT id, post_id, body, created_utc
        FROM comments
        WHERE LOWER(author) = LOWER(?)
        ORDER BY created_utc DESC
        LIMIT 300
        ''',
        (username,)
    ).fetchall()
    conn.close()

    return jsonify({
        'ok': True,
        'found': True,
        'username': username,
        'posts_count': len(posts),
        'comments_count': len(comments),
        'posts': [dict(r) for r in posts],
        'comments': [dict(r) for r in comments]
    })


@app.route('/api/keywords/analyze')
def keywords_analyze():
    keyword = (request.args.get('keyword') or '').strip().lower()
    if not keyword or len(keyword) < 2:
        return jsonify({'ok': False, 'error': 'keyword must be at least 2 characters'}), 400

    conn = get_raw_db_connection()
    post_rows = conn.execute('SELECT title, selftext FROM posts').fetchall()
    comment_rows = conn.execute('SELECT body FROM comments').fetchall()
    conn.close()

    pattern = keyword_pattern(keyword)

    docs = []
    keyword_frequency = 0
    for r in post_rows:
        text = f"{r['title'] or ''} {r['selftext'] or ''}".strip()
        if not text:
            continue
        c = len(pattern.findall(text))
        keyword_frequency += c
        docs.append(text)
    for r in comment_rows:
        text = (r['body'] or '').strip()
        if not text:
            continue
        c = len(pattern.findall(text))
        keyword_frequency += c
        docs.append(text)

    matched_token_sets = []
    co_counts = Counter()
    for doc in docs:
        if not pattern.search(doc):
            continue
        tokens = set(tokenize_text(doc))
        if keyword not in tokens:
            tokens.add(keyword)
        matched_token_sets.append(tokens)
        for t in tokens:
            if t == keyword:
                continue
            co_counts[t] += 1

    top_10 = co_counts.most_common(10)
    top_terms = [t for t, _ in top_10]

    labels = [keyword] + top_terms
    matrix = []
    for a in labels:
        row = []
        for b in labels:
            if a == b:
                row.append(1.0)
                continue
            a_docs = 0
            b_docs = 0
            both_docs = 0
            for tok_set in matched_token_sets:
                has_a = a in tok_set
                has_b = b in tok_set
                if has_a:
                    a_docs += 1
                if has_b:
                    b_docs += 1
                if has_a and has_b:
                    both_docs += 1
            denom = (a_docs + b_docs - both_docs)
            score = (both_docs / denom) if denom > 0 else 0.0  # Jaccard-like correlation
            row.append(round(score, 3))
        matrix.append(row)

    return jsonify({
        'ok': True,
        'keyword': keyword,
        'keyword_frequency': int(keyword_frequency),
        'matched_documents': len(matched_token_sets),
        'cooccurring': [{'term': t, 'count': int(c)} for t, c in top_10],
        'heatmap': {
            'labels': labels,
            'matrix': matrix
        }
    })


@app.route('/api/keywords/snippets')
def keywords_snippets():
    keyword = (request.args.get('keyword') or '').strip().lower()
    kind = (request.args.get('kind') or 'posts').strip().lower()
    offset = int(request.args.get('offset') or 0)
    limit = int(request.args.get('limit') or 5)

    if not keyword:
        return jsonify({'ok': False, 'error': 'keyword is required'}), 400
    if kind not in ('posts', 'comments'):
        return jsonify({'ok': False, 'error': 'kind must be posts or comments'}), 400

    offset = max(0, offset)
    limit = max(1, min(20, limit))
    pattern = keyword_pattern(keyword)

    conn = get_raw_db_connection()
    items = []
    total = 0

    if kind == 'posts':
        rows = conn.execute(
            '''
            SELECT id, author, title, selftext, created_utc, num_comments
            FROM posts
            WHERE LOWER(COALESCE(title, '') || ' ' || COALESCE(selftext, '')) LIKE ?
            ORDER BY created_utc DESC
            ''',
            (f'%{keyword}%',)
        ).fetchall()
        filtered = []
        for r in rows:
            full_text = f"{r['title'] or ''} {r['selftext'] or ''}"
            if pattern.search(full_text):
                filtered.append(r)
        total = len(filtered)
        slice_rows = filtered[offset: offset + limit]
        items = [
            {
                'id': r['id'],
                'author': r['author'],
                'title': r['title'],
                'selftext': r['selftext'],
                'created_utc': r['created_utc'],
                'num_comments': r['num_comments'],
            }
            for r in slice_rows
        ]
    else:
        rows = conn.execute(
            '''
            SELECT id, author, post_id, body, created_utc
            FROM comments
            WHERE LOWER(COALESCE(body, '')) LIKE ?
            ORDER BY created_utc DESC
            ''',
            (f'%{keyword}%',)
        ).fetchall()
        filtered = []
        for r in rows:
            if pattern.search(r['body'] or ''):
                filtered.append(r)
        total = len(filtered)
        slice_rows = filtered[offset: offset + limit]
        items = [
            {
                'id': r['id'],
                'author': r['author'],
                'post_id': r['post_id'],
                'body': r['body'],
                'created_utc': r['created_utc'],
            }
            for r in slice_rows
        ]

    conn.close()
    next_offset = offset + len(items)
    return jsonify({
        'ok': True,
        'keyword': keyword,
        'kind': kind,
        'offset': offset,
        'limit': limit,
        'next_offset': next_offset,
        'total': total,
        'has_more': next_offset < total,
        'items': items
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
