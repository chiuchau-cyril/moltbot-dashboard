#!/usr/bin/env python3
"""
Moltbot Analytics - Data Collector
Collects Reddit and GitHub stats for the dashboard
"""

import json
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Configuration
SUBREDDITS = ['clawdbot', 'moltbot', 'moltbothub', 'moltbothq', 'moltbotcommunity']
GITHUB_REPO = 'anthropics/claude-code'
DATA_FILE = Path(__file__).parent / 'data.json'
HISTORY_FILE = Path(__file__).parent / 'history.json'

# Timezone
TZ = timezone(timedelta(hours=8))  # GMT+8


def fetch_subreddit_stats(subreddit: str) -> dict:
    """Fetch stats for a subreddit using public JSON endpoint"""
    try:
        # About endpoint for subscriber count
        about_url = f'https://www.reddit.com/r/{subreddit}/about.json'
        headers = {'User-Agent': 'MoltbotAnalytics/1.0'}
        
        resp = requests.get(about_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ r/{subreddit} about: HTTP {resp.status_code}")
            return None
            
        about = resp.json().get('data', {})
        
        # Hot posts for activity metrics
        hot_url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit=100'
        resp = requests.get(hot_url, headers=headers, timeout=10)
        posts_data = resp.json().get('data', {}).get('children', []) if resp.status_code == 200 else []
        
        # Calculate 24h stats
        now = datetime.now(timezone.utc).timestamp()
        day_ago = now - 86400
        
        posts_24h = 0
        comments_24h = 0
        upvotes_24h = 0
        top_score = 0
        
        for post in posts_data:
            p = post.get('data', {})
            created = p.get('created_utc', 0)
            if created > day_ago:
                posts_24h += 1
                comments_24h += p.get('num_comments', 0)
                score = p.get('score', 0)
                upvotes_24h += score
                top_score = max(top_score, score)
        
        return {
            'name': f'r/{subreddit}',
            'key': subreddit,
            'subscribers': about.get('subscribers', 0),
            'active': about.get('accounts_active', 0) or 0,
            'posts_24h': posts_24h,
            'comments': comments_24h,
            'avg_score': round(upvotes_24h / max(posts_24h, 1)),
            'total_upvotes': upvotes_24h,
            'top_score': top_score
        }
        
    except Exception as e:
        print(f"  ❌ r/{subreddit}: {e}")
        return None


def fetch_github_stats() -> dict:
    """Fetch GitHub repo stats"""
    try:
        url = f'https://api.github.com/repos/{GITHUB_REPO}'
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ GitHub: HTTP {resp.status_code}")
            return None
            
        data = resp.json()
        return {
            'stars': data.get('stargazers_count', 0),
            'forks': data.get('forks_count', 0),
            'open_issues': data.get('open_issues_count', 0)
        }
    except Exception as e:
        print(f"  ❌ GitHub: {e}")
        return None


def load_history() -> list:
    """Load history data"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def load_previous_data() -> dict:
    """Load previous data for delta calculation"""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def collect_all_stats():
    """Collect all stats and update files"""
    print(f"🦞 Moltbot Analytics - Collecting stats...")
    print(f"   {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load previous data for deltas
    prev = load_previous_data()
    prev_reddit = prev.get('reddit', {})
    prev_github = prev.get('github', {})
    
    # Collect Reddit stats
    print("\n📱 Reddit:")
    subreddit_stats = []
    total_subs = 0
    total_active = 0
    total_posts = 0
    total_comments = 0
    total_upvotes = 0
    
    for sub in SUBREDDITS:
        stats = fetch_subreddit_stats(sub)
        if stats:
            subreddit_stats.append(stats)
            total_subs += stats['subscribers']
            total_active += stats['active']
            total_posts += stats['posts_24h']
            total_comments += stats['comments']
            total_upvotes += stats['total_upvotes']
            print(f"  ✅ r/{sub}: {stats['subscribers']:,} subs, {stats['posts_24h']} posts/24h")
    
    # Collect GitHub stats
    print("\n🐙 GitHub:")
    github = fetch_github_stats()
    if github:
        print(f"  ✅ {GITHUB_REPO}: ⭐ {github['stars']:,} | 🍴 {github['forks']:,}")
    else:
        github = {'stars': 0, 'forks': 0, 'open_issues': 0}
    
    # Build data object
    now = datetime.now(TZ)
    now_utc = datetime.now(timezone.utc)
    
    data = {
        'timestamp': now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'timestamp_local': now.strftime('%Y-%m-%d %H:%M:%S'),
        'data_points': len(load_history()) + 1,
        'reddit': {
            'total_subscribers': total_subs,
            'delta_subscribers': total_subs - prev_reddit.get('total_subscribers', total_subs),
            'total_active': total_active,
            'total_posts_24h': total_posts,
            'total_comments': total_comments,
            'total_upvotes': total_upvotes,
            'subreddits': subreddit_stats
        },
        'github': {
            'stars': github['stars'],
            'stars_delta': github['stars'] - prev_github.get('stars', github['stars']),
            'forks': github['forks'],
            'forks_delta': github['forks'] - prev_github.get('forks', github['forks']),
            'open_issues': github['open_issues']
        }
    }
    
    # Save current data
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Saved data.json")
    
    # Append to history
    history = load_history()
    history_entry = {
        'timestamp': now.isoformat(),
        'time_local': now.strftime('%m/%d %H:%M'),
        'reddit_total': total_subs,
        'reddit_active': total_active,
        'reddit_posts': total_posts,
        'reddit_comments': total_comments,
        'reddit_upvotes': total_upvotes,
    }
    
    # Add per-subreddit data
    for stats in subreddit_stats:
        key = stats['key']
        history_entry[f'{key}_subs'] = stats['subscribers']
        history_entry[f'{key}_active'] = stats['active']
        history_entry[f'{key}_posts'] = stats['posts_24h']
        history_entry[f'{key}_upvotes'] = stats['total_upvotes']
        history_entry[f'{key}_comments'] = stats['comments']
    
    history_entry['github_stars'] = github['stars']
    history_entry['github_forks'] = github['forks']
    history_entry['github_issues'] = github['open_issues']
    
    history.append(history_entry)
    
    # Keep only last 1000 entries
    if len(history) > 1000:
        history = history[-1000:]
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    print(f"📊 Updated history.json ({len(history)} entries)")
    
    return data


def git_push():
    """Commit and push changes"""
    try:
        repo_dir = Path(__file__).parent
        now = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        subprocess.run(['git', 'add', '-A'], cwd=repo_dir, check=True)
        subprocess.run(['git', 'commit', '-m', f'Update {now}'], cwd=repo_dir, check=True)
        subprocess.run(['git', 'push'], cwd=repo_dir, check=True)
        print(f"🚀 Pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git push failed: {e}")
        return False


if __name__ == '__main__':
    collect_all_stats()
    git_push()
