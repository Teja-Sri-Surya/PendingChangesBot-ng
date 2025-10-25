#!/bin/bash
# Type checking script for PendingChangesBot-ng

set -e

echo "🔬 Running type checking for PendingChangesBot-ng..."

# Install mypy if not already installed
if ! command -v mypy &> /dev/null; then
    echo "📦 Installing MyPy..."
    pip install mypy
fi

# Run MyPy type checking
echo "🔍 Running MyPy type checking..."
mypy app/ --config-file mypy.ini

echo "✅ Type checking completed!"
