# Branch Queue — Cola de Servicio Etiquetada

Gestor de turnos para las sucursales de Banco Meridional, en Python y para la terminal. Solo usa
la biblioteca estándar.

- Cada cliente saca un ticket para un servicio: `deposito`, `retiro` o `gestion_cuenta`.
- Los tickets se numeran desde el 1 con un **contador global**, compartido entre todos los
  servicios.
- Cada agente llama **al siguiente de su servicio**, en orden de llegada, sin recorrer al resto
  de la sala.

## Ejecutar

```bash
python branch_queue.py
```

Menú:

```
=== Banco Meridional — Turnos ===
1. Emitir ticket
2. Llamar al siguiente cliente de un servicio
3. Ver la lista de espera
4. Ver estadísticas
5. Salir
```

El servicio se puede escribir por número (`1`, `2`, `3`) o por nombre (`deposito`, `retiro`,
`gestion_cuenta`). Las entradas no válidas (opción inexistente, nombre vacío, servicio que no
existe, cola vacía, Ctrl+D o Ctrl+C) muestran un mensaje y el programa sigue o sale limpio, sin
romperse.

## Tests

```bash
python -m unittest -v
```

16 tests: numeración global, FIFO por servicio, cada agente solo recibe su servicio, `peek_next`
sin sacar, errores con cola vacía y servicio no válido, `list_waiting` agrupado, `stats` con
total, el menú con entradas válidas e inválidas, y varios hilos llamando y emitiendo a la vez
sin repetir clientes ni números.

## Estructura

| Archivo | Contenido |
|---|---|
| `branch_queue.py` | `Ticket` (dataclass), `BranchQueue` (las colas y el contador), `BranchCLI` (el menú) y `main()` |
| `tests/test_branch_queue.py` | Tests con `unittest` |
| `DESIGN.md` | Por qué una `deque` por servicio y cómo se evita llamar dos veces al mismo cliente |

## API de `BranchQueue`

| Método | Qué hace |
|---|---|
| `issue_ticket(client_name, service_type)` | Crea el ticket con el siguiente número, lo encola en su servicio y lo devuelve |
| `call_next(service_type)` | Saca y devuelve el siguiente de ese servicio; lanza `EmptyServiceQueueError` si no hay nadie |
| `peek_next(service_type)` | Devuelve el siguiente sin sacarlo; lanza `EmptyServiceQueueError` si no hay nadie |
| `list_waiting()` | `{servicio: [tickets en orden]}` para los tres servicios |
| `stats()` | `{"deposito": n, "retiro": n, "gestion_cuenta": n, "total": n}` |

Un servicio que no existe lanza `InvalidServiceError` con un mensaje que dice cuáles son válidos.
