# Job Search & Resume Matcher

A Streamlit app that searches for jobs across the web, scores them against your resume using Claude AI, tailors your resume for top matches, and tracks your applications in Google Sheets or a local CSV.

## Features

| Feature | Description |
|---|---|
| **Job Search** | Searches LinkedIn, Indeed, Glassdoor, ZipRecruiter, and more via JSearch (RapidAPI) or Google Jobs via SerpAPI |
| **Filters** | Location, date posted, employment type, remote-only |
| **Sponsorship Mode** | Filters to roles with confirmed visa/work-permit sponsorship, verified by Claude |
| **Fit Analysis** | Claude scores each job 1–5 stars with match score, matched skills, and missing skills |
| **Resume Tailoring** | Claude rewrites your resume, ATS-optimised for each 4-star / 5-star role |
| **Apply Links** | Direct link to apply for every job |
| **Job Tracker** | Google Sheets sync (or local CSV) with editable status, notes, and pipeline chart |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

You need:

| Key | Where to get it | Required? |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | **Yes** |
| `RAPIDAPI_KEY` | [rapidapi.com — JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | One of these two |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | One of these two |
| `GOOGLE_CREDENTIALS_JSON` | Google Cloud Console → Service Accounts (see below) | No (CSV used otherwise) |

### 3. Run the app

```bash
streamlit run app.py
```

---

## Google Sheets Setup (optional)

If you want applications synced to a Google Sheet:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → download the JSON credentials file
4. Set `GOOGLE_CREDENTIALS_JSON=/path/to/credentials.json` in your `.env`
5. The sheet named `Job Applications Tracker` is created automatically on first save

---

## How to Use

### Step 1 — Upload your resume
In the sidebar, upload a PDF, DOCX, or TXT resume (or paste the text directly).

### Step 2 — Set work authorization
Toggle **"I need visa sponsorship"** if you require employer sponsorship. The app will:
- Append `visa sponsorship` to every search query
- Use Claude to deep-verify sponsorship language in top-match JDs
- Surface a 🟢 badge on confirmed-sponsorship roles

### Step 3 — Search
On the **Search** tab, enter job title / keywords, location (e.g. `New York`, `UK`, `Remote`), date range, employment type, and how many pages to fetch.

### Step 4 — Review results
The **Results** tab shows all jobs ranked by star rating with:
- Match score and fit summary
- Matched ✅ and missing ⚠️ skills
- Direct apply link
- One-click **Save to Tracker**

### Step 5 — Tailor your resume
Click **✍️ Tailor Resume for this role** on any 4-star or 5-star job. Claude produces:
- A fully rewritten, ATS-optimised resume
- A changelog of what was altered and why
- Missing skills / certifications to acquire
- 5 cover letter bullet points

Download the tailored resume as Markdown from the **Tailor Resume** tab.

### Step 6 — Track applications
The **Job Tracker** tab shows all saved applications in an editable table. Update status (Saved → Applied → Interview → Offer), add notes, and export to CSV at any time.

---

## Project Structure

```
jobsearchtool/
├── app.py            # Streamlit UI
├── analyzer.py       # Claude AI — fit scoring & resume tailoring
├── job_search.py     # Job search — JSearch (RapidAPI) + SerpAPI
├── resume_parser.py  # Resume parsing — PDF, DOCX, TXT
├── tracker.py        # Job tracker — Google Sheets + CSV fallback
├── config.py         # Config, constants, env helpers
├── requirements.txt
└── .env.example
```

---

## Supported Resume Formats

- PDF (`.pdf`)
- Microsoft Word (`.docx`)
- Plain text (`.txt`, `.md`)
- Paste directly into the sidebar text area

---

## Star Rating Scale

| Stars | Meaning |
|---|---|
| ⭐⭐⭐⭐⭐ | Perfect Match — strong overlap, apply immediately |
| ⭐⭐⭐⭐ | Strong Match — minor gaps, tailor and apply |
| ⭐⭐⭐ | Good Match — some gaps, worth considering |
| ⭐⭐ | Partial Match — significant gaps |
| ⭐ | Weak Match — limited overlap |
