# Projekt rozwiązania

## Architektura: HAProxy jako reverse proxy + integracja WAF przez SPOE/SPOA

<!-- 
Opis architektury:
- HAProxy jako punkt wejścia (reverse proxy)
- SPOE (Stream Processing Offload Engine) -- mechanizm delegowania
- SPOA (Stream Processing Offload Agent) -- Coraza jako agent
- Przepływ żądania HTTP przez system
- Diagram architektury (assets/figures/)
-->

## Model polityk bezpieczeństwa (per domena/vhost)

<!-- 
Model polityk:
- Polityka per virtual host
- Tryby: detection / prevention / disabled
- Konfiguracja paranoia level per vhost
- Progi anomaly scoring
- Wyjątki od reguł (rule exclusions)
-->

## Projekt panelu administracyjnego (self-hosted) i model danych

<!-- 
Panel administracyjny:
- Stos: FastAPI (backend) + React/TypeScript (frontend)
- Model danych: vhosty, polityki, reguły, wyjątki, logi
- Diagram ERD (assets/figures/)
- Interfejs użytkownika -- główne widoki
-->

## Logowanie zdarzeń i obserwowalność (metryki, audyt)

<!-- 
Logowanie i monitoring:
- Struktura logów WAF
- Metryki (Prometheus-compatible)
- Audyt zmian konfiguracji
-->
