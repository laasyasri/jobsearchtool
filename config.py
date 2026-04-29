"""Central configuration and environment loading."""
import os
from dotenv import load_dotenv

load_dotenv()


def get_anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


def get_rapidapi_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "")


def get_serpapi_key() -> str:
    return os.getenv("SERPAPI_KEY", "")


def get_google_credentials_path() -> str:
    return os.getenv("GOOGLE_CREDENTIALS_JSON", "")


def get_google_sheet_name() -> str:
    return os.getenv("GOOGLE_SHEET_NAME", "Job Applications Tracker")


DATE_FILTER_OPTIONS = {
    "Any time": "",
    "Past 24 hours": "today",
    "Past 3 days": "3days",
    "Past week": "week",
    "Past month": "month",
}

EMPLOYMENT_TYPES = {
    "Any": "",
    "Full-time": "FULLTIME",
    "Part-time": "PARTTIME",
    "Contract": "CONTRACTOR",
    "Internship": "INTERN",
}

STAR_LABELS = {
    5: "⭐⭐⭐⭐⭐ Perfect Match",
    4: "⭐⭐⭐⭐ Strong Match",
    3: "⭐⭐⭐ Good Match",
    2: "⭐⭐ Partial Match",
    1: "⭐ Weak Match",
}

TRACKER_COLUMNS = [
    "Job Title",
    "Company",
    "Location",
    "Star Rating",
    "Date Posted",
    "Apply URL",
    "Sponsorship",
    "Status",
    "Date Added",
    "Date Applied",
    "Notes",
]

STATUS_OPTIONS = [
    "Saved",
    "Applied",
    "Phone Screen",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
]
