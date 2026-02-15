# Testy i wyniki

## Metodologia testów i scenariusze

<!-- 
Opis metodologii:
- Środowisko testowe
- Narzędzia (curl, nikto, sqlmap, custom scripts)
- Scenariusze testowe
- Metryki zbierane podczas testów
-->

## Testy SQL injection (skuteczność i FP)

<!-- 
Wyniki testów SQLi:
- Payloady testowe (OWASP Top 10)
- Tabela wyników: wykryte / pominięte
- Analiza false positives
- Porównanie przy różnych PL
-->

## Testy dostępu do plików wrażliwych (.env/.config) i reguły URI

<!-- 
Wyniki testów ochrony plików:
- Scenariusze dostępu do .env, .git, .config
- Skuteczność reguł URI
- Tabela wyników
-->

## Testy wpływu PL i progów anomaly scoring na wyniki

<!-- 
Analiza porównawcza:
- PL1 vs PL2 vs PL3 vs PL4
- Różne progi anomaly scoring
- Wpływ na FP/FN
- Wykresy i tabele porównawcze
-->

## Testy wydajności (RPS, latency)

<!-- 
Testy wydajnościowe:
- Requests per second (RPS)
- Latency (p50, p95, p99)
- Zużycie CPU i RAM
- Porównanie: z WAF vs bez WAF
- Wykresy obciążenia
-->
