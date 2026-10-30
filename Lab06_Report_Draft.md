# Lab 06: Weather Advisor in the Cloud

**Course:** ITMO 544 — Graduate submission  
**Student:** Bansari Yadav  
**Status:** Draft for student review. Live AWS testing and AWS cleanup are complete. Deletion of the replacement Google AI Studio key still needs confirmation.

## 1. Implementation and architecture

This lab extends the lab05 Python `stack/` package. Infrastructure creation and deletion use boto3 through `create_database.py`, `delete_database.py`, `create_weather_stack.py`, and `delete_weather_stack.py`. Both application services remain Node.js applications as specified in the assignment.

One internet-facing Application Load Balancer serves weather on port 8080 and advisor on port 8081. Each tier has a target group, launch template, IAM instance profile, and Auto Scaling Group. Application traffic on instance port 3000 is accepted from the ALB security group. The advisor calls the weather service through the ALB rather than using a particular instance address. Only weather reads the PostgreSQL password and uses the database. Advisor reads the Gemini API key. The two instance roles each have `ssm:GetParameter` on one exact parameter ARN.

The RDS PostgreSQL instance used `db.t4g.micro`, 20 GB storage, encrypted storage, one Availability Zone, no public access, and backup retention 0. Weather uses it as a forecast cache and lookup history. `CACHE_SECONDS` is 600 and the Gemini key cache is 60 seconds. The ALB is created before launch templates so advisor user-data can receive its DNS name. Weather user-data receives the database endpoint and the parameter name rather than the database password.

The private key file was unavailable locally, so service logs and SQL results were collected using EC2 Instance Connect. Its port-22 rule allowed the AWS-managed Instance Connect prefix list rather than the entire internet. That temporary rule was removed during cleanup.

## 2. Shared submission evidence — Section 16.1

Paths below are relative to the submitted `lab06` folder. Screenshot numbers are organizational labels, not instructor requirements.

| Assignment item | Evidence |
|---|---|
| Part 0 layout | [First 40 lines](evidence/Part0_folder_layout_first40.txt), [full layout](evidence/Part0_folder_layout_full.txt), [SS21a](evidence/SS21a.png). These are PowerShell/Python equivalents of the bash directory listing. |
| Part A ZIP and NWS calls | [ZIP 60616](evidence/A1_zip_60616.txt), [ZIP 00000](evidence/A1_zip_00000.txt), [NWS points](evidence/A2_nws_points_full.json), [forecast URL](evidence/A2_forecast_url.txt), [full forecast](evidence/A2_nws_forecast_full.json), [first period](evidence/A2_first_forecast_period.txt), SS1–SS3. |
| Database creation and settings | [Creation output](evidence/E2_database_creation.txt), [properties and backups](evidence/H4_database_verification.json), [SS8](evidence/SS8.png), [SS9](evidence/SS9.png). |
| Advisor page and same-ZIP JSON | [Required deployed-page screenshot, SS11](evidence/SS11.png), [60616 advice JSON](evidence/G2_advice_60616.json). Both use ZIP 60616; generated wording can differ between separate calls. |
| Nine-check smoke test | [Output](evidence/G3_smoke_test.txt), [SS10](evidence/SS10.png). |
| H1 weather journal | [Saved output](evidence/H1_weather_journal.txt), [SS12](evidence/SS12.png). |
| H2 history and SQL | [History JSON](evidence/H2_history.json), [SQL output screenshot, SS13](evidence/SS13.png). |
| H3 cache measurements | [Actual timing results](evidence/H3_cache_timings.json). |
| H4 external DB connection | [Connection result](evidence/H4_external_connection.json). |
| H5 four IAM decisions | [Simulator results](evidence/H5_iam_simulation.json). |
| H6 direct and ALB results | [Network results](evidence/H6_network_isolation.json). |
| H7 database isolation | [Responses and restoration](evidence/H7_database_failure.json), [db_error screenshot, SS14](evidence/SS14.png). The later chaos run refreshed the JSON; SS14 preserves the original run's journal. |
| H8 Gemini fallback | [Three responses](evidence/H8_fallback_answers.json), [Gemini journal, SS15](evidence/SS15.png), [restored smoke test](evidence/H8_restored_smoke_test.txt), [SS16a](evidence/SS16a.png), [SS16b](evidence/SS16b.png). |
| H9 weather replacement | [Latest recovery record](evidence/H9_weather_recovery.json), [initial run screenshots, SS17a](evidence/SS17a.png) and [SS17b](evidence/SS17b.png), [later chaos-run screenshot, SS19](evidence/SS19.png). |
| H10 cleanup proof | [Verification JSON](evidence/H10_final_verification.json), [verification output](evidence/H10_final_verification.txt), [SS20](evidence/SS20.png). |

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

## 3. Required shared paragraphs

### Why secrets belong in SSM

The Gemini API key and database password were stored as Standard SSM SecureStrings, with only parameter names in application configuration and launch-template user-data. This avoids placing reusable secrets in source code, a committed `.env`, screenshots, or user-data that can be inspected through AWS APIs. Separate instance roles limit the damage from a compromise: weather reads only the database-password ARN, and advisor reads only the Gemini-key ARN. The permissions of the local provisioning user are separate from those application roles. Python used `getpass` for Gemini input and `secrets.token_hex(16)` for the database password; evidence files contain metadata and results rather than real secret values.

### Why backups were disabled for this lab

Retention 0 eliminated automated backup retention and avoided leaving backup copies of disposable public-forecast cache data. Deletion also requested no final snapshot and removal of automated backups. The tradeoff is that the history/cache cannot be recovered through those backups after loss or deletion. That is acceptable for this temporary lab because the data can be regenerated and the database is intentionally destroyed afterward. It would be inappropriate for important production or regulated data without an approved recovery and retention design. For such data I would configure appropriate backup retention and recovery objectives, protection against accidental deletion, and tested restoration procedures.

### Data shared with Gemini

The supplied `buildPrompt` sends the ZIP code, city, state, forecast period, temperature and unit, conditions, wind, and precipitation probability, together with a short system instruction to produce clothing advice. It does not send a user's name, school email, street address, AWS account ID, database history, or AWS credentials as prompt content. The API key is an authentication header rather than weather prompt content. The assignment warns that free-tier prompt handling may permit product improvement and human review; that makes data minimization and checking the actual account/service terms necessary before using private data. The NWS contact email is used to identify NWS requests, not included in `buildPrompt`.

## 4. Section 15.1 — All review answers

### 1. Secret storage: where else could secrets leak?

Secrets can leak through shell history, process arguments, debug logs, committed configuration, screenshots, terminal recordings, temporary files, copied errors, and chat messages. Hidden input avoids echo and command-history entry, but applications still need the value in memory while authenticating. Avoid logging request headers or secret-bearing boto3 request dictionaries, limit who can inspect the process, and rotate any exposed key.

### 2. Least privilege: what if both roles had ssm:* on *?

Either compromised tier could potentially read, modify, or delete parameters far beyond its own secret, subject to other policies and encryption controls. It would remove the intended separation between advisor and weather and broaden the blast radius to other applications' parameters. Each application role should receive only the required read action on its exact parameter ARN.

### 3. Network exposure: why expose the ALB?

The ALB is the client entry point and must receive requests on its public listeners. Backend application port 3000 is restricted to the ALB security group, and the database has no public access and accepts PostgreSQL from the app group. The EC2 instances do have public IPs in this lab; it is their application-port access that is restricted, not a claim that the instances have no public addresses. Temporary administrative SSH access was separately restricted and removed.

### 4. Shared security group: what can advisor do, and how would I fix it?

Advisor can attempt a TCP connection to the database because both tiers share the source security group allowed by the database rule. Its IAM role cannot read the database password, but network reachability is still broader than necessary. Give weather and advisor separate security groups and allow database port 5432 only from weather's group.

### 5. Database login: what should replace the master login?

Provision the table/index through a separate administrative or migration identity. Run weather with a dedicated non-superuser login that has CONNECT to the database, USAGE on the relevant schema, SELECT and INSERT on `lookups`, and the sequence privilege needed by its generated ID. It should not have broad DDL, role-management, update, or deletion privileges merely to serve cache/history requests. Removing runtime CREATE TABLE/INDEX privileges also requires moving that initialization out of the application.

### 6. Encryption: why verify the certificate?

Encryption protects traffic from being read in transit. Certificate and hostname verification additionally checks that the server is the expected trusted endpoint, reducing the risk of an encrypted connection to an impersonator. The RDS CA bundle and `verify-full` configuration are used for that identity check.

### 7. SQL injection: show a safe line

The application uses:

```javascript
pool.query('INSERT INTO lookups (zip, payload) VALUES ($1, $2)', [zip, JSON.stringify(payload)])
```

The placeholders keep values separate from SQL syntax. Joining untrusted input directly into a SQL string can allow input to alter the query's meaning. Five-digit ZIP validation is helpful but is not a replacement for parameterized queries.

### 8. Backups: what is lost at retention 0?

The lab gives up automated backup-based recovery and point-in-time recovery; with no final/manual snapshot, deletion removes the database's stored data without those recovery copies. Important workloads need recovery objectives, suitable backup retention, protected copies where appropriate, and restore tests rather than assuming a backup setting alone proves recoverability.

### 9. Data lifecycle: who decides when data may be destroyed?

The organization's designated data owner and authorized retention/governance process should determine destruction timing, with security, records-management, compliance, and legal stakeholders as applicable. An engineer should execute an approved lifecycle policy and account for retention obligations or holds instead of deciding unilaterally that stored data is no longer needed.

### 10. Untrusted output: what if raw AI text were rendered?

A model could return attacker-influenced markup or script-bearing HTML. Rendering it as trusted markup could enable cross-site scripting, page manipulation, or theft of information accessible to that page. The supplied page escapes output through `escapeHtml`; model output is treated as untrusted even when the model service itself is legitimate.

### 11. Third-party data: what must change for real users or a school account?

Confirm institutional authorization, the particular account's contractual data terms, retention and training settings, permitted data categories, and required notices/consent before sending real-user data. Apply data minimization, access controls, and a reviewed secret-management design. A paid tier or school-owned account does not by itself establish that every proposed disclosure is permitted.

### 12. Abuse and cost: how could quota be exhausted?

An unauthenticated public endpoint can be repeatedly requested to trigger Gemini calls and consume quota or billable service usage. Add rate limits, request budgets, monitoring, and appropriate authentication or WAF controls, while considering caching and abuse detection. Rate-limit handling and fallback keep the app useful but do not prevent the abuse by themselves.

### 13. Availability: why label fallback and unavailable cache?

The labels distinguish a rule-based suggestion from model-generated advice and an uncached forecast from a database-backed response. This makes degraded operation observable and avoids presenting a successful HTTP response as proof that every dependency is healthy. Operators can alert on those fields and users can understand the answer's source.

## 5. Graduate discussion — What moto cannot prove (approximately half a page)

Moto tests verify that Python builds the intended requests, stores mocked resources, restricts the generated policy documents, handles repeated creation/deletion, and keeps user-data below the EC2 limit. However, a successful mocked test is not proof that AWS actually enforced those settings. The live `test_database_tls_and_backup_configuration` checks actual RDS properties and lists snapshots and automated backups. The post-deletion verification separately checks that the database and retained copies are absent. This matters because a simulated delete API cannot establish that real cloud storage has finished disappearing.

Network behavior is another gap. A mocked security-group rule can have the correct fields while a real subnet, routing table, security group, or endpoint is misconfigured. The live `test_application_access_only_through_alb` tests both tiers from the local computer, requiring direct connection timeouts and ALB success. `test_database_port_unreachable_from_computer` checks the private database boundary. Healthy target groups and successful history/cache requests provide additional checks that the intended internal paths work.

Moto does not establish a real TLS handshake, certificate chain, hostname verification, PostgreSQL authentication, or SQL execution. The live cache/history test exercises the deployed app's configured verified-TLS connection, and the browser-session `psql` query explicitly used `sslmode=verify-full` with the downloaded RDS CA bundle. These are positive-path checks; I did not run a deliberately invalid-certificate or impersonated-server negative test, so I do not claim that broader proof.

Finally, a local model cannot predict IAM propagation, EC2 boot duration, real Gemini behavior, or replacement timing. Live IAM simulation checks both roles against both parameter ARNs. The marked chaos tests revoke database access and terminate weather, asserting graceful degradation and recovery within 300 seconds. These complement request-level unit tests with observations of actual cloud behavior, while remaining measurements of these runs rather than universal availability guarantees.

## 6. Graduate discussion — Python compared with bash

For creating the database, Python made it easier to separate configuration, network discovery, password generation, request construction, waiting, and output writing into small functions. Boto3 returns structured dictionaries, so the code can inspect fields directly rather than passing JSON through shell parsing. Catching specific `ClientError` codes distinguishes a missing resource or duplicate from a genuine permission failure. The password can be generated in memory and passed to SSM/RDS without putting the value in a shell command. Bash is concise for a short manual sequence and makes AWS CLI steps easy to recognize, but quoting, pipelines, exit codes, and secret-bearing arguments need extra care. Python's request builder and mocked clients were easier to test for exact settings, repeat creation, cleanup, and absence of printed secrets. Both versions still need real integration tests because neither a shell script nor a mocked boto3 test can prove actual networking, TLS, backups, or recovery timing alone.

## 7. Graduate checklist and test record

| Requirement | Implementation/evidence |
|---|---|
| Four Python infrastructure entry points | `create_database.py`, `delete_database.py`, `create_weather_stack.py`, `delete_weather_stack.py`. |
| Extend lab05 package | New `stack/database.py` and weather-specific config, IAM, policy, compute, and runner modules reuse the existing helpers. |
| Required RDS settings and deletion flags | `database_create_request`, `delete_database`, database unit tests, H4 and H10 evidence. |
| ALB before launch templates | `create_weather_stack`; mocked ordering test and successful live deployment. |
| Separate one-secret policies | `secret_policy`, unit tests, and live four-way simulation. |
| Configuration-driven names, ports, instance class, cache | `WeatherSettings` and sanitized `.env.example`. Final local audit added `DB_PORT` to request construction, ingress, and weather user-data; the lab value remains 5432. |
| Repeat creation/deletion | Database repeat tests, launch-template one-version test, complete stack repeat-create/delete test. |
| Secure secret input/generation | `getpass` and `secrets.token_hex(16)`; no real secret is included in the report. |
| Smoke test runnable through pytest | `test_all_nine_smoke_checks` calls `testing/app_smoke_test.py`'s `run_checks`. |
| Real integration tests | **10 passed**; `evidence/graduate_integration_tests.txt`, SS18. |
| Real marked chaos tests | **2 passed**; `evidence/graduate_chaos_tests.txt`, SS19. The test-session duration includes time waiting for manual browser restart prompts; it is not the measured service-recovery time. |
| Unit tests without real AWS credentials | Initial evidence: **30 passed, 28 deselected**, SS21b. Final audit after adding a configuration test: **31 passed, 28 deselected**, `evidence/final_unit_tests_without_credentials.txt`. |

The final local configuration change was validated with mocked tests after AWS cleanup; the live deployment was not recreated solely for that change. Live evidence reflects the same port values used in the lab (3000, 5432, 8080, 8081). The new database-port test verifies that changing the configured port changes both the RDS request and security-group rule.

Earlier integration failures occurred while the old weather target/instance was still being released after replacement. Inspection confirmed the settled ASG and healthy target, and the rerun passed all ten tests. Cleanup also encountered asynchronous deletion delays; the deletion code now retries the specific target-group `ResourceInUse` condition instead of treating it as completed deletion.

## 8. Cleanup and cost record

Application resources were deleted before the database. The database deletion used `SkipFinalSnapshot=True` and `DeleteAutomatedBackups=True`. Final verification lists were empty for database instances, snapshots, automated backups, subnet groups, load balancers, target groups, Auto Scaling Groups, launch templates, both application roles/profiles, both secret parameters, the ALB/database security groups, nonterminated lab instances, and the temporary browser-SSH rule. The pre-existing app security group and local project were intentionally retained.

Free coverage was not confirmed: the account's Credits page showed no remaining credits, and the visible Free Tier page did not establish an RDS allowance. I therefore do not claim this run had zero cost. Check the final Billing view after usage reporting catches up. Cleanup verification concerns these named lab resources, not a claim that the entire AWS account contains no unrelated resources or that already accrued charges disappear.

**Outstanding external cleanup confirmation:** delete or restrict the replacement Gemini key in Google AI Studio, then record completion. Its SSM copy is already deleted, but that does not revoke the provider's key.

## 9. Before submitting

- Review this draft and make sure the explanations reflect your understanding.
- Confirm deletion/restriction of the Google AI Studio key and update the preceding status.
- Include the report, relevant source code/tests, sanitized `.env.example`, and evidence as required by the course upload page.
- Keep `.env`, private keys, virtual environments, `node_modules`, caches, and any real credentials out of an uploaded code package.
- Use `final_unit_tests_without_credentials.txt` for the final 31-test result; older screenshots accurately show earlier 30-test runs.
- The supplied PDF does not specify the portal, deadline, report file format, or ZIP/GitHub upload convention. Follow the course submission page for those details rather than assuming one.

**Assignment source:** `Weather_Advisor_TwoTier_APIs.pdf`, especially Sections 15.1, 16.1, and 16.2. Evidence links refer to the saved lab outputs and screenshots, not invented results.

## 10. Strict requirement audit follow-up

The PDF's graduate integration checklist specifically names `/weather?zip=60616` for an asserted miss followed by hit. The marked integration cache test currently selects another uncached ZIP. The saved weather journal proves a 60616 miss/hit sequence, and the pytest smoke test uses 60616, but the marked cache test does not explicitly assert that exact sequence for 60616. This is a strict wording mismatch, not missing cache functionality. Do not describe that exact pytest requirement as fully satisfied without updating and running the specific test. AWS remains deleted; no redeployment was performed for this audit.

The final database-port configuration edit also introduced a missing local configuration variable in the integration database-reachability function. This was corrected and the function was executed with a mocked socket timeout, verifying the configured host/port without contacting AWS. The correction is recorded in `evidence/integration_port_local_check.txt`. The saved ten-test live pass predates these final source edits; it should not be presented as a live run of the final edited source.
