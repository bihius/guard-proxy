# Wprowadzenie teoretyczne

## Reverse proxy i terminacja TLS w ochronie aplikacji WWW

Reverse proxy to serwer pośredniczący, który przyjmuje żądania od klientów i przekazuje je do serwerów docelowych. W kontekście bezpieczeństwa aplikacji webowych reverse proxy pełni kluczową rolę jako punkt kontroli ruchu HTTP/HTTPS, umożliwiając terminację TLS, inspekcję żądań oraz filtrowanie złośliwego ruchu zanim dotrze on do aplikacji[@haproxy-custom-rules].

HAProxy jest jednym z najpopularniejszych rozwiązań reverse proxy, oferującym zaawansowane mechanizmy równoważenia obciążenia oraz możliwość integracji z zewnętrznymi agentami przetwarzania poprzez protokół SPOE[@haproxy-rate-limiting].



## Web Application Firewall (WAF) -- rola, tryby pracy

<!-- 
Omówienie:
- Czym jest WAF i jakie pełni funkcje
- Tryby pracy: detection (monitoring) vs prevention (blocking)
- Miejsce WAF w modelu warstwowej ochrony
-->

## OWASP ModSecurity Core Rule Set (CRS) jako zestaw ogólnych reguł

<!-- 
Opis CRS:
- Historia i rozwój projektu
- Struktura reguł
- Powiązanie z ModSecurity i Coraza
-->

## Anomaly scoring i próg blokowania w CRS

<!-- 
Mechanizm anomaly scoring:
- Jak działają punkty anomalii
- Progi blokowania (inbound/outbound)
- Zalety w porównaniu z tradycyjnym trybem "deny on match"
-->

## Paranoia Levels (PL1--PL4) i wpływ na false positives

<!-- 
Poziomy paranoi CRS:
- PL1: minimalna ochrona, niski FP
- PL2: umiarkowana ochrona
- PL3: wysoka ochrona, więcej FP
- PL4: maksymalna ochrona, wysoki FP
- Praktyczne konsekwencje wyboru poziomu
-->
