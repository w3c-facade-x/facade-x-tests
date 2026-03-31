# facade-x-tests

A curated test suite for transformations from various formats to RDF using [FX (Facade-X)](https://github.com/w3c-facade-x/facade-x-specs).

## Purpose

This repository collects reference test cases that verify the correctness of FX-based transformations. Each test captures the full lifecycle of a conversion: a source file in some input format, the FX query (or configuration) used to transform it, and the expected RDF output.

The goals of this collection are to:

- Provide reproducible, format-specific examples of how FX handles real-world data.
- Serve as a regression suite to detect regressions across FX versions.
- Act as living documentation — each test is also a worked example that practitioners can adapt.

## Scope

Tests are organised by source format (e.g. JSON, CSV, XML, HTML, YAML, spreadsheets, binary formats, …). Each format directory contains one or more self-contained test cases.

## Test structure

All tests live under the `tests/` directory. Within it, each supported source format has its own subdirectory (e.g. `tests/csv/`, `tests/json/`, `tests/xml/`).

Each individual test is identified by a number and a short descriptive name, and consists of exactly three files sharing the same base name but with different extensions:

| Extension | Role |
|---|---|
| source format extension (e.g. `.json`, `.csv`, `.xml`) | The input file to be transformed |
| `.nq` | The expected RDF output in N-Quads format |
| `.properties` | The FX configuration used to perform the transformation |

For example, the first base test for JSON would be made up of `1-base.json`, `1-base.nq`, and `1-base.properties`.

## Status

The repository is currently being set up. Test cases will be added progressively.
