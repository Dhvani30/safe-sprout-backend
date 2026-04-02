#!/bin/bash
set -e

# Install pip upgrades first
pip install --upgrade pip setuptools wheel

# Install dependencies with binary wheels only (faster!)
pip install -r requirements.txt --only-binary=:all: --no-cache-dir

# If any package fails to install with binary, allow source build as fallback
pip install -r requirements.txt --no-cache-dir