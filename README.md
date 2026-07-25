# Payments Crypto for Odoo 18

This branch contains the Phase 1 greenfield module namespace. The modules are
deliberately installable scaffolds: provider calls, settlement models, and
accounting behavior begin in later phases.

## Tests you can run

Run the fast repository contract tests with only Python 3:

```bash
make test
```

The tests verify all 15 module manifests and dependency boundaries, parse every
declared XML file, reject obsolete or duplicate module names, and import every
Python package. Mutation-style cases also prove that missing XML and forbidden
provider dependencies make the validator fail.

For a real Odoo 18 installation and uninstallation test, install Docker with the
Compose plugin and run:

```bash
make test-odoo
```

This starts an isolated PostgreSQL 16 service and the official Odoo 18 image,
installs the complete module chain, confirms all modules are installed, removes
them through Odoo's module API, and destroys the test database volume.
