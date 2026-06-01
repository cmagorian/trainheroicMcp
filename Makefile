.DEFAULT_GOAL := help

.PHONY: help install test test-v run run-http generate-token setup-claude setup-openclaw check-env

help:
	@echo ""
	@echo "  install          Install all dependencies (runtime + dev)"
	@echo "  check-env        Verify .env credentials are present"
	@echo "  test             Run the test suite"
	@echo "  test-v           Run the test suite (verbose)"
	@echo "  run              Start the MCP server locally (stdio)"
	@echo "  run-http         Start the MCP server locally (HTTP on :8000)"
	@echo "  generate-token   Print a new random MCP_AUTH_TOKEN"
	@echo "  setup-claude     Register with Claude Code (project scope)"
	@echo "  setup-openclaw   Register with OpenClaw"
	@echo ""

install:
	uv sync --all-groups

check-env:
	@test -f .env || (echo "ERROR: .env not found — copy .env.example and fill in credentials" && exit 1)
	@grep -qE "TRAINHEROIC_EMAIL|TRAINHEROIC_SESSION_TOKEN" .env || \
		(echo "ERROR: .env has no TrainHeroic credentials" && exit 1)
	@echo "OK: .env looks good"

test:
	uv run pytest

test-v:
	uv run pytest -v

run: check-env
	uv run python -m trainheroic_mcp.server

run-http: check-env
	MCP_TRANSPORT=http uv run python -m trainheroic_mcp.server

generate-token:
	@python3 -c "import secrets; print('MCP_AUTH_TOKEN=' + secrets.token_hex(32))"

setup-claude:
	@command -v claude >/dev/null 2>&1 || \
		(echo "ERROR: 'claude' not found — install Claude Code first: https://claude.ai/code" && exit 1)
	claude mcp add --scope project trainheroic -- uv run --directory "$(CURDIR)" python -m trainheroic_mcp.server
	@echo ""
	@echo "Done. Restart Claude Code to pick up the new server."
	@echo "Credentials are loaded from $(CURDIR)/.env"

setup-openclaw:
	@command -v openclaw >/dev/null 2>&1 || \
		(echo "ERROR: 'openclaw' not found — install OpenClaw first: https://openclaw.ai" && exit 1)
	openclaw mcp set trainheroic '{"command":"uv","args":["run","python","-m","trainheroic_mcp.server"],"cwd":"$(CURDIR)"}'
	@echo ""
	@echo "Done. Restart OpenClaw to pick up the new server."
	@echo "Credentials are loaded from $(CURDIR)/.env"
