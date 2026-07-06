"""
pipeline/documents.py
---------------------
Document corpus. In production, replace DOCUMENTS with a loader that pulls
from S3, SharePoint, Confluence, or another document store.

tenant_id and access_group are injected here at ingest time.
At query time they must be enforced server-side from the authenticated
user's context — never accepted from the client request.
"""

from typing import Any, Dict, List

DOCUMENTS: List[Dict[str, Any]] = [
    {
        "doc_id": "hr-001",
        "title": "Remote Work Policy",
        "source": "hr-handbook-2025.pdf",
        "page": 12,
        "tenant_id": "acme-corp",
        "access_group": "hr",
        "text": (
            "Acme Corp permits remote work for all full time employees in eligible roles. "
            "Employees must work from an approved location within their country of employment. "
            "Cross border remote work is permitted for up to 30 days per calendar year with prior "
            "approval from HR and the employee's manager. International work beyond 30 days requires "
            "a formal relocation review and may have tax implications that must be reviewed by Finance. "
            "Equipment stipends of up to 1500 dollars are available annually for home office setup."
        ),
    },
    {
        "doc_id": "hr-002",
        "title": "Parental Leave",
        "source": "hr-handbook-2025.pdf",
        "page": 24,
        "tenant_id": "acme-corp",
        "access_group": "hr",
        "text": (
            "Acme Corp offers 16 weeks of fully paid parental leave to all primary caregivers regardless "
            "of gender or how the child joined the family, including birth, adoption, or surrogacy. "
            "Secondary caregivers receive 6 weeks of fully paid leave. Leave can be taken in up to three "
            "non consecutive blocks within the first 12 months. Employees must give 60 days notice when "
            "practicable. Health benefits continue uninterrupted during the leave period."
        ),
    },
    {
        "doc_id": "hr-003",
        "title": "Expense Reimbursement",
        "source": "finance-policy-2025.pdf",
        "page": 5,
        "tenant_id": "globex-corp",
        "access_group": "finance",
        "text": (
            "Employees may submit expenses for reimbursement through the corporate expense portal within "
            "60 days of the expense being incurred. Receipts are required for any single expense over "
            "25 dollars. Travel expenses require pre approval from a manager when the total trip cost "
            "exceeds 2000 dollars. Meals are reimbursed up to 75 dollars per day domestically and 100 "
            "dollars per day internationally. Alcohol is not reimbursable except in pre approved client "
            "entertainment contexts."
        ),
    },
    {
        "doc_id": "hr-004",
        "title": "Performance Review Cycle",
        "source": "hr-handbook-2025.pdf",
        "page": 31,
        "tenant_id": "acme-corp",
        "access_group": "hr",
        "text": (
            "Acme Corp conducts performance reviews twice per year, in March and September. The process "
            "includes a self assessment, manager assessment, and peer feedback from at least three "
            "colleagues. Compensation adjustments are made effective April 1 based on the March review. "
            "Promotion decisions are made at both cycles. Employees rated as Needs Improvement are placed "
            "on a 90 day performance improvement plan with weekly check ins."
        ),
    },
    {
        "doc_id": "hr-005",
        "title": "Security Clearance and Background Checks",
        "source": "security-policy-2025.pdf",
        "page": 8,
        "tenant_id": "globex-corp",
        "access_group": "security",
        "text": (
            "All employees undergo a background check at time of hire. Employees working on "
            "federal government contracts may be required to obtain and maintain a security clearance "
            "at the Secret, Top Secret, or TS SCI level depending on the program. Clearance investigations "
            "are conducted by the Defense Counterintelligence and Security Agency. Employees with active "
            "clearances must report foreign travel, foreign contacts, and significant changes in financial "
            "status to the Facility Security Officer."
        ),
    },
    {
        "doc_id": "hr-006",
        "title": "Stock and Equity Compensation",
        "source": "compensation-2025.pdf",
        "page": 14,
        "tenant_id": "globex-corp",
        "access_group": "compensation",
        "text": (
            "Eligible employees receive restricted stock units (RSUs) as part of their compensation. "
            "RSUs vest over four years on a 25 percent annual cliff followed by quarterly vesting. "
            "Employees may participate in the Employee Stock Purchase Plan (ESPP) which allows up to "
            "10 percent of base salary to be contributed to purchase company stock at a 15 percent "
            "discount. Tax withholding on RSU vesting is handled automatically through payroll. "
            "Employees should consult a tax advisor regarding the tax implications of equity compensation."
        ),
    },
    {
        "doc_id": "hr-007",
        "title": "Continuing Education and Certifications",
        "source": "hr-handbook-2025.pdf",
        "page": 42,
        "tenant_id": "acme-corp",
        "access_group": "hr",
        "text": (
            "Acme Corp reimburses up to 5250 dollars per year for accredited continuing education "
            "including degree programs, professional certifications, and conferences directly relevant "
            "to the employee's role. Reimbursement requires manager pre approval and proof of successful "
            "completion. AWS, Azure, and Google Cloud certifications are pre approved for technical roles. "
            "Employees who leave the company within 12 months of receiving reimbursement may be required "
            "to repay a prorated portion."
        ),
    },
]
