#!/bin/sh
# Hand-written release script, kept in build/ on purpose.
set -eu
npm ci
npm pack
