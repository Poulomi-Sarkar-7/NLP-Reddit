from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import re
from collections import Counter
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

KEYWORD_STOPWORDS = {
    'make', 'makes', 'made', 'the', 'a', 'an', 'and', 'or', 'like', 'just', 'know', 'people',
    'thread', 'post', 'posts', 'comment', 'comments', 'www', 'http', 'https', 'com', 've', 'don',
    'got', 'getting'
}
AI_TERMS = {'ai', 'machine', 'learning', 'ml', 'llm', 'llms', 'gpt', 'chatgpt', 'automation'}


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
        LIMIT 150
    ''', (topic_id,)).fetchall()
    
    comments_oppose = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = "Oppose" AND body IS NOT NULL
        LIMIT 150
    ''', (topic_id,)).fetchall()
    comments_neutral = conn.execute('''
        SELECT body FROM comment_stances
        WHERE topic = ? AND stance = "Neutral" AND body IS NOT NULL
        LIMIT 120
    ''', (topic_id,)).fetchall()
    
    conn.close()

    support_summary = summarize_comments(comments_support)
    oppose_summary = summarize_comments(comments_oppose)
    topic_info['support_summary'] = support_summary
    topic_info['oppose_summary'] = oppose_summary
    topic_info['description'] = build_topic_overview(
        topic_info.get('label', 'this topic'),
        clean_keywords(topic_info.get('keywords', '')),
        comments_support,
        comments_oppose,
        comments_neutral
    )
    
    return jsonify({
        'info': topic_info,
        'timeline': timeline,
        'stance_counts': stance_data,
        'top_comments': {
            'support': pick_top_comments(comments_support, limit=5),
            'oppose': pick_top_comments(comments_oppose, limit=5)
        }
    })

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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
