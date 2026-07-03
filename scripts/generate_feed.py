import os
import instaloader
from feedgen.feed import FeedGenerator
from datetime import timezone

TARGET_USERNAME = "the_instagram_username_you_want"  # no @ symbol
OUTPUT_PATH = "docs/feed.xml"
POST_LIMIT = 15

def build_session(loader: instaloader.Instaloader):
    sessionid = os.environ["IG_SESSIONID"]
    ds_user_id = os.environ["IG_DS_USER_ID"]
    loader.context._session.cookies.update({
        "sessionid": sessionid,
        "ds_user_id": ds_user_id,
    })
    loader.context.username = "your_throwaway_username"

def main():
    loader = instaloader.Instaloader()
    build_session(loader)

    profile = instaloader.Profile.from_username(loader.context, TARGET_USERNAME)

    fg = FeedGenerator()
    fg.title(f"{TARGET_USERNAME} - Instagram")
    fg.link(href=f"https://www.instagram.com/{TARGET_USERNAME}/", rel="alternate")
    fg.description(f"Latest posts from {TARGET_USERNAME}")

    for i, post in enumerate(profile.get_posts()):
        if i >= POST_LIMIT:
            break
        fe = fg.add_entry()
        fe.id(post.shortcode)
        fe.title(post.caption[:80] if post.caption else post.shortcode)
        fe.link(href=f"https://www.instagram.com/p/{post.shortcode}/")
        fe.description(post.caption or "")
        fe.pubDate(post.date_utc.replace(tzinfo=timezone.utc))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fg.rss_file(OUTPUT_PATH)
    print(f"Wrote {POST_LIMIT} posts to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
