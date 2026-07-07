# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only.
COPY pyproject.toml ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY docs/ ./docs/

RUN pip install --no-cache-dir -e .

# Create a non-root user and default project directory.
RUN groupadd -r research \
    && useradd -r -g research -d /project research \
    && mkdir -p /project \
    && chown research:research /project

USER research
WORKDIR /project

ENTRYPOINT ["research-engine"]
CMD ["--help"]
