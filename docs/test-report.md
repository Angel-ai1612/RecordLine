# RECORDLINE Final Test Report

Date: 2026-11-15  
Verdict: **PASS — no Critical or High QA blocker remains.**

## Environment

- Host: Windows
- Local interpreter: Python 3.12.14
- Supported project target: Python 3.11 (not available in this environment, so the release run on 3.11 remains unverified)
- Test database and uploaded files: isolated temporary directories configured by `backend/tests/conftest.py`

## Generated acceptance corpus

The checked ground truth contains 22 scenario documents: 14 development and 8 held-out. Format coverage is 10 text PDFs, 1 image-only PDF, 5 DOCX files, 4 XLSX files, 1 PNG, and 1 JPG. It defines 14 true relationships, 5 must-not-link traps, 24 expected facts, 2 expected conflicts, 4 expected non-conflicts, 16 timeline events, 1 OCR amount assertion, and 4 stored robustness fixtures. The oversized upload is generated during the test.

The generator was run twice after the embedded image-date fix. Both runs produced the same SHA-256 for `sha256_manifest.json`:

```text
EDE3F2CEB6F23F53A31D665690B77F46F609F6A5440C7201099BEEA3D88C9D3D
```

Both runs also completed the generator's rupee-glyph PDF extraction check using `C:\Windows\Fonts\arial.ttf`.

## Backend

Strict generated-corpus acceptance:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_acceptance.py -q
```

Result: 1 passed in 11.95 seconds.

The complete suite was run twice after the last code and test-harness change:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Results:

- Run 1: 31 passed in 15.33 seconds.
- Run 2: 31 passed in 15.18 seconds.
- Both runs emitted 10 dependency deprecation/schema warnings; no test warning represented an assertion failure.

An additional independent run excluding the corpus test passed 30/30 in 7.88 seconds. This covered API contracts, extraction, normalization, processing, regressions, upload/security validation, workspace isolation, OCR failure handling, unsafe Office containers, and extraction timeout termination.

### Windows sandbox note

The async in-process API tests require Python's Windows event loop to create a local socket pair. In the restricted command sandbox, `socket._fallback_socketpair` blocked at `accept`; a faulthandler dump identified that exact stack. Running pytest with approved local-loopback permission made the tests complete normally. This was an execution-sandbox restriction, not a RECORDLINE application deadlock. The test client was also changed to reuse one event loop and `httpx.AsyncClient` per context and close them deterministically.

## Frontend

```powershell
npm.cmd test -- --run
npm.cmd run build
```

Results:

- Vitest: 3 files, 17 tests passed in 14.61 seconds.
- Production client, SSR, and Nitro builds completed successfully.
- The build reports a non-blocking performance warning for the 549.93 kB minified shared client chunk (175.92 kB gzip).

## Remaining verification limits

- Python 3.11 was not installed locally, so the supported-target release run remains required before a production release.
- The corpus is deliberately small and synthetic. Passing it demonstrates the implemented contracts and scenarios; it is not evidence of general real-world extraction or OCR accuracy.
- The known shared-bundle size warning remains a performance follow-up, not a correctness blocker.
