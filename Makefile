.PHONY: run dev lint test clean web-dev web-build web-test web-lint

# Run the HUD (mock mode by default)
run:
	cd src && python main.py

# Run once and exit (useful for previewing a single frame)
dev:
	HUD_REFRESH_INTERVAL=0 cd src && python -c "\
from config import load_config; \
from display import get_display; \
from display.context import DisplayContext; \
from sysmon import get_system_monitor; \
from weather import get_weather_client; \
from main import render_frame; \
config = load_config(); \
d = get_display(config); \
ctx = DisplayContext(system_monitor=get_system_monitor(config), weather_client=get_weather_client(config)); \
render_frame(d, ctx=ctx); \
print('Frame saved to output/latest.png')"

# Lint with ruff
lint:
	ruff check src/ tests/

# Run tests
test:
	pytest tests/ -v

# Clean generated files
clean:
	rm -rf output/ __pycache__ src/__pycache__ src/display/__pycache__ src/audio/__pycache__ src/speech/__pycache__

# --- Web frontend (SvelteKit SPA in web/) ---

# Start Vite dev server (proxies /api to http://127.0.0.1:8080)
web-dev:
	cd web && pnpm run dev

# Build the SPA into web/dist/ — served by the Python telemetry server
web-build:
	cd web && pnpm run build

# Run Vitest unit/component tests
web-test:
	cd web && pnpm run test

# Lint + format check
web-lint:
	cd web && pnpm run lint
