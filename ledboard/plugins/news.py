
import os
import re
import time
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont

from plugin_base import BasePlugin


class NewsPlugin(BasePlugin):
    name = "news"
    refresh_seconds = 300
    display_seconds = 40  # long enough to cycle 4 stories at 10s each

    def __init__(self, app_context):
        super().__init__(app_context)

        self.api_token = os.environ["WEBZIO_TOKEN"]
        self.base_url = os.environ.get("WEBZIO_URL", "https://api.webz.io/newsApiLite")

        # Separate US and international feeds. We prefer US overall, but guarantee
        # at least one international story in the final top 4.
        self.us_queries = [
            os.environ.get("WEBZIO_QUERY_US_1", "election OR court ruling OR protest OR executive order"),
            os.environ.get("WEBZIO_QUERY_US_2", "shooting OR wildfire OR flood OR crash OR explosion"),
            os.environ.get("WEBZIO_QUERY_US_3", "attack OR strike OR missile OR drone"),
        ]
        self.world_queries = [
            os.environ.get("WEBZIO_QUERY_WORLD_1", "war OR invasion OR ceasefire OR coup"),
            os.environ.get("WEBZIO_QUERY_WORLD_2", "earthquake OR flood OR wildfire OR explosion OR crash"),
            os.environ.get("WEBZIO_QUERY_WORLD_3", "attack OR strike OR missile OR drone"),
        ]

        self.story_seconds = int(os.environ.get("NEWS_STORY_SECONDS", "10"))
        self.max_title_chars = int(os.environ.get("NEWS_MAX_TITLE_CHARS", "140"))
        self.per_query_size = int(os.environ.get("NEWS_PER_QUERY_SIZE", "8"))

        self.state = {
            "stories": [],
            "error": "",
        }

    def refresh(self):
        us_stories = self._fetch_group(self.us_queries, region="US")
        world_stories = self._fetch_group(self.world_queries, region="WORLD")

        if not us_stories and not world_stories:
            self.state = {"stories": [], "error": "No headlines"}
            super().refresh()
            return

        us_stories = self._dedupe(us_stories)
        world_stories = self._dedupe(world_stories)

        us_stories.sort(key=lambda s: (-s["score"], s["age"], s["title"]))
        world_stories.sort(key=lambda s: (-s["score"], s["age"], s["title"]))

        selected = self._select_top_four(us_stories, world_stories)

        self.state = {
            "stories": selected,
            "error": "",
        }
        super().refresh()

    def _fetch_group(self, queries, region):
        stories = []
        for query in queries:
            try:
                posts = self._run_query(query, self.per_query_size)
            except Exception:
                continue

            for post in posts:
                story = self._story_from_post(post, region)
                if story:
                    stories.append(story)
        return stories

    def _run_query(self, query, size):
        resp = requests.get(
            self.base_url,
            params={"token": self.api_token, "q": query, "size": size},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("posts", [])

    def _story_from_post(self, post, region):
        thread = post.get("thread", {}) or {}
        title = post.get("title") or thread.get("title") or ""
        if not title:
            return None

        country = (thread.get("country") or "").upper()

        if region == "US" and country and country != "US":
            return None
        if region == "WORLD" and country == "US":
            return None

        title = self._clean(title)
        if not title:
            return None

        lang = (post.get("language") or "").lower()
        if lang and lang != "english":
            return None

        published = post.get("published") or thread.get("published") or ""
        age = self._age_minutes(published)
        age = age if age is not None else 999999

        score = 0

        # Recency matters most
        if age < 30:
            score += 40
        elif age < 60:
            score += 32
        elif age < 180:
            score += 22
        elif age < 720:
            score += 12
        elif age < 1440:
            score += 6

        lower = title.lower()

        # Favor change/event headlines over analysis
        change_words = [
            "attack", "strike", "missile", "drone", "bomb", "killed", "dead",
            "injured", "crash", "fire", "earthquake", "flood", "evacuat",
            "ruling", "rules", "blocks", "orders", "ceasefire", "coup",
            "protest", "rescued", "downed", "explosion", "shooting",
            "warning", "ultimatum", "raid", "shelling", "airstrike",
            "declares emergency", "hostage", "tariffs", "ban",
        ]
        for word in change_words:
            if word in lower:
                score += 5

        # Penalize softer commentary-style headlines a bit
        soft_words = ["analysis", "opinion", "live updates", "what to know", "explainer"]
        for word in soft_words:
            if word in lower:
                score -= 8

        # Shorter, cleaner headlines usually read better on panel
        if len(title) <= 80:
            score += 8
        elif len(title) <= 110:
            score += 4

        # Prefer US overall
        if region == "US":
            score += 10

        return {
            "title": title[: self.max_title_chars].strip(),
            "age": age,
            "score": score,
            "region": region,
        }

    def _select_top_four(self, us_stories, world_stories):
        selected = []

        # Guarantee at least one international story if available.
        if world_stories:
            selected.append(world_stories[0])

        # Fill primarily from US.
        for story in us_stories:
            if len(selected) >= 4:
                break
            if not self._already_have(selected, story):
                selected.append(story)

        # Then fill remaining slots from world.
        for story in world_stories:
            if len(selected) >= 4:
                break
            if not self._already_have(selected, story):
                selected.append(story)

        # Final sort by score, but keep at least one world story present.
        selected.sort(key=lambda s: (-s["score"], s["age"], s["title"]))
        if world_stories and not any(s["region"] == "WORLD" for s in selected[:4]):
            if len(selected) >= 4:
                selected[-1] = world_stories[0]
            else:
                selected.append(world_stories[0])

        return selected[:4]

    def _already_have(self, selected, story):
        key = self._story_key(story["title"])
        for s in selected:
            if self._story_key(s["title"]) == key:
                return True
        return False

    def _dedupe(self, stories):
        best = {}
        for story in stories:
            key = self._story_key(story["title"])
            if key not in best or story["score"] > best[key]["score"]:
                best[key] = story
        return list(best.values())

    def _story_key(self, title):
        title = title.lower()
        title = re.sub(r"[^a-z0-9\s]", " ", title)
        stop = {
            "the", "and", "for", "with", "from", "that", "this", "after",
            "amid", "says", "say", "into", "over", "about", "live", "breaking",
            "update", "updates", "new"
        }
        words = [w for w in title.split() if len(w) > 2 and w not in stop]
        return " ".join(words[:8])

    def _clean(self, title):
        title = " ".join(str(title).split())
        title = re.sub(r"^(BREAKING|LIVE|UPDATES?):\s*", "", title, flags=re.IGNORECASE)
        for suffix in [
            " - Yahoo News Canada",
            " - Yahoo News UK",
            " - Yahoo Canada",
            " - Yahoo",
        ]:
            if title.endswith(suffix):
                title = title[: -len(suffix)].rstrip()
        return title.strip(" -:")

    def _age_minutes(self, published):
        if not published:
            return None
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return max(0, int((now - dt.astimezone(timezone.utc)).total_seconds() // 60))
        except Exception:
            return None

    def _load_first_font(self, size):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _load_fonts(self):
        return (
            self._load_first_font(14),
            self._load_first_font(13),
        )

    def _truncate_line(self, draw, text, font, max_width):
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text
        ellipsis = "…"
        lo, hi = 0, len(text)
        best = ellipsis
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = text[:mid].rstrip() + ellipsis
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def _wrap_text(self, draw, text, font, max_width, max_lines):
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = words[0]

        for word in words[1:]:
            candidate = f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines - 1:
                    break

        if len(lines) < max_lines:
            lines.append(current)

        consumed = len(" ".join(lines).split())
        if consumed < len(words):
            remainder = " ".join(words[consumed:])
            lines[-1] = self._truncate_line(draw, f"{lines[-1]} {remainder}", font, max_width)

        return lines[:max_lines]

    def _current_story_index(self):
        stories = self.state.get("stories", [])
        if not stories:
            return 0
        idx = int((time.time() - self.last_refresh) // self.story_seconds)
        return idx % len(stories)

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        font_big, font_big2 = self._load_fonts()
        draw.rectangle((0, 0, width - 1, height - 1), outline=(70, 70, 70))

        stories = self.state.get("stories", [])
        if not stories:
            draw.text((6, 24), "No news", font=font_big, fill=(200, 200, 200))
            return image

        story = stories[self._current_story_index()]
        lines = self._wrap_text(draw, story["title"], font_big2, width - 12, max_lines=4)

        # Center the headline block vertically.
        line_height = 14
        block_height = len(lines) * line_height
        y = max(4, (height - block_height) // 2)

        for line in lines:
            draw.text((6, y), line, font=font_big2, fill=(235, 235, 235))
            y += line_height

        # Tiny bottom progress dots for 4 stories.
        base_x = width // 2 - 14
        idx = self._current_story_index()
        for i in range(min(4, len(stories))):
            fill = (255, 210, 80) if i == idx else (70, 70, 70)
            draw.ellipse((base_x + i * 9, height - 7, base_x + i * 9 + 3, height - 4), fill=fill)

        return image
