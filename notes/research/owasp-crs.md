# OWASP Core Rule Set (CRS)

## Czym jest CRS

Zbiór reguł do WAF-ów kompatybilnych z ModSecurity/Coraza. Chroni przed atakami z OWASP Top 10: SQLi, XSS, command injection, path traversal i innymi. Coraza 3.x jest w 100% kompatybilne z CRS 4.x.

## Anomaly Scoring

CRS nie blokuje per-regułę. Każde dopasowanie reguły dodaje punkty do `TX:anomaly_score`. Blokowanie następuje w osobnych regułach (zakres 9XXXXX) gdy score przekroczy próg.

**Poziomy severity i przypisane punkty:**

| Severity | Punkty | Przykłady |
|----------|--------|-----------|
| CRITICAL | 5 | SQLi, XSS, RCE - większość detection reguł |
| ERROR | 4 | |
| WARNING | 3 | |
| NOTICE | 2 | |

Domyślny próg to **5 punktów** - ma to sens bo:
- Typowy atak SQLi dopasowuje kilka reguł CRITICAL → score 25+ → blokada pewna
- Jeden CRITICAL (score 5) już wystarczy do blokady - nie ma "fałszywej przepustki" dla prostych ataków
- Próg 5 ogranicza false positives z reguł NOTICE/WARNING które mogą matchować legitny ruch

**Dwa osobne progi:**
- `inbound_anomaly_score_threshold` - dla requestów (domyślnie 5)
- `outbound_anomaly_score_threshold` - dla responses (domyślnie 4), chroni przed wyciekiem danych. Często ustawiany wyżej bo response rules generują więcej FP.

## Paranoia Levels (PL)

Cztery poziomy, każdy wyższy **dodaje** reguły do poprzedniego - nie zastępuje.

| PL | Opis | Przypadki użycia |
|----|------|-----------------|
| PL1 | Baseline, najmniej FP | Publiczne witryny, start konfiguracji |
| PL2 | Więcej reguł, więcej FP | Witryny z danymi osobowymi |
| PL3 | Wysokie zabezpieczenia | Bankowość, e-commerce, dane wrażliwe |
| PL4 | Maksymalna paranoja, dużo FP | Krytyczna infrastruktura |

**Ważne:** żaden poziom nie jest "włącz i zapomnij". Każdy wymaga tuningu i zbierania false positives - to są tygodnie/miesiące pracy na produkcyjnym ruchu. Im wyższy PL, tym więcej pracy.

### Detection level vs Paranoia level

Można ustawić `tx.paranoia_level=2` ale `tx.detection_paranoia_level=4` - wtedy reguły PL3-PL4 są oceniane i logowane, ale **nie dodają punktów do score**. Przydatne do bezpiecznego testowania wyższych PL bez ryzyka blokowania.

## Flow przetwarzania

### Tryb standardowy

1. Wykonaj wszystkie reguły fazy 1 i 2 (request)
2. Podejmij decyzję blokowania na podstawie `inbound_anomaly_score_threshold`
3. Wykonaj wszystkie reguły fazy 3 i 4 (response)
4. Podejmij decyzję blokowania na podstawie `outbound_anomaly_score_threshold`

### Early blocking (opcjonalnie)

1. Wykonaj reguły fazy 1 (request headers)
2. Podejmij decyzję blokowania na podstawie inbound threshold
3. Wykonaj reguły fazy 2 (request body)
4. Podejmij decyzję blokowania na podstawie inbound threshold
5. Wykonaj reguły fazy 3 (response headers)
6. Podejmij decyzję blokowania na podstawie outbound threshold
7. Wykonaj reguły fazy 4 (response body)
8. Podejmij decyzję blokowania na podstawie outbound threshold

Early blocking pozwala zablokować już po nagłówkach zanim przeczyta body - zmniejsza obciążenie przy oczywistych atakach. Wadą jest więcej potencjalnych false positives, bo decyzja zapada przy niepełnych danych (brak body).

## Przestrzenie ID reguł

- **1-899999** - detection reguły (zbierają score)
- **900000-999999** - reguły scoring/blocking (podejmują decyzję blokowania na podstawie zebranego score)

Ważne przy pisaniu custom reguł: nie wchodzić w przestrzeń 900000+, unikać konfliktów z CRS. Bezpieczny zakres dla custom reguł: **1000000+**.

## Zarządzanie wykluczeniami

Reguł nie usuwa się z CRS - stosuje się wykluczenia:

**Kiedy:**
- configure-time - przy starcie WAF-a, mniejszy koszt runtime
- runtime - wykonywane per-request, wyższe obciążenie ale możliwe per-transakcja

**Zakres wykluczenia:**
- cały rule lub tag (np. wyłącz wszystkie reguły SQLi)
- pojedyncza zmienna w regule (np. ignoruj pole `search` w regule XSS)

Wykluczenia per-zmienna są lepsze - minimalizują obszar wyłączenia zamiast całkowicie ślepić WAF na dany typ ataku.

### Gotowe pakiety wykluczeń (CRS 4.x)

CRS dostarcza gotowe zestawy wykluczeń dla popularnych aplikacji:
cPanel, DokuWiki, Drupal, Nextcloud, phpBB, phpMyAdmin, WordPress, XenForo

## Źródła

- https://coreruleset.org/docs/2-how-crs-works/2-1-anomaly_scoring/
- https://coreruleset.org/docs/2-how-crs-works/2-2-paranoia_levels/
- https://coreruleset.org/docs/2-how-crs-works/2-3-false-positives-and-tuning/
- https://www.netnea.com/cms/apache-tutorial-8_handling-false-positives-modsecurity-core-rule-set/
