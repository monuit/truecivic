"""Centralized ingestion defaults shared across batch jobs and flows."""

from datetime import datetime

# Hard floor for ingestion windows: ignore parliamentary content before 2015.
MIN_BILL_INTRODUCED_DATE = datetime(2015, 1, 1)

# Default moving window (in days) used when deriving fallback look-back periods.
BILL_FETCH_WINDOW_DAYS = 3650
