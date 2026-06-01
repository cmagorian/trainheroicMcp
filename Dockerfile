FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (layer-cached before source copy)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy source
COPY src/ src/

ENV MCP_TRANSPORT=http

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "trainheroic_mcp.server"]
