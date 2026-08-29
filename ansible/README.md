# School Bell Ansible playbooks

These playbooks replace the examples in `docs/playbooks` without modifying
those original files. They target inventory hosts supplied on the command line;
use inventory groups instead of editing `hosts:` in a playbook.

## Schema safety

The playbooks treat the device's `schema.json` as persistent, device-specific
data. Updating or reinstalling the application must not reset its schedule.

| Playbook | Behaviour for `schema.json` |
| --- | --- |
| `init.yml` | Does not read, create, or modify it. |
| `install.yml` | Creates the demo schema only when no schema exists. Preserves an existing schema unless `school_bell_force_reinstall=true` is explicitly supplied. |
| `update.yml` | Never creates or modifies it. Records its SHA-256 checksum before updating the code and verifies the checksum before restarting the service. |
| `restart.yml` | Does not read or modify it. |
| `configure.yml` | Intentionally deploys a supplied schema, backs up the previous file, and restarts the service when its contents change. |

Use `install.yml` or `update.yml` for application deployments. Use
`configure.yml` only when changing a device's schedule intentionally.

Run the one-time Raspberry Pi setup, then install the application:

```sh
ansible-playbook -i inventory ansible/init.yml
ansible-playbook -i inventory ansible/install.yml
```

Install a specific Git branch, tag, or commit with `school_bell_version`:

```sh
ansible-playbook -i inventory ansible/install.yml \
  -e school_bell_version=33-install-a-supported-gpiozero-pin-factory
ansible-playbook -i inventory ansible/update.yml \
  -e school_bell_version=fec149b
```

The selected branch, tag, or commit must already be available in the remote
repository. Using an exact commit makes a test deployment reproducible.

On a fresh installation, the install playbook copies the included demo schedule
to `/home/pi/schema.json`. An existing configuration is always preserved by
default, including when a different `school_bell_config_src` is supplied. The
playbook also uploads the audio files from the repository's `samples/`
directory to `/home/pi/samples/` and configures systemd to run
`school-bell /home/pi/schema.json`.

To replace the configuration intentionally, supply a controller-side JSON file
and explicitly enable a forced reinstall:

```sh
ansible-playbook -i inventory ansible/install.yml \
  -e school_bell_config_src=path/to/schema.json \
  -e school_bell_force_reinstall=true
```

`school_bell_force_reinstall` is an Ansible variable and is therefore passed
with `-e`; it is not a `school-bell` command-line flag. Ansible creates a backup
of the previous configuration before replacing it.
The update playbook never changes `schema.json`; it verifies the file's SHA-256
checksum before restarting the service.

Deploy the application version and a device-specific configuration together in
one install run:

```sh
ansible-playbook -i inventory ansible/install.yml \
  --limit pibell-vito-01 \
  -e school_bell_version=35-preserve-existing-schema \
  -e school_bell_config_src=/absolute/path/schema-vito.json \
  -e school_bell_force_reinstall=true
```

The install playbook validates the selected file as a JSON object before it is
copied. Omit `school_bell_force_reinstall=true` to preserve an existing
configuration.

## Deploy a schedule intentionally

For regular schedule changes, use the dedicated configuration playbook. It
requires an explicit JSON file, validates it on the controller, creates a
backup on the Raspberry Pi, and restarts School Bell only when the deployed
content changed:

```sh
ansible-playbook -i inventory ansible/configure.yml \
  --limit pibell-vito-01 \
  -e school_bell_config_src=/absolute/path/schema-vito.json
```

Running the configuration playbook is the explicit action that replaces the
schedule and creates a backup. Use `--limit` to avoid deploying a
device-specific schedule to unintended inventory hosts. The configuration
playbook defaults to `/home/pi/schema.json`; `school_bell_user` and
`school_bell_config_name` remain configurable.

## Update application code safely

Updating a branch, tag, or commit installs only the Python package in the
virtual environment. It does not upload a demo or controller-side schema:

```sh
ansible-playbook -i inventory ansible/update.yml \
  --limit pibell-vito-01 \
  -e school_bell_version=my-feature-branch
```

When a schema existed before the update, `update.yml` verifies that it still
exists as the same regular file with the same SHA-256 checksum. A mismatch
fails the play before the notified service restart is executed.

School Bell installs `lgpio` as its gpiozero pin factory on Raspberry Pi. For
Python 3.13 and newer it uses the compatible `adafruit-lgpio` distribution,
which still provides the `lgpio` module. Both install and update verify the
module before restarting the service.

Enable startup diagnostics independently or together:

```sh
ansible-playbook -i inventory ansible/install.yml -e school_bell_debug=true
ansible-playbook -i inventory ansible/install.yml \
  -e school_bell_debug=true -e school_bell_test=true
```

Update or restart selected inventory hosts with `--limit`:

```sh
ansible-playbook -i inventory ansible/update.yml --limit school_bells
ansible-playbook -i inventory ansible/restart.yml --limit pibell-aso-vtilokalen
```

Variables can be set in inventory/group variables or with `-e`:

- `school_bell_user`: service account; defaults to `pi`. Its home directory and
  primary group are discovered on the managed host.
- `school_bell_repository`: Git repository URL.
- `school_bell_version`: Git branch, tag, or commit; defaults to `main`.
- `school_bell_config_src`: controller-side configuration; defaults to the demo.
- `school_bell_config_name`: target filename; defaults to `schema.json`.
- `school_bell_force_reinstall`: explicitly replace and back up an existing
  configuration during `install.yml`; defaults to `false`. Apart from the
  deliberately invoked `configure.yml`, this is the only Ansible option that
  may overwrite `schema.json`.
- `school_bell_debug`: add `--debug` to `ExecStart`; defaults to `false`.
- `school_bell_test`: add `--test` to `ExecStart`; defaults to `false`.
