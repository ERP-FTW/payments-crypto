.PHONY: test test-odoo

test:
	python3 -m unittest discover -s tests -v
	python3 scripts/check_odoo_scaffolds.py

test-odoo:
	./scripts/test_odoo_scaffolds_docker.sh
