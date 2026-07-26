# Dev image for the FastAPI orchestrator.
# Build context is the repo root: `docker build -f apps/api/Dockerfile .`
FROM python:3.12-slim

WORKDIR /app

# git: opencode worktrees/diffs. curl/unzip/ca-certificates: opencode installer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/* \
    # Host-mounted repos may be owned by a different uid; allow the container git
    # to work with them without interactive prompts.
    && git config --global --add safe.directory '*'

# opencode CLI (Implementation Agent), oriented to the opencode Zen/Go plans.
# Non-fatal: the image still builds offline; the runner detects availability at
# runtime and falls back to the deterministic stub when opencode is absent.
RUN curl -fsSL https://opencode.ai/install | bash || echo "opencode install skipped"
ENV PATH="/root/.opencode/bin:${PATH}"

# Install the package (editable) so `uvicorn --reload` picks up mounted sources.
COPY apps/api/ /app/
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
