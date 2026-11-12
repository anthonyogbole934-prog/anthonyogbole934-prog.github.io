#!/usr/bin/env python3
"""
Autonomous Blog Manager (100% free stack)
-----------------------------------------
Free AI (Google Gemini, OpenAI-compatible) -> writes Jekyll posts -> GitHub Pages hosts them.
GitHub Actions runs `python blog_manager.py once` every day and commits the results.

Cycle: sync traffic/revenue -> optimize (expand winners, refresh losers) -> plan topics ->
write -> quality-gate -> monetize (affiliate links, disclosure, ad slot) -> publish.
Commands: once | run | report | approve
"""
import os, sys, re, csv, json, time, sqlite3, datetime as dt
from urllib.parse import urlparse
import requests
try:
    import PIL  # noqa
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], check=False)

# ---------------- config (all optional; sensible defaults) ----------------
def cfg(k, d=""): return os.environ.get(k) or d
NICHE = cfg("BLOG_NICHE", "AI tools, software and online income ideas for freelancers, remote workers and solo business owners")
LLM_BASE = cfg("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
LLM_MODEL = cfg("LLM_MODEL", "gemini-flash-latest")
LLM_KEY = cfg("LLM_API_KEY")
POSTS_PER_DAY = int(cfg("POSTS_PER_DAY", "1"))
AUTO_PUBLISH = cfg("AUTO_PUBLISH", "true").lower() == "true"
MIN_WORDS, MIN_SCORE = int(cfg("MIN_WORDS", "1200")), 7
AD_SNIPPET = cfg("AD_SNIPPET", "")
GA4_PID = cfg("GA4_PROPERTY_ID")
repo = cfg("GITHUB_REPOSITORY", "you/blog"); owner, name = repo.split("/")
SITE = cfg("SITE_URL") or (f"https://{owner.lower()}.github.io" + ("" if name.lower() == f"{owner.lower()}.github.io" else f"/{name}"))
DATA = "data"; os.makedirs(DATA, exist_ok=True)
try: SITE = json.load(open(f"{DATA}/site.json"))["url"]  # set automatically after a domain switch
except Exception: pass

db = sqlite3.connect(f"{DATA}/blog.db"); db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, keyword TEXT UNIQUE, angle TEXT, cluster TEXT,
  status TEXT DEFAULT 'queued', created TEXT);
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, topic_id INT, title TEXT, slug TEXT, url TEXT,
  status TEXT, html TEXT, score REAL, published TEXT, refreshed TEXT, excerpt TEXT);
CREATE TABLE IF NOT EXISTS metrics(post_id INT, date TEXT, views INT DEFAULT 0, revenue REAL DEFAULT 0,
  PRIMARY KEY(post_id, date));""")
today = lambda: dt.date.today().isoformat()
log = lambda *a: print(f"[{dt.datetime.now():%H:%M:%S}]", *a, flush=True)

# ---------------- LLM (any OpenAI-compatible API; default = free Gemini) ----------------
FALLBACKS = [m.strip() for m in cfg("LLM_FALLBACK_MODELS", "gemini-flash-lite-latest").split(",") if m.strip()]

def ask(system, prompt, as_json=False, max_tokens=8000):
    models = [LLM_MODEL] + [m for m in FALLBACKS if m != LLM_MODEL]
    for attempt in range(8):
        model = models[(attempt // 2) % len(models)]  # switch to the backup model if the main one stays busy
        try:
            r = requests.post(f"{LLM_BASE}/chat/completions", timeout=240,
                headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
            if r.status_code in (429, 500, 502, 503, 504):  # busy / overloaded: wait longer and try again
                wait = min(30 * (attempt + 1), 180)
                log(f"AI busy ({r.status_code}) on {model}, waiting {wait}s"); time.sleep(wait); continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            time.sleep(4)  # stay under free-tier requests-per-minute
            if not as_json: return text
            return json.loads(re.search(r"(\{.*\}|\[.*\])", text, re.S).group(1), strict=False)
        except Exception as ex:
            log("LLM retry", attempt, model, ex); time.sleep(15)
    raise RuntimeError("LLM failed after many tries. Check LLM_API_KEY / LLM_MODEL, or run again later.")

# ---------------- strategist ----------------
def performance_summary():
    rows = db.execute("""SELECT p.title, t.cluster, SUM(m.views) v, SUM(m.revenue) r FROM posts p
        JOIN topics t ON t.id=p.topic_id LEFT JOIN metrics m ON m.post_id=p.id WHERE p.status='published'
        GROUP BY p.id ORDER BY r DESC, v DESC LIMIT 15""").fetchall()
    return "\n".join(f"- {r['title']} [{r['cluster']}] views={r['v'] or 0} rev=${r['r'] or 0:.2f}" for r in rows)

def plan_topics(n=10):
    existing = [r[0] for r in db.execute("SELECT keyword FROM topics")]
    out = ask("You are an SEO strategist for an English-language international blog. Reply with JSON only.",
        f"""Niche: {NICHE}
Existing keywords (never repeat): {existing[-80:]}
Performance so far:\n{performance_summary() or 'none yet'}
Propose {n} article topics: low-competition long-tail queries with clear search intent (comparisons,
'best X for Y', 'how to', alternatives, pricing, tutorials) that fit affiliate monetization. Audience is
global (US/UK/CA/AU/EU/Asia/Africa); avoid country-specific laws. Weight toward clusters that earn.
JSON: [{{"keyword":"","angle":"","cluster":""}}]""", as_json=True, max_tokens=3000)
    for t in out:
        db.execute("INSERT OR IGNORE INTO topics(keyword,angle,cluster,created) VALUES(?,?,?,?)",
                   (t["keyword"], t.get("angle", ""), t.get("cluster", "general"), today()))
    db.commit(); log(f"planned {len(out)} topics")

# ---------------- writer + quality gate ----------------
WRITER_SYS = """You are an expert blog writer with a clear, friendly, human voice. Rules: be accurate and genuinely
useful; NEVER invent statistics, quotes, studies, prices, features or personal experiences; if unsure, say so
or stay general and tell readers to check the official site; give honest pros AND cons for any product;
answer the search intent in the first paragraph; use H2/H3 structure, concrete examples, a short conclusion.
Do not put an FAQ in html; put 3-5 FAQs in "faq". Output JSON only:
{"title","slug","meta_description"(<=155 chars),"tags":[],"faq":[{"q","a"}],"html"} (html = body only, no <h1>)."""

WRITER_SYS += (f"\nToday's date is {today()}. Only put a year in the title if it is {dt.date.today().year}; never use older years. "
    "Proofread carefully: no typos. Do not state exact prices, free-plan limits or policy details unless you are certain; "
    "otherwise say 'check the official site for current pricing'. Prefer timeless advice over fast-changing specifics.")

def affiliates():
    try: return json.load(open("affiliates.json"))
    except Exception: return {}

def monetize(html):
    used = False
    for k, link in affiliates().items():
        if "EXAMPLE" in k or "your-affiliate" in link: continue
        pat = re.compile(rf"(?<![\w>/\"=])({re.escape(k)})(?![\w<])", re.I)
        if pat.search(html):
            html = pat.sub(rf'<a href="{link}" rel="sponsored nofollow noopener">\1</a>', html, count=1); used = True
    if AD_SNIPPET:
        parts = html.split("</p>")
        if len(parts) > 3: html = "</p>".join(parts[:3]) + "</p>" + AD_SNIPPET + "</p>".join(parts[3:])
    if used:
        html = "<p><em>Disclosure: this post contains affiliate links. We may earn a commission at no extra cost to you.</em></p>" + html
    return html

def faq_schema(faq):
    if not faq: return ""
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}
    return ("<h2>Frequently Asked Questions</h2>" + "".join(f"<h3>{f['q']}</h3><p>{f['a']}</p>" for f in faq)
            + f'<script type="application/ld+json">{json.dumps(data)}</script>')

def related_reading():
    rows = db.execute("SELECT title,url FROM posts WHERE status='published' ORDER BY RANDOM() LIMIT 3").fetchall()
    return ("<h2>Related reading</h2><ul>" + "".join(f'<li><a href="{r["url"]}">{r["title"]}</a></li>' for r in rows)
            + "</ul>") if rows else ""

def review(post):
    return ask("You are a strict editor. JSON only.",
        f"""Score this article 0-10 for accuracy risk, usefulness, originality, readability. Flag any
fabricated-looking statistics, quotes or claims. JSON: {{"score":0,"issues":[]}}\n\n{post['html'][:12000]}""",
        as_json=True, max_tokens=1000)

def write_post(topic):
    post = ask(WRITER_SYS, f"Keyword: {topic['keyword']}\nAngle: {topic['angle']}\nNiche: {NICHE}\n"
                           f"Minimum {MIN_WORDS} words.", as_json=True, max_tokens=12000)
    for attempt in range(3):
        words = len(re.sub("<[^>]+>", " ", post["html"]).split())
        rv = review(post); score = float(rv["score"])
        if (score >= MIN_SCORE and words >= MIN_WORDS * 0.8) or attempt == 2: break
        log(f"revising ({score}/10, {words} words): {rv.get('issues', [])[:3]}")
        post = ask(WRITER_SYS, f"Rewrite fixing these issues: {rv.get('issues')}. Keep >= {MIN_WORDS} words.\n\n"
                               f"{json.dumps(post)}", as_json=True, max_tokens=12000)
    post["score"] = score if score else 0
    post["html"] = monetize(post["html"]) + faq_schema(post.get("faq")) + related_reading()
    return post

# ---------------- publisher (writes Jekyll files; GitHub Pages serves them) ----------------
def unique_slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70] or "post"; base, n = s, 2
    while db.execute("SELECT 1 FROM posts WHERE slug=?", (s,)).fetchone(): s = f"{base}-{n}"; n += 1
    return s

# ---------------- pictures & video scripts ----------------
def make_cover(title, cluster, slug):
    """Branded 1200x630 cover image (also used when the post is shared on social media)."""
    path = f"assets/covers/{slug}.png"
    try:
        import textwrap, hashlib
        from PIL import Image, ImageDraw, ImageFont
        pal = [((255, 107, 74), (255, 170, 90)), ((14, 159, 148), (59, 130, 246)), ((139, 92, 246), (236, 72, 153)),
               ((245, 158, 11), (239, 68, 68)), ((16, 185, 129), (101, 163, 13))]
        a, b = pal[int(hashlib.md5(cluster.encode()).hexdigest(), 16) % len(pal)]
        W, H = 1200, 630
        img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.ellipse((850, -170, 1370, 350), fill=(255, 255, 255, 42)); od.ellipse((-170, 400, 350, 920), fill=(255, 255, 255, 36))
        od.ellipse((960, 390, 1260, 690), fill=(255, 255, 255, 30))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"); d = ImageDraw.Draw(img)
        fb = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") if os.path.exists(f)), None)
        F = lambda n: ImageFont.truetype(fb, n) if fb else ImageFont.load_default()
        title = re.sub(r"\s*[\(\[]?(19|20)\d\d[\)\]]?\s*$", "", title)
        size = 66 if len(title) < 55 else 54 if len(title) < 85 else 46
        lines = textwrap.wrap(title, width=max(12, int(1020 / (size * 0.62))))[:4]
        lh = int(size * 1.28); y0 = (H - lh * len(lines)) // 2 + 15
        for i, ln in enumerate(lines):
            d.text((72, y0 + i * lh + 3), ln, font=F(size), fill=tuple(int(c * 0.55) for c in a))
            d.text((70, y0 + i * lh), ln, font=F(size), fill=(255, 255, 255))
        f = F(28); label = "SoloStack"; tw = d.textlength(label, font=f)
        d.rounded_rectangle((60, 46, 60 + tw + 44, 100), 27, fill=(255, 255, 255)); d.text((82, 55), label, font=f, fill=tuple(int(c * 0.8) for c in a))
        tag = cluster.upper()[:28]; tw = d.textlength(tag, font=F(24))
        d.rounded_rectangle((60, 540, 60 + tw + 40, 586), 23, outline=(255, 255, 255), width=3); d.text((80, 548), tag, font=F(24), fill=(255, 255, 255))
        os.makedirs("assets/covers", exist_ok=True); img.save(path, optimize=True)
        return "/" + path
    except Exception as ex:
        log("cover failed:", ex); return None

PEXELS = cfg("PEXELS_API_KEY")
def pexels_photo(query, slug):
    """Optional: a real free stock photo, if you add a free PEXELS_API_KEY."""
    if not PEXELS: return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS}, timeout=30,
                         params={"query": query, "per_page": 1, "orientation": "landscape"}); r.raise_for_status()
        ph = r.json()["photos"][0]
        data = requests.get(ph["src"]["large"], timeout=60).content
        os.makedirs("assets/covers", exist_ok=True)
        open(f"assets/covers/{slug}.jpg", "wb").write(data)
        open(f"assets/covers/{slug}.txt", "w").write(f"Photo by {ph['photographer']} on Pexels")
        return f"/assets/covers/{slug}.jpg"
    except Exception as ex:
        log("pexels skipped:", ex); return None

def ensure_cover(p):
    for ext in ("jpg", "png"):
        if os.path.exists(f"assets/covers/{p['slug']}.{ext}"): return f"/assets/covers/{p['slug']}.{ext}"
    t = db.execute("SELECT keyword,cluster FROM topics WHERE id=?", (p["topic_id"],)).fetchone()
    return pexels_photo(t["keyword"], p["slug"]) or make_cover(p["title"], (t["cluster"] or "general"), p["slug"])

def video_script(p):
    """Saves a ready-to-record YouTube/Shorts script for each post (for your future channel)."""
    path = f"video_scripts/{p['slug']}.md"
    if cfg("GENERATE_VIDEO_SCRIPTS", "true").lower() != "true" or os.path.exists(path): return
    try:
        body = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", p["html"], flags=re.S))[:6000]
        txt = ask("You write short, engaging YouTube scripts. Plain text, no markdown tables.",
            f"Turn this article into a 60-90 second YouTube Shorts / short video script. Include: TITLE (under 70 chars), "
            f"HOOK (first 3 seconds), SCRIPT (spoken lines with [on-screen text] cues), CALL TO ACTION, DESCRIPTION, 5 HASHTAGS. "
            f"Only use facts from the article; invent nothing.\n\nARTICLE: {p['title']}\n{body}", max_tokens=2000)
        os.makedirs("video_scripts", exist_ok=True); open(path, "w", encoding="utf-8").write(txt)
        log("video script saved:", path)
    except Exception as ex:
        log("video script skipped:", ex)

def backfill():
    """Older posts get a cover picture (without rewriting your manual edits); a couple of scripts per day."""
    made = 0
    for p in db.execute("SELECT * FROM posts WHERE status='published'").fetchall():
        pf = f"_posts/{p['published']}-{p['slug']}.md"
        if os.path.exists(pf):
            txt = open(pf, encoding="utf-8").read(); parts = txt.split("---", 2)
            if len(parts) == 3 and "image:" not in parts[1]:
                img = ensure_cover(p)
                if img:
                    cr = f"assets/covers/{p['slug']}.txt"
                    extra = f"image: {img}\n" + (f"image_credit: {json.dumps(open(cr).read().strip())}\n" if os.path.exists(cr) else "")
                    open(pf, "w", encoding="utf-8").write("---" + parts[1].rstrip("\n") + "\n" + extra + "---" + parts[2])
                    log("cover added:", p["slug"])
        if made < 2 and not os.path.exists(f"video_scripts/{p['slug']}.md") and cfg("GENERATE_VIDEO_SCRIPTS", "true").lower() == "true":
            video_script(p); made += 1

def publish(post_id, status):
    p = db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    pub = p["published"] or today(); post_file = f"_posts/{pub}-{p['slug']}.md"
    extra = ""
    img = ensure_cover(p)
    if img:
        extra += f"image: {img}\n"; cr = f"assets/covers/{p['slug']}.txt"
        if os.path.exists(cr): extra += f"image_credit: {json.dumps(open(cr).read().strip())}\n"
    if os.path.exists(post_file):  # keep a YouTube video id you added by hand
        m = re.search(r"^youtube:\s*(\S+)", open(post_file, encoding="utf-8").read(), re.M)
        if m: extra += f"youtube: {m.group(1)}\n"
    front = (f'---\nlayout: post\ntitle: {json.dumps(p["title"])}\ndescription: {json.dumps(p["excerpt"] or "")}\n'
             f'date: {pub} 00:00:00 +0000\npermalink: /{p["slug"]}/\n{extra}---\n\n')
    draft = f"_drafts/{p['slug']}.md"
    if status == "publish":
        os.makedirs("_posts", exist_ok=True)
        open(post_file, "w", encoding="utf-8").write(front + p["html"])
        if os.path.exists(draft): os.remove(draft)
        db.execute("UPDATE posts SET status='published', url=?, published=? WHERE id=?", (f"{SITE}/{p['slug']}/", pub, post_id))
        log("PUBLISHED:", p["title"])
    else:
        os.makedirs("_drafts", exist_ok=True); open(draft, "w", encoding="utf-8").write(front + p["html"])
        db.execute("UPDATE posts SET status='draft' WHERE id=?", (post_id,)); log("DRAFT (needs review):", p["title"])
    db.commit()

def create_new_posts():
    q = "SELECT * FROM topics WHERE status='queued' ORDER BY id LIMIT 1"
    for _ in range(POSTS_PER_DAY):
        t = db.execute(q).fetchone()
        if not t: plan_topics(); t = db.execute(q).fetchone()
        if not t: log("no topics available"); return
        try:
            p = write_post(t)
            cur = db.execute("INSERT INTO posts(topic_id,title,slug,html,score,status,excerpt) VALUES(?,?,?,?,?,'new',?)",
                (t["id"], p["title"], unique_slug(p.get("slug") or p["title"]), p["html"], p["score"], p.get("meta_description", "")))
            db.execute("UPDATE topics SET status='written' WHERE id=?", (t["id"],)); db.commit()
            publish(cur.lastrowid, "publish" if AUTO_PUBLISH and p["score"] >= MIN_SCORE else "draft")
            video_script(db.execute("SELECT * FROM posts WHERE id=?", (cur.lastrowid,)).fetchone())
        except Exception as ex:
            log("post failed:", t["keyword"], ex); db.execute("UPDATE topics SET status='failed' WHERE id=?", (t["id"],)); db.commit()

def approve():
    for p in db.execute("SELECT id FROM posts WHERE status='draft'").fetchall(): publish(p["id"], "publish")

# ---------------- analyst (free sources: CSV files and optional GA4) ----------------
def sync_metrics():
    ids = {urlparse(p["url"]).path.rstrip("/"): p["id"] for p in db.execute("SELECT id,url FROM posts WHERE url IS NOT NULL")}
    for fname, col in ((f"{DATA}/traffic.csv", "views"), (f"{DATA}/revenue.csv", "revenue")):  # date,url,<col>
        if os.path.exists(fname):
            for r in csv.DictReader(open(fname)):
                pid = ids.get(urlparse(r["url"]).path.rstrip("/"))
                if pid: db.execute(f"INSERT INTO metrics(post_id,date,{col}) VALUES(?,?,?) ON CONFLICT(post_id,date) "
                                   f"DO UPDATE SET {col}=excluded.{col}", (pid, r["date"], float(r[col])))
    if GA4_PID:  # optional, advanced
        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
            rep = BetaAnalyticsDataClient().run_report(RunReportRequest(property=f"properties/{GA4_PID}",
                dimensions=[Dimension(name="pagePath"), Dimension(name="date")], metrics=[Metric(name="screenPageViews")],
                date_ranges=[DateRange(start_date="30daysAgo", end_date="today")]))
            for row in rep.rows:
                pid = ids.get(row.dimension_values[0].value.rstrip("/")); d = row.dimension_values[1].value
                if pid: db.execute("INSERT INTO metrics(post_id,date,views) VALUES(?,?,?) ON CONFLICT(post_id,date) "
                    "DO UPDATE SET views=excluded.views", (pid, f"{d[:4]}-{d[4:6]}-{d[6:]}", int(row.metric_values[0].value)))
        except Exception as ex: log("GA4 sync skipped:", ex)
    db.commit()

def stats():
    return db.execute("""SELECT p.id,p.title,p.published,p.refreshed,t.cluster,t.keyword,
        COALESCE(SUM(m.views),0) views, COALESCE(SUM(m.revenue),0) rev FROM posts p JOIN topics t ON t.id=p.topic_id
        LEFT JOIN metrics m ON m.post_id=p.id WHERE p.status='published' GROUP BY p.id""").fetchall()

# ---------------- optimizer ----------------
age = lambda d: (dt.date.today() - dt.date.fromisoformat(d)).days if d else 0

def optimize():
    rows = stats()
    if not rows or not db.execute("SELECT 1 FROM metrics LIMIT 1").fetchone(): return  # needs data first
    for w in sorted(rows, key=lambda r: (r["rev"], r["views"]), reverse=True)[:max(1, len(rows) // 5)]:
        if w["rev"] > 0 or w["views"] > 100:  # expand winners
            for t in ask("SEO strategist. JSON only.", f"Winning article: '{w['title']}'. Give 3 closely related long-tail "
                         f"topics. JSON: [{{\"keyword\":\"\",\"angle\":\"\"}}]", as_json=True, max_tokens=800):
                db.execute("INSERT OR IGNORE INTO topics(keyword,angle,cluster,created) VALUES(?,?,?,?)",
                           (t["keyword"], t.get("angle", ""), w["cluster"], today()))
    for r in rows:  # refresh weak, aging posts
        if age(r["refreshed"] or r["published"]) >= (60 if r["refreshed"] else 45) and r["views"] < 50:
            p = db.execute("SELECT * FROM posts WHERE id=?", (r["id"],)).fetchone()
            new = ask(WRITER_SYS, f"Improve this underperforming post for '{r['keyword']}': sharper title, better intro, "
                      f"more depth. Never invent facts.\n\n{p['html'][:15000]}", as_json=True, max_tokens=12000)
            db.execute("UPDATE posts SET title=?, html=?, refreshed=? WHERE id=?", (new["title"],
                monetize(new["html"]) + faq_schema(new.get("faq")) + related_reading(), today(), r["id"]))
            db.commit(); publish(r["id"], "publish"); log("refreshed:", r["title"])
    db.commit()

def report():
    rows = stats(); tv, tr = sum(r["views"] for r in rows), sum(r["rev"] for r in rows)
    print(f"\n{len(rows)} published | {int(tv)} views | ${tr:.2f} revenue\n")
    for r in sorted(rows, key=lambda r: r["rev"], reverse=True)[:15]: print(f"${r['rev']:>8.2f} {int(r['views']):>6}v  {r['title'][:60]}")
    print("Queued topics:", db.execute("SELECT COUNT(*) FROM topics WHERE status='queued'").fetchone()[0],
          "| Drafts:", db.execute("SELECT COUNT(*) FROM posts WHERE status='draft'").fetchone()[0])

def apply_domain(domain):
    """Switch the whole blog from the free github.io address to your own paid domain."""
    global SITE
    domain = re.sub(r"^https?://", "", domain.strip().lower()).strip("/")
    new, old = f"https://{domain}", SITE
    if new == old: return
    open("CNAME", "w").write(domain + "\n")  # tells GitHub Pages to serve your domain
    json.dump({"url": new}, open(f"{DATA}/site.json", "w"))
    SITE = new
    for p in db.execute("SELECT id,html FROM posts").fetchall():  # fix every stored link
        db.execute("UPDATE posts SET html=?, url=REPLACE(url,?,?) WHERE id=?", (p["html"].replace(old, new), old, new, p["id"]))
    db.commit()
    for p in db.execute("SELECT id FROM posts WHERE status='published'").fetchall(): publish(p["id"], "publish")
    log(f"DOMAIN SWITCHED: {old} -> {new}")

def cycle():
    if not LLM_KEY: sys.exit("Missing LLM_API_KEY (add it as a GitHub secret).")
    if cfg("CUSTOM_DOMAIN"): apply_domain(cfg("CUSTOM_DOMAIN"))
    log("cycle start; site:", SITE); sync_metrics(); backfill(); optimize(); create_new_posts(); report()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "once"
    if cmd == "run":
        while True:
            try: cycle()
            except Exception as ex: log("cycle error:", ex)
            time.sleep(86400)
    elif cmd == "report": report()
    elif cmd == "approve": approve()
    elif cmd == "domain" and len(sys.argv) > 2: apply_domain(sys.argv[2])
    else: cycle()
