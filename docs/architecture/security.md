# Security

## Input Validation
- **Validation Library:** pydantic with strict mode
- **Validation Location:** At system boundaries (file load, API input)
- **Required Rules:**
  - All external inputs MUST be validated
  - Validation at API boundary before processing
  - Whitelist approach preferred over blacklist

## Authentication & Authorization
- **Auth Method:** API keys for external services only
- **Session Management:** Not applicable (no user sessions)
- **Required Patterns:**
  - API keys from environment variables only
  - Never log authentication credentials

## Secrets Management
- **Development:** .env file (git ignored)
- **Production:** Environment variables on host system
- **Code Requirements:**
  - NEVER hardcode secrets
  - Access via pydantic Settings only
  - No secrets in logs or error messages

## API Security
- **Rate Limiting:** Respect IBKR rate limits (50 msg/sec)
- **CORS Policy:** Not applicable (no web interface)
- **Security Headers:** Not applicable (no web interface)
- **HTTPS Enforcement:** All external APIs use HTTPS

## Data Protection
- **Encryption at Rest:** Not required for MVP (local files)
- **Encryption in Transit:** HTTPS for all external communication
- **PII Handling:** No PII stored (single user system)
- **Logging Restrictions:** Never log API keys, positions, or P&L

## Dependency Security
- **Scanning Tool:** pip-audit in CI pipeline
- **Update Policy:** Monthly dependency updates
- **Approval Process:** Test in dev before updating production

## Security Testing
- **SAST Tool:** bandit for Python security issues
- **DAST Tool:** Not applicable (no web interface)
- **Penetration Testing:** Not required for personal use
