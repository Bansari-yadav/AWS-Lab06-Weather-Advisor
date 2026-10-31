# AWS Lab06 — Weather Advisor

Graduate cloud-computing lab built with Python/boto3, Node.js, Amazon EC2, an Application Load Balancer, Auto Scaling Groups, SSM Parameter Store, and private RDS PostgreSQL.

<!-- navigation-start -->
## Start here — Guide for the reviewer

This repository documents **Bansari Yadav's ITMO 544 graduate implementation** of *Weather Advisor in the Cloud: Two Tiers, a Free AI Model and a PostgreSQL Database*. This README brings together the assignment sequence, source-code links, recorded results, required written answers, and all 26 screenshots.

**Current status:** the deployed lab resources were deleted and the named-resource cleanup checks passed. The URLs in historical evidence are records of testing, not active demonstration links. Google AI Studio key deletion/restriction still needs confirmation.

### Contents

1. [Project structure](#project-structure)
2. [Assignment walkthrough — Parts 0 through H](#assignment-walkthrough)
3. [Graduate implementation and testing — Section 16.2](#graduate-checklist)
4. [Submission checklist — Section 16.1](#submission-map)
5. [Recorded results](#recorded-results)
6. [Required questions and written answers](#required-questions-and-written-answers)
7. [Experiment explanations](#parts-a-and-h--experiment-questions-and-explanations)
8. [Three required paragraphs](#section-161--three-required-written-paragraphs)
9. [All 13 security/privacy review Q&As](#section-151--security-and-privacy-review-13-questions-and-answers)
10. [Graduate short answers](#section-162--graduate-short-answers)
11. [Screenshot gallery](#screenshot-evidence)

<a id="project-structure"></a>
## Project structure

The tree below highlights the current lab and the inherited lab05 material. The linked source files are the implementation; the evidence folder contains outputs and screenshots from actual runs.

```text
lab06/
├── README.md                         # Walkthrough, Q&A, results, screenshots
├── .env.example                      # Configuration template without secrets
├── .gitignore                        # Excludes private settings and dependencies
├── requirements.txt                  # Python/boto3, pytest, and moto dependencies
├── pytest.ini                        # Unit/integration/chaos test selection
├── create_database.py                # Graduate Part E: create RDS dependencies and DB
├── delete_database.py                # Delete DB without final snapshot/backups
├── create_weather_stack.py           # Graduate Part F: create both application tiers
├── delete_weather_stack.py           # Delete application infrastructure
├── store_gemini_key.py                # Hidden key input and SSM storage
├── test_gemini_key.py                 # Gemini API connectivity check
├── collect_readonly_evidence.py       # History, cache, IAM, network evidence
├── experiment_database_failure.py    # H7: block and restore DB connectivity
├── experiment_gemini_failure.py       # H8: invalid-key fallback and restoration
├── experiment_weather_recovery.py    # H9: replacement and recovery measurement
├── cleanup_remaining.py              # Remove secret copy and temporary SSH rule
├── verify_cleanup.py                 # Verify named lab resources are absent
├── weather-app/
│   ├── app.js                        # ZIP/NWS requests, PostgreSQL cache/history
│   ├── package.json
│   └── package-lock.json
├── advisor-app/
│   ├── app.js                        # Weather dependency, Gemini, fallback, HTML
│   ├── package.json
│   └── package-lock.json
├── stack/
│   ├── clients.py                    # Shared boto3 clients
│   ├── database.py                   # DB request construction and lifecycle
│   ├── weather_config.py             # WeatherSettings configuration
│   ├── weather_compute.py            # User-data and launch templates
│   ├── weather_iam.py                # Roles and instance profiles
│   ├── weather_policies.py           # Exact-secret IAM policies
│   ├── weather_runner.py             # Create/delete orchestration
│   └── ...                           # Reused lab05 network/ALB/ASG helpers
├── testing/
│   ├── app_smoke_test.py              # Nine checks, callable from pytest
│   └── ...                           # Inherited testing helpers
├── tests/
│   ├── unit/                         # Mocked tests, including weather DB/stack
│   ├── integration/
│   │   └── test_weather_live.py       # Current lab's real-stack tests
│   ├── chaos/
│   │   └── test_weather_chaos.py      # DB failure and instance replacement
│   └── ...                           # Shared fixtures and inherited lab05 tests
├── evidence/
│   ├── A1_*, A2_*, C2_*, C3_*        # API exploration and secret metadata
│   ├── E*, F*, G*, H*                # Deployment and experiment outputs
│   ├── final_revision_*.txt          # Final tests and cleanup verification
│   ├── graduate_chaos_tests.txt      # Marked chaos-suite result
│   └── SS1.png ... SS23.png          # 26 images; some labels have a/b versions
└── previous/                         # Archived uploader/viewer and entry scripts
```

The local `.env`, virtual environment, and installed Node dependencies are excluded from Git. The archived `previous/` applications and inherited lab05 modules/tests explain the project's starting point; the weather-specific modules and tests above implement this assignment.

**Open the main folders:** [infrastructure](stack/) · [weather app](weather-app/) · [advisor app](advisor-app/) · [tests](tests/) · [evidence](evidence/) · [configuration example](.env.example).

<a id="assignment-walkthrough"></a>
## Assignment walkthrough — Parts 0 through H

The infrastructure was implemented in **Python/boto3**, as required for ITMO 544, while the two applications use Node.js. Mocked tests were run before cloud deployment, and live experiments were followed by cleanup. A later deployment verified the final configuration changes and the explicit ZIP 60616 integration requirement, then was also removed. Earlier and final evidence therefore represent separate runs.

### Part 0 — Prepare lab06 from lab05

I worked in a separate `lab06` copy, retained the Python `stack/` package and pytest setup, and moved the old uploader/viewer applications and their entry scripts into `previous/`. I removed old application settings and checked that region, availability zones, AMI, instance type, key-pair name, and app security-group settings remained.

**Review:** [archived previous applications](previous/) · [folder listing, first 40 lines](evidence/Part0_folder_layout_first40.txt) · [full folder listing](evidence/Part0_folder_layout_full.txt) · [SS21a](evidence/SS21a.png). The listing was collected using a Windows/Python equivalent of the PDF's bash command.

### Part A — Call the ZIP and NWS APIs manually

I looked up ZIP 60616 and checked that ZIP 00000 returned 404. I called the NWS points endpoint with an identifying User-Agent, extracted its forecast URL, and requested the first forecast period. This established the response fields and error handling before using them in the weather service. A fresh application lookup uses ZIP-to-coordinates, NWS points, and NWS forecast requests: three HTTP requests across two providers.

**Review:** [60616 ZIP response](evidence/A1_zip_60616.txt) · [00000 status](evidence/A1_zip_00000.txt) · [NWS points JSON](evidence/A2_nws_points_full.json) · [forecast URL](evidence/A2_forecast_url.txt) · [first period](evidence/A2_first_forecast_period.txt) · [SS1](evidence/SS1.png), [SS2](evidence/SS2.png), [SS3](evidence/SS3.png). The written API explanation appears below.

### Part B — Configure names, ports, and cache settings

I added weather/advisor resource names, listener ports 8080 and 8081, app port 3000, PostgreSQL port 5432, database settings, and parameter names. The forecast cache uses 600 seconds and the Gemini key cache uses 60 seconds. The Python settings module reads configuration rather than embedding deployment identifiers in resource-building functions.

**Review:** [sanitized configuration template](.env.example) · [WeatherSettings](stack/weather_config.py). Real secret values are not included in that template.

### Part C — Test Gemini and store its key securely

I created a Gemini key, tested a model request, and supplied the key through hidden input to the Python storage helper. The helper stored and verified a Standard SSM SecureString without printing its value. The published evidence records API results and parameter metadata.

**Review:** [key storage helper](store_gemini_key.py) · [API test helper](test_gemini_key.py) · [Gemini test result](evidence/C2_gemini_test.json) · [SSM metadata](evidence/C3_ssm_parameter_metadata.json) · [SS4](evidence/SS4.png).

### Part D — Build the weather and advisor applications

The weather service validates ZIP input, looks up coordinates and NWS forecasts, and provides `/weather` and `/history`. It uses parameterized PostgreSQL queries for forecast cache/history and a trusted RDS certificate bundle for its TLS connection. The advisor calls weather through the ALB, requests Gemini clothing advice, returns a labelled rule-based fallback if Gemini fails, and HTML-escapes page content. Both application files passed syntax checks and their dependencies were installed before local checks and deployment.

**Review:** [weather application](weather-app/app.js) · [weather dependencies](weather-app/package.json) · [advisor application](advisor-app/app.js) · [advisor dependencies](advisor-app/package.json). Deployed behavior is demonstrated in Parts G and H.

### Part E — Implement and create the private PostgreSQL database

I implemented the Python equivalent of database creation/deletion, including the DB security group, app-group-only ingress, two-AZ subnet group, random password in SSM, and output handling. Mocked tests checked settings, repeated creation/deletion, restricted ingress, and secret handling before creating the live DB.

The live database was PostgreSQL on `db.t4g.micro`, with 20 GB encrypted storage, single-AZ placement, public access disabled, and backup retention 0. The delete request skips a final snapshot and removes automated backups.

**Review:** [create entry point](create_database.py) · [delete entry point](delete_database.py) · [database helpers](stack/database.py) · [database unit tests](tests/unit/test_weather_database.py) · [creation output](evidence/E2_database_creation.txt) · [live DB settings](evidence/H4_database_verification.json) · [SS5](evidence/SS5.png), [SS8](evidence/SS8.png), [SS9](evidence/SS9.png).

### Part F — Implement and create the two-tier application stack

I added separate weather/advisor IAM roles and profiles. Each role may read only its own exact secret ARN. The runner prepares network access and target groups, ensures the ALB and listeners exist before building launch templates, then creates each Auto Scaling Group. Weather startup receives the DB endpoint; advisor startup receives the ALB DNS name. Secret values are not embedded in either startup script. Mocked tests cover ordering, policy separation, repeat creation, cleanup, and the 16 KB user-data limit.

**Review:** [create entry point](create_weather_stack.py) · [delete entry point](delete_weather_stack.py) · [stack orchestration](stack/weather_runner.py) · [IAM helpers](stack/weather_iam.py) · [policies](stack/weather_policies.py) · [startup and launch templates](stack/weather_compute.py) · [stack unit tests](tests/unit/test_weather_stack.py) · [SS6](evidence/SS6.png).

### Part G — Deploy and test both services

After the database was available, I ran the stack creation script and waited for both target groups to become healthy. I opened the deployed advisor page for ZIP 60616 and collected JSON for the same ZIP. The smoke test checked weather success, cache hit, saved history, invalid/unknown ZIP handling, advisor advice, Gemini source, advisor ZIP validation, and the homepage.

**Recorded outcome:** all nine smoke checks passed. The final live integration run also explicitly showed 60616 miss, then hit, and a matching history entry; all ten integration tests passed in 27.35 seconds.

**Review:** [stack creation output](evidence/G1_stack_creation.txt) · [target health](evidence/G1_target_health.json) · [60616 advice JSON](evidence/G2_advice_60616.json) · [nine-check output](evidence/G3_smoke_test.txt) · [smoke-test code](testing/app_smoke_test.py) · [final integration output](evidence/final_revision_integration_tests.txt) · [SS10](evidence/SS10.png), [SS11](evidence/SS11.png), [SS22](evidence/SS22.png). The page screenshot and JSON are separate requests for the same ZIP, so generated wording can differ.

### Part H — Run the ten experiments

| Step | What I did and observed | Evidence |
|---|---|---|
| **H1: Service logs** | Requested forecasts and inspected structured weather logs. One 60616 hit took 2 ms; the preceding miss took 156 ms. | [Journal](evidence/H1_weather_journal.txt), [SS12](evidence/SS12.png) |
| **H2: Stored data** | Requested history and queried PostgreSQL from weather with verified TLS. The SQL screenshot recorded five saved rows at that point. | [History](evidence/H2_history.json), [SQL screenshot SS13](evidence/SS13.png) |
| **H3: Cache timing** | Requested unused ZIP 98101 twice. Miss: 0.182 s; hit: 0.067 s. | [Timing JSON](evidence/H3_cache_timings.json) |
| **H4: DB exposure/backups** | Checked RDS properties and backup lists, then attempted a local DB connection. Retention was 0, snapshots/backups were empty, the DB was private/single-AZ/encrypted, and the external connection timed out. | [Properties](evidence/H4_database_verification.json), [external connection](evidence/H4_external_connection.json), [SS9](evidence/SS9.png) |
| **H5: Secret permissions** | Simulated both roles against both secrets. Each role was allowed only its own parameter and implicitly denied the other. | [Four decisions](evidence/H5_iam_simulation.json) |
| **H6: ALB-only app access** | Tried both instances directly on app port 3000 and through their ALB listeners. Direct access timed out; both ALB requests returned 200. | [Network results](evidence/H6_network_isolation.json) |
| **H7: Database failure** | Temporarily removed DB access, restarted weather, captured 200 with cache unavailable, history 503, and a DB error log, then restored access and checked recovery. | [Failure/restoration](evidence/H7_database_failure.json), [SS14](evidence/SS14.png), [experiment code](experiment_database_failure.py) |
| **H8: Gemini failure** | Temporarily stored an invalid key and waited for key-cache expiry. Three responses used fallback; logs showed Gemini HTTP 400. Restored the real key and passed the smoke test. | [Fallback responses](evidence/H8_fallback_answers.json), [restored checks](evidence/H8_restored_smoke_test.txt), [SS15](evidence/SS15.png), [SS16a](evidence/SS16a.png), [SS16b](evidence/SS16b.png), [experiment code](experiment_gemini_failure.py) |
| **H9: Instance failure** | Terminated weather through its ASG without reducing desired capacity. Advisor advice returned 502 while its homepage remained 200. Recovery took 80.3 s in the initial experiment and 77.7 s in the separate chaos run; saved cache state survived in RDS. | [Recovery record](evidence/H9_weather_recovery.json), [SS17a](evidence/SS17a.png), [SS17b](evidence/SS17b.png), [SS19](evidence/SS19.png), [experiment code](experiment_weather_recovery.py) |
| **H10: Cleanup** | Removed app instances and ALB, deleted the DB without a final snapshot/retained backups, completed dependency cleanup, removed secret parameters and the temporary SSH rule, then verified named resources absent. | [Final verification](evidence/final_revision_cleanup_verification.txt), [SS23](evidence/SS23.png), [cleanup verification code](verify_cleanup.py) |

The paragraphs below explain the logs, row count, cache policy, IAM boundary, security-group sources, retry pause, fallback weakness, and state placement. Cleanup encountered asynchronous AWS dependency delays; final verification, rather than an earlier failed delete attempt, is the evidence that removal completed. The actual Google AI Studio key is separate from its deleted SSM copy.

<a id="graduate-checklist"></a>
## Graduate implementation and testing — Section 16.2

| Graduate requirement | Implementation and recorded proof |
|---|---|
| Python/boto3 infrastructure built on lab05 | Four Python entry points and reusable [stack package](stack/); Node.js remains the application language. |
| Required database settings and deletion flags | [DB helpers](stack/database.py), [DB tests](tests/unit/test_weather_database.py), [live settings](evidence/H4_database_verification.json), [final cleanup](evidence/final_revision_cleanup_verification.txt). |
| ALB before launch templates; correct startup addresses | [Runner](stack/weather_runner.py), [startup builder](stack/weather_compute.py), [ordering/startup tests](tests/unit/test_weather_stack.py). |
| Separate exact-secret roles and no startup secret values | [Policies](stack/weather_policies.py), [IAM helpers](stack/weather_iam.py), [live IAM simulation](evidence/H5_iam_simulation.json). |
| Configuration, idempotency, user-data size, and error handling | [Settings](stack/weather_config.py), DB and stack unit tests. Weather-specific helpers extend the inherited code. |
| Unit tests with no real credentials | [Final no-credentials output: 31 passed](evidence/final_unit_tests_without_credentials.txt); [final revision output](evidence/final_revision_unit_tests.txt). Earlier screenshots record the earlier 30-test suite. |
| Real tests marked integration | [Current integration test](tests/integration/test_weather_live.py), [final result: 10 passed](evidence/final_revision_integration_tests.txt), [SS22](evidence/SS22.png). Covers exact 60616 sequence, history, errors, advice, network boundaries, and four IAM decisions. |
| Real tests marked chaos | [Chaos tests](tests/chaos/test_weather_chaos.py), [result: 2 passed](evidence/graduate_chaos_tests.txt), [SS19](evidence/SS19.png). Covers DB failure/restoration and recovery within 300 seconds. |
| Smoke test usable through pytest | [Nine-check helper](testing/app_smoke_test.py), called by the current live integration suite. |
| Half-page moto limitations and one-paragraph Python/bash comparison | Both answers appear under **Section 16.2 — Graduate short answers** below. |

The final 60616/configuration follow-up was redeployed and passed the ten live integration tests before its cleanup. The marked chaos results are from the earlier separate experiment run.

<a id="submission-map"></a>
## Submission checklist — Section 16.1

This table follows the professor's 18 shared checklist items. The ITMO 544 additions are mapped immediately above.

| PDF item | Where to review it in this README/repository |
|---|---|
| 1. Folder layout | Project structure; Part 0; [saved listing](evidence/Part0_folder_layout_first40.txt). |
| 2. NWS output and API explanation | Part A; Part A written answer; SS1–SS3. |
| 3. Database creation and required settings | Part E; H4; [creation output](evidence/E2_database_creation.txt), [live properties](evidence/H4_database_verification.json). |
| 4. Advisor page plus same-ZIP JSON | Part G; SS11; [60616 JSON](evidence/G2_advice_60616.json). |
| 5. Nine passing smoke checks | Part G; SS10; [smoke output](evidence/G3_smoke_test.txt). |
| 6. H1 journal and explanation | H1 experiment row; H1 written answer; SS12. |
| 7. H2 history and SQL | H2 experiment row; H2 written answer; SS13. |
| 8. H3 timings and two sentences | H3 experiment row; H3 written answer. |
| 9. H5 IAM decisions and advisor-compromise sentence | H5 experiment row; H5 written answer. |
| 10. H6 direct/ALB results and SG-source explanation | H6 experiment row; H6 written answer. |
| 11. H7 DB failure, log, and retry explanation | H7 experiment row; H7 written answer; SS14. |
| 12. H8 fallback, logs, and silent-failure explanation | H8 experiment row; H8 written answer; SS15/SS16a/SS16b. |
| 13. H9 recovery, advisor outage, and state explanation | H9 experiment row; H9 written answer; SS17a/SS17b/SS19. |
| 14. SSM paragraph | Section 16.1 — Three required written paragraphs: **Why secrets belong in SSM**. |
| 15. Backups paragraph | Same section: **Why backups were disabled for this lab**. |
| 16. Gemini data-sharing paragraph | Same section: **Data shared with Gemini**. |
| 17. All Section 15.1 review answers | Section 15.1 — Security and privacy review: **Questions 1–13**. |
| 18. Final deletion verification | H10; final validation section; [all-empty output](evidence/final_revision_cleanup_verification.txt); SS23. |

[Return to reviewer guide](#start-here--guide-for-the-reviewer)

<!-- navigation-end -->

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
