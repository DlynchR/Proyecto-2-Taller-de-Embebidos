# Atajos del proyecto EdgeAI. "make help" para ver la lista.
PY ?= python3
MOCK_PORT ?= 11435
DEV ?=

.PHONY: help test lint dev dev-real mock bench check-host setup build flash deps clean

help:
	@echo "Desarrollo (cualquier PC):"
	@echo "  make test        pruebas automáticas (sin hardware ni modelos)"
	@echo "  make lint        verificación de sintaxis y estilo de scripts"
	@echo "  make dev         app en http://127.0.0.1:8080 con el simulador de Ollama"
	@echo "  make dev-real    app contra un Ollama real en 127.0.0.1:11434"
	@echo "  make bench       casos de uso contra el simulador"
	@echo "Imagen Yocto (máquina Linux de build):"
	@echo "  make check-host  requisitos del host"
	@echo "  make setup       capas + directorio build/"
	@echo "  make build       bitbake edgeai-image"
	@echo "  make flash DEV=/dev/sdX"
	@echo "  make deps        árbol de dependencias en docs/generated/"

test:
	$(PY) -m unittest discover -s tests -t tests

lint:
	$(PY) -m compileall -q app/edgeai_helpdesk tools tests
	@if command -v shellcheck > /dev/null; then shellcheck -x scripts/*.sh app/bin/*; \
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

check-host:
	./scripts/check-host.sh

setup:
	./scripts/setup-build.sh

build:
	./scripts/build-image.sh

flash:
	@test -n "$(DEV)" || (echo "Uso: make flash DEV=/dev/sdX"; exit 1)
	./scripts/flash-sd.sh $(DEV)

deps:
	./scripts/dependency-graph.sh

clean:
	rm -rf var/ app/edgeai_helpdesk/__pycache__ tests/__pycache__ tools/__pycache__
