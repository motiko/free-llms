# Repository Guidelines

## Project Structure & Module Organization

This repository configures a LiteLLM proxy. `config.yaml` defines provider deployments, role aliases, fallbacks, and callbacks. `run.sh` starts the proxy, and `claude-free` connects Claude Code to it. `request_log.py` records requests; `reqlog` analyzes those logs. `bench/bench.py` runs capability probes and writes timestamped Markdown/JSON reports to `bench/results/`. `debug/` contains routing diagnostics. Consult `README.md` and `CLAUDE.md` for operational details. There is no dedicated test or asset directory.

## Build, Test, and Development Commands

- `./setup.sh`: install locked dependencies into `.venv` and create `.env` without replacing existing credentials.
- `./run.sh`: start the proxy on port 4000. It uses configuration and credentials beside the script and defaults to `127.0.0.1`; configure the listener in `.env`. Avoid starting a second instance when launchd already manages it.
- `./service.sh start|stop|restart|status|logs|uninstall`: manage the macOS user background service and login startup.
- `./claude-free`: launch Claude Code using the `smart` alias; select another with `CLAUDE_FREE_MODEL=code`.
- `.venv/bin/python bench/bench.py --only groq-`: benchmark selected deployments against the running proxy.
- `./reqlog --since 24h models`: inspect recent deployment performance.

There is no build step. Use the offline YAML/Router validation snippet in `README.md` before restarting a changed configuration.

## Coding Style & Naming Conventions

Use four-space indentation in Python and two-space indentation in YAML. Preserve each shell script's declared interpreter and existing style. Use `snake_case` for Python functions and variables. Deployment names follow `provider-model-size`, such as `groq-gptoss-120b`; preserve the `smart`, `fast`, `code`, `cheap`, and `embed` aliases. Maintain fallback entries for both deployment names and aliases. No formatter or linter is configured.

## Testing Guidelines

No unit-test framework or coverage threshold is configured. Validate configuration offline, then smoke-test the changed alias through the proxy. Benchmark probes check Anthropic tool calls, executable FizzBuzz output, and JSON responses; fallback use counts as failure. Limit runs with `--only` or `--skip` to conserve provider quotas. Reports use `<YYYYMMDD-HHMM>.md` and `.json` filenames.

## Commit & Pull Request Guidelines

Existing commits use short, plain summaries (`init`, `add logs analysis tool`); no formal convention is established. Keep commits focused. PRs should explain routing or utility changes, list validation performed, and link relevant issues. Include benchmark evidence when changing fallback order.

## Security & Configuration

Never commit `.env`, provider keys, or private request logs. Keep local model overrides in ignored `config.local.yaml`. Back up configuration before broad rewrites. Replace the default master key before exposing the proxy to other machines, and clearly label paid deployments.
