import requests
import pandas as pd
import sqlite3
import time
import random

# -----------------------------
# CONFIG
# -----------------------------
SUBREDDIT = "cscareerquestions"
AFTER = "2020-01-01"
BEFORE = "2026-03-30"
POST_LIMIT = 10000
COMMENTS_PER_POST = 10

BASE_POSTS = "https://arctic-shift.photon-reddit.com/api/posts/search"
BASE_COMMENTS = "https://arctic-shift.photon-reddit.com/api/comments/search"

# -----------------------------
# STEP 1: FETCH RANDOM POSTS
# -----------------------------
print("Fetching RANDOM posts...")

start_ts = int(pd.Timestamp(AFTER).timestamp())
end_ts = int(pd.Timestamp(BEFORE).timestamp())

all_posts = []
seen_ids = set()

while len(all_posts) < POST_LIMIT:
    # random timestamp
    rand_ts = random.randint(start_ts, end_ts)

    params = {
        "subreddit": SUBREDDIT,
        "after": rand_ts,
        "before": rand_ts + 43200,  # 12-hour window
        "limit": 100,
        "sort": "desc",
        "fields": "id,title,selftext,author,created_utc,num_comments"
    }

    try:
        res = requests.get(BASE_POSTS, params=params)
        data = res.json().get("data", [])
    except:
        continue

    if not data:
        continue

    for post in data:
        if post["id"] not in seen_ids:
            all_posts.append(post)
            seen_ids.add(post["id"])

            if len(all_posts) >= POST_LIMIT:
                break

    print(f"Collected posts: {len(all_posts)}")

    time.sleep(0.5)

df_posts = pd.DataFrame(all_posts)

print("Total posts collected:", len(df_posts))


# -----------------------------
# STEP 2: FETCH COMMENTS
# -----------------------------
all_comments = []

print("Fetching comments...")

for i, post_id in enumerate(df_posts["id"]):
    params = {
        "link_id": post_id,
        "limit": COMMENTS_PER_POST,
        "fields": "id,body,author,link_id,created_utc"
    }

    try:
        res = requests.get(BASE_COMMENTS, params=params)
        data = res.json().get("data", [])

        all_comments.extend(data)

    except:
        continue

    if i % 10 == 0:
        print(f"Processed {i} posts, comments collected: {len(all_comments)}")

    time.sleep(0.2)

df_comments = pd.DataFrame(all_comments)

print("Total comments collected:", len(df_comments))


# -----------------------------
# STEP 3: CLEAN IDS
# -----------------------------
if not df_comments.empty:
    df_comments["post_id"] = df_comments["link_id"].str.replace("t3_", "", regex=False)


# -----------------------------
# STEP 4: CREATE DATABASE
# -----------------------------
print("Saving to SQLite database...")

conn = sqlite3.connect("career.db")

df_posts.to_sql("posts", conn, if_exists="replace", index=False)
df_comments.to_sql("comments", conn, if_exists="replace", index=False)

conn.commit()
conn.close()

print("Database created: career.db")