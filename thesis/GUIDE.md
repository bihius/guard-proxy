# Przewodnik pisania pracy - Markdown + Pandoc

Krótki przewodnik po pisaniu pracy inżynierskiej w Markdown z kompilacją do PDF.

## Budowanie PDF

```bash
cd thesis/

make            # Zbuduj PDF (output/praca_inz.pdf)
make clean      # Usuń pliki wyjściowe
make debug      # Wygeneruj plik .tex do inspekcji
make watch      # Auto-rebuild przy zmianach (wymaga: brew install fswatch)
make wordcount  # Policz słowa w rozdziałach
make check      # Sprawdź czy pandoc parsuje pliki poprawnie
```

## Struktura rozdziałów

Rozdziały są w `chapters/` i sortowane alfabetycznie po nazwie pliku:

```
chapters/
├── 01-wstep.md           # Wstęp (nienumerowany)
├── 02-wprowadzenie.md    # Rozdział 1
├── 03-cele.md            # Rozdział 2
├── 04-projekt.md         # Rozdział 3
├── 05-implementacja.md   # Rozdział 4
├── 06-testy.md           # Rozdział 5
└── 07-podsumowanie.md    # Podsumowanie (nienumerowane)
```

### Dodawanie nowego rozdziału

1. Utwórz plik z odpowiednim prefiksem numerycznym, np. `chapters/04a-architektura.md`
2. Zacznij od nagłówka `# Tytuł rozdziału`
3. PDF sam się przebuduje z nowym rozdziałem (`make`)

### Sekcje nienumerowane

Dla rozdziałów bez numeru (Wstęp, Podsumowanie) dodaj `{-}` po tytule:

```markdown
# Wstęp {-}

Treść wstępu...
```

## Cytowania i bibliografia

### Składnia cytowań

W tekście Markdown używamy `[@klucz]`:

```markdown
HAProxy oferuje zaawansowane mechanizmy[@haproxy-rate-limiting].

Jak wskazuje dokumentacja Coraza[@coraza-waf, s. 15], silnik WAF...

Więcej o CRS[@owasp-crs; @crs-anomaly-scoring].
```

Efekt w PDF:
- `[@klucz]` → przypis dolny z pełnym opisem bibliograficznym
- `[@klucz, s. 15]` → przypis z numerem strony
- `[@klucz1; @klucz2]` → jeden przypis z dwoma źródłami

### Dodawanie nowego źródła

Edytuj `bibliography/references.bib` i dodaj wpis:

**Strona internetowa / dokumentacja online:**
```bibtex
@online{klucz-identyfikator,
  author  = {{Nazwa Organizacji}},
  title   = {Tytuł artykułu lub strony},
  url     = {https://example.com/pelna-sciezka},
  urldate = {2026-01-15}
}
```

**Książka:**
```bibtex
@book{klucz-identyfikator,
  author    = {Nazwisko, Imię},
  title     = {Tytuł książki},
  publisher = {Nazwa Wydawnictwa},
  address   = {Miejsce wydania},
  year      = {2024}
}
```

**Artykuł w czasopiśmie:**
```bibtex
@article{klucz-identyfikator,
  author  = {Nazwisko, Imię and Nazwisko2, Imię2},
  title   = {Tytuł artykułu},
  journal = {Nazwa Czasopisma},
  year    = {2024},
  volume  = {10},
  number  = {2},
  pages   = {15-30}
}
```

**Rozdział w książce zbiorowej:**
```bibtex
@incollection{klucz-identyfikator,
  author    = {Nazwisko, Imię},
  title     = {Tytuł rozdziału},
  booktitle = {Tytuł książki},
  editor    = {Redaktor, Imię},
  publisher = {Wydawnictwo},
  address   = {Miejsce},
  year      = {2024},
  pages     = {100-120}
}
```

**Uwagi:**
- Klucz (`klucz-identyfikator`) musi być unikalny - używaj go potem w `[@klucz-identyfikator]`
- Nazwy organizacji w podwójnych klamrach `{{OWASP}}` żeby nie były traktowane jako "Nazwisko, Imię"
- `urldate` to data dostępu do źródła internetowego (format: YYYY-MM-DD)

## Rysunki

Umieść pliki graficzne w `assets/figures/`, potem w Markdown:

```markdown
![Architektura systemu reverse proxy WAF](assets/figures/architektura.png){width=80%}
```

Parametry:
- `width=80%` — szerokość względem strony
- `height=10cm` — stała wysokość

Pandoc automatycznie generuje podpis "Rysunek N: Architektura systemu..." i dodaje do spisu rysunków.

### Odwołanie do rysunku w tekście

Aby odwoływać się do rysunków po numerze, użyj pandoc-crossref (opcjonalnie) lub po prostu napisz "na rysunku poniżej" / "jak pokazano na Rysunku 1".

## Tabele

```markdown
| Poziom paranoi | Opis                  | False Positives |
|:--------------:|:----------------------|:---------------:|
| PL1            | Minimalna ochrona     | Niski           |
| PL2            | Umiarkowana ochrona   | Średni          |
| PL3            | Wysoka ochrona        | Wysoki          |
| PL4            | Maksymalna ochrona    | Bardzo wysoki   |

: Porównanie poziomów paranoi CRS {#tbl:paranoia}
```

Wyrównanie kolumn:
- `:---` — do lewej
- `:---:` — do środka
- `---:` — do prawej

## Bloki kodu

### Krótki fragment inline

```markdown
Komenda `haproxy -c -f config.cfg` waliduje konfigurację.
```

### Blok kodu z podświetlaniem

````markdown
```yaml
# Przykład konfiguracji Docker Compose
services:
  haproxy:
    image: haproxy:2.9
    ports:
      - "80:80"
      - "443:443"
```
````

Obsługiwane języki: `python`, `bash`, `yaml`, `json`, `sql`, `javascript`, `go`, `lua`, `dockerfile` i wiele innych.

### Blok kodu z listingu (plik)

Aby dołączyć kod z pliku zewnętrznego, umieść go w `assets/listings/` i użyj:

````markdown
```{.python caption="Główna pętla serwera SPOA" #lst:spoa-loop}
def handle_connection(conn):
    while True:
        frame = conn.recv_frame()
        result = process_request(frame)
        conn.send_frame(result)
```
````

## Formatowanie tekstu

```markdown
**pogrubienie**
*kursywa*
~~przekreślenie~~

> Cytat blokowy (wcięty tekst)

---   ← linia pozioma

- lista punktowana
- element 2
  - zagnieżdżony element

1. lista numerowana
2. element 2
   a. podpunkt

Przypis dolny (nie bibliograficzny)^[Treść przypisu dolnego]
```

## Komentarze (niewidoczne w PDF)

```markdown
<!-- 
Ten tekst nie pojawi się w PDF.
Użyteczne do notatek i TODO.
-->
```

## Metadane

Plik `metadata.yaml` zawiera:
- Dane strony tytułowej (tytuł, autor, promotor, uczelnia)
- Ustawienia typografii (czcionka, marginesy, interlinia)
- Konfigurację bibliografii i spisu treści

**Zmień dane osobowe** w `metadata.yaml` przed oddaniem pracy:
- `author` — Twoje imię i nazwisko
- `student-id` — numer albumu
- `supervisor` — imię i nazwisko promotora z tytułem

## Wskazówki

1. **Kompiluj często** — `make` po każdej istotnej zmianie
2. **Sprawdzaj PDF** — otwórz `output/praca_inz.pdf` i zweryfikuj formatowanie
3. **Debuguj problemy** — `make debug` generuje `.tex` do inspekcji
4. **Komentarze HTML** — używaj `<!-- -->` do notatek, szkiców, TODO
5. **Git** — commituj regularnie, thesis/ jest w repozytorium
6. **Znaki specjalne** — `%`, `$`, `&`, `#`, `_` w tekście mogą wymagać escape'owania (`\%`, `\$`, itd.)
