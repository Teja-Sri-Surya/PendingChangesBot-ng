# Security Policy

## Supported Versions

We actively support the following versions of PendingChangesBot-ng:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Scanning

This project uses automated security scanning to identify potential vulnerabilities:

### Tools Used

- **Bandit**: Python security linter that finds common security issues
- **pip-audit**: Scans for known vulnerabilities in dependencies
- **MyPy**: Type checking to prevent runtime errors

### Running Security Checks

```bash
# Run all security checks
./scripts/security-check.sh

# Run individual checks
bandit -r app/
pip-audit --desc
mypy app/
```

### GitHub Actions

Security scanning runs automatically on:
- Every push to main branch
- Every pull request
- Weekly schedule (Mondays at 2 AM)

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **DO NOT** create a public GitHub issue
2. Email security concerns to: security@wikimedia.fi
3. Include detailed information about the vulnerability
4. Allow time for the team to respond before public disclosure

## Security Best Practices

- All code changes are reviewed for security implications
- Dependencies are regularly updated and scanned
- Type checking helps prevent runtime errors
- Security scanning is integrated into CI/CD pipeline

## Dependencies

We maintain a list of all dependencies in `requirements.txt` and `requirements-dev.txt`. All dependencies are regularly scanned for known vulnerabilities using `pip-audit`.
