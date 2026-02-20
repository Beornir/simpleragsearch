# Runbook: PostgreSQL Failover

**Owner:** Platform Team
**Last Tested:** April 2024

## When to Use

Use this runbook when the primary PostgreSQL instance is unhealthy and automatic failover has not triggered (or has failed).

## Prerequisites

- You have `kubectl` access to the production cluster
- You have DBA-level access in AWS RDS console
- You are the Incident Commander or have IC approval

## Steps

### 1. Verify the Problem

```bash
# Check connection to primary
psql -h meridian-db-primary.cluster-xyz.us-west-2.rds.amazonaws.com -U meridian_app -c "SELECT 1"

# Check replication lag
aws rds describe-db-instances --db-instance-identifier meridian-db-read-1 | jq '.DBInstances[0].StatusInfos'
```

If the primary is unreachable and replication lag is < 5 seconds, proceed with failover.

### 2. Promote Read Replica

```bash
aws rds promote-read-replica --db-instance-identifier meridian-db-read-1
```

This takes approximately 5-10 minutes. Monitor in the RDS console.

### 3. Update DNS

The application connects via a CNAME record. Update it:

```bash
# Update Route53 record
aws route53 change-resource-record-sets --hosted-zone-id Z1234567890 --change-batch '{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "meridian-db-primary.internal.meridian.tech",
      "Type": "CNAME",
      "TTL": 60,
      "ResourceRecords": [{"Value": "meridian-db-read-1.cluster-xyz.us-west-2.rds.amazonaws.com"}]
    }
  }]
}'
```

### 4. Restart Application Pods

Connection pools will be stale. Rolling restart:

```bash
kubectl rollout restart deployment api-gateway -n production
kubectl rollout restart deployment event-processor -n production
kubectl rollout restart deployment workflow-engine -n production
```

### 5. Verify Recovery

```bash
# Check application health
curl https://api.meridian.tech/health

# Check database connections
kubectl exec -it deploy/api-gateway -n production -- python -c "from app.db import engine; print(engine.execute('SELECT count(*) FROM events').scalar())"
```

### 6. Post-Failover

- Create a new read replica from the promoted instance
- Update PagerDuty to reflect new primary
- File incident post-mortem

## Estimated Recovery Time

- Automatic failover (when it works): ~2 minutes
- Manual failover using this runbook: ~15-20 minutes
- Full restore from backup (worst case): ~2-4 hours

## Contact

DBA on-call: Check PagerDuty "DBA" schedule. Escalation: Sarah Chen (Staff Eng, Platform).
