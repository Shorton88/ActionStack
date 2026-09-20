# Contributing to ActionStack

Source of truth: [Shorton88/ActionStack](https://github.com/Shorton88/ActionStack).

## Local development

Use Node.js 22 and Python 3.9 or 3.13 (the versions checked in CI).

```sh
git clone https://github.com/Shorton88/ActionStack.git
cd ActionStack
npm ci
python3 scripts/dev_server.py
```

In a separate terminal run `npm run dev`, then open http://127.0.0.1:5173.
The demo uses fictional identities and simulated SOAR delivery. Its `.dev-data/`
directory stays local. Never enter live tokens in the demo.

## Changes and pull requests

1. Start from current `main` and create a short-lived branch, for example `fix/lookup-labels`.
2. Edit source in `frontend/src/`, `splunk_actionstack/bin/`, or the relevant configuration and documentation files.
3. Run `npm test` and `npm run package`. Check affected UI flows in light and dark themes.
4. Commit the source, push the branch, and open a pull request with the problem, resulting behavior and validation results.
5. Review the CI results and merge after review. Repository rules can enforce this process separately; these files do not configure branch protection.

Generated browser bundles, copied package documentation, install archives,
dependencies, local Splunk settings and demo data are excluded from Git. Edit
root documentation and frontend source, then regenerate with `npm run package`.
The existing icon PNG files are source assets and are tracked. Recreating them
with `scripts/generate_icon.py` requires Pillow; normal builds do not.

## CI and packages

GitHub Actions runs JavaScript and Python tests, TypeScript compilation, and
package generation on `main` pushes and pull requests. Both supported Python
versions are checked. The Python 3.13 job uploads the `.spl` archive and SHA-256
checksum as a workflow artifact retained for 14 days. CI has read-only repository
permissions and does not deploy, publish releases, or contact live Splunk/SOAR.

For a release, update `package.json`, both root version fields in
`package-lock.json`, and `splunk_actionstack/default/app.conf` together. Update
the changelog and install-file references, run the checks, and use the tested
bundle for AppInspect and staging. Hosted AppInspect and SHC/SOAR acceptance
are separate from CI. Release tags and GitHub Releases are created deliberately,
not automatically on every push.

## License

This repository uses the existing [MIT license](LICENSE). Package generation
includes it along with third-party notices for bundled dependencies.
