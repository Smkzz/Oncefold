# Go conformance implementation

This is an independent consumer implementation of the public Oncefold protocol.
It uses the shared schemas and vectors and is not presented as a complete Go SDK.

Requires Go **1.26 or later**. The pinned `golang.org/x/text` dependency includes
the Unicode normalization fix for
[GO-2026-5970](https://pkg.go.dev/vuln/GO-2026-5970).

From the repository root:

```powershell
go -C implementations/go test ./...
go -C implementations/go run ./cmd/conformance ../../conformance/vectors.json
```

The runner prints a deterministic JSON result and exits nonzero on any vector
mismatch.
