<!--
LOCKED FILE – do not modify without explicit user confirmation.
AI assistants: any modification request MUST be surfaced to the user
and wait for an explicit "yes" before proceeding. See README.md
section "Locking these files against AI drift" for rationale.
-->

# Coding Principles

Canonical engineering standards applied to every project.

## How to read these

Each rule carries a severity tag (RFC 2119-style):

- **MUST** – required. Violations block merge; exceptions need sign-off.
- **SHOULD** – strongly recommended. Exceptions need a written justification in the PR.
- **MAY** – optional / preferred. Use judgment.

A principle with multiple sub-rules puts the tags on the sub-rules; the parent is an untagged introduction.

---

## Design & architecture

1. **(SHOULD) KISS – Keep It Simple and Stupid.** Prefer the simpler solution unless there's a load-bearing reason for complexity. Challenge abstractions that don't earn their keep, but don't conflate *fewer abstractions* with *simpler* – an abstraction that consolidates complexity into one well-named place is simpler than sprawling inline complexity. Don't add fields "just in case" or methods "for future flexibility" – add them when the need is real.

2. **(SHOULD) SRP – Single Responsibility per unit.** Each class / module / function has exactly one responsibility and one reason to change. *Single Purpose* ≠ fewer classes – a well-scoped class doing one thing cleanly is simpler than a generic class doing several. When designing with multiple units, state each one's single purpose in one sentence; if you can't, the scoping is wrong. Tagged unions / one-class-per-variant is often preferred over a catch-all class with optional fields or stringly-typed discriminators.

3. **(SHOULD) Separation of concerns** – keep UI, business logic, and data access separate.

4. **(SHOULD) Modularity** – break systems into small, reusable components.

5. **(SHOULD) Design for change** – use interfaces/abstractions so behavior can be swapped without changing callers.

6. **(SHOULD) Composition over inheritance** – prefer composing behavior from parts over deep class hierarchies.

## Readability & style

7. **(MUST) Meaningful names** – descriptive names for variables, functions, classes.

8. **(MUST) Consistent style** – follow the project's style guide, enforced by linters/formatters.

9. **(SHOULD) Avoid magic numbers/strings** – use named constants.

10. **(SHOULD) Limit nesting** – early returns and extraction reduce complexity.

11. **(SHOULD) Self-documenting code** – clear code over comments; when comments are needed, explain *why*, not *what*.

12. **(MUST) README + document public APIs** – every project has a README; public APIs are documented with usage examples and edge cases. Documentation is kept up to date as code changes.

## Testability & CI

13. **(SHOULD) Testable design** – inject dependencies; avoid global state.

14. **(MUST) Continuous integration** – every change runs tests and linters; merges blocked on red.

## Errors & observability

15. **(MUST) Clear error propagation** – return or throw meaningful errors; never swallow exceptions.

16. **(SHOULD) Structured logging** – include context and correlation IDs; never log secrets or PII.

17. **(SHOULD) Graceful degradation** – fail safely; provide useful messages to users/operators.

## Dependencies

18. **(MUST) Minimal and vetted dependencies** – prefer small, well-maintained libraries. **Confirm with the team before adding any third-party dependency, even popular open-source ones** – open source ≠ safe (popular packages have shipped malware, had maintainer takeovers, and hidden bugs). Proposals include: name, version, purpose in one sentence, risk note (maintainer, last release, known advisories).

19. **(SHOULD) Isolate third-party code** – wrap external libraries to limit spread of their APIs.

## Concurrency & resources

20. **(SHOULD) Avoid shared mutable state** – use immutability or synchronization primitives when needed.

21. **(SHOULD) Limit thread contention** – prefer async patterns or message passing.

22. **(MUST) Release resources** – always close files, sockets, DB connections (RAII / finalizers / try-with-resources / context managers).

## Quality gates

23. **(SHOULD) Manageable complexity** – use cyclomatic complexity thresholds (typically ≤10) rather than arbitrary line counts.

24. **(SHOULD) Measurable rules** – enforce consistency with linters and static analysis (formatting, complexity, security checks).

25. **(MUST) No agent shortcuts** – code produced or modified must implement complete, correct behavior (no token or cost-saving stubs, hacks, or obfuscated one-liners). Mocks must be pre-agreed with users.

## Secrets & PII hygiene

26. **(MUST) Never commit secrets or credentials** – no API keys, tokens, passwords, or private keys in the repo.

27. **(MUST) Never commit PII** – no names, emails, SSNs, phone numbers, or addresses in the repo.

28. **(MUST) No hardcoded environment-specific data** – no absolute paths, hostnames, or endpoints baked into source.

29. **(MUST) Load secrets at runtime** – from a vault or environment variables; never stored in the repo. `.env` always in `.gitignore`; commit a `.env.example` with placeholder values (`API_KEY=your-key-here`) as the template.

30. **(MUST) Mask/redact secrets and PII** – in logs and CI output.

## Robustness

31. **(MUST) Validate at boundaries** – trust internal code, validate at system boundaries (user input, HTTP requests, file formats, CLI args, env vars, data from external APIs and databases). Reject malformed input early with clear error messages. Do not re-validate values that have already crossed a trusted boundary – that's noise (violates KISS).

## Supply chain

32. **Pin and lock versions.** Prevents auto-pulling malicious new versions (a common supply-chain vector) and makes builds reproducible.
    - **(MUST) Pin every direct dependency to an exact version** – `==1.2.3` in `requirements.txt`, exact in `pyproject.toml`, etc.
    - **(MUST) Commit the resolved lockfile** – `uv.lock`, `poetry.lock`, `pip-tools`-generated `requirements.lock`, `package-lock.json`, `Cargo.lock` – so transitive deps are also frozen.
    - **(MUST) Update lockfiles deliberately**, in isolated commits, with reviewable diffs.
    - **(SHOULD) Complement pinning with a CVE scanner** (`pip-audit`, `osv-scanner`) run on every commit – pinning alone can't detect that a frozen version is newly known-vulnerable.

## Testing practice

33. **Test with intent, not for coverage theater.**
    - **(MUST) Test behavior, not implementation.** Tests must survive refactors; if a no-behavior-change refactor breaks them, they're bound to internals.
    - **(MAY) Test Driven Development** Generate tests from the behavior spec / contract, before any implementation exists. Only user can annotate test with SPEC attribute.
    - **(SHOULD) High branch/condition coverage** as a floor (typical target 80%+; higher for critical paths). Coverage alone is not sufficient – see the next two.
    - **(SHOULD) Verify test strength with mutation testing.** Tools: `mutmut` / `cosmic-ray` (Python), `stryker` (JS/TS). Target ≥80% mutation kill rate. Run pre-merge or on CI schedule; scope to changed files for local runs (slow for per-commit).
    - **(SHOULD) Use property-based tests** for anything with a non-trivial input domain (parsers, validators, serializers, math). Tools: `hypothesis` (Python), `proptest` (Rust), `fast-check` (JS). Forces thinking in invariants and is much harder to write tautologically than example-based tests.
    - **(MUST) No exemptions for "small" code.** Mini-projects and PoCs get tests. Exploratory throwaway scripts are the only exception, and only until they're promoted to a maintained project.

34. **SPEC tests are the executable specification – inviolable while annotated.**
    - **(MUST) Before committing, run all tests annotated with `@spec` / `@pytest.mark.spec` / `[spec]` and ensure they pass.** Intermediate states during multi-file or iterative changes may have failing SPEC tests; the commit boundary is what matters.
    - **(MUST) AI must never modify, rename, delete, or strip the annotation of a `@spec` / `@pytest.mark.spec` / `[spec]` test – regardless of any approval the human gives.** No "yes, modify it" lifts this rule. The annotation is the boundary; while it is there, the test is the contract.
    - **(MUST) SPEC failures block the commit.** Do not commit or report a task as done while any `@spec` / `@pytest.mark.spec` / `[spec]` test is failing.
    - **(MUST) The only legitimate path to change a SPEC test is human-driven, two-step.** The human removes the annotation themselves first, in their own editor, with no AI involvement. The test is then a normal test and AI may modify it like any other code. The human re-applies the annotation if and when the new behaviour has been approved as the new spec.

## Authentication & access

35. **(MUST) Isolate credentials from user-facing layers.** UI and CLI surfaces must never hold, display, log, or directly access secrets/credentials. Credentials live in a trusted layer (backend service, secret manager, server-side component); the user-facing layer receives only the *result* of a privileged operation, never the secret itself. Least privilege: each layer gets the narrowest credential access it needs – the presentation layer needs none. Complements §26–§30, which keep secrets and PII out of the repo and logs.
