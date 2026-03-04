---
date: 2026-03-04
tags: [decision, waf, crs, ux]
---

# Otwarte pytania projektowe - CRS i zarządzanie regułami

Pytania i pomysły zebrane podczas badania OWASP CRS. Do rozstrzygnięcia przed/podczas implementacji.

---

## 1. Domyślny poziom paranoi i early blocking

**Pytanie:** Jaki PL ustawić domyślnie? Czy włączyć early blocking?

**Kontekst:** PL1 jest bezpieczny ale słabo chroni. PL2+ wymaga tuningu. Early blocking zmniejsza obciążenie ale może generować więcej FP bo decyzja zapada po nagłówkach bez wiedzy o body.

**Propozycja:** Domyślnie PL1 + early blocking włączone, ale wyniki testów wydajnościowych mogą to zmienić. Early blocking warto zweryfikować w benchmarkach - czy faktycznie robi różnicę przy typowym ruchu.

---

## 2. UI do zarządzania wykluczeniami

**Pytanie:** Jak zorganizować zarządzanie wykluczeniami reguł, żeby było użyteczne dla administratora bez głębokiej wiedzy o CRS?

**Kontekst:** Tuning CRS to tygodnie/miesiące zbierania false positives i stopniowego wykluczania reguł. Standardowe podejście (edycja plików .conf) jest nieprzyjazne.

**Pomysły:**
- Lista defaultowych wykluczeń dla znanych aplikacji (WordPress, Nextcloud itd.) - gotowe pakiety CRS już to częściowo pokrywają
- Kwestionariusz przy dodawaniu vhosta: "Czy aplikacja używa SQL?" / "Czy jest Java backend?" - na podstawie odpowiedzi sugeruj wyłączenie niepotrzebnych grup reguł
- Micro LLM do analizowania logów FP i sugerowania wykluczeń - dużo możliwości, mało czasu

**Do rozstrzygnięcia:** Który wariant jest realny w ramach pracy? Kwestionariusz jest najprostszy do implementacji.

---

## 3. Granularność wykluczeń - reguła vs zmienna

**Pytanie:** Czy udostępniać w UI wykluczenia per-zmienna czy tylko per-reguła?

**Kontekst:** Wykluczenie per-zmienna (np. ignoruj pole `search` w regule XSS) jest bezpieczniejsze niż wyłączenie całej reguły. Ale jest trudniejsze do zrozumienia przez użytkownika i trudniejsze do zaimplementowania w UI.

**Propozycja:** Najpierw per-reguła (prostsze), per-zmienna jako advanced mode.

---

## 4. Niepotrzebne reguły a wydajność

**Pytanie:** Czy warto pozwolić użytkownikowi wyłączyć całe grupy reguł których nie potrzebuje (np. reguły Java gdy aplikacja jest w PHP)?

**Kontekst:** Każda reguła to dodatkowy koszt CPU. Reguły do technologii których nie ma w aplikacji to czysty overhead.

**Propozycja:** Tak, ale jako opcję zaawansowaną przy konfiguracji vhosta. Kwestionariusz technologiczny przy tworzeniu vhosta mógłby to automatyzować.

---

## 5. Rozszerzenie pakietów wykluczeń

**Pytanie:** Gotowe pakiety CRS pokrywają tylko 8 aplikacji. Czy warto tworzyć własne?

**Kontekst:** Dostępne pakiety: cPanel, DokuWiki, Drupal, Nextcloud, phpBB, phpMyAdmin, WordPress, XenForo. Brakuje np. Joomla, Moodle, Gitea, popularnych frameworków.

**Propozycja:** Poza zakresem pracy magisterskiej, ale warto odnotować jako kierunek rozwoju po obronie.
