#!/usr/bin/env python3
"""LiteLLM routing debugger

Usage:
    python inspect_router_debug.py <model-or-alias>

The script loads the project's `config.yaml`, builds a LiteLLM `Router`
instance, and prints the exact fallback chain that LiteLLM will walk for the
requested name.  It also shows which concrete provider/model ends up being
selected (the first enabled entry in the chain).

This is a *read‑only* helper – it does not modify any configuration files.
"""

import sys
import yaml
from litellm import Router
from pathlib import Path

# Path to the repository's config file (absolute, because the script may be run
# from any working directory).
CONFIG_PATH = Path("/Users/moti.koritz/litellm/config.yaml")

if not CONFIG_PATH.is_file():
    sys.stderr.write(f"Error: config.yaml not found at {CONFIG_PATH}\n")
    sys.exit(1)

if len(sys.argv) != 2:
    sys.stderr.write("Usage: python inspect_router_debug.py <model-or-alias>\n")
    sys.exit(1)

requested_name = sys.argv[1]

# Load the YAML configuration exactly as the daemon does.
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)

router = Router(model_list=cfg["model_list"], **cfg["router_settings"])  # type: ignore[arg-type]

# Helper to print a nicely formatted chain.
def print_fallback_chain(name: str):
    chain = router.get_fallbacks(name)
    print(f"Requested: {name}\nFallback chain (first match wins):")
    for i, entry in enumerate(chain, start=1):
        print(f"  {i}. {entry}")
    # Resolve the final model that will be used.
    try:
        final = router.get_fallback_model(name)
        print(f"\n=> Selected provider/model: {final}\n")
    except Exception as e:
        print(f"\n=> No enabled model found in the chain. Reason: {e}\n")

print_fallback_chain(requested_name)
