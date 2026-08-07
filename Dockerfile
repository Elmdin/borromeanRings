# borromeanRings — reproducible environment for running the gate.
# Build:  docker build -t borromeanRings .
# Gate:   docker run --rm borromeanRings            # runs ./verify.sh
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

# Run the gate as a non-root user (least privilege). /app is chowned so verify.sh
# can write its receipts. Dogfoods 14_container's non_root rule (ADR-0044).
RUN useradd --create-home --uid 10001 runner && chown -R runner:runner /app
USER runner

# Default: run borromeanRings's own gate (fail-closed; non-zero exit on failure).
CMD ["bash", "verify.sh"]
