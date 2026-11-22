"""Branch Queue — cola de servicio etiquetada para las sucursales de Banco Meridional.

Una deque por tipo de servicio y un contador global de tickets. Solo biblioteca estándar.
La decisión de diseño está en DESIGN.md.
Uso: python branch_queue.py
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

SERVICE_TYPES = {
    "deposito": "Depósitos",
    "retiro": "Retiros",
    "gestion_cuenta": "Gestión de cuenta",
}


class InvalidServiceError(ValueError):
    """Tipo de servicio que no existe."""


class EmptyServiceQueueError(Exception):
    """No hay clientes esperando para ese tipo de servicio."""


def validate_service(service_type: str) -> str:
    if service_type not in SERVICE_TYPES:
        valid = ", ".join(SERVICE_TYPES)
        raise InvalidServiceError(f"Tipo de servicio no válido: {service_type!r}. Usa uno de: {valid}.")
    return service_type


@dataclass(frozen=True)
class Ticket:
    number: int
    client_name: str
    service_type: str
    issued_at: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return (
            f"Ticket #{self.number} — {self.client_name} "
            f"({SERVICE_TYPES[self.service_type]}), llegó a las {self.issued_at:%H:%M:%S}"
        )


class BranchQueue:
    """Una cola FIFO (deque) por tipo de servicio y un contador global de tickets.

    - call_next / peek_next / issue_ticket son O(1): solo tocan la cola de ese servicio.
    - Un lock protege a la vez el contador y las colas, así dos agentes nunca se llevan
      el mismo ticket y dos clientes nunca reciben el mismo número.
    """

    def __init__(self) -> None:
        self._queues: dict[str, deque[Ticket]] = {service: deque() for service in SERVICE_TYPES}
        self._next_number = 1
        self._lock = threading.Lock()

    def issue_ticket(self, client_name: str, service_type: str) -> Ticket:
        validate_service(service_type)
        if not isinstance(client_name, str) or not client_name.strip():
            raise ValueError("El nombre del cliente no puede estar vacío.")
        with self._lock:
            ticket = Ticket(self._next_number, client_name.strip(), service_type)
            self._next_number += 1
            self._queues[service_type].append(ticket)
        return ticket

    def call_next(self, service_type: str) -> Ticket:
        validate_service(service_type)
        with self._lock:
            queue = self._queues[service_type]
            if not queue:
                raise EmptyServiceQueueError(
                    f"No hay clientes esperando para {SERVICE_TYPES[service_type]}."
                )
            return queue.popleft()

    def peek_next(self, service_type: str) -> Ticket:
        validate_service(service_type)
        with self._lock:
            queue = self._queues[service_type]
            if not queue:
                raise EmptyServiceQueueError(
                    f"No hay clientes esperando para {SERVICE_TYPES[service_type]}."
                )
            return queue[0]

    def list_waiting(self) -> dict[str, list[Ticket]]:
        with self._lock:
            return {service: list(queue) for service, queue in self._queues.items()}

    def stats(self) -> dict[str, int]:
        with self._lock:
            counts = {service: len(queue) for service, queue in self._queues.items()}
        counts["total"] = sum(counts.values())
        return counts


class BranchCLI:
    """Menú de terminal. Solo pide datos y muestra resultados; la lógica está en BranchQueue."""

    MENU = (
        "\n=== Banco Meridional — Turnos ===\n"
        "1. Emitir ticket\n"
        "2. Llamar al siguiente cliente de un servicio\n"
        "3. Ver la lista de espera\n"
        "4. Ver estadísticas\n"
        "5. Salir"
    )

    def __init__(self, queue: BranchQueue | None = None, input_fn=input, output_fn=print) -> None:
        self.queue = queue or BranchQueue()
        self._input = input_fn
        self._print = output_fn
        self._actions = {
            "1": self.issue_ticket,
            "2": self.call_next,
            "3": self.show_waiting,
            "4": self.show_stats,
        }

    def run(self) -> None:
        while True:
            self._print(self.MENU)
            try:
                choice = self._input("Elige una opción (1-5): ").strip()
                if choice == "5":
                    self._print("Hasta luego.")
                    return
                action = self._actions.get(choice)
                if action is None:
                    self._print("Opción no válida. Escribe un número del 1 al 5.")
                    continue
                action()
            except (EOFError, KeyboardInterrupt):
                self._print("\nHasta luego.")
                return

    def _ask_service(self) -> str | None:
        options = list(SERVICE_TYPES)
        for index, service in enumerate(options, start=1):
            self._print(f"  {index}. {SERVICE_TYPES[service]} ({service})")
        raw = self._input("Tipo de servicio (número o nombre): ").strip().lower()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        try:
            return validate_service(raw)
        except InvalidServiceError as exc:
            self._print(str(exc))
            return None

    def issue_ticket(self) -> None:
        name = self._input("Nombre del cliente: ").strip()
        if not name:
            self._print("El nombre no puede estar vacío.")
            return
        service = self._ask_service()
        if service is None:
            return
        ticket = self.queue.issue_ticket(name, service)
        self._print(f"Emitido: {ticket}")

    def call_next(self) -> None:
        service = self._ask_service()
        if service is None:
            return
        try:
            ticket = self.queue.call_next(service)
        except EmptyServiceQueueError as exc:
            self._print(str(exc))
            return
        self._print(f"Siguiente en {SERVICE_TYPES[service]}: {ticket}")

    def show_waiting(self) -> None:
        for service, tickets in self.queue.list_waiting().items():
            self._print(f"{SERVICE_TYPES[service]}:")
            if not tickets:
                self._print("  (nadie esperando)")
            for ticket in tickets:
                self._print(f"  {ticket}")

    def show_stats(self) -> None:
        counts = self.queue.stats()
        for service in SERVICE_TYPES:
            self._print(f"{SERVICE_TYPES[service]}: {counts[service]}")
        self._print(f"Total en espera: {counts['total']}")


def main() -> None:
    BranchCLI().run()


if __name__ == "__main__":
    main()
