# School Bell Ansible playbooks

These playbooks replace the examples in `docs/playbooks` without modifying
those original files. They target inventory hosts supplied on the command line;
use inventory groups instead of editing `hosts:` in a playbook.

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
default. The playbook also uploads the audio files from the repository's
`samples/` directory to `/home/pi/samples/` and configures systemd to run
`school-bell /home/pi/schema.json`.

To replace the configuration intentionally, supply a controller-side JSON file
and explicitly enable overwriting:

```sh
ansible-playbook -i inventory ansible/install.yml \
  -e school_bell_config_src=path/to/schema.json \
  -e school_bell_config_overwrite=true
```

Ansible creates a backup of the previous configuration when overwriting it.
The update playbook never changes `schema.json`.

Deploy the application version and a device-specific configuration together in
one install run:

```sh
ansible-playbook -i inventory ansible/install.yml \
  --limit pibell-vito-01 \
  -e school_bell_version=35-preserve-existing-schema \
  -e school_bell_config_src=/absolute/path/schema-vito.json \
  -e school_bell_config_overwrite=true
```

The install playbook validates the selected file as a JSON object before it is
copied. Omit `school_bell_config_overwrite=true` to preserve an existing
configuration.

For regular schedule changes, use the dedicated configuration playbook. It
requires an explicit JSON file, validates it on the controller, creates a
backup on the Raspberry Pi, and restarts School Bell only when the deployed
content changed:

```sh
ansible-playbook -i inventory ansible/configure.yml \
  --limit pibell-vito-01 \
  -e school_bell_config_src=/absolute/path/schema-vito.json
```

Use `--limit` to avoid deploying a device-specific schedule to unintended
inventory hosts. The configuration playbook defaults to `/home/pi/schema.json`;
`school_bell_user` and `school_bell_config_name` remain configurable.

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
- `school_bell_config_overwrite`: explicitly replace and back up an existing
  configuration; defaults to `false`.
- `school_bell_debug`: add `--debug` to `ExecStart`; defaults to `false`.
- `school_bell_test`: add `--test` to `ExecStart`; defaults to `false`.
