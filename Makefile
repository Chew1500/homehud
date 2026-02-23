.PHONY: run dev lint test clean

# Run the HUD (mock mode by default)
run:
	cd src && python main.py

# Run once and exit (useful for previewing a single frame)
dev:
	HUD_REFRESH_INTERVAL=0 cd src && python -c "\
from config import load_config; \
from display import get_display; \
from main import render_frame; \
config = load_config(); \
d = get_display(config); \
render_frame(d); \
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
