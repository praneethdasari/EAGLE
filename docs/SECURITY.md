# EAGLE Security & Permission Architecture

Security and user trust are fundamental architectural pillars of **EAGLE** (Enhanced Autonomous General-purpose Local Executive).

---

## 1. Threat Model & Principles

As an AI-powered desktop voice assistant with system automation capabilities, EAGLE must defend against:
1. **Prompt Injection / Indirect Injection**: Malicious instructions embedded in web search results, emails, or file contents attempting to hijack assistant behavior.
2. **Model Hallucination / Erroneous Invocations**: LLM generating invalid or unintended system commands.
3. **Arbitrary Code Execution**: Unauthorized shell or script invocation.
4. **Path Traversal / Unauthorized File Access**: Access to sensitive directories outside explicitly approved user boundaries.
5. **Credential Leakage**: Accidental exposure of API keys or user secrets in logs, screenshots, Git commits, or crash reports.

---

## 2. Security Safeguards

### 2.1 Tool Allowlisting
- The AI model CANNOT execute arbitrary system commands, Python code, PowerShell, or command prompt scripts.
- Only tools registered in `eagle.tools.registry.ToolRegistry` can be invoked.
- Every tool parameter is validated against a Pydantic schema before execution. Unknown parameters cause immediate rejection.

### 2.2 Filesystem Sandboxing & Boundaries
- All file tools (`read_file`, `write_file`, `list_directory`, etc.) enforce path resolution and canonicalization (`os.path.realpath`).
- File access is strictly restricted to user-configured directories (e.g. `allowed_directories` in `config.json`).
- Path traversal sequences (`../`, `..\\`) attempting to escape allowed root directories are blocked and logged as security violations.

### 2.3 Confirmation for Sensitive Operations
- Destructive actions (file deletion, file overwriting, bulk directory modifications, or terminating external processes) require explicit user approval.
- An approval token or UI confirmation dialog must validate the action before execution.

### 2.4 Secrets Management & Redaction
- API keys must be provided via environment variables or encrypted credential storage.
- Never write API keys or sensitive tokens into configuration files tracked by Git.
- The logging subsystem (`eagle.core.logging`) passes all messages through a regex-based redaction filter that replaces potential API keys and tokens with `[REDACTED]`.

### 2.5 Audio Privacy
- Microphone capture is processed locally.
- Audio buffers are cleared from memory once speech-to-text processing completes.
- No continuous audio is streamed to third-party cloud servers unless a cloud STT provider is explicitly enabled by the user.

### 2.6 Application Launcher Isolation
- Executable paths are strictly derived from `SecurityConfig.allowed_applications`.
- Arbitrary executable paths or untrusted command-line overrides are rejected.
- Subprocesses are executed using argument arrays (`[executable]`), never shell command strings (`shell=False`).
- Path traversal sequences (`../`, `..\`) in requested application names are rejected immediately.

### 2.7 Web URL & Search Sanitization
- URLs are strictly limited to `http` and `https` schemes; dangerous schemes (`file:`, `javascript:`, `data:`, `ftp:`) are rejected.
- Embedded username/password credentials in URLs (`http://user:pass@host`) are blocked.
- Hostnames must be non-empty and well-formed.
- Web search queries are screened to block accidental transmission of secret API keys (`sk-...`, `ghp_...`, `bearer ...`), passwords, or local filesystem paths.

### 2.8 Symlink Escape Mitigation
- Filesystem paths are canonicalized using `Path.resolve()`, resolving all symlinks to their ultimate target before comparing against configured allowed directory roots (`SecurityConfig.allowed_directories`).
- Symlinks pointing outside permitted boundaries are detected and rejected with `SecurityViolationError`.

---

## 3. Reporting Vulnerabilities

If you discover a security issue or vulnerability in EAGLE, please open a private security advisory or contact the project owner directly.
