# Dokumentacja projektu kursowego

## 1. Ogólne zalozenia projektu

Guard Proxy to self-hosted Web Application Firewall, czyli system ochrony ruchu
HTTP uruchamiany przed aplikacja webowa. System laczy HAProxy jako reverse proxy,
Coraza WAF z regułami OWASP CRS, backend FastAPI, panel administracyjny React
oraz baze danych.

Glownym celem projektu jest zarzadzanie konfiguracja WAF z poziomu panelu:

- tworzenie i edycja wirtualnych hostow,
- tworzenie i edycja polityk WAF,
- domain policy assignment, including path-scoped bindings,
- policy tuning through CRS rule overrides, rule target exclusions, and custom
  rules in the reserved ID range,
- stosowanie wygenerowanej konfiguracji HAProxy/Coraza,
- odbieranie i przegladanie logow zdarzen WAF,
- zabezpieczenie panelu przez logowanie i role uzytkownikow.

Cele dodatkowe (mierzalne i raportowane, nie gwarantowane):

- wykazanie, ze integracja HAProxy–Coraza przez SPOE nie degraduje skutecznosci
  regul CRS w stosunku do ich referencyjnego dzialania (fidelity),
- zmierzenie narzutu czasowego warstwy WAF wzgledem ruchu bez inspekcji i wykazanie,
  ze pozostaje on ponizej akceptowalnego progu,
- zademonstrowanie, ze wylaczenie lub modyfikacja reguly przez panel zmienia
  obserwowalne zachowanie WAF na ustalonym korpusie testowym.



## 2. Zastosowane technologie

| Warstwa | Technologie |
| --- | --- |
| Reverse proxy | HAProxy 3.0 |
| WAF | Coraza SPOA, OWASP CRS 4.x |
| Backend | Python 3.13, FastAPI, SQLAlchemy, Alembic |
| Baza centralna | PostgreSQL w Docker Compose |
| Baza lokalna/dev/test | SQLite przez SQLAlchemy |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Uwierzytelnianie | JWT access token, HttpOnly refresh token cookie |
| Konteneryzacja | Docker, Docker Compose |
| Testy | pytest, Vitest |

## 3. Architektura systemu

```mermaid
graph TB
    U[Uzytkownik / przegladarka] --> FE[React Admin Panel]
    FE -->|REST API| BE[FastAPI Backend]
    BE --> DB[(PostgreSQL)]

    C[Klient HTTP] --> H[HAProxy]
    H -.->|SPOE| WAF[Coraza WAF + OWASP CRS]
    WAF -.->|allow / deny| H
    H --> APP[Aplikacja chroniona]

    WAF --> LOG[Audit log]
    LOG --> LS[Log shipper]
    LS -->|POST /logs/ingest| BE
```

Backend pelni role control plane. Panel React komunikuje sie z nim przez REST API,
a backend zapisuje konfiguracje i dane w PostgreSQL. HAProxy oraz Coraza tworza
warstwe runtime, ktora obsluguje rzeczywisty ruch HTTP. Log shipper przesyla
zdarzenia z Corazy do backendu.

## 4. REST API

API jest udostepnione przez FastAPI. Dokumentacja interaktywna jest dostepna po
uruchomieniu backendu pod adresem:

```text
http://127.0.0.1:8000/docs
```

Najwazniejsze endpointy:

| Metoda | Endpoint | Opis |
| --- | --- | --- |
| GET | `/health` | Health check backendu |
| POST | `/auth/login` | Logowanie uzytkownika |
| POST | `/auth/refresh` | Odnowienie access tokena z refresh cookie |
| POST | `/auth/logout` | Wylogowanie |
| GET | `/auth/me` | Dane aktualnie zalogowanego uzytkownika |
| GET | `/vhosts` | Paginated virtual host list. Query params: `page`, `per_page`, `q` (domain search). Response: `{ items, total, page, per_page }`. |
| POST | `/vhosts` | Utworzenie wirtualnego hosta |
| GET | `/vhosts/{id}` | Szczegoly wirtualnego hosta |
| PATCH | `/vhosts/{id}` | Edycja wirtualnego hosta |
| DELETE | `/vhosts/{id}` | Usuniecie wirtualnego hosta |
| GET | `/policies` | Paginated WAF policy list. Query params: `page`, `per_page`, `q` (name search). Response: `{ items, total, page, per_page }`. |
| POST | `/policies` | Utworzenie polityki WAF |
| GET | `/policies/{id}` | Szczegoly polityki WAF |
| PATCH | `/policies/{id}` | Edycja polityki WAF |
| DELETE | `/policies/{id}` | Usuniecie polityki WAF |
| GET | `/policies/{policy_id}/rules` | Lista override'ow reguł CRS |
| POST | `/policies/{policy_id}/rules` | Dodanie override'u reguly CRS |
| PATCH | `/policies/{policy_id}/rules/{id}` | Edycja override'u reguly CRS |
| DELETE | `/policies/{policy_id}/rules/{id}` | Usuniecie override'u reguly CRS |
| GET | `/policies/{policy_id}/exclusions` | List CRS rule target exclusions |
| POST | `/policies/{policy_id}/exclusions` | Add an exclusion (rule_id + target + optional scope_path) |
| PATCH | `/policies/{policy_id}/exclusions/{id}` | Edit an exclusion |
| DELETE | `/policies/{policy_id}/exclusions/{id}` | Delete an exclusion |
| GET | `/policies/{policy_id}/custom-rules` | List custom rules for a policy |
| POST | `/policies/{policy_id}/custom-rules` | Add a custom rule (rule_id in the 9000000-9099999 range) |
| PATCH | `/policies/{policy_id}/custom-rules/{id}` | Edit a custom rule |
| DELETE | `/policies/{policy_id}/custom-rules/{id}` | Delete a custom rule |
| GET | `/vhosts/{vhost_id}/policy-bindings` | List path-scoped policy bindings for a vhost |
| POST | `/vhosts/{vhost_id}/policy-bindings` | Add a policy binding for a path prefix |
| DELETE | `/vhosts/{vhost_id}/policy-bindings/{id}` | Delete a policy binding |
| GET | `/logs` | Lista logow WAF z filtrami i paginacja |
| POST | `/logs/ingest` | Przyjmowanie logow z log shippera |
| POST | `/config/apply` | Wygenerowanie i zastosowanie konfiguracji runtime |
| GET | `/runtime/status` | Status ostatnich operacji runtime |

### Przykladowe zapytania

Logowanie:

```http
POST /auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "TwojeHaslo12345"
}
```

Przykladowa odpowiedz:

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

Utworzenie wirtualnego hosta:

```http
POST /vhosts
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "domain": "juice.local",
  "backend_url": "http://juiceshop:3000",
  "description": "OWASP Juice Shop",
  "ssl_enabled": false,
  "is_active": true,
  "policy_id": 1
}
```

Utworzenie polityki WAF:

```http
POST /policies
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "name": "Default CRS",
  "description": "Domyslna polityka OWASP CRS",
  "paranoia_level": 1,
  "inbound_anomaly_threshold": 5,
  "outbound_anomaly_threshold": 4,
  "enforcement_mode": "block"
}
```

Pobranie logow:

```http
GET /logs?page=1&page_size=50&action=deny
Authorization: Bearer jwt-token
```

## 5. Schemat bazy danych

Najwazniejsze tabele:

| Tabela | Przeznaczenie |
| --- | --- |
| `users` | Konta uzytkownikow panelu, rola |
| `vhosts` | Domeny obslugiwane przez HAProxy i ich backendy |
| `policies` | Polityki WAF: poziom paranoi, progi anomalii, tryb pracy |
| `rule_overrides` | Wlaczenia/wylaczenia konkretnych reguł OWASP CRS dla polityki |
| `rule_exclusions` | CRS rule target exclusions, such as ARGS:token, optionally scoped by path |
| `custom_rules` | Administrator-authored custom rules in the reserved ID range 9000000-9099999 |
| `policy_bindings` | Path-prefix scoped policy bindings for vhosts |
| `logs` | Zdarzenia WAF/proxy odebrane przez log shippera |
| `runtime_operations` | Historia operacji zastosowania konfiguracji runtime |

Glowne relacje:

- `vhosts.policy_id` points to `policies.id` as the vhost default policy.
- `rule_overrides.policy_id`, `rule_exclusions.policy_id`, and
  `custom_rules.policy_id` point to `policies.id`; deleting a policy cascades
  to the related records.
- `policy_bindings.vhost_id` and `policy_bindings.policy_id` point to
  `vhosts.id` and `policies.id`; deleting a vhost or policy cascades to its
  bindings.
- `vhosts.created_by` i `policies.created_by` wskazuja na `users.id`.
- `logs.vhost_id` i `logs.policy_id` moga wskazywac na powiazany vhost i polityke.

### Wizualny schemat relacji 

```mermaid
erDiagram
    users {
        int id PK
        string email UK
        string hashed_password
        string full_name
        UserRole role
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    
    vhosts {
        int id PK
        string domain UK
        string backend_url
        string description
        boolean is_active
        boolean ssl_enabled
        int policy_id FK
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    policies {
        int id PK
        string name UK
        string description
        int paranoia_level
        int inbound_anomaly_threshold
        int outbound_anomaly_threshold
        PolicyEnforcementMode enforcement_mode
        boolean is_active
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    rule_overrides {
        int id PK
        int policy_id FK
        int rule_id
        RuleAction action
        string comment
        datetime created_at
    }

    rule_exclusions {
        int id PK
        int policy_id FK
        int rule_id
        TargetType target_type
        string target_value
        string scope_path
        string comment
        datetime created_at
    }

    custom_rules {
        int id PK
        int policy_id FK
        int rule_id
        RulePhase phase
        string variables
        RuleOperator operator
        string operator_argument
        string actions
        string comment
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    policy_bindings {
        int id PK
        int vhost_id FK
        int policy_id FK
        string path_prefix
        int priority
        string comment
        datetime created_at
        datetime updated_at
    }

    logs {
        int id PK
        string producer_event_id UK
        datetime event_at
        string vhost
        LogAction action
        string source_ip
        string method
        string request_uri
        int status_code
        int rule_id
        string rule_message
        int anomaly_score
        int paranoia_level
        LogSeverity severity
        string message
        dict raw_context
        int vhost_id FK
        int policy_id FK
    }

    runtime_operations {
        int id PK
        RuntimeOperationType operation_type
        RuntimeOperationStatus status
        string config_checksum
        string message
        dict metadata_json
        datetime created_at
    }

    users ||--o{ vhosts : "created_by"
    users ||--o{ policies : "created_by"
    policies ||--o{ vhosts : "policy_id"
    policies ||--o{ rule_overrides : "policy_id"
    policies ||--o{ rule_exclusions : "policy_id"
    policies ||--o{ custom_rules : "policy_id"
    vhosts ||--o{ policy_bindings : "vhost_id"
    policies ||--o{ policy_bindings : "policy_id"
    vhosts ||--o{ logs : "vhost_id"
    policies ||--o{ logs : "policy_id"
```

Migracje bazy sa zarzadzane przez Alembic. W Docker Compose system uzywa
PostgreSQL. W trybie lokalnym i testowym mozliwe jest uzycie SQLite, bo warstwa
dostepu do danych jest oparta na SQLAlchemy.

## 6. Operacje CRUD

Projekt spelnia podstawowe wymagania CRUD na centralnej bazie danych:

- `vhosts`: create, read, update, delete,
- `policies`: create, read, update, delete,
- `rule_overrides`, `rule_exclusions`, `custom_rules`: create, read, update, delete,
- `policy_bindings`: create, read, delete,
- `logs`: ingest and filtered read.

Operacje modyfikujace sa dostepne tylko dla uzytkownikow z rola `admin`.
Uzytkownik `viewer` moze odczytywac dane, ale nie moze ich zmieniac.

## 7. Uwierzytelnianie i bezpieczenstwo

Panel administracyjny wymaga logowania. Backend stosuje:

- hashowanie hasel,
- JWT access token do autoryzacji zapytan API,
- refresh token przechowywany w HttpOnly cookie,
- role `admin` i `viewer`,
- zabezpieczenie endpointow przez zaleznosci FastAPI,
- celowo ogolny komunikat bledu logowania, aby ograniczyc enumeracje kont.

Endpoint `/logs/ingest` jest dodatkowo chroniony wspoldzielonym sekretem w
naglowku `X-Guard-Proxy-Ingest-Secret`, poniewaz korzysta z niego wewnetrzny
log shipper, a nie uzytkownik panelu.

## 8. Obsluga bledow

Backend zwraca standardowe kody HTTP, m.in.:

- `401 Unauthorized` przy braku lub blednym tokenie,
- `403 Forbidden` przy braku wymaganej roli,
- `404 Not Found` gdy zasob nie istnieje,
- `409 Conflict` przy konflikcie unikalnosci,
- `422 Unprocessable Entity` przy blednych danych wejsciowych,
- `500 Internal Server Error` przy bledach runtime/config apply.

Frontend ma wspolny klient API, ktory rozpoznaje bledy odpowiedzi i pozwala
wyswietlic komunikat w interfejsie. Widoki korzystaja ze stanow ladowania,
bledu i pustej listy.

## 9. Frontend

Panel administracyjny jest aplikacja webowa React. Aktualnie obejmuje:

- ekran logowania,
- ochrone tras wymagajacych zalogowania,
- dashboard z informacja o roli i stanie runtime,
- zarzadzanie wirtualnymi hostami,
- formularze tworzenia, edycji i usuwania vhostow,
- przycisk zastosowania konfiguracji,
- wspolne komponenty UI: tabele, status badges, modale, stany ladowania i bledow.

Aplikacja jest (prawie) responsywna i korzysta z backendowego REST API przez `fetch`.

## 10. Uruchomienie projektu

Przygotowanie konfiguracji:

```bash
cp deploy/docker/.env.example deploy/docker/.env
```

Uruchomienie pelnego stacka:

```bash
make run
```

Uruchomienie trybu debug:

```bash
make dev
```

Utworzenie konta administratora:

```bash
make seed
```

Najwazniejsze adresy:

| Usluga | Adres |
| --- | --- |
| Panel administracyjny | `http://localhost:3000` |
| API przez HAProxy | `http://localhost:8080` |
| Swagger UI | `http://127.0.0.1:8000/docs` |

## 11. Demo i laboratorium ewaluacyjne

Projekt uruchamia Guard Proxy przez glowny plik `deploy/docker/docker-compose.yml`.
Laboratorium w `benchmarks/lab` dodaje aplikacje testowe za WAF-em. Pozwala to
pokazac:

- logowanie do panelu,
- utworzenie polityki WAF,
- utworzenie vhostow kierujacych na aplikacje Juice Shop, DVWA i WordPress,
- routing po naglowku `Host` (`juice.local`, `dvwa.local`, `wp.local`),
- zastosowanie konfiguracji,
- poprawne przepuszczenie zwyklego ruchu HTTP,
- dzialanie HAProxy, Coraza i backendu jako jednego systemu.

## 12. Testy

Backend ma testy jednostkowe i integracyjne w `src/backend/tests`. Frontend ma
testy komponentow i klienta API w `src/frontend/src`. Dodatkowo istnieja testy
end-to-end dla stacka Docker Compose.

Testy dziel sie na dwie kategorie:

**Bramy zaliczenia (pass/fail, egzekwowane w CI):**
- Znany payload ataku jest blokowany (403) — smoke test,
- Znany benign request przechodzi (200) — smoke test,
- Wylaczenie i ponowne wlaczenie reguly przez panel zmienia zachowanie WAF na
  zywo (e2e test `test_policy_apply.py`, regula `913100`),
- Narzut WAF ponizej 20% — testy wydajnosciowe.

**Pomiary raportowane (nie egzekwowane):**
- Wspolczynnik wykrycia (TP) per klasa ataku (SQLi, XSS, path traversal),
- Wspolczynnik false positive na korpusie benign,
- Delta FP przed i po zastosowaniu override reguly na ustalonym korpusie.

Kazdy pomiar raportowany jest zapisywany razem z punktem odniesienia: commit
submodulu CRS, poziom paranoi, progi anomalii.

Przykladowe komendy:

```bash
cd src/backend
uv run pytest
uv run pytest -m e2e tests/e2e/test_policy_apply.py
```

```bash
cd src/frontend
pnpm run test
pnpm run type-check
pnpm run lint
```

```bash
bash benchmarks/smoke/e2e.sh
```

## 13. Plan ewaluacji

Ewaluacja projektu obejmuje dwie klasy pomiarow: bramy zaliczenia (egzekwowane w CI)
oraz obserwacje raportowane (mierzone na ustalonym korpusie i zapisywane z punktem
odniesienia, nie uzywane jako kryterium zdania).

| ID | Co mierzymy | Jak | Typ |
|----|-------------|-----|-----|
| E1 | Poprawnosc funkcjonalna zarzadzania | e2e: utworzenie vhosta → polityki → zastosowanie → rollback; toggle reguly widoczny w zachowaniu live | **Brama (pass/fail)** |
| E2 | Fidelity integracji | Replay korpusu atakow i benign przez proxy; raport TP per klasa + FP z zapisanym SHA submodulu CRS, PL i progami | **Raportowane** |
| E3 | Narzut wydajnosciowy | wrk/k6: latencja p50/p95/p99 + przepustowosc, WAF-on vs WAF-bypass | **Brama (<20% narzutu)** |
| E4 | Skutecznosc tuningu | FP na korpusie WordPress przed i po overridzie reguly; wynik to delta, nie wartosc bezwzgledna | **Raportowane (delta)** |
| E5 | Porownanie referencyjne (M6, opcjonalne) | Ten sam korpus przez Guard Proxy vs raw Coraza/standalone — brak degradacji fidelity | **Raportowane** |

### Punkt odniesienia dla E2, E4, E5

Kazdy raport zapisuje:

- SHA commitu submodulu `configs/coraza/crs` (wersja CRS),
- poziom paranoi i progi anomalii (domyslnie PL1, inbound 5, outbound 4),
- korpus testowy (`benchmarks/payloads/`: sqli.txt, xss.txt, legitimate.txt).

Bez tych danych wyniki nie sa porownywalne miedzyokresowo.

## 15. Screenshoty

Do uzupelnienia przed oddaniem projektu:

- ekran logowania,
- dashboard,
- lista vhostow,
- formularz tworzenia vhosta,
- lista polityk lub szczegoly polityki,
- wynik requestu przepuszczonego przez WAF,
- wynik requestu zablokowanego przez WAF,
- Swagger UI z endpointami API.
