from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = sqlite3.connect('career_processed.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/dashboard')
def dashboard():
    conn = get_db_connection()
    stats = dict(conn.execute('SELECT * FROM dashboard_stats LIMIT 1').fetchone())
    conn.close()
    return jsonify(stats)

@app.route('/api/topics')
def topics():
    conn = get_db_connection()
    topics_rows = conn.execute('SELECT * FROM topics').fetchall()
    conn.close()
    return jsonify([dict(row) for row in topics_rows])

@app.route('/api/topic/<int:topic_id>')
def topic_details(topic_id):
    conn = get_db_connection()
    
    topic_info = dict(conn.execute('SELECT * FROM topics WHERE topic_id = ?', (topic_id,)).fetchone())
    
    timeline_rows = conn.execute('SELECT year, count FROM topic_volumes WHERE topic = ? ORDER BY year', (topic_id,)).fetchall()
    timeline = [{'year': r['year'], 'count': r['count']} for r in timeline_rows]
    
    stances = conn.execute('SELECT stance, count(*) as count FROM comment_stances WHERE topic = ? GROUP BY stance', (topic_id,)).fetchall()
    stance_data = {r['stance']: r['count'] for r in stances}
    
    comments_support = conn.execute('''
        SELECT body FROM comment_stances 
        WHERE topic = ? AND stance = "Support" AND body IS NOT NULL
        ORDER BY length(body) DESC LIMIT 5
    ''', (topic_id,)).fetchall()
    
    comments_oppose = conn.execute('''
        SELECT body FROM comment_stances 
        WHERE topic = ? AND stance = "Oppose" AND body IS NOT NULL
        ORDER BY length(body) DESC LIMIT 5
    ''', (topic_id,)).fetchall()
    
    conn.close()
    
    return jsonify({
        'info': topic_info,
        'timeline': timeline,
        'stance_counts': stance_data,
        'top_comments': {
            'support': [r['body'] for r in comments_support],
            'oppose': [r['body'] for r in comments_oppose]
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
    
    return jsonify({
        'timeline': res,
        'topics': [{'id': t['topic_id'], 'label': t['label'], 'status': t['status']} for t in topics_list]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
