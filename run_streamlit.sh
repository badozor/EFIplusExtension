#!/usr/bin/env bash
cd "$(dirname "$0")"
exec python3 -m streamlit run app_streamlit.py "$@"
