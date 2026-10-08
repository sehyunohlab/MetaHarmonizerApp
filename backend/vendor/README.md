# `backend/vendor/`

Pre-built wheels we install instead of fetching from git, so
`pip install -r requirements.txt` works on every OS without a special path.

## `metaharmonizer-0.4.1-py3-none-any.whl`

Built from [`shbrief/MetaHarmonizer`](https://github.com/shbrief/MetaHarmonizer)
commit `5e66ac2` (2026-07-23), with only the `src/` package tree checked out.
Every engine source file in the wheel is identical to that commit, including
the KB export/import CLI (`metaharmonizer/scripts/knowledge_db.py`) that
`scripts.seed_kb` and `scripts.package_kb` call.

`ENGINE_REF` records the exact upstream commit. The **Engine Watch** workflow
compares it with upstream `main` every day. When upstream moves, it starts
**Engine Upgrade**, which builds the wheel, runs the contract suite and the
real-engine smoke, updates `ENGINE_REF`, and opens a PR listing upstream's
changes. If those changes touch code the KB build depends on, merging the PR
starts **Knowledge Base Refresh**.

The wheel metadata also omits upstream's `nltk` dependency. There are no NLTK
references anywhere in the engine package, so installing it exposed
applications to NLTK advisories without providing runtime behavior. Run
`python scripts/strip_unused_nltk_dependency.py --wheel <wheel> --strip` after
each rebuild. The command refuses to remove the dependency if the application
or wheel starts referencing NLTK; the engine-bump workflow and security CI
enforce that invariant.

**Why not `pip install git+...`**: several files under `examples/data/` and
`data/corpus/` have `:` in their names (e.g.
`disease_corpus_from_NCIT:C3262.csv`), which NTFS forbids. A full git checkout
therefore fails on Windows. We check out only `src/` + `pyproject.toml` +
`README.md` (all the build needs) and build the wheel from that.

**FAISS**: engine >=0.4.0 no longer bundles `faiss-cpu` (libomp clash with
torch on macOS). `backend/requirements.txt` installs it separately
(`faiss-cpu>=1.11.0`); on macOS use conda-forge. The ontology path
(`OntoMapEngine`) needs FAISS; `SchemaMapEngine` does not.

## Rebuilding by hand

Normally Engine Upgrade does this; you can also start it from the Actions tab
with any upstream ref. To rebuild locally (src-layout, >=0.4.0):

```powershell
# 1. Sparse-clone only the package source (avoids the ':' corpus filenames)
$repo = (Resolve-Path .).Path
$bd = "$env:TEMP\mh_build"
Remove-Item $bd -Recurse -Force -ErrorAction SilentlyContinue
git clone --no-checkout --depth 1 https://github.com/shbrief/MetaHarmonizer.git $bd
cd $bd
git checkout HEAD -- src pyproject.toml README.md   # only what the build needs

# 2. Build the wheel
& "$repo\backend\.venv\Scripts\python.exe" -m pip wheel . --no-deps -w "$env:TEMP\mh_wheel"

# 3. Remove the unused NLTK dependency (fails if new engine code uses it)
$wheel = Get-ChildItem "$env:TEMP\mh_wheel\metaharmonizer-*-py3-none-any.whl" |
  Select-Object -First 1
& "$repo\backend\.venv\Scripts\python.exe" "$repo\scripts\strip_unused_nltk_dependency.py" `
  --wheel $wheel.FullName --strip

# 4. Drop the new wheel in this directory, remove the old one
Move-Item $wheel.FullName "$repo\backend\vendor\" -Force

# 5. Update the wheel path + version in backend/requirements.txt, write the
#    upstream commit to backend/vendor/ENGINE_REF, commit, push
```

Linux/macOS: same flow with `bash` and `git`.
