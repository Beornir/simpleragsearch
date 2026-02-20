# Data Retention Policy

**Effective Date:** August 2024
**Department:** Legal / Engineering
**Status:** Active

## Customer Data

- **Active customer data**: Retained for the duration of the customer relationship plus 30 days after account closure.
- **Usage logs**: Retained for **12 months**, then aggregated and anonymized.
- **Payment information**: PCI-compliant storage through Stripe. We do not store raw card numbers. Tokenized records retained for **7 years** per financial regulations.

## Internal Data

- **Slack messages**: Retained for **2 years**, then archived. Archived messages are searchable but not in the main Slack interface.
- **Code repositories**: Retained indefinitely in GitHub. Branch cleanup: branches merged to main are auto-deleted after 30 days.
- **Meeting recordings**: Auto-deleted after **90 days** unless explicitly saved to the Notion knowledge base.
- **Employee data**: Retained for duration of employment plus **3 years** after departure.

## GDPR and CCPA

- Customers can request data export or deletion through the Privacy Center (privacy.meridian.tech).
- Deletion requests must be fulfilled within **30 days**.
- Engineering implementation: the `data-privacy-service` handles deletion cascades across all services. See the service README for details.

## Backups

- Database backups: Daily snapshots retained for **30 days**. Weekly snapshots retained for **6 months**.
- Backup location: AWS S3 in us-west-2, with cross-region replication to us-east-1.
- Backup encryption: AES-256 with keys managed in AWS KMS.

## Contact

Data retention questions: legal@meridian.tech or #data-privacy in Slack.
