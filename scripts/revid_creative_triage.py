"""Conservative creative-topic triage for personal, in-memory research.

Categories are local hypotheses, not proof of a viral trend or production method.
No upstream text is returned or persisted.
"""
import re
from collections import defaultdict

TOPICS = {
    "visual-transformation": r"\b(?:transformation|morphing|match cut|transitions?|visual effects|vfx|face swap|portal effect)\b",
    "cinematic": r"\b(?:cinematic|filmmaking|camera movement|dolly shot|one shot|long take|film trailer)\b",
    "character-ip": r"\b(?:harry potter|spider[- ]?man|superhero|character redesign|character crossover|fan film)\b",
    "advertising": r"\b(?:product commercial|product reveal|product showcase|creative ad|comedy ad|brand film|spec ad)\b",
    "storytelling": r"\b(?:animated story|storytelling|short film|plot twist|mini drama|ai story|aistory)\b",
    "seasonal": r"\b(?:christmas|black friday|cyber monday|halloween|thanksgiving|new year)\b",
}
CREATIVE = r"\b(?:video|film|animation|animated|visual|shot|scene|cinematic|story|aivideo|aistory|vfx|reel|commercial)\b"
PRICE = r"\b(?:pricing|credits?|discount|subscription|price|costs?|affordable|per second|promo code)\b|\$\s*\d"
NON_CREATIVE = r"\b(?:ai news|ai worries|ai debate|stock market|political debate|benchmark results)\b"
DEMO = r"\b(?:product reveal|visual transformation|match cut|plot twist|comedy ad|short film|animated story|fan film)\b"


def classify(row):
    """Return local category labels for plausible creative works, else empty.

    Rules intentionally favor precision; generic AI tags alone are insufficient.
    Price-led tool announcements need specific creative evidence to survive.
    """
    if not isinstance(row, dict) or row.get("isTextPost") is True:
        return ()
    style = row.get("style")
    style = style if isinstance(style, dict) else {}
    fields = [row.get("description"), row.get("summary"), row.get("hook"),
              style.get("contentType"), style.get("visualOrigin")]
    text = " ".join(v[:2000] for v in fields if isinstance(v, str)).lower()
    labels = tuple(k for k, pattern in TOPICS.items() if re.search(pattern, text))
    if not labels or not re.search(CREATIVE, text):
        return ()
    if re.search(NON_CREATIVE, text) and not re.search(DEMO, text):
        return ()
    if re.search(PRICE, text) and not re.search(DEMO, text):
        return ()
    if labels == ("seasonal",):
        return ()
    return labels


def group_topics(candidates):
    """Group by category, not a claim that different posts are the same trend.

    Original URLs are counted once per category; views are never summed.
    """
    groups = defaultdict(dict)
    for item in candidates:
        for label in item.get("creativeTopics", ()):
            if label in TOPICS and item.get("url"):
                groups[label].setdefault(item["url"], item)
    return [{"topic": label, "distinctPosts": len(posts),
             "platforms": sorted({item["platform"] for item in posts.values()}),
             "posts": sorted(posts.values(), key=lambda v: v["views"], reverse=True)}
            for label, posts in sorted(groups.items())]
