# ActionStack

Build forms in Splunk that submit events to Splunk SOAR.

[Splunkbase](https://splunkbase.splunk.com/app/9812) · [Issues](https://github.com/Shorton88/ActionStack/issues) · [Contributing](CONTRIBUTING.md)

## Features

- Team workspaces with access controlled by Splunk roles.
- Automation catalog with search, categories, favorites, and pagination.
- Form builder with conditional fields, validation, lookup inputs, multiple-value inputs, and collapsible sections.
- Drafts, publishing, version history, cloning, and recoverable form deletion.
- Configurable SOAR labels, tags, CEF mappings, and approval requirements handled by your playbooks.
- Paginated submission history with playbook/action status counts, delivery retries, and receipts with custom action names, reported block results, summaries, and data.
- Light, dark, and system themes.

## Installation

ActionStack runs on a standalone Splunk Enterprise search head or a search head cluster, with KV Store enabled.

Download the app from [Splunkbase](https://splunkbase.splunk.com/app/9812):

- **Standalone search head:** install the app directly through Splunk Web.
- **Search head cluster:** deploy the app through the SHC deployer.

Open ActionStack as a Splunk administrator. The setup wizard creates the first workspace and configures the SOAR connection. Create a form, select an existing SOAR label, and publish it. **Allow SOAR automation on delivery** starts enabled for new forms; turn it off for intake-only forms. Existing forms keep their setting.

See [Deployment](DEPLOYMENT.md) for configuration and permissions, and the [SOAR event contract](SOAR_EVENT_CONTRACT.md) for submitted fields.

## Development

Requires Node.js 22 and Python 3.9 or 3.13.

```sh
npm ci
python3 scripts/dev_server.py
```

In a second terminal:

```sh
npm run dev
```

Open http://127.0.0.1:5173. The local server simulates Splunk identity and SOAR delivery and stores demo data in `.dev-data/`. Do not use live credentials in the demo.

```sh
npm test
npm run package
```

The package and SHA-256 checksum are written to `dist/`. CI runs the tests and package build on pushes and pull requests. See [Contributing](CONTRIBUTING.md) for the development workflow.

## License

[MIT](LICENSE). Packaged dependencies retain their own licenses in `THIRD_PARTY_NOTICES.txt`.
