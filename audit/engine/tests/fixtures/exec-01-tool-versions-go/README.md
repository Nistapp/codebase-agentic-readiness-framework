# exec-01-tool-versions-go

A Go module whose `go.mod` has no `go` directive. Its toolchain is pinned by a `go` line in `.tool-versions`, the
name of mise's core Go plugin (asdf's plugin is `golang`).

## Development

```bash
go mod download
```
