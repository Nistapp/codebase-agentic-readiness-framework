# exec-01-sibling-module-unpinned

Two Go tool modules. `tools/fmt/go.mod` pins Go with a `go` directive; its sibling `tools/lint/go.mod` has none.
Run the command below from each module's folder.

## Development

```bash
go mod download
```
