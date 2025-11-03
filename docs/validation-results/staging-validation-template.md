# Staging Validation Report Template

Use this template to document the Media Clustering staging validation pass before production rollout.

## 1. Metadata
- Date:
- Engineer(s):
- Feature Flags:
- Staging Grafana Dashboard URL:
- Related Tickets/PRs:

## 2. Dashboard Deployment
- Command:
- Response (HTTP status + body excerpt):
- Folder/UID confirmation:

## 3. Alert Tests
### Dry-Run Recap
- Payload artifact:

### Staging Alertmanager Send
- Command:
- Response status/body:
- Slack notification timestamp / screenshot:
- PagerDuty incident ID (if triggered):

## 4. End-to-End Flow Metrics
- `cluster_jobs_total` delta (success vs. failure):
- `cluster_job_duration_seconds` p95:
- `cluster_last_noise_count` before/after:
- Additional observations:

## 5. Incident Drill (Optional)
- Scenario triggered:
- Outcome & mitigation:

## 6. Follow-ups
- Runbook updates needed:
- Tickets filed:
- Production rollout blockers:

## 7. Sign-off
- Summary paragraph (copy to release notes):
- Stakeholder notifications sent:
