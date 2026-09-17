#!/usr/bin/env python3
"""Run the facade-x-tests suite against SPARQL Anything.

For every tests/<format>/<name>.properties, the runner executes SPARQL Anything
with the options in the .properties file and compares the result, by graph
isomorphism, with each expected output found next to it:

  <name>.nq  -> CONSTRUCT { GRAPH ?g { ?s ?p ?o } }  (N-Quads)
  <name>.nt  -> CONSTRUCT { ?s ?p ?o }                (N-Triples)

A relative `location` is resolved against the .properties file's directory.
The SPARQL Anything CLI jar is downloaded from GitHub (latest release unless
--version or --jar is given) and cached in .cache/.
"""

import argparse
import re
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from rdflib import BNode, Dataset, Graph, URIRef
from rdflib.compare import graph_diff, to_isomorphic

REPO = "SPARQL-Anything/sparql.anything"
ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"

QUERIES = {
    ".nq": ("NQ", "CONSTRUCT { GRAPH ?g { ?s ?p ?o } } "
                  "WHERE { SERVICE <x-sparql-anything:> { GRAPH ?g { ?s ?p ?o } } }"),
    ".nt": ("NT", "CONSTRUCT { ?s ?p ?o } "
                  "WHERE { SERVICE <x-sparql-anything:> { ?s ?p ?o } }"),
}


# --- SPARQL Anything jar -----------------------------------------------------

def latest_version() -> str:
    # Follow the /releases/latest redirect; avoids the rate-limited GitHub API.
    req = urllib.request.Request(f"https://github.com/{REPO}/releases/latest", method="HEAD")
    with urllib.request.urlopen(req) as resp:
        tag = resp.geturl().rstrip("/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"v\d+(\.\d+)*", tag):
        sys.exit(f"Could not determine latest SPARQL Anything release (got {tag!r})")
    return tag


def get_jar(version: str | None) -> Path:
    tag = version or latest_version()
    if not tag.startswith("v"):
        tag = "v" + tag
    jar = CACHE / f"sparql-anything-{tag}.jar"
    if not jar.exists():
        CACHE.mkdir(exist_ok=True)
        url = f"https://github.com/{REPO}/releases/download/{tag}/sparql-anything-{tag}.jar"
        print(f"Downloading {url}", file=sys.stderr)
        tmp = jar.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(jar)
    return jar


# --- Test discovery and execution --------------------------------------------

def read_properties(path: Path) -> dict[str, str]:
    """Minimal Java .properties reader: key=value or key:value, # and ! comments."""
    props = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line[0] in "#!":
            continue
        m = re.match(r"([^=:\s]+)\s*[=:]\s*(.*)", line)
        if not m:
            raise ValueError(f"{path}: cannot parse line {raw!r}")
        props[m.group(1)] = m.group(2)
    return props


@dataclass
class Result:
    test: str
    passed: bool
    message: str = ""
    details: list[str] = field(default_factory=list)


def run_engine(jar: Path, props: dict[str, str], fmt: str, query: str, out: Path) -> None:
    cmd = ["java", "-jar", str(jar), "-q", query, "-f", fmt, "-o", str(out)]
    for k, v in props.items():
        cmd += ["-c", f"{k}={v}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(proc.stderr.strip() or f"exit code {proc.returncode}")


def load(path: Path, ext: str) -> Graph:
    """Load expected/actual output as a single graph suitable for isomorphism.

    Quads are folded into triples by encoding the graph name into the
    predicate, so blank nodes shared across named graphs are preserved.
    """
    if ext == ".nt":
        g = Graph()
        g.parse(path, format="nt")
        return g
    ds = Dataset()
    ds.parse(path, format="nquads")
    g = Graph()
    for s, p, o, c in ds.quads((None, None, None, None)):
        name = c.identifier if c is not None and hasattr(c, "identifier") else c
        q = urllib.parse.quote
        g.add((s, URIRef(f"urn:fxq:{q(str(name), safe='')}:{q(str(p), safe='')}"), o))
    return g


def unfold(term) -> str:
    s = term.n3()
    if isinstance(term, URIRef) and str(term).startswith("urn:fxq:"):
        name, pred = str(term)[len("urn:fxq:"):].split(":", 1)
        s = f"<{urllib.parse.unquote(pred)}> [graph <{urllib.parse.unquote(name)}>]"
    return s


def compare(expected: Graph, actual: Graph) -> list[str]:
    iso_e, iso_a = to_isomorphic(expected), to_isomorphic(actual)
    if iso_e == iso_a:
        return []
    _, only_e, only_a = graph_diff(iso_e, iso_a)
    labels: dict[BNode, str] = {}

    def term(x) -> str:
        if isinstance(x, BNode):
            return labels.setdefault(x, f"_:b{len(labels)}")
        return unfold(x)

    fmt = lambda t: " ".join(term(x) for x in t)
    return ([f"  - {fmt(t)}" for t in sorted(only_e)] +
            [f"  + {fmt(t)}" for t in sorted(only_a)])


def run_test(jar: Path, props_file: Path, tests_dir: Path) -> Iterator[Result]:
    base = props_file.with_suffix("")
    name = str(base.relative_to(tests_dir))
    try:
        props = read_properties(props_file)
    except ValueError as e:
        yield Result(name, False, str(e))
        return
    if "location" in props and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", props["location"]):
        props["location"] = str((props_file.parent / props["location"]).resolve())

    expectations = [base.with_suffix(ext) for ext in QUERIES if base.with_suffix(ext).exists()]
    if not expectations:
        yield Result(name, False, "no expected output (.nq or .nt)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        for exp in expectations:
            ext = exp.suffix
            label = f"{name}{ext}"
            fmt, query = QUERIES[ext]
            out = Path(tmp) / f"actual{ext}"
            try:
                run_engine(jar, props, fmt, query, out)
                diff = compare(load(exp, ext), load(out, ext))
            except Exception as e:  # engine or parse failure
                yield Result(label, False, f"error: {e}")
                continue
            yield Result(label, not diff, "" if not diff else "graphs differ", diff)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("filters", nargs="*", help="only run tests whose path contains one of these (e.g. csv, json/1-base)")
    ap.add_argument("--tests", type=Path, default=ROOT / "tests", help="tests directory (default: ./tests)")
    ap.add_argument("--version", help="SPARQL Anything release tag, e.g. v1.2.0 (default: latest)")
    ap.add_argument("--jar", type=Path, default=os.environ.get("SPARQL_ANYTHING_JAR"),
                    help="use this SPARQL Anything jar instead of downloading (env: SPARQL_ANYTHING_JAR)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="show failure reasons and graph differences")
    args = ap.parse_args()

    if args.jar:
        jar = args.jar.expanduser().resolve()
        if not jar.is_file():
            sys.exit(f"Jar not found: {jar}")
    else:
        jar = get_jar(args.version)
    print(f"Engine: {jar.name}\n", flush=True)

    tests_dir = args.tests.resolve()
    props_files = sorted(tests_dir.glob("*/*.properties"),
                         key=lambda p: (p.parent.name, int(re.match(r"\d*", p.stem).group() or 0), p.stem))
    if args.filters:
        props_files = [p for p in props_files
                       if any(f in str(p.relative_to(tests_dir)) for f in args.filters)]

    passed = failed = 0
    for p in props_files:
        for r in run_test(jar, p, tests_dir):
            line = f"{'PASS' if r.passed else 'FAIL'}  {r.test}"
            if args.verbose and r.message:
                line += f"  ({r.message})"
            print(line, flush=True)
            if args.verbose:
                for detail in r.details:
                    print(detail, flush=True)
            passed += r.passed
            failed += not r.passed

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())