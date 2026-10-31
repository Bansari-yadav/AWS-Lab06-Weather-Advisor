# AWS Lab06 — Weather Advisor

Graduate cloud-computing lab built with Python/boto3, Node.js, Amazon EC2, an Application Load Balancer, Auto Scaling Groups, SSM Parameter Store, and private RDS PostgreSQL.

## Report and evidence

- [Screenshots and saved outputs](evidence/)

## Recorded results

- 31 unit tests passed without real AWS credentials.
- 10 live integration tests passed.
- 2 live chaos tests passed.
- All nine application smoke checks passed.
- AWS cleanup verified no named lab resources or database backups remained.

The final deployed integration suite explicitly verified ZIP 60616 miss then hit and history, with all ten tests passing. See SS22 and the final-revision output in evidence/. Final cleanup is verified in SS23. Google API-key deletion still requires student confirmation.

## Source

- `create_database.py` and `delete_database.py`
- `create_weather_stack.py` and `delete_weather_stack.py`
- `stack/` — infrastructure helpers
- `weather-app/` and `advisor-app/` — application services
- `tests/` — unit, integration, and chaos tests

The deployed AWS resources have been deleted. Historical application URLs are no longer expected to work.

Private configuration and key files are excluded. `.env.example` contains configuration examples.

## Screenshot evidence

Screenshots record separate stages of the lab. SS22 shows the final integration run; SS23 shows the final cleanup. Earlier test counts and recovery measurements belong to earlier runs.

### API exploration

**SS1 — ZIP 60616 lookup**

![SS1: ZIP 60616 lookup](evidence/SS1.png)

**SS2 — NWS points and forecast URL**

![SS2: NWS points and forecast URL](evidence/SS2.png)

**SS3 — First forecast period**

![SS3: First forecast period](evidence/SS3.png)

**SS4 — SSM SecureString metadata; secret value hidden**

![SS4: SSM SecureString metadata; secret value hidden](evidence/SS4.png)

### Unit tests and database creation

**SS5 — Database unit tests**

![SS5: Database unit tests](evidence/SS5.png)

**SS6 — Stack unit tests**

![SS6: Stack unit tests](evidence/SS6.png)

**SS7 — Initial complete unit suite**

![SS7: Initial complete unit suite](evidence/SS7.png)

**SS8 — Database creation**

![SS8: Database creation](evidence/SS8.png)

**SS9 — Database settings and healthy application targets**

![SS9: Database settings and healthy application targets](evidence/SS9.png)

### Application and database evidence

**SS10 — Nine application smoke checks**

![SS10: Nine application smoke checks](evidence/SS10.png)

**SS11 — Deployed Weather Advisor page**

![SS11: Deployed Weather Advisor page](evidence/SS11.png)

**SS12 — Weather service journal**

![SS12: Weather service journal](evidence/SS12.png)

**SS13 — Saved lookup rows and SQL count**

![SS13: Saved lookup rows and SQL count](evidence/SS13.png)

**SS14 — Database failure log and continued weather response**

![SS14: Database failure log and continued weather response](evidence/SS14.png)

### Gemini fallback and restoration

**SS15 — Advisor Gemini error journal**

![SS15: Advisor Gemini error journal](evidence/SS15.png)

**SS16a — Fallback responses with an invalid test key**

![SS16a: Fallback responses with an invalid test key](evidence/SS16a.png)

**SS16b — Real key restored and smoke checks passed**

![SS16b: Real key restored and smoke checks passed](evidence/SS16b.png)

### Recovery and graduate tests

**SS17a — Advisor outage behavior and initial recovery measurement**

![SS17a: Advisor outage behavior and initial recovery measurement](evidence/SS17a.png)

**SS17b — Initial recovery and subsequent smoke checks**

![SS17b: Initial recovery and subsequent smoke checks](evidence/SS17b.png)

**SS18 — Initial live integration suite**

![SS18: Initial live integration suite](evidence/SS18.png)

**SS19 — Graduate chaos tests and 77.7-second recovery**

![SS19: Graduate chaos tests and 77.7-second recovery](evidence/SS19.png)

### Cleanup and final verification

**SS20 — First deployment cleanup verification**

![SS20: First deployment cleanup verification](evidence/SS20.png)

**SS21a — Project folder layout**

![SS21a: Project folder layout](evidence/SS21a.png)

**SS21b — Earlier unit tests without real AWS credentials**

![SS21b: Earlier unit tests without real AWS credentials](evidence/SS21b.png)

**SS22 — Final integration suite: ZIP 60616 miss, hit, history, and ten tests passed**

![SS22: Final integration suite: ZIP 60616 miss, hit, history, and ten tests passed](evidence/SS22.png)

**SS23 — Final deployment cleanup: all checked lab resources absent**

![SS23: Final deployment cleanup: all checked lab resources absent](evidence/SS23.png)
