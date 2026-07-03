import os
import sys
import time
import logging
import requests
import instaloader
from feedgen.feed import FeedGenerator
from datetime import timezone

# ---- Config ----
TARGET_USERNAME = os.environ["TARGET_USERNAME"]
THROWAWAY_USERNAME = os.environ["THROWAWAY_USERNAME"]
OUTPUT_PATH = "docs/feed.xml"
POST_LIMIT = 15
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("insta-rss")


def notify_discord_failure(error_message: str):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("No DISCORD_WEBHOOK_URL set, skipping failure notification")
        return

    payload = {
        "content": (
            f"⚠️ **Instagram RSS feed generator failed**\n"
            f"Target: `{TARGET_USERNAME}`\n"
            f"Error: ```{error_message[:1500]}```"
        )
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Sent failure notification to Discord")
    except Exception as e:
        log.error(f"Failed to send Discord notification: {e}")


def build_session(loader: instaloader.Instaloader):
    sessionid = os.environ["IG_SESSIONID"]
    ds_user_id = os.environ["IG_DS_USER_ID"]
    loader.context._session.cookies.update({
        "sessionid": sessionid,
        "ds_user_id": ds_user_id,
    })
    loader.context.username = THROWAWAY_USERNAME


def fetch_posts_with_retry():
    last_exception = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"Attempt {attempt}/{MAX_RETRIES}: fetching posts for {TARGET_USERNAME}")
            loader = instaloader.Instaloader()
            build_session(loader)
            profile = instaloader.Profile.from_username(loader.context, TARGET_USERNAME)
            posts = []
            for i, post in enumerate(profile.get_posts()):
                if i >= POST_LIMIT:
                    break
                posts.append(post)
            log.info(f"Successfully fetched {len(posts)} posts")
            return posts
        except instaloader.exceptions.ConnectionException as e:
            last_exception = e
            log.warning(f"Connection/rate-limit error on attempt {attempt}: {e}")
        except instaloader.exceptions.ProfileNotExistsException as e:
            # Not worth retrying — the profile name is wrong, fail immediately
            raise RuntimeError(f"Profile '{TARGET_USERNAME}' does not exist: {e}")
        except Exception as e:
            last_exception = e
            log.warning(f"Unexpected error on attempt {attempt}: {e}")

        if attempt < MAX_RETRIES:
            log.info(f"Retrying in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"All {MAX_RETRIES} attempts failed. Last error: {last_exception}")


def build_feed(posts):
    fg = FeedGenerator()
    fg.title(f"{TARGET_USERNAME} - Instagram")
    fg.link(href=f"https://www.instagram.com/{TARGET_USERNAME}/", rel="alternate")
    fg.description(f"Latest posts from {TARGET_USERNAME}")

    for post in posts:
        fe = fg.add_entry()
        fe.id(post.shortcode)
        fe.title(post.caption[:80] if post.caption else post.shortcode)
        fe.link(href=f"https://www.instagram.com/p/{post.shortcode}/")
        fe.description(post.caption or "")
        fe.pubDate(post.date_utc.replace(tzinfo=timezone.utc))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fg.rss_file(OUTPUT_PATH)
    log.info(f"Wrote {len(posts)} posts to {OUTPUT_PATH}")


def main():
    try:
        posts = fetch_posts_with_retry()
        build_feed(posts)
    except Exception as e:
        log.error(f"Feed generation failed: {e}")
        notify_discord_failure(str(e))
        sys.exit(1)  # non-zero exit fails the Action step


if __name__ == "__main__":
    main()
