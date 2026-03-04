Owasp CRS to zbior regul OWASP do wspoldzialania z WAFami. Chroni przede wszystkim przed atakami z OWASP Top 10. 

Dzialanie opiera sie o sprawdzanie requestow i responsow wedlug faz. Za kazda match w jakims rule dodaje punkt do scoringu anomalii. 

Sa 4 poziomy paranoi:
- PL1 - najmniej restrykcyjny
- PL2 - ok gdy sa dane osobowe w witrynie
- PL3 - dobry dla np. bankowosci
- PL4 - najbardziej restrykcyjny

Domyslnie jest 1. Uwaga!
Na kazdym poziomie mozna zbierac false positives. To nie jest tak, ze to wystarczy wlaczyc i tyle - to sa tygodnie pracy i zbierania danych i wykluaczanie kolejnych regul. Wazne w tym projekcie bedzie wygodne UI do zarzadzania tymi regulami.
Poza poziomami paranoi jest jeszcze anomaly scoring. Domyslnie jest ustawiony na 5. Jest to score, ktory jest dodawany do transakcji. Jezeli score przekroczy próg, to transakcja jest blokowana. 

Ten anomaly scoring threshold jako 5 jest zazwyczaj ok ze wzgledu na to, ze:
Jeden typ ataku sql moze byc oznaczony przez 5 roznych rule, co da wynik 25 i zablokuje transakcje. 
Jednakze, moze byc jakis rzadki typ ataku, ktory moze byc oznaczony przez 1 rule, co da wynik 5 i nie zablokuje transakcji przy wyzszym threshold.

Sa 4 poziomy severity:
- NOTICE - 2
- WARNING - 3 
- ERROR - 4
- CRITICAL - 5

Domyslnie flow CRS opiera sie o 4 fazy:
1. Execute all request rules
2. Make a blocking decision using the inbound anomaly score threshold
3. Execute all response rules
4. Make a blocking decision using the outbound anomaly score threshold

Jednakze, jest opcja uruchomienia early blocking - blokowania na poczatku requestu. W tym przypadku, flow CRS wyglada nastepujaco:
1. Execute all phase 1 (request header) rules
2. Make an early blocking decision using the inbound anomaly score threshold
3. Execute all phase 2 (request body) rules
4. Make a blocking decision using the inbound anomaly score threshold
5. Execute all phase 3 (response header) rules
6. Make an early blocking decision using the outbound anomaly score threshold
7. Execute all phase 4 (response body) rules
8. Make a blocking decision using the outbound anomaly score threshold

Prawdopodobnie domyslnie w tym projekcie bedzie wlaczone early blocking. Zobaczymy jeszcze jak to wyjdzie w testach wydajnosciowych. 
Jedyny drawback early blocking jest taki, ze nie ma mozliwosci logowania anomalii na poczatku requestu.

Rule'i nie powinno sie usuwac z CRS. Powinno sie je wykluczac.  
- w configure-time np przy restarcie wafa
- w runtime np przy wykonywaniu zapytania (wieksze obciazenie w aplikacji bo dodatkowy rule wykluczajacy)

Dwie motody wykluaczania:
- caly rule/tag 
- pojedyncza zmienna w rule

Tu tez nasuwa sie pytanie - jak to fajnie zorganizowac? aby koncowy administrator/uzytkownik mogl latwo zarzadzac tymi wykluczeniami? Moze jakas lista defaultowych wykluczen dla konkretnych aplikacji/przypadkow? moze jakis micro llm? Duzo mozliwosci, malo czasu :////
Ale tez w druga strone - ktos kto nie ma aplikacji krozystajacej z javy, sql or whatever - po co mu rule do tego? niepotrzebne dodatkowe obciazenie. Moze jakis kwestionariusz przy dodawaniu aplikacji?

Dostepne rule exlusion packages sa bardzo biedne:cPanel
DokuWiki
Drupal
Nextcloud
phpBB
phpMyAdmin
WordPress
XenForo

Moze by daloby sie jakos to fajnie zautomatyzowac i stworzyc wiecej wykluczen? 

do dalszej lektury w przyszlosci: https://www.netnea.com/cms/apache-tutorial-8_handling-false-positives-modsecurity-core-rule-set/


Zrodla:
https://coreruleset.org/docs/2-how-crs-works/2-1-anomaly_scoring/
https://coreruleset.org/docs/2-how-crs-works/2-2-paranoia_levels/index.html
https://coreruleset.org/docs/2-how-crs-works/2-3-false-positives-and-tuning/
