#!/usr/bin/env bash
set -euo pipefail

# Enable debug output if DEBUG environment variable is set
if [[ "${DEBUG:-0}" == "1" ]]; then
    set -x
fi

# Initialize default source directory
default_src="."

# Check if command-line arguments are provided
if [ $# -gt 0 ]; then
    # Use all command-line arguments as source paths
    SRC="$@"
else
    # Use default source directory if no arguments provided
    SRC="$default_src"
fi

export ZENML_DEBUG=1
export ZENML_ANALYTICS_OPT_IN=false

# autoflake replacement: removes unused imports and variables
ruff check $SRC --select F401,F841 --fix --exclude "__init__.py" --isolated

# sorts imports
ruff check $SRC --select I --fix --ignore D
ruff format $SRC
