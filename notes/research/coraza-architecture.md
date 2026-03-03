# Coraza WAF - Architektura

## Model WAF i Transakcji

Coraza opiera się na dwóch głównych konceptach: **WAF** i **Transaction**.

**WAF** to singleton ze skompilowanymi regułami. Przechowuje ustawienia i załadowane reguły. Można mieć wiele instancji WAF (np. per-vhost). Reguły są współdzielone między transakcjami tej samej instancji WAF - transakcja nigdy nie może modyfikować reguły, wszystkie mutowalne dane muszą być przechowywane w transakcji. Ma to bezpośrednie implikacje dla thread-safety.

**Transaction** to per-request instancja - tworzona przez `waf.NewTransaction()`. Przechowuje kolekcje zmiennych, stan przetwarzania i wyniki dopasowań. Transakcja *może* zwrócić interruption jeśli dopasowana reguła wywoła akcję disruptive - nie każda transakcja kończy się przerwaniem. Po zakończeniu zawsze należy wywołać `tx.ProcessLogging()` i `tx.Close()`.

## SecRuleEngine - tryby działania

- `On` - aktywne blokowanie, reguły mogą przerywać transakcje
- `DetectionOnly` - reguły są oceniane i logowane, ale nigdy nie blokują
- `Off` - WAF wyłączony

Tryb `DetectionOnly` jest kluczowy przy implementacji per-vhost policies - pozwala włączyć WAF w trybie obserwacji zanim zacznie blokować.

## Rules Flow

Dla każdej reguły w danej fazie:

1. Pomiń regułę jeśli została usunięta dla tej transakcji (`SecRuleRemoveById`)
2. Wypełnij zmienną `RULE` danymi bieżącej reguły
3. Zastosuj usunięte targety dla tej transakcji
4. Skompiluj każdą zmienną: normalne, liczniki, negacje i "always match"
5. Zastosuj transformacje dla każdej zmiennej (match lub multi-match)
6. Wykonaj operator dla każdej zmiennej
7. Kontynuuj tylko jeśli było dopasowanie
8. Oceń wszystkie akcje non-disruptive
9. Oceń łańcuchy (chains) rekurencyjnie
10. Zaloguj dane jeśli wymagane
11. Oceń akcje disruptive i flow

## Akcje

- **non-disruptive** - wykonują coś, ale nie wpływają na flow przetwarzania reguł. Mogą jednak zmieniać stan transakcji - np. `setvar`, `setuid`, `setenv`. Oceniane po dopasowaniu reguły, mogą wystąpić w każdej regule, w tym w chainach.
- **flow** - zmieniają przepływ wykonania reguł, np. `skip`, `skipAfter`. Oceniane po dopasowaniu, tylko dla reguły nadrzędnej w chainie.
- **disruptive** - przerywają transakcję: `deny`, `drop`, `redirect`, `allow`. Oceniane na końcu.
- **metadata** - dostarczają informacje o regule: `id`, `rev`, `severity`, `msg`. Tylko inicjalizowane, nigdy nie są wywoływane w runtime.

## Fazy przetwarzania

Reguły są sortowane **według fazy, nie według ID**. Reguła z `phase:1` wykona się przed regułą z `phase:2` niezależnie od numeru ID.

| Faza | Nazwa | Co zawiera |
|------|-------|------------|
| 1 | Request Headers | połączenie (IP, port), URI, GET args, nagłówki (cookies, content-type) |
| 2 | Request Body | POST args, multipart/pliki, JSON, XML, raw body. Działa tylko gdy `SecRequestBodyAccess On` |
| 3 | Response Headers | status code, nagłówki odpowiedzi |
| 4 | Response Body | raw body odpowiedzi |
| 5 | Logging | uruchamia się zawsze, nawet po wysłaniu odpowiedzi. Zamyka handlery, zapisuje persistent collections, zapisuje audit log |

## Collections i Zmienne

Collections to sposób przechowywania zmiennych w transakcji. Każda zmienna (REQUEST_HEADERS, ARGS, FILES itd.) jest kolekcją. Dostęp przez `tx.GetCollection(variables.RequestHeaders)`.

Zmienne są kompilowane w runtime - obsługują regex, negacje i wyjątki. Przy `GetField` z regexem Coraza używa `RuleVariable.Regex` zamiast klucza.

Collections **nie są** thread-safe - nie należy współdzielić transakcji między goroutines.

## Macro Expansion

Mechanizm "kompilowania" stringów zawierających makra do konkretnych wartości w kontekście transakcji. Wyrażenie regularne szuka wzorców `%{nazwa_zmiennej}` i zastępuje je wartością z kolekcji transakcji.

```
%{request_headers.user-agent}  →  wartość nagłówka User-Agent
%{tx.anomaly_score}            →  bieżący score anomalii
```

## Body Handling

**BodyBuffer** buforuje body requestu/response w pamięci lub w pliku tymczasowym. Buforowanie jest konieczne, bo Coraza musi przeczytać całe body zanim wyda decyzję o blokowaniu. Pliki tymczasowe są usuwane przez `tx.ProcessLogging()`.

**Body Processors** parsują body według content-type:

| Procesor | Request | Response | Correlation | Tinygo |
|----------|---------|----------|-------------|--------|
| URLEncoded | tak | nie | nie | tak |
| Multipart | tak | nie | nie | tak |
| JSON | tak | tak | nie | tak |
| XML (częściowe) | tak | tak | nie | nie |
| GraphQL | TBD | TBD | tak | TBD |

Jeśli content-type nie pasuje do żadnego procesora, body nie jest parsowane i zmienne POST/FILES pozostają puste. Można to obejść przez `SecRequestBodyForceBufferVar On` - wymusi przetwarzanie jako URLEncoded.

## Integracja z HAProxy przez SPOA

Coraza SPOA działa jako osobny proces nasłuchujący na gniazdo TCP/Unix. HAProxy wysyła do niego ramki SPOE z danymi requestu/response.

Mapowanie na model Coraza:
- jedno wywołanie SPOE = jedna transakcja Coraza
- HAProxy wysyła request headers i body w osobnych wiadomościach SPOE
- SPOA zwraca zmienną (np. `waf.action`) z decyzją: `allow` lub `deny`
- HAProxy na podstawie tej zmiennej podejmuje decyzję ACL

Ważne: SPOA obsługuje fazy 1-2 (request). Fazy 3-4 (response) wymagają osobnej konfiguracji i nie zawsze są wspierane w trybie SPOE.

## Źródła

- https://coraza.io/docs/reference/internals
- https://coraza.io/docs/seclang/execution-flow
- https://coraza.io/docs/reference/body-processing
- https://github.com/corazawaf/coraza-spoa
