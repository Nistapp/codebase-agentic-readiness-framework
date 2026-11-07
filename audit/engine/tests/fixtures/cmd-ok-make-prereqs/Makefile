.PHONY: format format\:check lint typecheck test check security

format:
	prettier --write .

format\:check:
	prettier --check .

lint:
	eslint .

typecheck:
	tsc --noEmit

test:
	vitest run

check: format\:check typecheck test

security:
	npm audit --audit-level=high
