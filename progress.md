# Progress Tracker - Guard Proxy WAF
*Praca inżynierska: Self-hosted Reverse Proxy WAF z HAProxy i OWASP Coraza*

---

## Ogólny Postęp: 0/100%



---

## 1. Research i Fundamenty [15%] ⬜ 0/15

- [ ] **Analiza HAProxy + SPOE protocol** (4%)
  - [ ] Przeczytanie dokumentacji HAProxy SPOE
  - [ ] Zrozumienie SPOE frame format
  - [ ] Testowanie przykładowych SPOE agents
  - [ ] Notatka: `notes/research/haproxy-spoe.md`

- [ ] **Deep dive w Coraza architecture i OWASP CRS** (4%)
  - [ ] Architektura Coraza WAF
  - [ ] OWASP ModSecurity Core Rule Set documentation
  - [ ] Paranoia Levels (PL1-PL4) - różnice i zastosowanie
  - [ ] Anomaly scoring mechanism
  - [ ] Notatka: `notes/research/coraza-architecture.md` i `notes/research/owasp-crs.md`

- [ ] **Testowanie podstawowych setupów** (4%)
  - [ ] Standalone HAProxy config (reverse proxy bez WAF)
  - [ ] Standalone Coraza (podstawowe testy)
  - [ ] Pierwszy working prototype HAProxy + Coraza
  - [ ] Dokumentacja problemów i rozwiązań

- [ ] **Dokumentacja decyzji architektonicznych (ADR)** (3%)
  - [ ] ADR-001: Wybór FastAPI vs Flask/Django
  - [ ] ADR-002: PostgreSQL vs SQLite
  - [ ] ADR-003: Frontend framework (React)
  - [ ] ADR-004: Deployment strategy (Docker Compose)
  - [ ] Pliki w: `notes/decisions/`

---

## 2. Infrastruktura Docker [8%] ⬜ 0/8

- [ ] **Docker Compose setup** (3%)
  - [ ] `docker-compose.yml` - base configuration
  - [ ] `docker-compose.dev.yml` - development overrides
  - [ ] `docker-compose.prod.yml` - production setup
  - [ ] Service definitions: haproxy, coraza, postgres, backend, frontend

- [ ] **Networking między kontenerami** (2%)
  - [ ] Custom bridge network dla internal communication
  - [ ] HAProxy → Coraza via SPOE
  - [ ] Backend → PostgreSQL
  - [ ] Frontend → Backend API
  - [ ] Expose tylko HAProxy i Frontend na host

- [ ] **Volume management dla configów i logów** (2%)
  - [ ] Volumes dla HAProxy configs (`src/haproxy/`)
  - [ ] Volumes dla Coraza rules (`src/coraza/rules/`)
  - [ ] Volume dla PostgreSQL data
  - [ ] Volume dla logów (HAProxy, Coraza, backend)

- [ ] **Environment variables i secrets** (1%)
  - [ ] `.env.example` template
  - [ ] Secrets management (DB passwords, API keys)
  - [ ] Config validation on startup

---

## 3. Integracja HAProxy + Coraza [12%] ⬜ 0/12

- [ ] **Konfiguracja HAProxy z SPOE** (4%)
  - [ ] `haproxy.cfg` - główna konfiguracja
  - [ ] Frontend definition z SPOE filter
  - [ ] Backend definition
  - [ ] SPOE message configuration
  - [ ] ACLs dla WAF decisions (allow/deny)

- [ ] **Setup Coraza jako SPOA** (4%)
  - [ ] `coraza.yaml` - konfiguracja SPOA
  - [ ] Listen address i port dla SPOE
  - [ ] Transaction handling
  - [ ] Response format (verdict: allow/deny/tarpit)

- [ ] **Testowanie komunikacji HAProxy ↔ Coraza** (3%)
  - [ ] Weryfikacja SPOE frames (tcpdump/Wireshark)
  - [ ] Logi z obu stron (HAProxy i Coraza)
  - [ ] Test request flow: client → HAProxy → Coraza → backend
  - [ ] Handling timeouts i errors

- [ ] **Debugging SPOE frame processing** (1%)
  - [ ] HAProxy debug mode
  - [ ] Coraza verbose logging
  - [ ] Dokumentacja troubleshooting tips

---

## 4. OWASP CRS Integration [10%] ⬜ 0/10

- [ ] **Import CRS ruleset do Coraza** (3%)
  - [ ] Download OWASP CRS (latest version)
  - [ ] Setup `crs-setup.conf` base configuration
  - [ ] Include rulesets w `coraza.yaml`
  - [ ] Weryfikacja load order

- [ ] **Konfiguracja Paranoia Levels (PL1-PL4)** (3%)
  - [ ] Implementacja PL1 (baseline)
  - [ ] Implementacja PL2
  - [ ] Implementacja PL3
  - [ ] Implementacja PL4 (max security)
  - [ ] Dokumentacja trade-offs per level

- [ ] **Anomaly scoring setup** (2%)
  - [ ] Inbound anomaly score threshold
  - [ ] Outbound anomaly score threshold
  - [ ] Blocking vs logging mode
  - [ ] Notatka: `notes/research/paranoia-levels.md`

- [ ] **Custom rules per-vhost** (2%)
  - [ ] Struktura katalogów: `src/coraza/rules/custom/<vhost>/`
  - [ ] Przykładowe custom rules
  - [ ] Rule ID ranges (avoid conflicts with CRS)
  - [ ] Testing custom rules

---

## 5. Backend Panelu (FastAPI) [18%] ⬜ 0/18

- [ ] **Project setup** (2%)
  - [ ] `pyproject.toml` z dependencies (FastAPI, SQLAlchemy, Alembic, pytest)
  - [ ] `uv` lock file
  - [ ] Folder structure: `app/`, `tests/`, `alembic/`
  - [ ] Base FastAPI app w `app/main.py`

- [ ] **Database models (SQLAlchemy)** (3%)
  - [ ] Model: `VHost` (domain, backend_url, policy_id)
  - [ ] Model: `Policy` (name, paranoia_level, ip_whitelist, ip_blacklist)
  - [ ] Model: `Rule` (custom rules, exclusions)
  - [ ] Model: `User` (authentication)
  - [ ] Relationships między modelami

- [ ] **Alembic migrations** (1%)
  - [ ] Initial migration
  - [ ] Migration scripts w `alembic/versions/`
  - [ ] `alembic.ini` config

- [ ] **Pydantic schemas** (2%)
  - [ ] `VHostCreate`, `VHostUpdate`, `VHostResponse`
  - [ ] `PolicyCreate`, `PolicyUpdate`, `PolicyResponse`
  - [ ] `RuleCreate`, `RuleUpdate`, `RuleResponse`
  - [ ] Validation rules

- [ ] **API endpoints - VHosts** (3%)
  - [ ] `POST /api/v1/vhosts` - create vhost
  - [ ] `GET /api/v1/vhosts` - list vhosts
  - [ ] `GET /api/v1/vhosts/{id}` - get vhost detail
  - [ ] `PUT /api/v1/vhosts/{id}` - update vhost
  - [ ] `DELETE /api/v1/vhosts/{id}` - delete vhost

- [ ] **API endpoints - Policies** (2%)
  - [ ] `POST /api/v1/policies` - create policy
  - [ ] `GET /api/v1/policies` - list policies
  - [ ] `PUT /api/v1/policies/{id}` - update policy
  - [ ] `DELETE /api/v1/policies/{id}` - delete policy

- [ ] **API endpoints - Logs** (1%)
  - [ ] `GET /api/v1/logs` - fetch HAProxy/Coraza logs
  - [ ] Filtering (date range, vhost, severity)
  - [ ] Pagination

- [ ] **Service layer - Config generation** (3%)
  - [ ] `haproxy_service.py` - generate HAProxy vhost configs
  - [ ] `coraza_service.py` - generate Coraza rule configs
  - [ ] Jinja2 templates dla configs
  - [ ] Validation generated configs

- [ ] **HAProxy reload mechanism** (1%)
  - [ ] HAProxy Runtime API (socket communication)
  - [ ] Graceful reload bez downtime
  - [ ] Error handling i rollback

---

## 6. Frontend Panelu (React) [15%] ⬜ 0/15

- [ ] **Project setup** (2%)
  - [ ] Vite + React + TypeScript
  - [ ] `package.json` dependencies (TanStack Query, React Router, shadcn/ui)
  - [ ] `pnpm-lock.yaml`
  - [ ] Tailwind CSS setup

- [ ] **Routing i layout** (2%)
  - [ ] React Router setup
  - [ ] Main layout component (navbar, sidebar)
  - [ ] Routes: `/dashboard`, `/vhosts`, `/policies`, `/logs`

- [ ] **API client layer** (2%)
  - [ ] Axios/fetch wrapper w `src/api/client.ts`
  - [ ] TypeScript types z backend schemas
  - [ ] TanStack Query hooks (`useVHosts`, `usePolicies`)
  - [ ] Error handling

- [ ] **Dashboard page** (2%)
  - [ ] Metrics cards (total vhosts, active policies, blocked requests)
  - [ ] Recent activity feed
  - [ ] Charts (if applicable)

- [ ] **VHost manager** (3%)
  - [ ] VHost list view (table z search i filtering)
  - [ ] Add VHost form (domain, backend URL, policy selection)
  - [ ] Edit VHost dialog
  - [ ] Delete confirmation

- [ ] **Policy editor** (3%)
  - [ ] Policy list view
  - [ ] Policy create/edit form
  - [ ] Paranoia Level selector (PL1-PL4)
  - [ ] IP whitelist/blacklist inputs (array of IPs)
  - [ ] Anomaly score threshold inputs

- [ ] **Log viewer** (1%)
  - [ ] Log table z filtering
  - [ ] Date range picker
  - [ ] Severity filter
  - [ ] VHost filter
  - [ ] Pagination

---

## 7. Testowanie Bezpieczeństwa [10%] ⬜ 0/10

- [ ] **Przygotowanie payloadów** (2%)
  - [ ] `benchmarks/payloads/sqli.txt` - SQL injection attempts
  - [ ] `benchmarks/payloads/xss.txt` - XSS payloads
  - [ ] `benchmarks/payloads/path_traversal.txt` - path traversal
  - [ ] `benchmarks/payloads/rce.txt` - remote code execution attempts
  - [ ] Sources: OWASP Testing Guide, SecLists

- [ ] **Testy skuteczności per Paranoia Level** (4%)
  - [ ] PL1 - baseline tests (detection rate)
  - [ ] PL2 - moderate security
  - [ ] PL3 - high security
  - [ ] PL4 - maximum paranoia
  - [ ] Metryki: True Positives, False Positives, False Negatives
  - [ ] Tabele z wynikami

- [ ] **Analiza False Positives/Negatives** (2%)
  - [ ] Identyfikacja FP (legitimate requests blocked)
  - [ ] Identyfikacja FN (attacks missed)
  - [ ] Fine-tuning rules dla FP reduction
  - [ ] Dokumentacja trade-offs

- [ ] **OWASP ZAP automation** (2%)
  - [ ] ZAP baseline scan
  - [ ] ZAP full scan
  - [ ] ZAP API scan
  - [ ] Script: `benchmarks/scripts/security_scan.sh`
  - [ ] Report generation

---

## 8. Testowanie Wydajności [8%] ⬜ 0/8

- [ ] **Baseline benchmarks (bez WAF)** (2%)
  - [ ] Wrk tests: `benchmarks/scripts/wrk_baseline.sh`
  - [ ] Metryki: RPS, latency (p50, p95, p99), throughput
  - [ ] Save results: `benchmarks/results/<date>_baseline.json`

- [ ] **Benchmarks z WAF per Paranoia Level** (3%)
  - [ ] PL1 performance impact
  - [ ] PL2 performance impact
  - [ ] PL3 performance impact
  - [ ] PL4 performance impact
  - [ ] Script: `benchmarks/scripts/wrk_with_waf.sh`
  - [ ] Save results per PL

- [ ] **Locust distributed load testing** (2%)
  - [ ] `benchmarks/scripts/locust_test.py` setup
  - [ ] Simulate realistic traffic patterns
  - [ ] Multi-vhost testing
  - [ ] Results + charts

- [ ] **Generowanie wykresów** (1%)
  - [ ] RPS comparison chart (baseline vs PL1-4)
  - [ ] Latency comparison chart
  - [ ] Throughput comparison chart
  - [ ] Save charts: `benchmarks/results/charts/`

---

## 9. Monitoring i Observability [4%] ⬜ 0/4

- [ ] **Prometheus setup** (1%)
  - [ ] `deploy/monitoring/prometheus/prometheus.yml`
  - [ ] Scrape configs dla HAProxy i Coraza
  - [ ] `deploy/monitoring/prometheus/alerts.yml`

- [ ] **Grafana dashboards** (2%)
  - [ ] HAProxy dashboard: `deploy/monitoring/grafana/dashboards/haproxy.json`
    - Requests per second
    - Response times
    - Backend health
  - [ ] Coraza dashboard: `deploy/monitoring/grafana/dashboards/coraza.json`
    - Blocked requests
    - Anomaly scores
    - Rules triggered
  - [ ] Datasource config: `deploy/monitoring/grafana/datasources.yml`

- [ ] **Loki log aggregation** (1%)
  - [ ] `deploy/monitoring/loki/loki-config.yml`
  - [ ] Log ingestion z HAProxy i Coraza
  - [ ] Grafana Explore integration

---

## 10. Dokumentacja Pracy [10%] ⬜ 0/10

- [ ] **Rozdział 1: Wstęp** (1%)
  - [ ] Motywacja i cel pracy
  - [ ] Zakres pracy
  - [ ] Struktura dokumentu

- [ ] **Rozdział 2: Analiza** (2%)
  - [ ] State-of-the-art WAF solutions
  - [ ] HAProxy vs Nginx vs Traefik
  - [ ] Coraza vs ModSecurity
  - [ ] SPOE/SPOA protocol
  - [ ] OWASP CRS

- [ ] **Rozdział 3: Projekt** (2%)
  - [ ] Architektura systemu (diagramy)
  - [ ] Wybór technologii (uzasadnienie)
  - [ ] Design polityk bezpieczeństwa
  - [ ] Design panelu zarządzania

- [ ] **Rozdział 4: Implementacja** (2%)
  - [ ] HAProxy + Coraza integration
  - [ ] CRS configuration
  - [ ] Backend (FastAPI)
  - [ ] Frontend (React)
  - [ ] Monitoring stack

- [ ] **Rozdział 5: Testy** (2%)
  - [ ] Metodologia testowania
  - [ ] Wyniki testów bezpieczeństwa (tabele, wykresy)
  - [ ] Wyniki testów wydajności (tabele, wykresy)
  - [ ] Analiza i wnioski

- [ ] **Rozdział 6: Podsumowanie** (1%)
  - [ ] Osiągnięte cele
  - [ ] Limitations i future work
  - [ ] Wnioski końcowe


