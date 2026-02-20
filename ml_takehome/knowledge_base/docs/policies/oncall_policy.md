# On-Call Policy

**Effective Date:** March 1, 2024
**Department:** Engineering
**Status:** Active

## Overview

All backend and infrastructure engineers participate in the on-call rotation. On-call shifts run for one week, Monday 9am to Monday 9am Pacific Time.

## Rotation Schedule

- Rotations are managed in **PagerDuty** under the "Meridian Primary" schedule.
- Each team maintains its own rotation. Current teams: Platform, Payments, Search, ML Infrastructure.
- Engineers are on-call approximately **once every 6 weeks** (varies by team size).

## Expectations During On-Call

1. **Response time**: Acknowledge pages within **15 minutes** during business hours (9am-6pm PT), **30 minutes** outside business hours.
2. **Availability**: Must have laptop and reliable internet access. No international travel without a swap arranged.
3. **Escalation**: If you cannot resolve a P1 within 30 minutes, escalate to the **secondary on-call** via PagerDuty. If secondary is unreachable, page the Engineering Manager.

## Compensation

- **Weekday on-call**: $200/day stipend
- **Weekend/holiday on-call**: $400/day stipend
- **Incident response**: If paged between 10pm-7am and spend >30 minutes responding, you may take equivalent time off the next business day (no PTO required).

## Swaps and Overrides

- Arrange swaps directly in PagerDuty. No manager approval needed for swaps.
- For planned absences, find your own replacement at least **1 week in advance**.
- If unable to find a swap, notify your Engineering Manager at least 3 business days ahead.

## Incident Severity Definitions

| Severity | Definition | Response Target |
|----------|-----------|----------------|
| P1 | Service fully down, revenue impact | 15 min |
| P2 | Degraded service, partial impact | 30 min |
| P3 | Minor issue, no user impact | Next business day |
| P4 | Cosmetic or low-priority | Sprint planning |

## Post-Incident

All P1 and P2 incidents require a **post-mortem within 3 business days**. Use the template in Notion under "Engineering > Incident Post-Mortems". Post-mortems are blameless — focus on systemic improvements, not individual errors.

## Contact

On-call questions: #oncall-help in Slack or oncall@meridian.tech
