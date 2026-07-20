"""Statutory Government Health Warning Statement, 27 CFR Part 16.

Stored as two parts because the compliance rule is two-part:
- PREFIX is compared case-sensitively (must be exact, all caps).
- BODY is compared word-for-word, case-insensitively, whitespace-collapsed.
"""

PREFIX = "GOVERNMENT WARNING:"

BODY = (
    "(1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability "
    "to drive a car or operate machinery, and may cause health problems."
)
