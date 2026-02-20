# Information Security Policy

**Effective Date:** February 2024
**Department:** Security
**Status:** Active

## Access Control

- All internal systems use **Okta SSO**. No local accounts permitted.
- **MFA required** on all accounts. Hardware keys (YubiKey) required for engineers with production access.
- Access reviews conducted **quarterly**. Managers must re-certify their reports' access.
- **Principle of least privilege**: Request only the access you need. Elevated access expires after 30 days unless renewed.

## Data Classification

| Level | Description | Examples | Handling |
|-------|------------|----------|----------|
| Public | Freely shareable | Blog posts, open-source code | No restrictions |
| Internal | Company-wide | Meeting notes, internal docs | Don't share externally |
| Confidential | Need-to-know | Customer data, financial reports | Encrypted at rest and in transit |
| Restricted | Highly sensitive | PII, credentials, security logs | Encrypted, access-logged, no local copies |

## Credentials and Secrets

- **Never** commit secrets to Git. Use **Vault** (HashiCorp) for all secrets management.
- API keys, database credentials, and service tokens must be rotated every **90 days**.
- If you suspect a credential has been exposed, immediately rotate it AND report to #security-incidents.

## Laptop Security

- FileVault (macOS) must be enabled. IT verifies during onboarding.
- Auto-lock after **5 minutes** of inactivity.
- No company data on personal devices unless using the approved MDM (Jamf).

## Vendor Security Reviews

Any new SaaS vendor that will handle customer data or connect to internal systems must pass a security review. File a request at security-review@meridian.tech. Typical turnaround: 2-3 weeks.

## Incident Reporting

Report security incidents to #security-incidents in Slack or security@meridian.tech. All reports are confidential. Do NOT attempt to investigate on your own — the security team will coordinate response.
