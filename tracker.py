"""Job application tracker — Google Sheets primary, local CSV fallback."""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import TRACKER_COLUMNS, get_google_credentials_path, get_google_sheet_name

LOCAL_CSV = Path("job_tracker.csv")


# ── Public API ────────────────────────────────────────────────────────────────

def load_tracker() -> pd.DataFrame:
    """Load existing tracker data (Sheets > CSV > empty frame)."""
    try:
        sheet = _open_sheet()
        records = sheet.get_all_records()
        df = pd.DataFrame(records) if records else _empty_df()
        return _ensure_columns(df)
    except Exception:
        pass

    if LOCAL_CSV.exists():
        try:
            df = pd.read_csv(LOCAL_CSV, dtype=str).fillna("")
            return _ensure_columns(df)
        except Exception:
            pass

    return _empty_df()


def save_application(job: dict[str, Any], status: str = "Saved", notes: str = "") -> bool:
    """Add or update a job application in the tracker. Returns True on success."""
    row = {
        "Job Title": job.get("title", ""),
        "Company": job.get("company", ""),
        "Location": job.get("location", ""),
        "Star Rating": str(job.get("stars", "")),
        "Date Posted": job.get("date_posted", ""),
        "Apply URL": job.get("apply_url", ""),
        "Sponsorship": "Yes" if job.get("sponsorship_confirmed") else
                       ("Mentioned" if job.get("sponsorship_mentioned") else "No"),
        "Status": status,
        "Date Added": datetime.now().strftime("%Y-%m-%d"),
        "Date Applied": "",
        "Notes": notes,
    }

    # Try Google Sheets first
    try:
        sheet = _open_sheet()
        _upsert_row(sheet, row)
        return True
    except Exception:
        pass

    # Fall back to local CSV
    return _csv_upsert(row)


def update_status(company: str, title: str, status: str, notes: str = "") -> bool:
    """Update status for an existing application."""
    df = load_tracker()
    mask = (df["Company"] == company) & (df["Job Title"] == title)
    if not mask.any():
        return False

    df.loc[mask, "Status"] = status
    if status == "Applied" and not df.loc[mask, "Date Applied"].any():
        df.loc[mask, "Date Applied"] = datetime.now().strftime("%Y-%m-%d")
    if notes:
        df.loc[mask, "Notes"] = notes

    return _save_df(df)


def _save_df(df: pd.DataFrame) -> bool:
    try:
        sheet = _open_sheet()
        sheet.clear()
        sheet.update([df.columns.tolist()] + df.values.tolist())
        return True
    except Exception:
        pass
    try:
        df.to_csv(LOCAL_CSV, index=False)
        return True
    except Exception:
        return False


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def _open_sheet():
    """Open (or create) the Google Sheet. Raises on failure."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds_path = get_google_credentials_path()
    if not creds_path or not os.path.exists(creds_path):
        raise FileNotFoundError("Google credentials not found")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet_name = get_google_sheet_name()

    try:
        spreadsheet = gc.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        spreadsheet = gc.create(sheet_name)
        # Share with anyone who has the link (view)
        spreadsheet.share("", perm_type="anyone", role="writer")

    ws = spreadsheet.sheet1

    # Ensure header row exists
    existing = ws.row_values(1)
    if existing != TRACKER_COLUMNS:
        ws.clear()
        ws.append_row(TRACKER_COLUMNS)

    return ws


def _upsert_row(sheet, row: dict) -> None:
    """Insert or update row matching Company + Job Title."""
    records = sheet.get_all_records()
    for idx, rec in enumerate(records, start=2):  # 1-indexed, row 1 = header
        if rec.get("Company") == row["Company"] and rec.get("Job Title") == row["Job Title"]:
            sheet.update(f"A{idx}:{_col_letter(len(TRACKER_COLUMNS))}{idx}",
                         [[row.get(c, "") for c in TRACKER_COLUMNS]])
            return
    sheet.append_row([row.get(c, "") for c in TRACKER_COLUMNS])


def _col_letter(n: int) -> str:
    """Convert 1-based column index to letter (1→A, 26→Z, 27→AA)."""
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _csv_upsert(row: dict) -> bool:
    df = load_tracker()
    mask = (df["Company"] == row["Company"]) & (df["Job Title"] == row["Job Title"])
    if mask.any():
        for col, val in row.items():
            df.loc[mask, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    try:
        df.to_csv(LOCAL_CSV, index=False)
        return True
    except Exception:
        return False


# ── DataFrame utilities ───────────────────────────────────────────────────────

def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TRACKER_COLUMNS)


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in TRACKER_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[TRACKER_COLUMNS]


def export_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()
