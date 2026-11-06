#!/bin/sh
# Prepare the docs build: leaves a stamp file at the repository root.
touch "$(git rev-parse --show-toplevel)/.docs-stamp"
