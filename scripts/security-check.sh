#!/bin/bash
# Security scanning script for PendingChangesBot-ng

set -e

echo "🔒 Running security checks for PendingChangesBot-ng..."

# Install security tools
echo "📦 Installing security tools..."
pip install mypy bandit pip-audit

# Run Bandit security linter
echo "🛡️ Running Bandit security linter..."
bandit -r app/ -ll

# Run pip-audit for vulnerability scanning
echo "🔍 Running pip-audit vulnerability scan..."
pip-audit --desc

# Run MyPy type checking
echo "🔬 Running MyPy type checking..."
mypy app/ --ignore-missing-imports

echo "✅ Security checks completed!"
