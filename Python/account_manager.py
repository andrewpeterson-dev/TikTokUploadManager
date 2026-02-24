#!/usr/bin/env python3
"""
TikTok Account Manager
Manages multiple accounts, tracks performance, and handles posting queues.

Note: This doesn't use TikTok's official API (which requires business verification).
Instead, it manages account metadata and integrates with manual posting or
third-party scheduling tools.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class Account:
    """TikTok account representation"""
    id: str
    username: str
    display_name: str
    niche: str
    bio: str
    status: str  # created, aging, active, monetized, banned
    created_at: str
    topics: List[str]
    hashtags: List[str]

    # Posting config
    posts_per_day: int = 5
    best_hours: List[int] = None
    timezone: str = "America/New_York"

    # Stats
    followers: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_posts: int = 0
    engagement_rate: float = 0.0

    # Internal tracking
    last_post: str = None
    notes: List[str] = None

    def __post_init__(self):
        if self.best_hours is None:
            self.best_hours = [9, 12, 15, 18, 21]
        if self.notes is None:
            self.notes = []


@dataclass
class Post:
    """Posted clip tracking"""
    id: str
    account_id: str
    clip_path: str
    source_video: str
    posted_at: str
    caption: str
    hashtags: List[str]

    # Performance
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0

    # Status
    status: str = "queued"  # queued, posted, viral, removed

    def engagement(self) -> float:
        if self.views == 0:
            return 0
        return (self.likes + self.comments + self.shares) / self.views * 100


class AccountManager:
    """Manage multiple TikTok accounts"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to TikTokUploadManager/data/accounts.db
            base_dir = Path(__file__).parent.parent
            db_path = base_dir / "data" / "accounts.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Accounts table
        c.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                display_name TEXT,
                niche TEXT,
                bio TEXT,
                status TEXT,
                created_at TEXT,
                topics TEXT,
                hashtags TEXT,
                posts_per_day INTEGER,
                best_hours TEXT,
                timezone TEXT,
                followers INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_posts INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0,
                last_post TEXT,
                notes TEXT
            )
        """)

        # Posts table
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                account_id TEXT,
                clip_path TEXT,
                source_video TEXT,
                posted_at TEXT,
                caption TEXT,
                hashtags TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)

        # Posting queue
        c.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                clip_path TEXT,
                caption TEXT,
                hashtags TEXT,
                scheduled_time TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)

        # Performance history
        c.execute("""
            CREATE TABLE IF NOT EXISTS stats_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                date TEXT,
                followers INTEGER,
                views INTEGER,
                likes INTEGER,
                posts INTEGER,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)

        conn.commit()
        conn.close()

    def add_account(self, account: Account) -> bool:
        """Add a new account"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute("""
                INSERT INTO accounts
                (id, username, display_name, niche, bio, status, created_at,
                 topics, hashtags, posts_per_day, best_hours, timezone,
                 followers, total_views, total_likes, total_posts,
                 engagement_rate, last_post, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account.id, account.username, account.display_name,
                account.niche, account.bio, account.status, account.created_at,
                json.dumps(account.topics), json.dumps(account.hashtags),
                account.posts_per_day, json.dumps(account.best_hours),
                account.timezone, account.followers, account.total_views,
                account.total_likes, account.total_posts, account.engagement_rate,
                account.last_post, json.dumps(account.notes)
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = c.fetchone()
        conn.close()

        if row:
            return self._row_to_account(row)
        return None

    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Get account by username"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM accounts WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()

        if row:
            return self._row_to_account(row)
        return None

    def _row_to_account(self, row) -> Account:
        """Convert database row to Account object"""
        return Account(
            id=row[0],
            username=row[1],
            display_name=row[2],
            niche=row[3],
            bio=row[4],
            status=row[5],
            created_at=row[6],
            topics=json.loads(row[7]) if row[7] else [],
            hashtags=json.loads(row[8]) if row[8] else [],
            posts_per_day=row[9],
            best_hours=json.loads(row[10]) if row[10] else [9, 12, 18, 21],
            timezone=row[11],
            followers=row[12],
            total_views=row[13],
            total_likes=row[14],
            total_posts=row[15],
            engagement_rate=row[16],
            last_post=row[17],
            notes=json.loads(row[18]) if row[18] else []
        )

    def get_all_accounts(self, status: str = None) -> List[Account]:
        """Get all accounts, optionally filtered by status"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if status:
            c.execute("SELECT * FROM accounts WHERE status = ?", (status,))
        else:
            c.execute("SELECT * FROM accounts")

        rows = c.fetchall()
        conn.close()

        return [self._row_to_account(row) for row in rows]

    def get_accounts_by_niche(self, niche: str) -> List[Account]:
        """Get accounts for a specific niche"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM accounts WHERE niche = ?", (niche,))
        rows = c.fetchall()
        conn.close()

        return [self._row_to_account(row) for row in rows]

    def update_account_stats(self, account_id: str, followers: int = None,
                             views: int = None, likes: int = None) -> bool:
        """Update account statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        updates = []
        values = []

        if followers is not None:
            updates.append("followers = ?")
            values.append(followers)
        if views is not None:
            updates.append("total_views = ?")
            values.append(views)
        if likes is not None:
            updates.append("total_likes = ?")
            values.append(likes)

        if not updates:
            return False

        values.append(account_id)
        query = f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?"

        c.execute(query, values)
        conn.commit()
        conn.close()

        # Record history
        self._record_stats(account_id, followers, views, likes)

        return True

    def update_account_status(self, account_id: str, status: str) -> bool:
        """Update account status"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))
        conn.commit()
        result = c.rowcount > 0
        conn.close()

        return result

    def _record_stats(self, account_id: str, followers: int, views: int, likes: int):
        """Record daily stats for trending analysis"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")

        # Check if we already have today's entry
        c.execute("""
            SELECT id FROM stats_history
            WHERE account_id = ? AND date = ?
        """, (account_id, today))

        if c.fetchone():
            # Update existing
            c.execute("""
                UPDATE stats_history
                SET followers = ?, views = ?, likes = ?
                WHERE account_id = ? AND date = ?
            """, (followers, views, likes, account_id, today))
        else:
            # Insert new
            c.execute("""
                INSERT INTO stats_history (account_id, date, followers, views, likes, posts)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (account_id, today, followers, views, likes))

        conn.commit()
        conn.close()

    def add_post(self, post: Post) -> bool:
        """Record a posted clip"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute("""
                INSERT INTO posts
                (id, account_id, clip_path, source_video, posted_at, caption,
                 hashtags, views, likes, comments, shares, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.id, post.account_id, post.clip_path, post.source_video,
                post.posted_at, post.caption, json.dumps(post.hashtags),
                post.views, post.likes, post.comments, post.shares, post.status
            ))

            # Update account post count
            c.execute("""
                UPDATE accounts
                SET total_posts = total_posts + 1, last_post = ?
                WHERE id = ?
            """, (post.posted_at, post.account_id))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding post: {e}")
            return False
        finally:
            conn.close()

    def get_posts(self, account_id: str = None, limit: int = 50) -> List[Post]:
        """Get posts, optionally filtered by account"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if account_id:
            c.execute("""
                SELECT * FROM posts WHERE account_id = ?
                ORDER BY posted_at DESC LIMIT ?
            """, (account_id, limit))
        else:
            c.execute("""
                SELECT * FROM posts ORDER BY posted_at DESC LIMIT ?
            """, (limit,))

        rows = c.fetchall()
        conn.close()

        posts = []
        for row in rows:
            posts.append(Post(
                id=row[0],
                account_id=row[1],
                clip_path=row[2],
                source_video=row[3],
                posted_at=row[4],
                caption=row[5],
                hashtags=json.loads(row[6]) if row[6] else [],
                views=row[7],
                likes=row[8],
                comments=row[9],
                shares=row[10],
                status=row[11]
            ))

        return posts

    def update_post_stats(self, post_id: str, views: int = None, likes: int = None,
                          comments: int = None, shares: int = None) -> bool:
        """Update post performance metrics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        updates = []
        values = []

        if views is not None:
            updates.append("views = ?")
            values.append(views)
        if likes is not None:
            updates.append("likes = ?")
            values.append(likes)
        if comments is not None:
            updates.append("comments = ?")
            values.append(comments)
        if shares is not None:
            updates.append("shares = ?")
            values.append(shares)

        if not updates:
            return False

        values.append(post_id)
        query = f"UPDATE posts SET {', '.join(updates)} WHERE id = ?"

        c.execute(query, values)
        conn.commit()
        conn.close()

        return True

    def queue_post(self, account_id: str, clip_path: str, caption: str,
                   hashtags: List[str], scheduled_time: datetime = None) -> int:
        """Add a clip to the posting queue"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if scheduled_time is None:
            scheduled_time = self._get_next_slot(account_id)

        c.execute("""
            INSERT INTO queue (account_id, clip_path, caption, hashtags,
                              scheduled_time, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            account_id, clip_path, caption, json.dumps(hashtags),
            scheduled_time.isoformat(), datetime.now().isoformat()
        ))

        queue_id = c.lastrowid
        conn.commit()
        conn.close()

        return queue_id

    def _get_next_slot(self, account_id: str) -> datetime:
        """Calculate next available posting slot for account"""
        account = self.get_account(account_id)
        if not account:
            return datetime.now() + timedelta(hours=1)

        # Get last scheduled time
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            SELECT MAX(scheduled_time) FROM queue
            WHERE account_id = ? AND status = 'pending'
        """, (account_id,))

        result = c.fetchone()
        conn.close()

        if result[0]:
            last_scheduled = datetime.fromisoformat(result[0])
        else:
            last_scheduled = datetime.now()

        # Calculate gap between posts (spread across day)
        posts_per_day = account.posts_per_day or 5
        hours_between = 24 / posts_per_day

        next_slot = last_scheduled + timedelta(hours=hours_between)

        # Align to best posting hours if possible
        if account.best_hours:
            target_hour = min(account.best_hours, key=lambda h: abs(h - next_slot.hour))
            next_slot = next_slot.replace(hour=target_hour, minute=0)

        return next_slot

    def get_pending_posts(self, account_id: str = None) -> List[dict]:
        """Get pending queued posts"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if account_id:
            c.execute("""
                SELECT * FROM queue WHERE account_id = ? AND status = 'pending'
                ORDER BY scheduled_time
            """, (account_id,))
        else:
            c.execute("""
                SELECT * FROM queue WHERE status = 'pending'
                ORDER BY scheduled_time
            """)

        rows = c.fetchall()
        conn.close()

        return [{
            "id": row[0],
            "account_id": row[1],
            "clip_path": row[2],
            "caption": row[3],
            "hashtags": json.loads(row[4]) if row[4] else [],
            "scheduled_time": row[5],
            "status": row[6],
            "created_at": row[7]
        } for row in rows]

    def get_due_posts(self) -> List[dict]:
        """Get posts that are due for posting (scheduled time passed)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = datetime.now().isoformat()

        c.execute("""
            SELECT q.*, a.username, a.display_name
            FROM queue q
            JOIN accounts a ON q.account_id = a.id
            WHERE q.status = 'pending' AND q.scheduled_time <= ?
            ORDER BY q.scheduled_time
        """, (now,))

        rows = c.fetchall()
        conn.close()

        return [{
            "id": row[0],
            "account_id": row[1],
            "clip_path": row[2],
            "caption": row[3],
            "hashtags": json.loads(row[4]) if row[4] else [],
            "scheduled_time": row[5],
            "status": row[6],
            "username": row[8],
            "display_name": row[9]
        } for row in rows]

    def mark_posted(self, queue_id: int, post_id: str = None) -> bool:
        """Mark a queued post as posted"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            UPDATE queue SET status = 'posted' WHERE id = ?
        """, (queue_id,))

        conn.commit()
        result = c.rowcount > 0
        conn.close()

        return result

    def get_analytics(self, account_id: str = None, days: int = 30) -> dict:
        """Get analytics summary"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        if account_id:
            # Single account analytics
            c.execute("""
                SELECT SUM(views), SUM(likes), SUM(comments), SUM(shares), COUNT(*)
                FROM posts
                WHERE account_id = ? AND posted_at >= ?
            """, (account_id, cutoff))

            row = c.fetchone()

            # Get growth
            c.execute("""
                SELECT followers FROM stats_history
                WHERE account_id = ?
                ORDER BY date DESC LIMIT 2
            """, (account_id,))

            follower_rows = c.fetchall()
            growth = 0
            if len(follower_rows) >= 2:
                growth = follower_rows[0][0] - follower_rows[1][0]

            conn.close()

            return {
                "total_views": row[0] or 0,
                "total_likes": row[1] or 0,
                "total_comments": row[2] or 0,
                "total_shares": row[3] or 0,
                "post_count": row[4] or 0,
                "follower_growth": growth
            }
        else:
            # All accounts
            c.execute("""
                SELECT SUM(views), SUM(likes), COUNT(DISTINCT account_id), COUNT(*)
                FROM posts
                WHERE posted_at >= ?
            """, (cutoff,))

            row = c.fetchone()
            conn.close()

            return {
                "total_views": row[0] or 0,
                "total_likes": row[1] or 0,
                "active_accounts": row[2] or 0,
                "total_posts": row[3] or 0
            }

    def get_top_performers(self, metric: str = "views", limit: int = 10) -> List[dict]:
        """Get top performing posts"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        valid_metrics = ["views", "likes", "comments", "shares"]
        if metric not in valid_metrics:
            metric = "views"

        c.execute(f"""
            SELECT p.*, a.username, a.display_name
            FROM posts p
            JOIN accounts a ON p.account_id = a.id
            ORDER BY p.{metric} DESC
            LIMIT ?
        """, (limit,))

        rows = c.fetchall()
        conn.close()

        return [{
            "post_id": row[0],
            "account": row[12],  # username
            "clip_path": row[2],
            "views": row[7],
            "likes": row[8],
            "comments": row[9],
            "shares": row[10],
            "posted_at": row[4]
        } for row in rows]

    def import_personas(self, personas_file: str):
        """Import personas from persona generator"""
        with open(personas_file) as f:
            personas = json.load(f)

        for p in personas:
            account = Account(
                id=p["id"],
                username=p["username"],
                display_name=p["display_name"],
                niche=p["niche"],
                bio=p["bio"],
                status=p.get("status", "created"),
                created_at=p.get("created_at", datetime.now().isoformat()),
                topics=p.get("topics", []),
                hashtags=p.get("hashtags", []),
                posts_per_day=p.get("posting_schedule", {}).get("posts_per_day", 5),
                best_hours=p.get("posting_schedule", {}).get("best_hours", [9, 12, 18, 21]),
                timezone=p.get("posting_schedule", {}).get("timezone", "America/New_York"),
                followers=p.get("followers", 0),
                total_views=p.get("total_views", 0),
                total_likes=0,
                total_posts=p.get("total_posts", 0)
            )

            self.add_account(account)

        return len(personas)


def print_dashboard(manager: AccountManager):
    """Print account management dashboard"""
    accounts = manager.get_all_accounts()
    analytics = manager.get_analytics()

    print("\n" + "="*70)
    print("CLIP EMPIRE - ACCOUNT DASHBOARD")
    print("="*70)

    print(f"\nOverall Stats (Last 30 Days):")
    print(f"  Total Views:    {analytics['total_views']:,}")
    print(f"  Total Likes:    {analytics['total_likes']:,}")
    print(f"  Active Accounts: {analytics['active_accounts']}")
    print(f"  Total Posts:    {analytics['total_posts']}")

    print(f"\n{'='*70}")
    print(f"ACCOUNTS ({len(accounts)})")
    print("="*70)

    status_counts = {}
    for acc in accounts:
        status_counts[acc.status] = status_counts.get(acc.status, 0) + 1

    print(f"\nBy Status: {status_counts}")

    print(f"\n{'Username':<25} {'Niche':<20} {'Followers':>10} {'Posts':>8} {'Status':<12}")
    print("-"*70)

    for acc in sorted(accounts, key=lambda x: x.followers, reverse=True)[:20]:
        print(f"{acc.username:<25} {acc.niche:<20} {acc.followers:>10,} {acc.total_posts:>8} {acc.status:<12}")

    # Show queue status
    due_posts = manager.get_due_posts()
    if due_posts:
        print(f"\n{'='*70}")
        print(f"DUE FOR POSTING ({len(due_posts)})")
        print("="*70)
        for post in due_posts[:5]:
            print(f"  @{post['username']}: {Path(post['clip_path']).name}")

    # Top performers
    top = manager.get_top_performers(limit=5)
    if top:
        print(f"\n{'='*70}")
        print("TOP PERFORMERS")
        print("="*70)
        for p in top:
            print(f"  @{p['account']}: {p['views']:,} views, {p['likes']:,} likes")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TikTok Account Manager")
    parser.add_argument("--import", "-i", dest="import_file", help="Import personas file")
    parser.add_argument("--list", "-l", action="store_true", help="List all accounts")
    parser.add_argument("--niche", "-n", help="Filter by niche")
    parser.add_argument("--dashboard", "-d", action="store_true", help="Show dashboard")
    parser.add_argument("--due", action="store_true", help="Show posts due for posting")

    args = parser.parse_args()

    manager = AccountManager()

    if args.import_file:
        count = manager.import_personas(args.import_file)
        print(f"Imported {count} personas")

    elif args.list:
        accounts = manager.get_all_accounts()
        if args.niche:
            accounts = [a for a in accounts if a.niche == args.niche]

        for acc in accounts:
            print(f"@{acc.username} ({acc.niche}) - {acc.status} - {acc.followers} followers")

    elif args.due:
        due = manager.get_due_posts()
        print(f"\nDue for posting ({len(due)}):")
        for post in due:
            print(f"  @{post['username']}: {post['clip_path']}")
            print(f"    Scheduled: {post['scheduled_time']}")

    elif args.dashboard:
        print_dashboard(manager)

    else:
        print_dashboard(manager)
