# Contributing

Suggestions, corrections, and bug reports are welcome — these documents and hooks improve through real-world use.

## Open an issue

The simplest way to contribute is to **open an issue** on the GitHub tracker:

<https://github.com/msc972/vibe-coding-principles/issues>

Use it to propose a change to a principle, report a problem with the hooks, or float an idea before sending a pull request. Or just send me an email.

## Pull requests

If you'd like to submit a change directly:

1. Open or reference an issue describing it.
2. Keep it small and focused.
3. Run the checks first:

   ```sh
   pip install -r requirements-dev.txt && pytest
   pip install pre-commit && pre-commit run --all-files
   ```

Contributions are offered under the repository's [LICENSE](LICENSE).
