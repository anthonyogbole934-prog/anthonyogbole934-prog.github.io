# Free Autonomous Blog: Setup Guide (no coding, no payment)

**What you get:** a free international blog (SoloStack: AI tools, software reviews and online income
ideas for freelancers and remote workers). Every day, in the cloud, it plans a topic, writes a post,
checks quality, adds affiliate links + disclosure, and publishes. Your computer can stay off.

**Everything used is free:** GitHub (hosting, free domain `yourname.github.io`, daily scheduler) and Google Gemini (AI writer).
No credit card needed for either.

## Step 1: Create a free GitHub account
Go to github.com and sign up. Remember your username.

## Step 2: Create your blog's home
1. Click **+** (top right) > **New repository**.
2. **Name it exactly `YOUR-USERNAME.github.io`** (for example `jane.github.io`). Choose **Public**.
   Click **Create repository**.
3. Your FREE domain is now: `https://YOUR-USERNAME.github.io` (clean, no extra folder name).

## Step 3: Upload the files
1. Unzip the download on your phone/computer.
2. In your new repository click **uploading an existing file**.
3. Drag in ALL the unzipped files (blog_manager.py, _config.yml, index.md, about.md, privacy.md,
   disclaimer.md, affiliates.json, requirements.txt, workflow_copy.yml, and the `data` folder if present).
   Click **Commit changes**.

## Step 4: Add the daily robot
1. In the repository click **Add file > Create new file**.
2. In the name box type exactly: `.github/workflows/blog.yml`
3. Open `workflow_copy.yml` from the download, copy everything, paste it in. Click **Commit changes**.

## Step 5: Get your free AI key
1. Go to **aistudio.google.com** and sign in with a Google account.
2. Click **Get API key > Create API key**. Copy it. (No card needed.)

## Step 6: Give the key to your robot
Repository **Settings > Secrets and variables > Actions > New repository secret**
Name: `LLM_API_KEY`  Value: (paste your key). Save.

## Step 7: Allow it to save posts
**Settings > Actions > General > Workflow permissions** > choose **Read and write permissions** > Save.

## Step 8: Turn on the website
**Settings > Pages** > Source: **Deploy from a branch** > Branch: **main**, folder **/(root)** > Save.

## Step 9: Start it
Click the **Actions** tab > **Blog Manager** > **Run workflow**. In ~3-6 minutes your first post is
written and the site updates ~1-2 minutes after. After that it runs by itself every day.

If the run fails with a model error, go to Settings > Secrets and variables > Actions > **Variables** tab,
add `LLM_MODEL` and set it to the current free Gemini Flash model name shown in Google AI Studio.

## Step 10: Get found on Google (free, week 1)
- **Google Search Console** (search.google.com/search-console): add your blog address as a "URL prefix"
  property, verify it, then submit `sitemap.xml`.
- Also add the site to **Bing Webmaster Tools** (it can import from Search Console).
- Edit `about.md` on GitHub (pencil icon) and put your real contact email.
- Share each new post on Reddit (relevant communities, follow their rules), X, LinkedIn, Pinterest, and
  free communities. Traffic from real people speeds up everything.

## Step 11: Make money (free)
- **Affiliate programs are free to join** (many software companies pay commissions, some monthly
  and recurring). Join the programs for tools the blog mentions. Then edit `affiliates.json`
  on GitHub like: `{ "Notion": "https://your-link", "Canva": "https://your-link" }`.
  The robot links the first mention and adds the disclosure automatically.
- **Google AdSense** generally wants your own domain, which costs money, so treat ads as a later step
  once affiliate income pays for it.
- To let the robot learn what works, upload `data/traffic.csv` (date,url,views) and
  `data/revenue.csv` (date,url,revenue) from your dashboards. It then writes more like your winners
  and rewrites weak posts after 45 days.

## Free domain now, your own domain later
**Free now:** `yourname.github.io` is your free domain, with free HTTPS. Truly free registered domains
(like .com or .net) no longer exist. The old free ones (.tk etc.) collapsed. Other free options such as
is-a.dev (developers only), eu.org (slow approval) and DigitalPlat are less trusted by Google and ad
networks, so I don't recommend them for a blog you want to monetize. Starting on github.io costs nothing
and loses nothing, because the move later is built in.

**When your blog starts earning, switch to your own domain (about 10 minutes, one-time):**
1. Buy a domain (a .com is usually about $10-15/year at registrars like Cloudflare, Namecheap or Porkbun).
2. At the registrar's DNS settings add these 4 **A records** for the root domain (`@`):
   `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   and one **CNAME** record: name `www`, value `YOUR-USERNAME.github.io`.
3. In your GitHub repository: **Settings > Secrets and variables > Actions > Variables > New variable**
   Name: `CUSTOM_DOMAIN`  Value: `yourdomain.com`
4. Run the robot once (**Actions > Blog Manager > Run workflow**). It automatically rewrites every post's
   links to the new domain and adds the file GitHub needs.
5. **Settings > Pages**: confirm the Custom domain shows your domain, tick **Enforce HTTPS** (may take
   up to an hour after DNS updates).
6. Add the new domain in Google Search Console and submit `https://yourdomain.com/sitemap.xml`.
   GitHub redirects the old github.io address to your new one, so visitors and links aren't lost.
7. Now apply for Google AdSense with your own domain.

## Honest expectations
- New blogs usually take 3-6 months to rank. The first weeks test reliability, not income.
- Free AI limits change and quality varies. Review the first ~10 posts. Low-scoring posts go to a
  `_drafts` folder instead of publishing.
- Free-tier AI usage may be used by Google to improve its products, and free limits can change.
  Don't put anything private into it.
- Auto-publishing AI content with no human check can hurt rankings if it is thin or wrong, so skim
  your posts weekly. GitHub may also pause a schedule if a repo is inactive for a long time.
