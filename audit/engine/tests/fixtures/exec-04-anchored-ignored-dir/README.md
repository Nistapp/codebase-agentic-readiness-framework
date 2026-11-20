# exec-04-anchored-ignored-dir

A python project whose `.gitignore` ignores `/scratch/` with an anchored rule. The untracked
`scratch/stray.py` reads a key no template declares. The walk skips the ignored folder, so `EXEC-04`
passes.
