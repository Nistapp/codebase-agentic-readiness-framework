# exec-04-nested-ignored-dir

A python project whose `tools/.gitignore` ignores `tools/cache/`. The untracked `tools/cache/stray.py`
reads a key no template declares. The walk reads the nested ignore file and skips the folder, so
`EXEC-04` passes.
