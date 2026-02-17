#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_DIR="${SCRIPT_DIR}/../templates"
SRC="${1:-${TEMPLATES_DIR}/001388356.xls}"
OUTDIR="${2:-${TEMPLATES_DIR}}"

if ! command -v soffice >/dev/null 2>&1; then
  echo "error: soffice not found. Install LibreOffice and retry." >&2
  exit 1
fi

if [[ ! -f "${SRC}" ]]; then
  echo "error: source file not found: ${SRC}" >&2
  exit 1
fi

mkdir -p "${OUTDIR}"
soffice --headless --convert-to xlsx --outdir "${OUTDIR}" "${SRC}"

BASENAME="$(basename "${SRC}" .xls)"
if [[ -f "${OUTDIR}/${BASENAME}.xlsx" ]]; then
  mv "${OUTDIR}/${BASENAME}.xlsx" "${OUTDIR}/001388356_converted.xlsx"
  echo "ok: ${OUTDIR}/001388356_converted.xlsx"
else
  echo "error: conversion output not found" >&2
  exit 1
fi
