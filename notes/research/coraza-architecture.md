Coraza dziala na podstawie transakcji. Kazdy request jest traktowany jako transakcja. 
Kazda transakcja tworzy przerwanie aby dokonac decyzji na podstawie reguł. 

WAF moe mieć nieskonczenie wiele instancji, a kazda instancja moze miec nieskonczenie wiele transakcji. 

Rules flow:
Skip if this rule is removed for the current transaction
Fill the RULE variable data which contains fields from the current rule
Apply removed targets for this transaction
Compile each variable, normal, counters, negations and “always match”
Apply transformations for each variable, match or multi-match
Execute the current operator for each variable
Continue if there was any match
Evaluate all non-disruptive actions
Evaluate chains recursively
Log data if requested
Evaluate disruptive and flow rules

Akcje:
- non-disruptive - nie zmieniają stanu transakcji
- flow - zmieniaja flow np. skip lub skipAfter. Sa wykonywane po zmatchowaniu reguly
- metadata - uzywane do uzyskiwania wiecej informacji o regule

Fazy:
1. Request headers - polaczenie, url, headery
2. Request body - body. Dziala tylko gdy RequestBodyAces jest On. 
3. Response headers
4. response body
5. logging - uruchamia sie zawsze. Zamyka handlery, zapisuje persistent collection i zapisuje logi. 

WaF 