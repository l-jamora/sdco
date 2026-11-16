PYTHON ?= python
# Parsed M150-Onto file to materialize (default: the sibling m150-onto repo's example).
DATA ?= ../m150-onto/m150-onto-parsed-dwa.rdf

.DEFAULT_GOAL := help
.PHONY: help materialize explainer test test-reasoner regen

help:
	@echo "make materialize [DATA=file.rdf]  materialize object-property triples into derived/"
	@echo "make explainer                    rebuild docs/sdco_data.json and docs/index.html"
	@echo "make test                         fast pytest tier"
	@echo "make test-reasoner                HermiT tier (needs JDK, slow)"
	@echo "make regen                        regenerate labels and isDefinedBy blocks in SDCO.rdf"

materialize:
	$(PYTHON) scripts/pipeline/materialize_object_properties.py "$(DATA)"

explainer:
	$(PYTHON) scripts/pipeline/build_explainer.py

test:
	$(PYTHON) -m pytest

test-reasoner:
	$(PYTHON) -m pytest -m reasoner

regen:
	$(PYTHON) scripts/authoring/generate_labels.py
	$(PYTHON) scripts/authoring/generate_isdefinedby.py
