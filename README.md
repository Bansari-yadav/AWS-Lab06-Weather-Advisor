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

## Required questions and written answers

**Student:** Bansari Yadav
**Course:** ITMO 544 — Graduate

This write-up addresses the written prompts in Parts A and H, the three paragraphs in Section 16.1, all 13 review questions in Section 15.1, and both graduate short answers in Section 16.2 of *Weather_Advisor_TwoTier_APIs.pdf*. Screenshot numbers organize the evidence; the professor did not prescribe those numbers.

## Parts A and H — Experiment questions and explanations

### Part A — Why more than one upstream request is needed

The ZIP lookup provider converts a ZIP code to coordinates, NWS `/points` converts those coordinates to a forecast URL, and a request to that URL returns the forecast: there are two API providers and three HTTP requests on a cache miss. The PDF's references to “two upstream calls” should not obscure this actual request sequence. ZIP 00000 returned 404. The manual NWS example used the coordinates printed in the assignment; the application uses the ZIP provider's returned coordinates.

### H1 — Explain one weather_success line

The journal entry at `02:51:28.032Z` records ZIP 60616 with `cache: hit` and `ms: 2`, meaning weather served a recent database forecast in 2 milliseconds rather than fetching it again from the public providers. The preceding miss for that ZIP took 156 milliseconds. These are service-side journal durations, distinct from the end-to-end timing experiment below.

### H2 — Explain the stored rows

The direct SQL screenshot shows five saved rows, including ZIPs 90210, 10001, 60616, and 98101, and `saved_lookups = 5` at that point in the experiment. This count was a snapshot before later tests added more data. There are fewer saved rows than total requests because a cache hit reuses a row instead of inserting another one; invalid ZIP requests also do not create saved forecasts. Repeated SELECT queries caused by the browser's duplicate paste behavior only read data and did not add rows.

### H3 — Cache timing and two required sentences

For ZIP 98101, the first measured response was HTTP 200 with `cache: miss` in **0.182 seconds**; the second was HTTP 200 with `cache: hit` in **0.067 seconds**. Cache status and timing were obtained from the same request rather than timing one request and printing another request's cache status.

A short cache reduces repeated upstream work and helps avoid consuming a rate-limited provider's quota unnecessarily. Weather cache lifetimes should not be too long because a technically successful response can still be misleading if it describes conditions that have already changed.

### H4 — Database settings and network isolation

The live RDS response showed `db.t4g.micro`, PostgreSQL, `MultiAZ: false`, `Public: false`, `Encrypted: true`, and `BackupRetentionDays: 0`. Snapshot and automated-backup lists were empty. A port-5432 connection from the local computer timed out. The database was reachable from weather over verified TLS, as exercised by working cache/history calls and the direct `psql` command configured with `sslmode=verify-full` and the RDS CA bundle.

### H5 — Least privilege

| Role | Database password | Gemini key |
|---|---|---|
| Weather | allowed | implicitDeny |
| Advisor | implicitDeny | allowed |

An attacker controlling advisor could use its instance role to read the Gemini key, but that role would not authorize reading the database password; the shared app security group still permits network attempts to the database port, which is a separate design limitation.

### H6 — Security-group sources

Direct HTTP requests to port 3000 timed out for both weather and advisor, while requests through their ALB listeners returned HTTP 200. A rule naming the ALB security group permits traffic associated with that group and follows instance/address changes, whereas a CIDR rule permits an address range rather than expressing that security-group relationship.

### H7 — Database failure and the retry pause

After revoking the database ingress rule and restarting weather to close existing connections, weather returned HTTP 200 with `cache: unavailable`, while `/history` returned HTTP 503 and `database_unavailable`. The journal recorded a database connection timeout. Restoring the rule and waiting for the retry pause allowed HTTP 200 responses with `cache: miss` again. The 30-second pause prevents every incoming request from repeatedly paying a database-connection timeout while the database is unreachable.

### H8 — Gemini failure and silent fallback

The stored API key was temporarily overwritten with an invalid test value. After waiting for the 60-second key cache to expire, all three calls returned HTTP 200 with `source: fallback` and rule-based clothing advice. Advisor journal entries recorded `gemini_error`, status 400, and `gemini_http_error`. The real key was restored, the cache was allowed to expire again, and all nine smoke checks passed with Gemini as the source. Silent fallback can hide a persistent provider failure from operators unless logs are monitored and degradation triggers alerts.

### H9 — Recovery and state placement

The initial experiment recovered in **80.3 seconds**. The separate marked chaos test recovered in **77.7 seconds**, also below the required 300 seconds. These are separate runs, not contradictory measurements. During the outage, advisor returned HTTP 502 with `weather_service_unavailable`; its homepage continued to return HTTP 200. The replacement weather instance returned a cache hit for 60616, showing that its useful state survived in RDS. Durable state should live outside replaceable instances so replacing an instance does not discard data needed by the new one. Recovery times are sampled observations, not a guarantee that every future recovery will take the same time.

## Section 16.1 — Three required written paragraphs

### Why secrets belong in SSM

The Gemini API key and database password were stored as Standard SSM SecureStrings, with only parameter names in application configuration and launch-template user-data. This avoids placing reusable secrets in source code, a committed `.env`, screenshots, or user-data that can be inspected through AWS APIs. Separate instance roles limit the damage from a compromise: weather reads only the database-password ARN, and advisor reads only the Gemini-key ARN. The permissions of the local provisioning user are separate from those application roles. Python used `getpass` for Gemini input and `secrets.token_hex(16)` for the database password; evidence files contain metadata and results rather than real secret values.

### Why backups were disabled for this lab

Retention 0 eliminated automated backup retention and avoided leaving backup copies of disposable public-forecast cache data. Deletion also requested no final snapshot and removal of automated backups. The tradeoff is that the history/cache cannot be recovered through those backups after loss or deletion. That is acceptable for this temporary lab because the data can be regenerated and the database is intentionally destroyed afterward. It would be inappropriate for important production or regulated data without an approved recovery and retention design. For such data I would configure appropriate backup retention and recovery objectives, protection against accidental deletion, and tested restoration procedures.

### Data shared with Gemini

The supplied `buildPrompt` sends the ZIP code, city, state, forecast period, temperature and unit, conditions, wind, and precipitation probability, together with a short system instruction to produce clothing advice. It does not send a user's name, school email, street address, AWS account ID, database history, or AWS credentials as prompt content. The API key is an authentication header rather than weather prompt content. The assignment warns that free-tier prompt handling may permit product improvement and human review; that makes data minimization and checking the actual account/service terms necessary before using private data. The NWS contact email is used to identify NWS requests, not included in `buildPrompt`.

## Section 15.1 — Security and privacy review: 13 questions and answers

The question headings below paraphrase the professor's prompts; the answers describe this implementation and its limitations.

### Question 1 — Secret storage: Where else could each secret leak, including shell history, process lists, logs, screenshots, and Git?

Secrets can leak through shell history, process arguments, debug logs, committed configuration, screenshots, terminal recordings, temporary files, copied errors, and chat messages. Hidden input avoids echo and command-history entry, but applications still need the value in memory while authenticating. Avoid logging request headers or secret-bearing boto3 request dictionaries, limit who can inspect the process, and rotate any exposed key.

### Question 2 — Least privilege: What would change if both roles had ssm:* on *?

Either compromised tier could potentially read, modify, or delete parameters far beyond its own secret, subject to other policies and encryption controls. It would remove the intended separation between advisor and weather and broaden the blast radius to other applications' parameters. Each application role should receive only the required read action on its exact parameter ARN.

### Question 3 — Network exposure: Why is the ALB open to the internet but application and database access restricted?

The ALB is the client entry point and must receive requests on its public listeners. Backend application port 3000 is restricted to the ALB security group, and the database has no public access and accepts PostgreSQL from the app group. The EC2 instances do have public IPs in this lab; it is their application-port access that is restricted, not a claim that the instances have no public addresses. Temporary administrative SSH access was separately restricted and removed.

### Question 4 — Shared security group: What can an advisor instance do that it should not, and how would you fix it?

Advisor can attempt a TCP connection to the database because both tiers share the source security group allowed by the database rule. Its IAM role cannot read the database password, but network reachability is still broader than necessary. Give weather and advisor separate security groups and allow database port 5432 only from weather's group.

### Question 5 — Database login: What would you create instead of the master login, and which privileges would it need?

Provision the table/index through a separate administrative or migration identity. Run weather with a dedicated non-superuser login that has CONNECT to the database, USAGE on the relevant schema, SELECT and INSERT on `lookups`, and the sequence privilege needed by its generated ID. It should not have broad DDL, role-management, update, or deletion privileges merely to serve cache/history requests. Removing runtime CREATE TABLE/INDEX privileges also requires moving that initialization out of the application.

### Question 6 — Encryption: What does certificate verification protect against that TLS without verification does not?

Encryption protects traffic from being read in transit. Certificate and hostname verification additionally checks that the server is the expected trusted endpoint, reducing the risk of an encrypted connection to an impersonator. The RDS CA bundle and `verify-full` configuration are used for that identity check.

### Question 7 — SQL injection: Show one application line and explain what could go wrong if SQL were built by joining strings.

The application uses:

```javascript
pool.query('INSERT INTO lookups (zip, payload) VALUES ($1, $2)', [zip, JSON.stringify(payload)])
```

The placeholders keep values separate from SQL syntax. Joining untrusted input directly into a SQL string can allow input to alter the query's meaning. Five-digit ZIP validation is helpful but is not a replacement for parameterized queries.

### Question 8 — Backups: What would you lose with real data, and what would you configure instead?

The lab gives up automated backup-based recovery and point-in-time recovery; with no final/manual snapshot, deletion removes the database's stored data without those recovery copies. Important workloads need recovery objectives, suitable backup retention, protected copies where appropriate, and restore tests rather than assuming a backup setting alone proves recoverability.

### Question 9 — Data lifecycle: Who decides when stored data may be destroyed in a real organization?

The organization's designated data owner and authorized retention/governance process should determine destruction timing, with security, records-management, compliance, and legal stakeholders as applicable. An engineer should execute an approved lifecycle policy and account for retention obligations or holds instead of deciding unilaterally that stored data is no longer needed.

### Question 10 — Untrusted output: What could an attacker gain if the page printed raw model output?

A model could return attacker-influenced markup or script-bearing HTML. Rendering it as trusted markup could enable cross-site scripting, page manipulation, or theft of information accessible to that page. The supplied page escapes output through `escapeHtml`; model output is treated as untrusted even when the model service itself is legitimate.

### Question 11 — Third-party data: What must change before using a paid or school-owned Gemini account for real users?

Confirm institutional authorization, the particular account's contractual data terms, retention and training settings, permitted data categories, and required notices/consent before sending real-user data. Apply data minimization, access controls, and a reviewed secret-management design. A paid tier or school-owned account does not by itself establish that every proposed disclosure is permitted.

### Question 12 — Abuse and cost: How could someone exhaust the quota, and what protections could you add?

An unauthenticated public endpoint can be repeatedly requested to trigger Gemini calls and consume quota or billable service usage. Add rate limits, request budgets, monitoring, and appropriate authentication or WAF controls, while considering caching and abuse detection. Rate-limit handling and fallback keep the app useful but do not prevent the abuse by themselves.

### Question 13 — Availability: Why must responses identify source: fallback or cache: unavailable?

The labels distinguish a rule-based suggestion from model-generated advice and an uncached forecast from a database-backed response. This makes degraded operation observable and avoids presenting a successful HTTP response as proof that every dependency is healthy. Operators can alert on those fields and users can understand the answer's source.

## Section 16.2 — Graduate short answers

### Graduate question 1 — What could moto not prove, and which integration tests cover each gap?

**Requested length:** approximately half a page.

Moto tests verify that Python builds the intended requests, stores mocked resources, restricts the generated policy documents, handles repeated creation/deletion, and keeps user-data below the EC2 limit. However, a successful mocked test is not proof that AWS actually enforced those settings. The live `test_database_tls_and_backup_configuration` checks actual RDS properties and lists snapshots and automated backups. The post-deletion verification separately checks that the database and retained copies are absent. This matters because a simulated delete API cannot establish that real cloud storage has finished disappearing.

Network behavior is another gap. A mocked security-group rule can have the correct fields while a real subnet, routing table, security group, or endpoint is misconfigured. The live `test_application_access_only_through_alb` tests both tiers from the local computer, requiring direct connection timeouts and ALB success. `test_database_port_unreachable_from_computer` checks the private database boundary. Healthy target groups and successful history/cache requests provide additional checks that the intended internal paths work.

Moto does not establish a real TLS handshake, certificate chain, hostname verification, PostgreSQL authentication, or SQL execution. The live cache/history test exercises the deployed app's configured verified-TLS connection, and the browser-session `psql` query explicitly used `sslmode=verify-full` with the downloaded RDS CA bundle. These are positive-path checks; I did not run a deliberately invalid-certificate or impersonated-server negative test, so I do not claim that broader proof.

Finally, a local model cannot predict IAM propagation, EC2 boot duration, real Gemini behavior, or replacement timing. Live IAM simulation checks both roles against both parameter ARNs. The marked chaos tests revoke database access and terminate weather, asserting graceful degradation and recovery within 300 seconds. These complement request-level unit tests with observations of actual cloud behavior, while remaining measurements of these runs rather than universal availability guarantees.

### Graduate question 2 — Compare Python and bash for the same step: what was easier to get right and easier to test?

**Requested length:** one paragraph.

For creating the database, Python made it easier to separate configuration, network discovery, password generation, request construction, waiting, and output writing into small functions. Boto3 returns structured dictionaries, so the code can inspect fields directly rather than passing JSON through shell parsing. Catching specific `ClientError` codes distinguishes a missing resource or duplicate from a genuine permission failure. The password can be generated in memory and passed to SSM/RDS without putting the value in a shell command. Bash is concise for a short manual sequence and makes AWS CLI steps easy to recognize, but quoting, pipelines, exit codes, and secret-bearing arguments need extra care. Python's request builder and mocked clients were easier to test for exact settings, repeat creation, cleanup, and absence of printed secrets. Both versions still need real integration tests because neither a shell script nor a mocked boto3 test can prove actual networking, TLS, backups, or recovery timing alone.


## Final validation and cleanup evidence

The final deployment passed all **10 integration tests**, explicitly showing ZIP **60616 miss → hit** and its saved history. The final revision passed **31 unit tests**; the recorded graduate chaos suite passed **2 tests**. The final cleanup verification showed every checked named lab-resource list empty.

- [Final integration output](evidence/final_revision_integration_tests.txt)
- [Final unit-test output](evidence/final_revision_unit_tests.txt)
- [Final cleanup verification](evidence/final_revision_cleanup_verification.txt)
- [Final integration screenshot](evidence/SS22.png)
- [Final cleanup screenshot](evidence/SS23.png)

The AWS SSM copy of the Gemini key is deleted. Deletion or restriction of the actual replacement key in Google AI Studio still needs confirmation; deleting an SSM copy does not revoke Google's key.

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
