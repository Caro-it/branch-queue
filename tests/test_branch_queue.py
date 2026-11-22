import threading
import unittest

from branch_queue import (
    BranchCLI,
    BranchQueue,
    EmptyServiceQueueError,
    InvalidServiceError,
)


def names(tickets):
    return [t.client_name for t in tickets]


class BranchQueueTests(unittest.TestCase):
    def setUp(self):
        self.q = BranchQueue()

    def test_ticket_numbers_are_global_and_sequential(self):
        a = self.q.issue_ticket("Ana", "deposito")
        b = self.q.issue_ticket("Luis", "retiro")
        c = self.q.issue_ticket("Eva", "gestion_cuenta")
        d = self.q.issue_ticket("Iñaki", "deposito")
        self.assertEqual([a.number, b.number, c.number, d.number], [1, 2, 3, 4])

    def test_fifo_within_a_service(self):
        for name in ("A", "B", "C"):
            self.q.issue_ticket(name, "retiro")
        self.assertEqual([self.q.call_next("retiro").client_name for _ in range(3)], ["A", "B", "C"])

    def test_agent_only_gets_its_own_service(self):
        self.q.issue_ticket("Retiro1", "retiro")
        self.q.issue_ticket("Deposito1", "deposito")
        self.q.issue_ticket("Retiro2", "retiro")
        self.assertEqual(self.q.call_next("deposito").client_name, "Deposito1")
        self.assertEqual(self.q.stats()["retiro"], 2)

    def test_peek_does_not_remove(self):
        self.q.issue_ticket("Ana", "deposito")
        self.assertEqual(self.q.peek_next("deposito").client_name, "Ana")
        self.assertEqual(self.q.stats()["deposito"], 1)

    def test_empty_service_raises_descriptive_error(self):
        self.q.issue_ticket("Ana", "deposito")
        with self.assertRaisesRegex(EmptyServiceQueueError, "Retiros"):
            self.q.call_next("retiro")
        with self.assertRaisesRegex(EmptyServiceQueueError, "Retiros"):
            self.q.peek_next("retiro")

    def test_invalid_service_is_rejected(self):
        for bad in ("prestamo", "", "DEPOSITO"):
            with self.assertRaisesRegex(InvalidServiceError, "no válido"):
                self.q.issue_ticket("Ana", bad)
        with self.assertRaises(InvalidServiceError):
            self.q.call_next("prestamo")
        self.assertEqual(self.q.stats()["total"], 0)

    def test_invalid_ticket_does_not_consume_a_number(self):
        with self.assertRaises(InvalidServiceError):
            self.q.issue_ticket("Ana", "prestamo")
        self.assertEqual(self.q.issue_ticket("Ana", "retiro").number, 1)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.q.issue_ticket("  ", "retiro")

    def test_list_waiting_grouped_and_ordered(self):
        self.q.issue_ticket("a", "retiro")
        self.q.issue_ticket("b", "deposito")
        self.q.issue_ticket("c", "retiro")
        waiting = self.q.list_waiting()
        self.assertEqual(set(waiting), {"deposito", "retiro", "gestion_cuenta"})
        self.assertEqual(names(waiting["retiro"]), ["a", "c"])
        self.assertEqual(names(waiting["deposito"]), ["b"])
        self.assertEqual(waiting["gestion_cuenta"], [])

    def test_list_waiting_is_a_copy(self):
        self.q.issue_ticket("a", "retiro")
        self.q.list_waiting()["retiro"].clear()
        self.assertEqual(self.q.stats()["retiro"], 1)

    def test_stats_with_total(self):
        self.q.issue_ticket("a", "retiro")
        self.q.issue_ticket("b", "retiro")
        self.q.issue_ticket("c", "gestion_cuenta")
        self.assertEqual(self.q.stats(), {"deposito": 0, "retiro": 2, "gestion_cuenta": 1, "total": 3})

    def test_concurrent_agents_never_call_the_same_client_twice(self):
        total = 3000
        for i in range(total):
            self.q.issue_ticket(f"c{i}", "deposito")
        called, lock = [], threading.Lock()

        def agent():
            while True:
                try:
                    ticket = self.q.call_next("deposito")
                except EmptyServiceQueueError:
                    return
                with lock:
                    called.append(ticket.number)

        threads = [threading.Thread(target=agent) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(called), list(range(1, total + 1)))

    def test_concurrent_issuing_never_repeats_a_number(self):
        numbers, lock = [], threading.Lock()

        def kiosk(service):
            for i in range(500):
                n = self.q.issue_ticket(f"x{i}", service).number
                with lock:
                    numbers.append(n)

        threads = [threading.Thread(target=kiosk, args=(s,)) for s in ("deposito", "retiro", "gestion_cuenta") * 2]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(numbers), list(range(1, 3001)))


class CLITests(unittest.TestCase):
    def run_cli(self, answers):
        out, it = [], iter(answers)
        BranchCLI(input_fn=lambda _: next(it), output_fn=out.append).run()
        return "\n".join(out)

    def test_full_session(self):
        text = self.run_cli(["1", "Ana", "2", "1", "Luis", "deposito", "3", "4", "2", "1", "5"])
        self.assertIn("Emitido: Ticket #1 — Ana (Retiros)", text)
        self.assertIn("Emitido: Ticket #2 — Luis (Depósitos)", text)
        self.assertIn("Total en espera: 2", text)
        self.assertIn("Siguiente en Depósitos: Ticket #2 — Luis", text)

    def test_invalid_input_does_not_crash(self):
        text = self.run_cli(["x", "1", "", "1", "Ana", "prestamo", "1", "Ana", "9", "2", "retiro", "5"])
        self.assertIn("Opción no válida", text)
        self.assertIn("El nombre no puede estar vacío", text)
        self.assertEqual(text.count("Tipo de servicio no válido"), 2)
        self.assertIn("No hay clientes esperando para Retiros", text)

    def test_ctrl_d_exits_cleanly(self):
        def eof(_):
            raise EOFError
        out = []
        BranchCLI(input_fn=eof, output_fn=out.append).run()
        self.assertIn("Hasta luego", out[-1])


if __name__ == "__main__":
    unittest.main()
