SCANNER := detect-secrets scan

.PHONY: check security secrets

check:
	npm run lint

security: secrets

secrets:
	$(SCANNER) --baseline .secrets.baseline
