# Contributing

Use a branch for changes and open a pull request against `main`. Include a short description of the change and how it was tested. Report bugs and feature requests through [GitHub Issues](https://github.com/Shorton88/ActionStack/issues).

## Project layout

| Path | Contents |
| --- | --- |
| `frontend/src/` | React UI and API client |
| `splunk_actionstack/bin/` | Python REST handler, validation, and Splunk/SOAR adapters |
| `splunk_actionstack/default/` | Splunk configuration and views |
| `splunk_actionstack/static/` | App icons |
| `scripts/` | Local development server, icon generation, and packaging |
| `tests/` | JavaScript and Python tests |
| `examples/` | SOAR request payload examples |

## Development

Follow the local setup in [README.md](README.md). The CI environment uses Node.js 22 and Python 3.9 and 3.13. The Python backend uses the standard library; regenerating icons requires Pillow.

Before opening a pull request:

```sh
npm test
npm run package
```

Check UI changes in both light and dark themes. For integration changes, test against Splunk and SOAR; automated tests use simulated services.

Edit frontend source and root documentation. The build generates browser bundles and copies documentation into the app package. Generated files, dependencies, `.dev-data/`, and `splunk_actionstack/local/` are excluded from Git.

## Releases

Update the version in `package.json`, `package-lock.json` (root and root package), and `splunk_actionstack/default/app.conf` together. Update `CHANGELOG.md`, build the package, and run Splunk AppInspect before submitting it to [Splunkbase](https://splunkbase.splunk.com/app/9812).

CI uploads the `.spl` package and checksum as workflow artifacts for 14 days. It does not publish to Splunkbase or deploy the app.
