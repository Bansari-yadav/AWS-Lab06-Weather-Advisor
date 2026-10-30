# AWS Lab06 — Weather Advisor

Graduate cloud-computing lab built with Python/boto3, Node.js, Amazon EC2, an Application Load Balancer, Auto Scaling Groups, SSM Parameter Store, and private RDS PostgreSQL.

## Report and evidence

- [Report and requirement audit](Lab06_Report_Draft.md)
- [Screenshots and saved outputs](evidence/)

## Recorded results

- 31 unit tests passed without real AWS credentials.
- 10 live integration tests passed.
- 2 live chaos tests passed.
- All nine application smoke checks passed.
- AWS cleanup verified no named lab resources or database backups remained.

The report identifies remaining submission qualifications, including the exact-ZIP integration-test difference and Google API-key cleanup confirmation.

## Source

- `create_database.py` and `delete_database.py`
- `create_weather_stack.py` and `delete_weather_stack.py`
- `stack/` — infrastructure helpers
- `weather-app/` and `advisor-app/` — application services
- `tests/` — unit, integration, and chaos tests

The deployed AWS resources have been deleted. Historical application URLs are no longer expected to work.

Private configuration and key files are excluded. `.env.example` contains configuration examples.
