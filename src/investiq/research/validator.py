"""Output validation rules for analyst findings.

Ensures evidence traceability integrity, confidence range limits, field completeness,
and enforces zero trading recommendation policy.
"""

import re
from investiq.models.evidence import EvidenceItem
from investiq.models.research import ResearchFinding


PROHIBITED_RECOMMENDATION_KEYWORDS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bstrong buy\b",
    r"\bstrong sell\b",
    r"\bprice target\b",
    r"\btarget price\b",
    r"\bcio stance\b",
    r"\bportfolio allocation\b",
]


class ValidationError(ValueError):
    """Raised when an analyst finding fails output validation rules."""

    pass


def validate_analyst_finding(
    finding: ResearchFinding,
    valid_evidence_items: list[EvidenceItem],
) -> None:
    """Validate a single ResearchFinding against audit rules.

    Args:
        finding: The finding output to validate.
        valid_evidence_items: List of EvidenceItem instances provided in prompt payload.

    Raises:
        ValidationError: If finding fails any validation rule.
    """
    # 1. Required fields check
    if not finding.analyst or not finding.analyst.strip():
        raise ValidationError("Finding is missing required 'analyst' field.")
    if not finding.title or not finding.title.strip():
        raise ValidationError("Finding is missing required 'title' field.")
    if not finding.statement or not finding.statement.strip():
        raise ValidationError("Finding is missing required 'statement' field.")
    if not finding.category:
        raise ValidationError("Finding is missing required 'category' field.")

    # 2. Confidence range check (0.0 to 1.0)
    if finding.confidence < 0.0 or finding.confidence > 1.0:
        raise ValidationError(
            f"Confidence score {finding.confidence} is outside valid range [0.0, 1.0]."
        )

    # 3. Evidence IDs existence check
    valid_ids = {ev.evidence_id for ev in valid_evidence_items}
    if not finding.evidence_ids:
        raise ValidationError("Finding must reference at least one valid evidence_id.")

    invalid_ids = [eid for eid in finding.evidence_ids if eid not in valid_ids]
    if invalid_ids:
        raise ValidationError(
            f"Finding references invalid evidence_id(s) not in input payload: {invalid_ids}. "
            f"Valid IDs: {sorted(list(valid_ids))}"
        )

    # 4. Prohibited recommendation keywords check
    combined_text = f"{finding.title} {finding.statement}".lower()
    for kw_pattern in PROHIBITED_RECOMMENDATION_KEYWORDS:
        if re.search(kw_pattern, combined_text):
            raise ValidationError(
                f"Finding contains prohibited trading/investment recommendation term matching pattern '{kw_pattern}'. "
                f"Analyst outputs must remain decision support only and avoid BUY/SELL stances."
            )


def validate_analyst_findings(
    findings: list[ResearchFinding],
    valid_evidence_items: list[EvidenceItem],
) -> list[ResearchFinding]:
    """Validate a list of findings, raising ValidationError if any finding fails validation."""
    for finding in findings:
        validate_analyst_finding(finding, valid_evidence_items)
    return findings
