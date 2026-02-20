# notification-service

Handles all outbound notifications: email, Slack, and webhooks.

## Tech Stack
- Go 1.21
- Kafka consumer
- SendGrid (email)
- Slack API

## How It Works

Consumes from Kafka topic `notifications.send`:

```json
{
  "notification_id": "uuid",
  "tenant_id": "uuid",
  "channel": "email|slack|webhook",
  "recipient": "email address or webhook URL or Slack channel",
  "template": "template_name",
  "data": {}
}
```

## Templates

Email templates are stored in `templates/` directory as Go templates (.tmpl files).

Available templates:
- `incident_alert` — P1/P2 incident notification
- `weekly_digest` — Weekly analytics summary
- `password_reset` — Password reset link
- `welcome` — New user onboarding
- `usage_alert` — Near plan limit warning

## Rate Limits

- Email: 100/hour per tenant (SendGrid limit: 10,000/hour total)
- Slack: 1/second per channel (Slack API limit)
- Webhooks: 50/minute per endpoint, with exponential backoff on failures

## Retry Policy

Failed notifications are retried with exponential backoff:
- 1st retry: 1 minute
- 2nd retry: 5 minutes
- 3rd retry: 30 minutes
- After 3 failures: notification moved to dead letter queue, alert sent to #notifications-alerts

## Setup

```bash
go build -o notification-service ./cmd/server
./notification-service
```

Requires: `SENDGRID_API_KEY`, `SLACK_BOT_TOKEN`, `KAFKA_BOOTSTRAP_SERVERS`
