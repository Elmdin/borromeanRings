# borromeanRings — reproducible environment for running the gate.
# Build:  docker build -t borromeanRings .
# Gate:   docker run --rm borromeanRings            # runs ./verify.sh
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

# Default: run borromeanRings's own gate (fail-closed; non-zero exit on failure).
CMD ["bash", "verify.sh"]
