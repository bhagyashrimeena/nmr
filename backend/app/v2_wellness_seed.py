"""Tenant-scoped education, plan rules and seminar fixtures."""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from .v2_models import WellnessBenefitAccess, WellnessBenefitRule, WellnessContentV2, WellnessSeminar


def seed_wellness(db: Session):
    items = [
        ("ED-RET-01", "toyota-demo", "Planning for retirement", "retirement", "PUBLISHED", date(2027, 5, 31)),
        ("ED-EQ-01", "toyota-demo", "Understanding equity awards", "equity", "PUBLISHED", date(2027, 5, 31)),
        ("ED-DRAFT-01", "toyota-demo", "Investment basics", "investment", "DRAFT", date(2027, 5, 31)),
        ("ED-EXPIRED-01", "toyota-demo", "Prior benefits overview", "benefits", "PUBLISHED", date(2026, 10, 31)),
        ("ED-SAK-01", "secondary-demo", "Saving through work", "saving", "PUBLISHED", date(2027, 5, 31)),
    ]
    for item_id, tenant_id, title, category, state, expiry in items:
        if not db.get(WellnessContentV2, item_id):
            db.add(WellnessContentV2(id=item_id, tenant_id=tenant_id, title=title,
                                     category=category, language="en",
                                     body=f"{title}: review your employer plan documents and account details before making decisions.",
                                     state=state, source_reference=f"NMR-EDU-{item_id}",
                                     effective_date=date(2026, 1, 1), review_expires_on=expiry, revision=1))
    if not db.get(WellnessBenefitRule, "BEN-TOYOTA-SHARE"):
        db.add(WellnessBenefitRule(id="BEN-TOYOTA-SHARE", tenant_id="toyota-demo",
                                   benefit_key="shareholding_incentive",
                                   rule_text="The employer adds 5% to eligible monthly shareholding contributions.",
                                   source_reference="TOYOTA-SHARE-01/RULES/2026", effective_date=date(2026, 1, 1),
                                   review_expires_on=date(2027, 12, 31)))
    if not db.get(WellnessBenefitAccess, "BEN-TOYOTA-SHARE"):
        db.add(WellnessBenefitAccess(rule_id="BEN-TOYOTA-SHARE", underlying_service="stock"))
    if not db.get(WellnessBenefitRule, "BEN-TOYOTA-DC"):
        db.add(WellnessBenefitRule(id="BEN-TOYOTA-DC", tenant_id="toyota-demo",
                                   benefit_key="corporate_pension_contributions",
                                   rule_text="The employer contributes to the corporate defined-contribution plan. Participant top-ups are permitted under this plan.",
                                   source_reference="TOYOTA-DC-01/RULES/2026", effective_date=date(2026, 1, 1),
                                   review_expires_on=date(2027, 12, 31)))
    if not db.get(WellnessBenefitAccess, "BEN-TOYOTA-DC"):
        db.add(WellnessBenefitAccess(rule_id="BEN-TOYOTA-DC", underlying_service="pension"))
    if not db.get(WellnessSeminar, "SEM-TOYOTA-01"):
        db.add(WellnessSeminar(id="SEM-TOYOTA-01", tenant_id="toyota-demo",
                               title="Workplace savings and benefits", starts_at=datetime(2026, 12, 8, 9, tzinfo=timezone.utc),
                               capacity=40, registrations=18, status="OPEN"))
    db.commit()
