import sqlite3
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from collections import Counter
import re

nltk.download('vader_lexicon', quiet=True)

CUSTOM_STOPWORDS = {
    'make', 'makes', 'made', 'really', 'just', 'like', 'know', 'think', 'people', 'thing',
    'things', 'good', 'bad', 'way', 'want', 'dont', 'didnt', 'doesnt', 'im', 'ive', 'youre',
    'theyre', 'thats', 'cant', 'wont', 'isnt', 'wasnt', 'https', 'http', 'www', 'com', 'reddit',
    'thread', 'post', 'posts', 'comment', 'comments', 'today', 'tomorrow', 'yesterday'
}
AI_TERMS = {
    'ai', 'artificial', 'intelligence', 'machine', 'learning', 'ml', 'llm', 'llms', 'gpt',
    'chatgpt', 'automation', 'automate', 'neural', 'model', 'models'
}


def choose_topic_count(post_count):
    # Keep within assignment constraints (5-20) and avoid a hard-coded 10.
    dynamic = 8 + (post_count // 1500)
    return int(max(5, min(20, dynamic)))


def clean_top_keywords(topic_weights, feature_names, top_n=10):
    ranked_idx = topic_weights.argsort()[::-1]
    cleaned = []

    for idx in ranked_idx:
        term = feature_names[idx].strip().lower()
        if (
            not term
            or term in CUSTOM_STOPWORDS
            or term.isnumeric()
            or len(term) <= 2
            or '_' in term
            or term.startswith('http')
        ):
            continue
        if term not in cleaned:
            cleaned.append(term)
        if len(cleaned) == top_n:
            break

    return cleaned


def build_topic_description(topic_label, topic_keywords, topic_posts, topic_comments):
    keyword_preview = ', '.join(topic_keywords[:5]) if topic_keywords else 'general career concerns'
    if topic_posts.empty and topic_comments.empty:
        return f"This topic centers on {topic_label.lower()}, with recurring terms such as {keyword_preview}."

    text_blob = ' '.join(
        pd.concat([topic_posts['title'].fillna(''), topic_posts['selftext'].fillna(''), topic_comments['body'].fillna('')]).tolist()
    ).lower()
    focus_map = [
        ('interview preparation and coding rounds', {'interview', 'leetcode', 'oa', 'round'}),
        ('job search strategy and applications', {'job', 'apply', 'application', 'resume', 'offer'}),
        ('salary, compensation, and negotiation', {'salary', 'compensation', 'offer', 'tc', 'negotiat'}),
        ('education, degree choices, and coursework', {'degree', 'college', 'university', 'masters', 'study'}),
        ('AI impact, automation, and future roles', AI_TERMS),
        ('workplace culture, growth, and team dynamics', {'manager', 'team', 'culture', 'promotion', 'career'}),
        ('layoffs, uncertainty, and market conditions', {'layoff', 'fired', 'market', 'hiring', 'freeze'}),
    ]
    matched_focus = []
    for description, token_set in focus_map:
        if any(token in text_blob for token in token_set):
            matched_focus.append(description)

    if matched_focus:
        if len(matched_focus) == 1:
            focus_text = matched_focus[0]
        else:
            focus_text = ', '.join(matched_focus[:-1]) + f", and {matched_focus[-1]}"
        return (
            f"People in this topic mainly discuss {focus_text}. "
            f"Common terms include {keyword_preview}, and the conversation mixes practical advice with personal experiences."
        )

    return (
        f"People in this topic discuss {topic_label.lower()} from multiple angles. "
        f"Frequent terms include {keyword_preview}, with both tactical guidance and opinion-based debate."
    )


def summarize_stance_arguments(comments_df):
    if comments_df.empty:
        return "No clear arguments were found for this stance."

    sentences = []
    splitter = re.compile(r'(?<=[.!?])\s+')
    for text in comments_df['body'].dropna().astype(str):
        if len(text) < 40:
            continue
        parts = splitter.split(text.strip())
        for part in parts:
            s = part.strip().replace('\n', ' ')
            if 30 <= len(s) <= 220:
                sentences.append(s)

    if not sentences:
        return "Discussion exists, but comments are too short to summarize reliably."

    token_counts = Counter()
    tokenized = []
    for sent in sentences:
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z]{3,}\b', sent)]
        tokens = [t for t in tokens if t not in CUSTOM_STOPWORDS]
        tokenized.append(tokens)
        token_counts.update(tokens)

    if not token_counts:
        return "Discussion exists, but no strong repeated themes were detected."

    sentence_scores = []
    for idx, tokens in enumerate(tokenized):
        if not tokens:
            continue
        score = sum(token_counts[t] for t in tokens) / len(tokens)
        sentence_scores.append((idx, score))

    sentence_scores.sort(key=lambda x: x[1], reverse=True)
    selected = []
    used = set()
    for idx, _ in sentence_scores:
        sent = sentences[idx]
        normalized = sent.lower()
        if normalized in used:
            continue
        used.add(normalized)
        selected.append(sent)
        if len(selected) == 2:
            break

    if not selected:
        return "Discussion exists, but no consistent argument patterns were extracted."

    return ' '.join(selected)


def map_topic_label(keywords):
    # Try to map to standard CS career topics if possible
    kw = keywords.lower()
    if 'interview' in kw or 'leetcode' in kw: return "Interviews & Prep"
    if 'resume' in kw or 'apply' in kw: return "Job Seeking & Resumes"
    if 'salary' in kw or 'offer' in kw: return "Compensation & Offers"
    if 'study' in kw or 'college' in kw or 'degree' in kw: return "Education & Degrees"
    if 'manager' in kw or 'team' in kw: return "Workplace Dynamics"
    if 'layoff' in kw or 'fired' in kw: return "Layoffs & Severance"
    # Fallback to Top 3 capitalized keywords
    parts = keywords.split(', ')
    return f"{parts[0].title()}, {parts[1].title()} & {parts[2].title()}"

def run_pipeline():
    print("Loading data from career.db...")
    conn = sqlite3.connect('career.db')
    df_posts = pd.read_sql_query("SELECT * FROM posts", conn)
    df_comments = pd.read_sql_query("SELECT * FROM comments", conn)
    
    # 0. DATA CLEANING
    print("Filtering out [removed] and [deleted] data...")
    initial_posts = len(df_posts)
    initial_comments = len(df_comments)
    
    df_posts = df_posts[~df_posts['selftext'].isin(['[removed]', '[deleted]'])]
    df_comments = df_comments[~df_comments['body'].isin(['[removed]', '[deleted]'])]
    
    print(f"Dropped {initial_posts - len(df_posts)} removed posts and {initial_comments - len(df_comments)} removed comments.")
    
    # 1. Topic Modeling
    print("Performing Topic Modeling (NMF)...")
    df_posts['title'] = df_posts['title'].fillna('')
    df_posts['selftext'] = df_posts['selftext'].fillna('')
    df_posts['text'] = df_posts['title'] + " " + df_posts['selftext']
    
    n_topics = choose_topic_count(len(df_posts))
    tfidf_vectorizer = TfidfVectorizer(
        max_df=0.9,
        min_df=3,
        stop_words='english',
        token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+\b'
    )
    tfidf = tfidf_vectorizer.fit_transform(df_posts['text'])
    
    nmf = NMF(n_components=n_topics, random_state=42, l1_ratio=.5).fit(tfidf)
    feature_names = tfidf_vectorizer.get_feature_names_out()
    
    topics_info = []
    
    # Assign topics to posts
    W = nmf.transform(tfidf)
    df_posts['topic'] = W.argmax(axis=1) + 1
    
    for topic_idx, topic in enumerate(nmf.components_):
        top_features = clean_top_keywords(topic, feature_names, top_n=10)
        keywords_str = ", ".join(top_features)
        label = map_topic_label(keywords_str)
        share = (df_posts['topic'] == (topic_idx + 1)).mean() * 100
        
        topics_info.append({
            'topic_id': topic_idx + 1,
            'label': label,
            'keywords': keywords_str,
            'share': share
        })
    
    topic_df = pd.DataFrame(topics_info)
    
    # 2. Trending vs Persistent Topics (recent momentum + spike check)
    print("Evaluating Trending vs Persistent Topics...")
    df_posts['created_date'] = pd.to_datetime(df_posts['created_utc'], unit='s')
    df_posts['year_month'] = df_posts['created_date'].dt.to_period('M')
    
    volume_df = df_posts.groupby(['topic', 'year_month']).size().reset_index(name='count')
    # Use standard year output for simpler UI
    volume_df_ui = df_posts.groupby(['topic', df_posts['created_date'].dt.year]).size().reset_index(name='count')
    volume_df_ui.rename(columns={'created_date': 'year'}, inplace=True)
    
    trend_labels = {}
    for topic_idx in range(1, n_topics + 1):
        topic_series = volume_df[volume_df['topic'] == topic_idx].sort_values('year_month')['count'].to_numpy()
        if len(topic_series) < 6:
            trend_labels[topic_idx] = 'Persistent'
            continue

        recent_window = topic_series[-6:] if len(topic_series) >= 6 else topic_series
        prior_window = topic_series[:-6] if len(topic_series) > 6 else topic_series

        recent_mean = np.mean(recent_window)
        prior_mean = np.mean(prior_window) if len(prior_window) > 0 else np.mean(topic_series)
        momentum_ratio = (recent_mean + 1) / (prior_mean + 1)

        peak_ratio = topic_series.max() / (np.median(topic_series) + 1)
        x = np.arange(len(topic_series))
        slope = np.polyfit(x, topic_series, 1)[0] if len(topic_series) > 1 else 0

        if momentum_ratio >= 1.25 and peak_ratio >= 1.6 and slope > 0:
            trend_labels[topic_idx] = 'Trending'
        else:
            trend_labels[topic_idx] = 'Persistent'

    topic_df['status'] = topic_df['topic_id'].map(trend_labels)
    
    # 3. Compute Stances
    print("Computing Stances (VADER sentiment analysis)...")
    df_comments = df_comments.merge(df_posts[['id', 'topic']], left_on='post_id', right_on='id', how='inner', suffixes=('', '_post'))
    if 'id_post' in df_comments.columns:
        df_comments.drop(columns=['id_post'], inplace=True)
    
    sia = SentimentIntensityAnalyzer()
    
    def get_stance(text):
        if not isinstance(text, str):
            return "Neutral"
        score = sia.polarity_scores(text)['compound']
        if score >= 0.15: # slightly raised thresholds to increase neutral counts uniquely
            return "Support"
        elif score <= -0.15:
            return "Oppose"
        else:
            return "Neutral"
            
    df_comments['stance'] = df_comments['body'].apply(get_stance)
    
    # 4. Better Summaries
    print("Generating Summaries per topic...")
    summary_data = []
    for topic_idx in range(1, n_topics + 1):
        rel_comments = df_comments[df_comments['topic'] == topic_idx].dropna(subset=['body'])
        
        support_comms = rel_comments[rel_comments['stance'] == 'Support']
        support_summary = summarize_stance_arguments(support_comms)

        oppose_comms = rel_comments[rel_comments['stance'] == 'Oppose']
        oppose_summary = summarize_stance_arguments(oppose_comms)

        topic_posts = df_posts[df_posts['topic'] == topic_idx]
        topic_keywords = topic_df.iloc[topic_idx - 1]['keywords'].split(', ') if topic_df.iloc[topic_idx - 1]['keywords'] else []
        description = build_topic_description(
            topic_df.iloc[topic_idx - 1]['label'],
            topic_keywords,
            topic_posts,
            rel_comments
        )
        
        summary_data.append({
            'topic_id': topic_idx,
            'description': description,
            'support_summary': support_summary[:420] + ("..." if len(support_summary) > 420 else ""),
            'oppose_summary': oppose_summary[:420] + ("..." if len(oppose_summary) > 420 else "")
        })
        
    summary_df = pd.DataFrame(summary_data)
    topic_df = topic_df.merge(summary_df, on='topic_id')

    # Force one explicit AI-oriented topic label based on lexical concentration.
    ai_scores = []
    for topic_idx in range(1, n_topics + 1):
        topic_texts = df_posts[df_posts['topic'] == topic_idx]['text'].dropna().astype(str).str.lower()
        if topic_texts.empty:
            ai_scores.append((topic_idx, 0))
            continue
        ai_hits = topic_texts.apply(lambda t: any(term in t for term in AI_TERMS)).mean()
        ai_scores.append((topic_idx, ai_hits))
    best_ai_topic, best_ai_score = max(ai_scores, key=lambda x: x[1])
    if best_ai_score > 0:
        topic_df.loc[topic_df['topic_id'] == best_ai_topic, 'label'] = 'AI Careers & Impact'
    
    # Save processed data
    print("Saving processed data to career_processed.db...")
    out_conn = sqlite3.connect('career_processed.db')
    
    topic_df.to_sql('topics', out_conn, if_exists='replace', index=False)
    
    # Yearly counts for line charts in UI
    volume_df_ui.to_sql('topic_volumes', out_conn, if_exists='replace', index=False)
    
    # Monthly counts for unified time series mapping
    volume_df['year_month_str'] = volume_df['year_month'].astype(str)

    volume_df.to_sql('topic_volumes_monthly', out_conn, if_exists='replace', index=False)
    
    df_posts[['id', 'topic']].to_sql('post_topics', out_conn, if_exists='replace', index=False)
    df_comments[['id', 'post_id', 'topic', 'stance', 'body']].to_sql('comment_stances', out_conn, if_exists='replace', index=False)
    
    counts = pd.DataFrame([{
        'total_posts': len(df_posts),
        'total_users': len(pd.concat([df_posts['author'], df_comments['author']]).unique()),
        'total_comments': len(df_comments)
    }])
    counts.to_sql('dashboard_stats', out_conn, if_exists='replace', index=False)
    
    out_conn.commit()
    out_conn.close()
    print("Done! Clean data ready for UI.")

if __name__ == "__main__":
    run_pipeline()
