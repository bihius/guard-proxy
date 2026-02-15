# Implementacja

## Konfiguracja HAProxy i przekazywanie transakcji do Coraza via SPOA

<!-- 
Szczegóły implementacji:
- Konfiguracja HAProxy (frontend, backend, SPOE filter)
- Definicja wiadomości SPOE
- Zmienne przekazywane między HAProxy a Coraza
- Przykładowe fragmenty konfiguracji
-->

## Uruchomienie Coraza SPOA i wpięcie OWASP CRS

<!-- 
Konfiguracja Coraza:
- Kompilacja/uruchomienie coraza-spoa
- Integracja z OWASP CRS
- Konfiguracja reguł bazowych
- Dostrojenie progów i poziomów paranoi
-->

## Implementacja panelu: zarządzanie vhostami, trybami, politykami, IP allow/deny, wyjątkami

<!-- 
Panel zarządzania:
- Backend API (FastAPI) -- endpointy, modele, schematy
- Frontend (React + TypeScript) -- komponenty, widoki
- CRUD operacje na politykach
- Mechanizm list IP
- Zarządzanie wyjątkami od reguł
-->

## Wdrażanie zmian, wersjonowanie, audyt

<!-- 
Proces wdrożenia:
- Docker Compose -- orkiestracja usług
- Hot-reload konfiguracji HAProxy
- Wersjonowanie polityk
- Dziennik audytu zmian
-->
