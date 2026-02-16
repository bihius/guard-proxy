
```dataviewjs
const current = dv.current();
const tasks = current?.file?.tasks ?? [];
const total = tasks.length;
const done = total ? tasks.filter((t) => t.completed).length : 0;
const pct = total ? Math.round((done / total) * 100) : 0;
dv.header(2,`${pct}% done (${done}/${total} task${total === 1 ? '' : 's'})`);
```



## 1. Research i Fundamenty [15%]
- [x] **Analiza HAProxy + SPOE protocol** (4%)
    - [x] Przeczytać dokumentację HAProxy SPOE
    - [x] Zrozumieć format ramek SPOE
    - [x] Przetestować przykładowe agenty SPOE
    - [x] Zapisać wyniki w `notes/research/haproxy-spoe.md`

- [ ] **Deep dive w architekturę Coraza i OWASP CRS** (4%)
    - [ ] Przestudiować architekturę Coraza WAF
    - [ ] Przejść przez dokumentację OWASP ModSecurity Core Rule Set
    - [ ] Porównać poziomy paranoi PL1–PL4 i przypadki użycia
    - [ ] Opisać mechanizm oceny anomaliów
    - [ ] Uzupełnić `notes/research/coraza-architecture.md` i `notes/research/owasp-crs.md`

- [ ] **Testowanie podstawowych setupów** (4%)
    - [ ] Stworzyć niezależną konfigurację HAProxy (reverse proxy bez WAF)
    - [ ] Odrębny zestaw do testów Coraza
    - [ ] Złożyć pierwszy prototyp HAProxy + Coraza
    - [ ] Udokumentować napotkane problemy i rozwiązania

- [ ] **Dokumentacja decyzji architektonicznych (ADR)** (3%)
    - [ ] ADR-001: Wybór FastAPI vs Flask/Django
    - [ ] ADR-002: PostgreSQL vs SQLite
    - [ ] ADR-003: Frontend framework (React)
    - [ ] ADR-004: Strategia deploymentu (Docker Compose)
    - [ ] Zadania zapisane w `notes/decisions/`

---

## 2. Infrastruktura Docker [8%]
- [ ] **Docker Compose setup** (3%)
    - [ ] Przygotować `docker-compose.yml` z podstawową konfiguracją
    - [ ] Dodać `docker-compose.dev.yml` z nadpisaniami developerskimi
    - [ ] Stworzyć `docker-compose.prod.yml` dla produkcji
    - [ ] Zdefiniować serwisy: haproxy, coraza, postgres, backend, frontend

- [ ] **Networking między kontenerami** (2%)
    - [ ] Skonfigurować custom bridge network dla komunikacji wewnętrznej
    - [ ] Zapewnić HAProxy → Coraza przez SPOE
    - [ ] Połączyć backend z PostgreSQL
    - [ ] Połączyć frontend z backend API
    - [ ] Eksponować tylko HAProxy i frontend na hoście

- [ ] **Volume management dla configów i logów** (2%)
    - [ ] Volumes dla konfiguracji HAProxy (`src/haproxy/`)
    - [ ] Volumes dla reguł Coraza (`src/coraza/rules/`)
    - [ ] Volume dla danych PostgreSQL
    - [ ] Volume dla logów HAProxy, Coraza i backendu

- [ ] **Environment variables i secrets** (1%)
    - [ ] `.env.example` jako szablon
    - [ ] Bezpieczne zarządzanie secretami (hasła DB, klucze API)
    - [ ] Walidacja konfiguracji przy starcie

---

## 3. Integracja HAProxy + Coraza [12%]
- [ ] **Konfiguracja HAProxy z SPOE** (4%)
    - [ ] Zaktualizować `haproxy.cfg` z główną konfiguracją
    - [ ] Dodać frontend z filtrem SPOE
    - [ ] Określić backendy
    - [ ] Skonfigurować wiadomości SPOE
    - [ ] ACL-e dla decyzji WAF (allow/deny)

- [ ] **Setup Coraza jako SPOA** (4%)
    - [ ] Dopracować `coraza.yaml` z konfiguracją SPOA
    - [ ] Ustawić adres i port nasłuchu dla SPOE
    - [ ] Obsługa transakcji przez Coraza
    - [ ] Ustawić format odpowiedzi (allow/deny/tarpit)

- [ ] **Testowanie komunikacji HAProxy ↔ Coraza** (3%)
    - [ ] Weryfikować ramki SPOE (tcpdump/Wireshark)
    - [ ] Analizować logi HAProxy i Coraza
    - [ ] Przetestować przepływ żądań client → HAProxy → Coraza → backend
    - [ ] Obsłużyć timeouty i błędy

- [ ] **Debugging przetwarzania ramek SPOE** (1%)
    - [ ] Włączyć tryb debugowania HAProxy
    - [ ] Włączyć verbose logging Coraza
    - [ ] Udokumentować wskazówki troubleshootingowe

---

## 4. OWASP CRS Integration [10%]
- [ ] **Import CRS ruleset do Coraza** (3%)
    - [ ] Pobrać najnowszy OWASP CRS
    - [ ] Skonfigurować `crs-setup.conf`
    - [ ] Dodać include reguł w `coraza.yaml`
    - [ ] Zweryfikować kolejność ładowania

- [ ] **Konfiguracja poziomów paranoi PL1–PL4** (3%)
    - [ ] Implementacja PL1 (baseline)
    - [ ] Implementacja PL2
    - [ ] Implementacja PL3
    - [ ] Implementacja PL4 (maksymalne zabezpieczenia)
    - [ ] Udokumentować kompromisy dla każdego poziomu

- [ ] **Ustawienia scoringu anomalii** (2%)
    - [ ] Próg oceny anomalii inbound
    - [ ] Próg oceny anomalii outbound
    - [ ] Tryby blokowania vs logowania
    - [ ] Notatka w `notes/research/paranoia-levels.md`

- [ ] **Custom rules per-vhost** (2%)
    - [ ] Struktura katalogów `src/coraza/rules/custom/<vhost>/`
    - [ ] Przykładowe reguły custom
    - [ ] Zakresy ID reguł (unikaj konfliktów z CRS)
    - [ ] Testy reguł custom

---

## 5. Backend Panelu (FastAPI) [18%]
- [ ] **Project setup** (2%)
    - [ ] `pyproject.toml` z dependencies (FastAPI, SQLAlchemy, Alembic, pytest)
    - [ ] `uv` lock file
    - [ ] Struktura folderów: `app/`, `tests/`, `alembic/`
    - [ ] Bazowa aplikacja FastAPI w `app/main.py`

- [ ] **Modele bazy (SQLAlchemy)** (3%)
    - [ ] Model `VHost` (domain, backend_url, policy_id)
    - [ ] Model `Policy` (nazwa, paranoia_level, ip_whitelist, ip_blacklist)
    - [ ] Model `Rule` (custom rules, exclusions)
    - [ ] Model `User` (autoryzacja)
    - [ ] Relacje między modelami

- [ ] **Alembic migrations** (1%)
    - [ ] Initial migration
    - [ ] Skrypty w `alembic/versions/`
    - [ ] Konfiguracja w `alembic.ini`

- [ ] **Schematy Pydantic** (2%)
    - [ ] `VHostCreate`, `VHostUpdate`, `VHostResponse`
    - [ ] `PolicyCreate`, `PolicyUpdate`, `PolicyResponse`
    - [ ] `RuleCreate`, `RuleUpdate`, `RuleResponse`
    - [ ] Walidacje danych

- [ ] **Endpointy API – VHosts** (3%)
    - [ ] `POST /api/v1/vhosts`
    - [ ] `GET /api/v1/vhosts`
    - [ ] `GET /api/v1/vhosts/{id}`
    - [ ] `PUT /api/v1/vhosts/{id}`
    - [ ] `DELETE /api/v1/vhosts/{id}`

- [ ] **Endpointy API – Policies** (2%)
    - [ ] `POST /api/v1/policies`
    - [ ] `GET /api/v1/policies`
    - [ ] `PUT /api/v1/policies/{id}`
    - [ ] `DELETE /api/v1/policies/{id}`

- [ ] **Endpointy API – Logs** (1%)
    - [ ] `GET /api/v1/logs`
    - [ ] Filtry (zakres dat, vhost, severity)
    - [ ] Paginacja

- [ ] **Warstwa serwisowa – generowanie konfiguracji** (3%)
    - [ ] `haproxy_service.py` generuje konfiguracje dla vhostów
    - [ ] `coraza_service.py` generuje konfiguracje reguł
    - [ ] Szablony Jinja2 dla configów
    - [ ] Walidacja wygenerowanych configów

- [ ] **Mechanizm przeładowania HAProxy** (1%)
    - [ ] Runtime API HAProxy (socket)
    - [ ] Bezproblemowy reload bez przestojów
    - [ ] Obsługa błędów i rollback

---

## 6. Frontend Panelu (React) [15%]
- [ ] **Project setup** (2%)
    - [ ] Vite + React + TypeScript
    - [ ] `package.json` z zależnościami (TanStack Query, React Router, shadcn/ui)
    - [ ] `pnpm-lock.yaml`
    - [ ] Konfiguracja Tailwind CSS

- [ ] **Routing i layout** (2%)
    - [ ] Ustawić React Router
    - [ ] Layout główny (navbar, sidebar)
    - [ ] Trasy: `/dashboard`, `/vhosts`, `/policies`, `/logs`

- [ ] **Warstwa klienta API** (2%)
    - [ ] Wrapper Axios/fetch w `src/api/client.ts`
    - [ ] Typy TypeScript zgodne z backendowymi schematami
    - [ ] Hooki TanStack Query (`useVHosts`, `usePolicies`)
    - [ ] Obsługa błędów

- [ ] **Strona Dashboard** (2%)
    - [ ] Karty metryk (total vhosts, active policies, blocked requests)
    - [ ] Feed ostatnich aktywności
    - [ ] Wykresy (jeśli dotyczy)

- [ ] **Manager VHostów** (3%)
    - [ ] Widok listy VHostów (tabela + filtry)
    - [ ] Formularz dodawania VHostu (domain, backend URL, policy)
    - [ ] Dialog edycji VHostu
    - [ ] Potwierdzenie usunięcia

- [ ] **Edytor polityk** (3%)
    - [ ] Lista polityk
    - [ ] Formularz tworzenia/edycji polityki
    - [ ] Selektor poziomu paranoi (PL1–PL4)
    - [ ] Inputy whitelist/blacklist IP (tablica adresów)
    - [ ] Inputy progów scoringu anomalii

- [ ] **Przeglądarka logów** (1%)
    - [ ] Tabela logów z filtrami
    - [ ] Wybór zakresu dat
    - [ ] Filtr severity
    - [ ] Filtr VHost
    - [ ] Paginacja

---

## 7. Testowanie Bezpieczeństwa [10%]
- [ ] **Przygotowanie payloadów** (2%)
    - [ ] `benchmarks/payloads/sqli.txt`
    - [ ] `benchmarks/payloads/xss.txt`
    - [ ] `benchmarks/payloads/path_traversal.txt`
    - [ ] `benchmarks/payloads/rce.txt`
    - [ ] Źródła: OWASP Testing Guide, SecLists

- [ ] **Testy skuteczności per poziom paranoi** (4%)
    - [ ] PL1 – baza
    - [ ] PL2 – średnie zabezpieczenia
    - [ ] PL3 – wysokie zabezpieczenia
    - [ ] PL4 – maksymalna paranoja
    - [ ] Metryki: TP, FP, FN
    - [ ] Tabele wyników

- [ ] **Analiza false positives/negatives** (2%)
    - [ ] Identyfikacja FP (blokowane legitne żądania)
    - [ ] Identyfikacja FN (niezauważone ataki)
    - [ ] Dostosowanie reguł do redukcji FP
    - [ ] Dokumentacja kompromisów

- [ ] **Automatyzacja OWASP ZAP** (2%)
    - [ ] ZAP baseline scan
    - [ ] ZAP full scan
    - [ ] ZAP API scan
    - [ ] Skrypt `benchmarks/scripts/security_scan.sh`
    - [ ] Generowanie raportu

---

## 8. Testowanie Wydajności [8%]
- [ ] **Benchmarki bazowe (bez WAF)** (2%)
    - [ ] `benchmarks/scripts/wrk_baseline.sh`
    - [ ] Metryki: RPS, latency (p50, p95, p99), throughput
    - [ ] Zapisać wyniki w `benchmarks/results/<date>_baseline.json`

- [ ] **Benchmarki z WAF per poziom paranoi** (3%)
    - [ ] Wpływ PL1
    - [ ] Wpływ PL2
    - [ ] Wpływ PL3
    - [ ] Wpływ PL4
    - [ ] Skrypt `benchmarks/scripts/wrk_with_waf.sh`
    - [ ] Zapisać wyniki dla każdego PL

- [ ] **Locust distributed load testing** (2%)
    - [ ] `benchmarks/scripts/locust_test.py`
    - [ ] Symulacja realistycznego ruchu
    - [ ] Testowanie multi-vhost
    - [ ] Wyniki + wykresy

- [ ] **Generowanie wykresów** (1%)
    - [ ] Porównanie RPS (baseline vs PL1-PL4)
    - [ ] Porównanie latencji
    - [ ] Porównanie throughputu
    - [ ] Zapis wykresów w `benchmarks/results/charts/`

---

## 9. Monitoring i Observability [4%]
- [ ] **Prometheus** (1%)
    - [ ] `deploy/monitoring/prometheus/prometheus.yml`
    - [ ] Scrape config dla HAProxy i Coraza
    - [ ] `deploy/monitoring/prometheus/alerts.yml`

- [ ] **Grafana dashboards** (2%)
    - [ ] Dashboard HAProxy `deploy/monitoring/grafana/dashboards/haproxy.json`
    - [ ] Dashboard Coraza `deploy/monitoring/grafana/dashboards/coraza.json`
    - [ ] Dane do monitorowania: RPS, czas odpowiedzi, zdrowie backendu, zablokowane żądania, score anomalii
    - [ ] Datasource config `deploy/monitoring/grafana/datasources.yml`

- [ ] **Loki log aggregation** (1%)
    - [ ] `deploy/monitoring/loki/loki-config.yml`
    - [ ] Przyjmowanie logów z HAProxy i Coraza
    - [ ] Integracja w Grafana Explore

---

## 10. Dokumentacja Pracy [10%]
- [ ] **Rozdział 1: Wstęp** (1%)
    - [ ] Motywacja i cel pracy
    - [ ] Zakres pracy
    - [ ] Struktura dokumentu

- [ ] **Rozdział 2: Analiza** (2%)
    - [ ] State-of-the-art WAF solutions
    - [ ] Porównanie HAProxy vs Nginx vs Traefik
    - [ ] Coraza vs ModSecurity
    - [ ] Protokół SPOE/SPOA
    - [ ] OWASP CRS

- [ ] **Rozdział 3: Projekt** (2%)
    - [ ] Architektura systemu (diagramy)
    - [ ] Uzasadnienie wyboru technologii
    - [ ] Projekt polityk bezpieczeństwa
    - [ ] Projekt panelu zarządzania

- [ ] **Rozdział 4: Implementacja** (2%)
    - [ ] Integracja HAProxy + Coraza
    - [ ] Konfiguracja CRS
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
    - [ ] Ograniczenia i przyszła praca
    - [ ] Wnioski końcowe
