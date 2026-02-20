# Incident Response Playbook

**Effective Date:** May 2024
**Department:** Engineering
**Status:** Active

## Incident Declaration

Any engineer can declare an incident. If you see something, say something. Better to declare and downgrade than to miss a real incident.

**To declare an incident:**
1. Run `/incident declare` in the #incidents Slack channel
2. This auto-creates: a Slack channel (#inc-NNNN), a Zoom bridge, a PagerDuty incident, and a Notion doc
3. The on-call engineer for the affected service becomes the **Incident Commander** by default

## Roles

| Role | Responsibility |
|------|---------------|
| Incident Commander (IC) | Coordinates response, makes decisions, communicates status |
| Technical Lead | Debugs and implements the fix |
| Communications Lead | Updates stakeholders every 30 min via #incidents and email |
| Scribe | Documents timeline, actions, and decisions in Notion |

## Severity Levels

**P1 — Critical**
- Service fully down OR data loss OR security breach
- Customer-facing revenue impact
- All hands on deck. Page the VP of Engineering.
- Status page updated within 15 minutes
- External customer communication within 30 minutes

**P2 — Major**
- Service degraded but partially functional
- Some customers affected
- Assigned team responds. Manager notified.
- Status page updated within 30 minutes

**P3 — Minor**
- No customer impact but internal tooling broken or elevated error rates
- Handled during business hours
- No status page update needed

## Communication Templates

### Internal Update (every 30 min during P1/P2)
```
**Incident #[NUMBER] Update — [TIMESTAMP]**
**Status**: [Investigating/Identified/Fixing/Resolved]
**Impact**: [description of user impact]
**Current actions**: [what we're doing now]
**Next update**: [time]
```

### External Update (P1 only)
Post to status.meridian.tech and email affected customers:
```
We are currently experiencing [issue description]. Our team is actively working to resolve this. We will provide an update within [timeframe].
```

## Post-Incident Process

1. **Incident Resolved**: IC sends final update, closes PagerDuty incident
2. **Within 24 hours**: IC assigns post-mortem owner (usually Technical Lead)
3. **Within 3 business days**: Post-mortem document completed in Notion
4. **Within 1 week**: Post-mortem review meeting with team + stakeholders
5. **Action items**: Tracked in Jira under the `INCIDENT` project. Must have owners and due dates.

## Post-Mortem Template

Located in Notion at: Engineering > Incident Post-Mortems > Template

Required sections: Summary, Timeline, Root Cause, Contributing Factors, Action Items, Lessons Learned.

**Post-mortems at Meridian are blameless.** We focus on improving systems, not assigning blame. Avoid language like "X failed to..." — use "The system did not..." instead.
