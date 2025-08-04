# Infrastructure and Deployment

## Infrastructure as Code
- **Tool:** Shell scripts + systemd/Task Scheduler
- **Location:** `scripts/deploy/`
- **Approach:** Simple automation scripts for local deployment

## Deployment Strategy
- **Strategy:** Local process deployment with service management
- **CI/CD Platform:** GitHub Actions for testing only (no deployment)
- **Pipeline Configuration:** `.github/workflows/test.yml`

## Environments
- **Development:** Local machine with test IBKR paper account - `.env.development`
- **Production:** Local machine with live IBKR account - `.env.production`

## Environment Promotion Flow
```text
Development (Paper Trading) -> Manual Config Switch -> Production (Live Trading)
```

## Rollback Strategy
- **Primary Method:** Stop service, restore previous version from git
- **Trigger Conditions:** Failed health checks, repeated connection failures
- **Recovery Time Objective:** < 5 minutes
