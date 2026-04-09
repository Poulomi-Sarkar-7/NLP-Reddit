import sqlite3
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from datetime import datetime

nltk.download('vader_lexicon', quiet=True)

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
    
    n_topics = 10
    tfidf_vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, stop_words='english')
    tfidf = tfidf_vectorizer.fit_transform(df_posts['text'])
    
    nmf = NMF(n_components=n_topics, random_state=42, l1_ratio=.5).fit(tfidf)
    feature_names = tfidf_vectorizer.get_feature_names_out()
    
    topics_info = []
    
    # Assign topics to posts
    W = nmf.transform(tfidf)
    df_posts['topic'] = W.argmax(axis=1) + 1
    
    for topic_idx, topic in enumerate(nmf.components_):
        top_features_ind = topic.argsort()[:-10 - 1:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        
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
    
    # 2. Trending vs Persistent Topics (Z-Score approach)
    print("Evaluating Trending vs Persistent Topics...")
    df_posts['created_date'] = pd.to_datetime(df_posts['created_utc'], unit='s')
    df_posts['year_month'] = df_posts['created_date'].dt.to_period('M')
    
    volume_df = df_posts.groupby(['topic', 'year_month']).size().reset_index(name='count')
    # Use standard year output for simpler UI
    volume_df_ui = df_posts.groupby(['topic', df_posts['created_date'].dt.year]).size().reset_index(name='count')
    volume_df_ui.rename(columns={'created_date': 'year'}, inplace=True)
    
    trend_labels = {}
    for topic_idx in range(1, n_topics + 1):
        topic_counts = volume_df[volume_df['topic'] == topic_idx]['count']
        if len(topic_counts) <= 2:
            trend_labels[topic_idx] = 'Persistent'
            continue
        
        mean = topic_counts.mean()
        std = topic_counts.std()
        max_val = topic_counts.max()
        
        # If the max peak is at least 2 standard deviations above the mean, it's a strongly trending spike.
        if max_val > (mean + 2 * std) and std > 0:
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
    
    # 4. Extractive Summarization
    print("Generating Summaries per topic...")
    summary_data = []
    for topic_idx in range(1, n_topics + 1):
        rel_comments = df_comments[df_comments['topic'] == topic_idx].dropna(subset=['body'])
        
        support_comms = rel_comments[rel_comments['stance'] == 'Support']
        top_support = support_comms.sort_values(by='body', key=lambda x: x.str.len(), ascending=False).head(1)['body'].values
        support_summary = top_support[0] if len(top_support) > 0 else "No supportive comments found."
        
        oppose_comms = rel_comments[rel_comments['stance'] == 'Oppose']
        top_oppose = oppose_comms.sort_values(by='body', key=lambda x: x.str.len(), ascending=False).head(1)['body'].values
        oppose_summary = top_oppose[0] if len(top_oppose) > 0 else "No opposing comments found."
        
        summary_data.append({
            'topic_id': topic_idx,
            'description': f"Analyzed posts discussing {topic_df.iloc[topic_idx-1]['label']} focusing heavily on keywords like {topic_df.iloc[topic_idx-1]['keywords'].split(', ')[0]}.",
            'support_summary': support_summary[:300] + ("..." if len(support_summary) > 300 else ""),
            'oppose_summary': oppose_summary[:300] + ("..." if len(oppose_summary) > 300 else "")
        })
        
    summary_df = pd.DataFrame(summary_data)
    topic_df = topic_df.merge(summary_df, on='topic_id')
    
    # Save processed data
    print("Saving processed data to career_processed.db...")
    out_conn = sqlite3.connect('career_processed2.db')
    
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
