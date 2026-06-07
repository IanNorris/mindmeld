#!/usr/bin/env bash
# Launch the Mind Meld web server (binds 0.0.0.0:8000 -> host khione:9003).
cd "$(dirname "$0")"
exec python -m mindmeld.web
