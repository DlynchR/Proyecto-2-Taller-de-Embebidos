# Atajos de desarrollo de la aplicacion EdgeAI.
PY ?= python3
MOCK_PORT ?= 11435

.PHONY: help test lint dev dev-real mock bench clean

help:
	@echo "Desarrollo (cualquier PC):"
	@echo "  make test        pruebas automaticas (sin hardware ni modelos)"
	@echo "  make lint        verificacion de sintaxis y scripts de la aplicacion"
	@echo "  make dev         aplicacion con el simulador de Ollama"
	@echo "  make dev-real    aplicacion contra un Ollama real"
	@echo "  make bench       casos de uso contra el simulador"

test:
	$(PY) -m unittest discover -s tests -t tests

lint:
	$(PY) -m compileall -q app/edgeai_helpdesk tools tests
	@if command -v shellcheck > /dev/null; then shellcheck -x app/bin/*; \
	 else echo "shellcheck no instalado: se omite"; fi

mock:
	$(PY) tools/mock_ollama.py --port $(MOCK_PORT)

dev:
	@echo "Kiosco: http://127.0.0.1:8080   Panel: http://127.0.0.1:8080/panel"
	@$(PY) tools/mock_ollama.py --port $(MOCK_PORT) & \
	 MOCK=$$!; trap "kill $$MOCK" EXIT INT TERM; sleep 0.5; \
	 EDGEAI_OLLAMA_URL=http://127.0.0.1:$(MOCK_PORT) PYTHONPATH=app $(PY) -m edgeai_helpdesk.server

dev-real:
	PYTHONPATH=app $(PY) -m edgeai_helpdesk.server

bench:
	@$(PY) tools/mock_ollama.py --port $(MOCK_PORT) --latencia-decision 0 --latencia-llm 0 & \
	 MOCK=$$!; trap "kill $$MOCK" EXIT INT TERM; sleep 0.5; \
	 EDGEAI_OLLAMA_URL=http://127.0.0.1:$(MOCK_PORT) PYTHONPATH=app $(PY) -m edgeai_helpdesk.bench --llm

clean:
	rm -rf var/ app/edgeai_helpdesk/__pycache__ tests/__pycache__ tools/__pycache__