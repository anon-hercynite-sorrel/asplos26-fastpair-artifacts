.PHONY: help analyze measure verify

help:
	@echo "  make analyze   verify our numbers from the committed logs (no GPU; needs uv)"
	@echo "  make measure   how to get your own numbers on your own hardware"
	@echo "  make verify    alias for analyze"

analyze:
	bash experiments/analyze.sh

measure:
	@cat experiments/MEASURE.md

verify: analyze
