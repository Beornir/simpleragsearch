# PRD: Dashboard V2 Redesign

**Author:** Jessica Liu (Product Manager)
**Date:** April 2024
**Status:** In Development (targeting Q3 2024 release)

## Problem Statement

Customer satisfaction surveys show that 62% of users find the current dashboard "cluttered" and "hard to navigate." The average time to find a specific metric is 4.2 clicks, compared to our target of 2.

## Goals

1. Reduce average clicks-to-metric from 4.2 to 2 or fewer
2. Increase dashboard NPS from 32 to 50+
3. Support customizable layouts (drag-and-drop widgets)
4. Mobile-responsive design (30% of logins are from mobile)

## Key Features

### Customizable Widgets
Users can add, remove, and rearrange dashboard widgets. Default layout provided per role (admin, analyst, viewer).

### Saved Views
Users can save and name custom dashboard configurations. Share with team members.

### Real-Time Refresh
Dashboards auto-refresh every 30 seconds. Websocket connection for live data streaming (previously polled every 2 minutes).

### Export
One-click export of any widget's data as CSV or PDF. Full dashboard export as PDF for reports.

## Technical Requirements

- Frontend: React + D3.js for charting (replacing our current Chart.js implementation)
- Backend: New `/v2/dashboard` API endpoints. Must maintain backward compatibility with v1 for 6 months.
- Performance: Dashboard initial load under 2 seconds (p95). Widget data load under 500ms (p95).
- Feature flagged: `dashboard-v2` flag in LaunchDarkly. Gradual rollout starting with beta customers.

## Timeline

| Milestone | Date | Description |
|-----------|------|-------------|
| Design complete | May 15, 2024 | Figma designs approved |
| Alpha (internal) | June 30, 2024 | Internal dogfooding |
| Beta (10% customers) | Aug 15, 2024 | Selected customers opted in |
| GA | Oct 1, 2024 | Full rollout, v1 deprecated |
| V1 sunset | April 1, 2025 | V1 endpoints removed |

## Open Questions

- Do we need offline support? (mobile users with spotty connections)
- Budget for D3.js migration: Frontend team estimates 6 weeks.
- How do we handle customers with complex v1 saved queries?
