# Guard Proxy — instrukcja dla zespołu kursowego

---

## 1. O projekcie (2 minuty)

Guard Proxy to self-hosted WAF (Web Application Firewall) zbudowany na HAProxy + Coraza + OWASP CRS. Panel administracyjny (ten frontend) służy do zarządzania politykami bezpieczeństwa i wirtualnymi hostami.

Pełny opis: [README.md](../README.md) · Architektura: [README.architecture.md](../README.architecture.md)

---

## 2. Postawienie środowiska

### 2.1 Wymagania

- **Git** — do klonowania repozytorium
- **Python 3.13+** i **uv** — backend ([instalacja uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js 20+** i **pnpm** — frontend (`npm install -g pnpm`)

### 2.2 Backend (FastAPI)

```bash
cd src/backend

# 1. Zmienne środowiskowe
cp .env.example .env
# Otwórz .env i uzupełnij JWT_SECRET_KEY (dowolny ciąg znaków, np. "devsecret123456")

# 2. Zależności + baza danych
uv sync
uv run alembic upgrade head 

# 3. Konto admin (hasło min. 12 znaków)
uv run python scripts/seed_admin.py --email admin@example.com --password TwojeHaslo12345

# 4. Uruchomienie
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Weryfikacja:** otwórz <http://127.0.0.1:8000/docs> — powinieneś zobaczyć Swagger UI z listą endpointów.

### 2.3 Frontend (React + Vite)

```bash
cd src/frontend

pnpm install
cp .env.example .env   # opcjonalnie, jeśli backend nie jest na domyślnym URL
pnpm run dev
```

**Weryfikacja:** otwórz <http://localhost:5173>, zaloguj się danymi admina z kroku 2.2. Powinieneś zobaczyć dashboard z placeholderowymi danymi.

### 2.4 Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| `uv: command not found` | Zainstaluj uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `pnpm: command not found` | `npm install -g pnpm` |
| Błąd CORS w konsoli przeglądarki | Upewnij się, że backend działa na `127.0.0.1:8000` |
| Nie można się zalogować | Sprawdź czy `alembic upgrade head` przeszło i czy seed_admin się wykonał |

---

## 3. Zasady pracy

### 3.1 Git i PR

1. **Branch bazowy:** `main`. Z niego tworzysz swój branch.
2. **Nazewnictwo brancha:** `feat/<krótki-opis>` (np. `feat/dashboard-api`, `feat/policies-list`).
3. **Jeden PR = jedno zadanie.** Opis po polsku lub angielsku — co zrobiłeś i jak przetestowałeś.
4. **Przed wystawieniem PR** uruchom w `src/frontend/`:

   ```bash
   pnpm run type-check   # musi przejść bez błędów
   pnpm run lint          # musi przejść bez błędów
   ```

### 3.2 Obowiązkowe wzorce kodu

| Co | Jak | Plik |
|----|-----|------|
| Requesty HTTP | `apiRequest()` | `src/frontend/src/lib/api-client.ts` |
| Token i rola | `useAuth()` | `src/frontend/src/hooks/use-auth.ts` |
| Tabele danych | `DataTable` | `src/frontend/src/components/shared/DataTable.tsx` |
| UI ogólne | `PageHeader`, `SectionCard`, `StatCard`, `StatusBadge` | `src/frontend/src/components/shared/` |
| Stany UI | `LoadingState`, `ErrorState`, `EmptyState` | `src/frontend/src/components/shared/` |

**Przykład: pobranie danych z API**

```typescript
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

const { token } = useAuth();
const data = await apiRequest<Policy[]>("/policies", { method: "GET", token });
```

**Przykład: warunkowe wyświetlanie przycisków dla admina**

```typescript
const { hasRole } = useAuth();

{hasRole("admin") && (
  <button>Utwórz nową politykę</button>
)}
```

### 3.3 Czego NIE zmieniać bez zgody 

- `styles/globals.css` — design tokeny i motywy
- `features/auth/` — kontekst autoryzacji
- `lib/api-client.ts` — klient API
- `components/layout/NavBar.tsx` — nawigacja
- `app/router.tsx` — **wyjątek:** możesz dodać nową trasę, jeśli Twoje zadanie tego wymaga (np. `/policies/:policyId`)

---

## 4. Zadania

### 4.1 Mateusz Kw — Dashboard (GitHub #28)

**Cel:** Zamienić placeholderowe dane na dashboardzie na prawdziwe dane z API.

#### Co zrobić

1. **Karty statystyk z prawdziwymi danymi:**
   - Liczba vhostów — pobierz `GET /vhosts` (zwraca tablicę `VHostResponse[]`), policz `data.length`.
   - Liczba polityk — pobierz `GET /policies` (zwraca tablicę `PolicyResponse[]`), policz `data.length`.
   - Trzecia karta (np. status WAF/proxy) — zostaw jako placeholder z informacją, że infrastruktura nie jest jeszcze podpięta.

2. **Sekcja "ostatnia aktywność"** — zostaw mockowe dane (nie ma jeszcze endpointu logów).

3. **Stany ładowania i błędów:** pokaż `LoadingState` podczas pobierania danych i `ErrorState` jeśli request się nie powiedzie.

#### Co zwraca API

`GET /vhosts` → tablica obiektów:
```json
[
  {
    "id": 1,
    "domain": "example.com",
    "backend_url": "http://10.0.0.1:3000",
    "is_active": true,
    "ssl_enabled": false,
    "policy_id": 1,
    "created_at": "2026-03-20T10:00:00"
  }
]
```

`GET /policies` → tablica obiektów:
```json
[
  {
    "id": 1,
    "name": "Default CRS",
    "paranoia_level": 1,
    "anomaly_threshold": 5,
    "is_active": true,
    "created_at": "2026-03-20T10:00:00"
  }
]
```

#### Pliki do edycji

- `src/frontend/src/pages/dashboard/DashboardPage.tsx` — główny (i prawdopodobnie jedyny) plik do zmian.

#### Definition of done

- [ ] Karty "Vhosts" i "Policies" pokazują prawdziwe liczby z API
- [ ] Podczas ładowania widać `LoadingState`
- [ ] Przy błędzie API widać `ErrorState`
- [ ] `pnpm run type-check` i `pnpm run lint` przechodzą

---

### 4.2 Dawid L— Virtual Hosts (GitHub #29)

**Cel:** Zbudować widok listy vhostów z filtrowaniem po domenie i widok szczegółu.

#### Co zrobić

1. **Lista vhostów** na stronie `/vhosts`:
   - Pobierz dane z `GET /vhosts` (zwraca pełną tablicę, bez paginacji).
   - Wyświetl w tabeli (użyj komponentu `DataTable`): domena, backend URL, status (active/inactive), SSL, przypisana polityka.
   - Dodaj pole tekstowe do **filtrowania po domenie po stronie klienta** — API nie obsługuje filtrowania, więc filtruj tablicę w JS (`domain.toLowerCase().includes(query)`).

2. **Widok szczegółu** po kliknięciu w wiersz:
   - Trasa `/vhosts/:vhostId` już istnieje w routerze, strona `VHostDetailPage.tsx` też.
   - Pobierz `GET /vhosts/{id}` — odpowiedź zawiera zagnieżdżony obiekt `policy` (pełne dane polityki, nie tylko ID).
   - Wyświetl wszystkie pola vhosta + informacje o przypisanej polityce (jeśli jest).

3. **Role:**
   - Viewer — tylko odczyt, brak przycisków tworzenia/edycji/usuwania.
   - Admin — opcjonalnie prosty formularz `POST /vhosts` (tylko jeśli starczy czasu; **MVP to read-only**).

#### Co zwraca API

`GET /vhosts/{id}` → obiekt z zagnieżdżoną polityką:
```json
{
  "id": 1,
  "domain": "example.com",
  "backend_url": "http://10.0.0.1:3000",
  "description": "Main website",
  "is_active": true,
  "ssl_enabled": false,
  "policy_id": 1,
  "created_by": 1,
  "created_at": "2026-03-20T10:00:00",
  "updated_at": "2026-03-20T10:00:00",
  "policy": {
    "id": 1,
    "name": "Default CRS",
    "paranoia_level": 1,
    "anomaly_threshold": 5,
    "is_active": true
  }
}
```

#### Pliki do edycji

- `src/frontend/src/pages/vhosts/VHostsPage.tsx` — lista z filtrowaniem
- `src/frontend/src/pages/vhosts/VHostDetailPage.tsx` — widok szczegółu

#### Definition of done

- [ ] Lista vhostów pobiera dane z `GET /vhosts` i wyświetla je w `DataTable`
- [ ] Filtrowanie po domenie działa (pole tekstowe, filtrowanie client-side)
- [ ] Kliknięcie w wiersz przenosi na `/vhosts/:id` z danymi z API
- [ ] Widok szczegółu pokazuje dane vhosta i przypisaną politykę
- [ ] `LoadingState`, `ErrorState`, `EmptyState` używane we właściwych miejscach
- [ ] Viewer nie widzi przycisków akcji (tworzenie/edycja/usuwanie)
- [ ] `pnpm run type-check` i `pnpm run lint` przechodzą

---

### 4.2b Dawid L — Docker Compose dev (GitHub #53)

**Cel:** Przygotować `docker-compose.yml`, który stawia cały stack developerski jedną komendą.

> To zadanie realizujesz **po** zakończeniu VHosts (#29) lub równolegle, jeśli chcesz zacząć od niego.

#### Co zrobić

1. **`docker-compose.yml`** w katalogu głównym repozytorium z serwisami:
   - `postgres` — obraz `postgres:16`, volume na dane, zmienne `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` z `.env`.
   - `backend` — budowany z `src/backend/`, nasłuchuje na porcie `8000`, zależy od `postgres`, czyta `.env`.
   - `frontend` — budowany z `src/frontend/`, nasłuchuje na porcie `5173`, `VITE_API_BASE_URL` wskazujący na backend.

2. **`src/backend/Dockerfile`** — wieloetapowy (multi-stage) build:
   - Bazowy obraz: `python:3.13-slim`.
   - Instalacja zależności przez `uv` (skopiuj `pyproject.toml` + `uv.lock`).
   - Uruchomienie: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

3. **`src/frontend/Dockerfile`** — dla dev servera:
   - Bazowy obraz: `node:20-slim`.
   - Instalacja przez `pnpm install`.
   - Uruchomienie: `pnpm run dev --host` (flaga `--host` żeby Vite słuchał na `0.0.0.0`).

4. **Aktualizacja `.env.example`** — dodaj zmienne potrzebne dla Docker Compose (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`).

#### Jak zweryfikować

```bash
docker compose up -d
# Poczekaj ~15s na start
curl http://localhost:8000/health    # powinien zwrócić {"status": "ok"}
curl http://localhost:5173           # powinien zwrócić HTML frontendu
docker compose down
```

#### Pliki do utworzenia / edycji

- `docker-compose.yml` — **nowy plik** w katalogu głównym
- `src/backend/Dockerfile` — **nowy plik**
- `src/frontend/Dockerfile` — **nowy plik**
- `src/backend/.env.example` — aktualizacja o zmienne Postgres

#### Definition of done

- [ ] `docker compose up -d` stawia 3 serwisy bez błędów
- [ ] Backend odpowiada na `GET /health`
- [ ] Frontend serwuje stronę na porcie 5173
- [ ] Backend łączy się z PostgreSQL (logowanie działa)
- [ ] `docker compose down` czyści wszystko
- [ ] Nie commituje żadnych haseł — wszystko przez `.env`
- [ ] `pnpm run type-check` i `pnpm run lint` przechodzą (frontend bez zmian logiki)

---

### 4.3 Mateusz Ka — Policies (GitHub #30)

**Cel:** Zbudować widok listy polityk WAF i widok szczegółu z rule overrides.

#### Co zrobić

1. **Lista polityk** na stronie `/policies`:
   - Pobierz dane z `GET /policies` (tablica `PolicyResponse[]`).
   - Wyświetl w tabeli (użyj `DataTable`): nazwa, paranoia level (1–4), anomaly threshold, status (active/inactive).

2. **Widok szczegółu** — nowa strona:
   - Utwórz `PolicyDetailPage.tsx` w `src/frontend/src/pages/policies/`.
   - Dodaj trasę `/policies/:policyId` w `app/router.tsx`.
   - Pobierz `GET /policies/{id}` — odpowiedź zawiera tablicę `rule_overrides`.
   - Wyświetl dane polityki + listę rule overrides (tabela lub lista: rule ID, akcja enable/disable, komentarz).

3. **Role:**
   - Viewer — tylko odczyt.
   - Admin — opcjonalnie formularz tworzenia/edycji polityki (`POST` / `PATCH`); **MVP to read-only**.

#### Co zwraca API

`GET /policies` → tablica (BEZ rule overrides):
```json
[
  {
    "id": 1,
    "name": "Default CRS",
    "description": "Standard OWASP ruleset",
    "paranoia_level": 1,
    "anomaly_threshold": 5,
    "is_active": true,
    "created_by": 1,
    "created_at": "2026-03-20T10:00:00",
    "updated_at": "2026-03-20T10:00:00"
  }
]
```

`GET /policies/{id}` → obiekt z rule overrides:
```json
{
  "id": 1,
  "name": "Default CRS",
  "description": "Standard OWASP ruleset",
  "paranoia_level": 1,
  "anomaly_threshold": 5,
  "is_active": true,
  "created_by": 1,
  "created_at": "2026-03-20T10:00:00",
  "updated_at": "2026-03-20T10:00:00",
  "rule_overrides": [
    {
      "id": 1,
      "policy_id": 1,
      "rule_id": 942100,
      "action": "disable",
      "comment": "False positive on search form",
      "created_at": "2026-03-20T10:00:00"
    }
  ]
}
```

#### Pliki do edycji / utworzenia

- `src/frontend/src/pages/policies/PoliciesPage.tsx` — lista
- `src/frontend/src/pages/policies/PolicyDetailPage.tsx` — **nowy plik**, widok szczegółu
- `src/frontend/src/app/router.tsx` — dodać trasę `/policies/:policyId`

#### Definition of done

- [ ] Lista polityk pobiera dane z `GET /policies` i wyświetla je w `DataTable`
- [ ] Kliknięcie w wiersz przenosi na `/policies/:policyId`
- [ ] Widok szczegółu pokazuje dane polityki i tabelę/listę rule overrides
- [ ] `LoadingState`, `ErrorState`, `EmptyState` używane we właściwych miejscach
- [ ] Viewer nie widzi przycisków akcji
- [ ] `pnpm run type-check` i `pnpm run lint` przechodzą

---

### 4.3b Mateusz Ka — Rule Overrides frontend (część GitHub #66)

**Cel:** Dodać możliwość zarządzania rule overrides z poziomu widoku szczegółu polityki.

> To zadanie realizujesz **po** zakończeniu Policies (#30) — bazujesz na `PolicyDetailPage`, którą już zbudujesz.

#### Kontekst

Rule overrides pozwalają adminowi wyłączyć konkretną regułę OWASP CRS dla danej polityki (np. reguła 942100 generuje false positive na formularzu wyszukiwania — admin ją wyłącza). Endpointy backendowe będą gotowe — Twoja robota to frontend.

#### Co zrobić

1. **Formularz dodawania override'a** (tylko dla admina) w `PolicyDetailPage`:
   - Pola: Rule ID (number, np. `942100`), Action (select: `enable` / `disable`), Comment (opcjonalny tekst).
   - Submit wysyła `POST /policies/{policyId}/rule-overrides` z body `{ "rule_id": 942100, "action": "disable", "comment": "..." }`.
   - Po sukcesie — odśwież listę overrides.

2. **Przycisk usunięcia** przy każdym overridzie (tylko dla admina):
   - Wysyła `DELETE /policies/{policyId}/rule-overrides/{overrideId}`.
   - Po sukcesie — odśwież listę.

3. **Viewer** — widzi overrides w trybie read-only (bez formularza i przycisków usunięcia).

#### Co przyjmuje / zwraca API

`POST /policies/{policyId}/rule-overrides`:
```json
// Request
{ "rule_id": 942100, "action": "disable", "comment": "False positive on search" }

// Response (201 Created)
{
  "id": 5,
  "policy_id": 1,
  "rule_id": 942100,
  "action": "disable",
  "comment": "False positive on search",
  "created_at": "2026-04-10T12:00:00"
}
```

`DELETE /policies/{policyId}/rule-overrides/{overrideId}` → `204 No Content`

#### Pliki do edycji

- `src/frontend/src/pages/policies/PolicyDetailPage.tsx` — rozszerzenie widoku szczegółu

#### Definition of done

- [ ] Admin widzi formularz dodawania override'a na stronie szczegółu polityki
- [ ] Po dodaniu override'a lista odświeża się bez przeładowania strony
- [ ] Admin może usunąć override przyciskiem, lista odświeża się
- [ ] Viewer widzi overrides, ale nie widzi formularza ani przycisku usunięcia
- [ ] Obsługa błędów: `ErrorState` / komunikat przy nieudanym requeście
- [ ] `pnpm run type-check` i `pnpm run lint` przechodzą

---

## 5. Jak testować ręcznie

Zanim wystawisz PR, przetestuj te scenariusze:

| Scenariusz | Jak zasymulować | Czego szukać |
|------------|-----------------|--------------|
| **Happy path** | Zaloguj się, przejdź na swój ekran | Dane wyświetlają się poprawnie |
| **Brak danych** | Nie twórz żadnych vhostów/polityk (świeża baza) | `EmptyState` zamiast pustej tabeli |
| **Błąd sieci** | Wyłącz backend (Ctrl+C w terminalu), odśwież stronę | `ErrorState` zamiast białego ekranu |
| **Ładowanie** | Otwórz DevTools → Network → Throttle: Slow 3G | `LoadingState` widoczny przed załadowaniem danych |
| **Rola viewer** | Utwórz usera z rolą viewer (lub zmień rolę w bazie) | Brak przycisków tworzenia/edycji/usuwania |

---

## 6. Checklist przed oznaczeniem PR jako gotowy

- [ ] `pnpm run type-check` — przechodzi
- [ ] `pnpm run lint` — przechodzi
- [ ] Przetestowane ręcznie: happy path, brak danych, błąd sieci, ładowanie
- [ ] Nie commituje `.env`, sekretów ani `node_modules`
- [ ] Opis PR zawiera: co zrobiłem, jak przetestowałem
- [ ] PR jest wystawiony do brancha `main`

---

## 7. Przydatne linki

| Co | Gdzie |
|----|-------|
| Swagger UI (dokumentacja API) | <http://127.0.0.1:8000/docs> |
| Frontend dev server | <http://localhost:5173> |
| Tablica projektu | [GitHub Projects](https://github.com/users/bihius/projects/1) |
| Struktura frontendu | [src/frontend/README.md](../src/frontend/README.md) |
| Komendy developerskie | [README.commands.md](../README.commands.md) |

Pytania techniczne → do właściciela repozytorium.
