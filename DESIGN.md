# Notas de diseño — Branch Queue

## 1. Una cola por tipo de servicio (`dict[str, deque]`)

`BranchQueue` guarda un diccionario con una `collections.deque` por servicio:

```python
{"deposito": deque([...]), "retiro": deque([...]), "gestion_cuenta": deque([...])}
```

y un contador global `_next_number` para numerar los tickets.

| Operación | Coste |
|---|---|
| `issue_ticket` | O(1): busca la cola en el diccionario y hace `append` al final |
| `call_next` | O(1): `popleft` de la cola de ese servicio |
| `peek_next` | O(1): mira `queue[0]` |
| `list_waiting` | O(n): copia las tres colas |
| `stats` | O(1): `len()` de cada cola |

### Por qué es más eficiente que una única cola compartida

Con **una sola lista** de todos los clientes en orden de llegada, el agente de depósitos tiene
que **recorrerla desde el principio** hasta encontrar el primer ticket de depósito. Si delante
hay 200 personas de retiros, mira 200 tickets antes de encontrar el suyo: O(n). Además, sacarlo
del medio de una lista desplaza a todos los que van detrás, que también es O(n). Cuanto más
se llena la sucursal, más tarda cada agente, aunque no haya nadie de su servicio.

Con **una cola por servicio**, el siguiente cliente de depósitos **siempre está en la primera
posición de su propia cola**. `call_next("deposito")` no mira a nadie de retiros ni de gestión
de cuenta: es O(1) tenga la sala 5 personas o 500. Es justo el problema del enunciado: el agente
de depósitos ya no puede quedarse parado con un cliente suyo «enterrado» en la lista general.

### Por qué `deque` y no `list`

`list.pop(0)` es O(n), porque desplaza todos los elementos. `deque.popleft()` es O(1), porque
la `deque` está pensada para sacar por un extremo y meter por el otro.

### El orden FIFO y el número global

Dentro de cada cola, los tickets entran con `append` y salen con `popleft`, así que el orden de
llegada se respeta. El número del ticket es un contador **único para toda la sucursal**: un
cliente de retiros y uno de depósitos nunca comparten número. Un ticket con un servicio no
válido se rechaza **antes** de consumir número, así no quedan huecos en la numeración.

## 2. Dos agentes del mismo servicio llamando a la vez

Escenario: dos agentes de depósitos quedan libres a la vez y los dos llaman a
`call_next("deposito")`.

**Qué puede salir mal sin protección:** si cada agente hace «mirar quién es el primero» y
después «sacarlo» como dos pasos separados, los dos pueden mirar a la vez, ver **al mismo
cliente** (ticket #7) y llamarlo los dos. Después, uno de los dos saca al #8 sin haberlo llamado,
o se pierde un cliente. Lo mismo pasa con el contador: dos quioscos podrían leer el mismo número
y dar el #12 a dos clientes.

**Qué mutación tiene que ocurrir primero:** **sacar el ticket de la cola**. La extracción
(`popleft`) es lo que «reserva» al cliente para un agente: el cliente sale de la cola **antes**
de que el agente lo anuncie o lo atienda. Así, cuando el segundo agente mira la cola, el #7 ya
no está y se lleva el #8. Nunca se hace `peek_next` y luego `call_next` para atender: `peek_next`
es solo informativo.

**Cómo lo garantizo:** `BranchQueue` tiene un `threading.Lock`. `call_next` comprueba que la
cola no esté vacía y hace `popleft` **dentro del mismo bloque con lock**, sin soltarlo entre
medias. `issue_ticket` lee el número, lo incrementa y encola también dentro del lock, así el
número y la posición en la cola siempre van juntos. Así:

1. El agente A toma el lock, saca el #7 y lo suelta.
2. El agente B toma el lock y saca el #8.

Nadie se llama dos veces y nadie se pierde.

Hay dos tests que lo comprueban (`tests/test_branch_queue.py`):

- `test_concurrent_agents_never_call_the_same_client_twice`: 8 agentes vacían a la vez una cola
  de 3000 clientes, y cada número sale exactamente una vez.
- `test_concurrent_issuing_never_repeats_a_number`: 6 quioscos emiten 3000 tickets a la vez, y
  salen los números del 1 al 3000 sin repetir ninguno.

**Una mejora posible:** un lock por servicio dejaría que el agente de depósitos y el de retiros
nunca se esperen entre sí. No lo hice porque el contador global también necesita su protección,
y con colas tan pequeñas un solo lock es más simple y no se nota.

**Si esto creciera** a varios quioscos en máquinas distintas, un lock en memoria no bastaría.
La extracción tendría que ser atómica en la base de datos (por ejemplo
`SELECT … FOR UPDATE SKIP LOCKED` en PostgreSQL) o usar una cola de mensajes con ACK, y el
número de ticket saldría de una secuencia de la base de datos.
