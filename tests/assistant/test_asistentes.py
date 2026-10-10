"""Puerto y adaptadores del asistente (ADR-0012). Adaptadores remotos: issue #32."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from transim.assistant.null import NullAssistant
from transim.assistant.port import Assistant
from transim.fpu.format import BINARY32


def test_null_cumple_el_puerto() -> None:
    a = NullAssistant()
    assert isinstance(a, Assistant)
    assert "traza" in a.explain_trace("traza")
    assert a.nl_to_program("sumar").rstrip().endswith("HALT")
    pares = a.propose_edge_cases("+", BINARY32, 10)
    assert len(pares) == 10
    assert all(0 <= x < 2**32 and 0 <= y < 2**32 for x, y in pares)


def test_programa_del_null_ensambla() -> None:
    from transim.cpu.assembler import assemble

    assert assemble(NullAssistant().nl_to_program("lo que sea")) == [0xFF000000]


@pytest.fixture
def ollama_falso() -> Iterator[str]:
    """Servidor HTTP local que imita ``POST /api/generate`` de Ollama."""
    respuestas = iter(
        ["Explicación.", "```\nLI F1, 1.0\nHALT\n```", "0x3f800000 0x0\nbasura\n0x1 0x2"]
    )

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert cuerpo["model"] == "modelo-local"
            datos = json.dumps({"response": next(respuestas), "done": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *args: object) -> None:
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}"
    servidor.shutdown()


def test_ollama_contra_servidor_local(ollama_falso: str) -> None:
    from transim.assistant.ollama import OllamaAssistant

    a = OllamaAssistant("modelo-local", url=ollama_falso)
    assert isinstance(a, Assistant)
    assert a.explain_trace("t") == "Explicación."
    assert a.nl_to_program("carga 1") == "LI F1, 1.0\nHALT\n"  # sin cercas de código
    assert a.propose_edge_cases("+", BINARY32, 5) == [(0x3F800000, 0), (1, 2)]  # ignora basura


def test_anthropic_exige_la_clave(monkeypatch: pytest.MonkeyPatch) -> None:
    from transim.assistant.anthropic import API_KEY_ENV, AnthropicAssistant

    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError) as info:
        AnthropicAssistant("modelo")
    assert API_KEY_ENV in str(info.value)
