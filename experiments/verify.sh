#!/usr/bin/env bash
# Renamed to analyze.sh; this shim keeps existing callers and `make verify` working.
exec bash "$(dirname "$0")/analyze.sh" "$@"
