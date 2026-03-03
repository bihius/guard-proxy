Działa na haproxy 1.7+

#### Infrastruktura:
Stream Processing Offload Engine (SPOE) - wewnatrz haproxy
Stream Processing Offload Agent (SPOA) - aplikacja zewnetrzna
Stream Processing Offload Protocol (SPOP) - protokol

Eventy triggerujace wyslanie danych do agenta:

| Event                      | Meaning                                                                                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `on-client-session`        | Triggered when a new client session is created. This event is only available for SPOE filters declared in a `frontend` or a `listen` section.                                      |
| `on-frontend-tcp-request`  | Triggered just before the evaluation of `tcp-request content` rules in a `frontend`. This event is only available for SPOE filters declared in a `frontend` or a `listen` section. |
| `on-backend-tcp-request`   | Triggered just before the evaluation of `tcp-request content` rules in a `backend`. This event is skipped for SPOE filters declared in a `listen` section.                         |
| `on-frontend-http-request` | Triggered just before the evaluation of `http-request` rules in a `frontend`. This event is only available for SPOE filters declared in a `frontend` or a `listen` section.        |
| `on-backend-http-request`  | Triggered just before the evaluation of `http-request` rules in a `backend`. This event is skipped for SPOE filters declared in a `listen` section.                                |
| `on-server-sessions`       | Triggered when a session with the server is established.                                                                                                                           |
| `on-tcp-response`          | Triggered just before the evaluation of `tcp-response content` rules.                                                                                                              |
| `on-http-response`         | Triggered just before the evaluation of `http-response` rules.                                                                                                                     |

mozna tez wykonac http-request send-spoe-group. Wymagane wczesniej deklaracja grupy wiadomosci. 

#### Typy ramek:

| Type (ID)                | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| 0 – _UNSET_              | Used for all frames except the first when a payload is fragmented.    |
| 1 – _HAPROXY-HELLO_      | Sent by HAProxy when it opens a connection to an agent.               |
| 2 – _HAPROXY-DISCONNECT_ | Sent by HAProxy when it wants to close the connection.                |
| 3 – _NOTIFY_             | Sent by HAProxy to pass information to an agent.                      |
| 101 – _AGENT-HELLO_      | Reply to a _HAPROXY-HELLO_ frame, when the connection is established. |
| 102 – _AGENT-DISCONNECT_ | Sent by an agent just before closing the connection.                  |
| 103 – _ACK_              | Sent to acknowledge a _NOTIFY_ frame.                                 |

Jesli cos pojdzie nie tak, haproxy przesyla Disconnect z **informacja o bledzie.**


#### Akcje
Mozna wykorzystywac zmienne zadeklarowane przez agenta do 
- filtrowania ruchu np:
`tcp-request content reject if { var(sess.iprep.ip_score) -m int lt 20 }`
- monitorowania:
`http-request capture var(sess.iprep.ip_score) len 3`


**Wydajnosc**:
SPOP moze wynegocjowac pipelining - wtedy ramki roznych polaczen beda przesylane wspolnym polaczeniem (mniej ramek HELLO). 

Moze tez dzialac asynchronicznie - ramki NOTIFY beda leciec jakimkolwiek polaczeniem. 


Źródła:
https://deepwiki.com/haproxy/haproxy/6.2-stream-processing-offload-engine-(spoe)
https://www.haproxy.com/blog/extending-haproxy-with-the-stream-processing-offload-engine