#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")"
source venv/bin/activate
exec python main.py
