"""Claude AI: job fit scoring and resume tailoring with prompt caching."""
import json
import re
from typing import Any
import anthropic

MODEL = "claude-sonnet-4-6"


def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """Quick check that the Anthropic key is valid and has credits. Returns (ok, message)."""
    if not api_key or not api_key.strip():
        return False, "Anthropic API key is missing. Add it to Streamlit Secrets as ANTHROPIC_API_KEY."
    try:
        client = _client(api_key)
        client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, "OK"
    except anthropic.AuthenticationError:
        return False, "Invalid Anthropic API key. Check the key value in Streamlit Secrets."
    except anthropic.PermissionDeniedError:
        return False, "Anthropic API key lacks permissions. Ensure it is a valid API key."
    except Exception as e:
        return False, f"Anthropic API error: {e}"


# ── Fit Analysis ─────────────────────────────────────────────────────────────

FIT_SYSTEM = """You are a senior technical recruiter and career coach with deep expertise in matching candidates to job descriptions.
Your analysis is precise, honest, and actionable."""

FIT_PROMPT_TEMPLATE = """Analyze the fit between the candidate's resume and the job description below.

<resume>
{resume}
</resume>

<job_listings>
{jobs_json}
</job_listings>

For EACH job, return a JSON object in an array with exactly these fields:
- "job_id": the job's id field
- "stars": integer 1-5 (5=perfect, 4=strong, 3=good, 2=partial, 1=weak)
- "match_score": float 0-100
- "matched_skills": list of skills/keywords from JD found in resume
- "missing_skills": list of important JD requirements NOT found in resume
- "sponsorship_confirmed": boolean — true only if JD explicitly mentions sponsorship available
- "fit_summary": 2-sentence explanation of the star rating
- "why_apply": one compelling reason to apply if stars >= 4, else empty string

Return ONLY a valid JSON array, no markdown, no extra text."""


def score_jobs(
    resume_text: str,
    jobs: list[dict[str, Any]],
    api_key: str,
    batch_size: int = 10,
) -> list[dict[str, Any]]:
    """
    Score all jobs in batches. Returns list of score dicts keyed by job_id.
    Uses prompt caching on the resume (system prompt + resume = cached prefix).
    """
    client = _client(api_key)
    scored = []

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i: i + batch_size]
        # Trim descriptions to keep tokens reasonable
        slim_batch = [
            {
                "id": j["id"] or f"job_{i + idx}",
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "description": (j["description"] or "")[:3000],
                "sponsorship_mentioned": j.get("sponsorship_mentioned", False),
            }
            for idx, j in enumerate(batch)
        ]

        prompt = FIT_PROMPT_TEMPLATE.format(
            resume=resume_text[:6000],
            jobs_json=json.dumps(slim_batch, indent=2),
        )

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": FIT_SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            batch_scores = json.loads(text)
            scored.extend(batch_scores)
        except Exception as e:
            # On failure, give each job a default score so UI still shows them
            for j in slim_batch:
                scored.append({
                    "job_id": j["id"],
                    "stars": 0,
                    "match_score": 0,
                    "matched_skills": [],
                    "missing_skills": [],
                    "sponsorship_confirmed": j["sponsorship_mentioned"],
                    "fit_summary": f"Analysis failed: {e}",
                    "why_apply": "",
                })

    return scored


def merge_scores(jobs: list[dict], scores: list[dict]) -> list[dict]:
    """Merge score dicts back into job dicts by job_id."""
    score_map = {s["job_id"]: s for s in scores}
    result = []
    for idx, j in enumerate(jobs):
        jid = j["id"] or f"job_{idx}"
        score = score_map.get(jid, {})
        result.append({**j, "id": jid, **score})
    return result


# ── Resume Tailoring ──────────────────────────────────────────────────────────

TAILOR_SYSTEM = """You are an expert resume writer and career coach.
You create highly targeted, ATS-optimized resumes that are honest and specific."""

TAILOR_PROMPT_TEMPLATE = """Tailor the candidate's resume specifically for the following job.

<original_resume>
{resume}
</original_resume>

<job>
Title: {title}
Company: {company}
Description:
{description}
</job>

Produce:
1. **TAILORED RESUME** — Rewrite the resume to:
   - Mirror language and keywords from the JD (ATS optimization)
   - Reorder and reframe bullet points to front-load the most relevant experience
   - Add a concise Professional Summary (3-4 lines) targeted to this specific role
   - Preserve all factual content; never fabricate experience or skills
   - Remove or de-emphasize experiences irrelevant to this role

2. **KEY CHANGES** — Bullet list of what was changed and why (max 8 bullets)

3. **MISSING SKILLS TO ADDRESS** — Skills/certs the candidate should mention if they have them, or acquire

4. **COVER LETTER BULLETS** — 5 strong bullet points for a cover letter

Format each section with a clear heading: ## TAILORED RESUME, ## KEY CHANGES, ## MISSING SKILLS TO ADDRESS, ## COVER LETTER BULLETS"""


def tailor_resume(
    resume_text: str,
    job: dict[str, Any],
    api_key: str,
) -> str:
    """Return tailored resume + analysis as markdown string."""
    client = _client(api_key)

    prompt = TAILOR_PROMPT_TEMPLATE.format(
        resume=resume_text,
        title=job.get("title", ""),
        company=job.get("company", ""),
        description=(job.get("description") or "")[:5000],
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": TAILOR_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Sponsorship Deep-Check ────────────────────────────────────────────────────

SPONSORSHIP_PROMPT = """Read this job description and answer with JSON only:
{{"confirmed_sponsorship": true/false, "sponsorship_note": "quoted text from JD or empty string"}}

Rules:
- confirmed_sponsorship = true ONLY if the JD explicitly says they WILL sponsor visas/work permits
- false if they say "must be authorized", "no sponsorship", or if sponsorship is not mentioned at all

Job Description:
{description}"""


def check_sponsorship_deep(job: dict, api_key: str) -> dict:
    """Ask Claude to verify sponsorship status from the full JD."""
    client = _client(api_key)
    prompt = SPONSORSHIP_PROMPT.format(
        description=(job.get("description") or "")[:4000]
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception:
        return {"confirmed_sponsorship": False, "sponsorship_note": ""}
