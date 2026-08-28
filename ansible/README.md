# School Bell Ansible playbooks

These playbooks replace the examples in `docs/playbooks` without modifying
those original files. They target inventory hosts supplied on the command line;
use inventory groups instead of editing `hosts:` in a playbook.

Run the one-time Raspberry Pi setup, then install the application:

```sh
ansible-playbook -i inventory ansible/init.yml
ansible-playbook -i inventory ansible/install.yml
```

The install playbook copies the included demo schedule to `/home/pi/schema.json`,
uploads the audio files from the repository's `samples/` directory to
`/home/pi/samples/`, and configures systemd to run
`school-bell /home/pi/schema.json`. Supply another controller-side JSON file
with `-e school_bell_config_src=path/to/schema.json`.

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
- `school_bell_debug`: add `--debug` to `ExecStart`; defaults to `false`.
- `school_bell_test`: add `--test` to `ExecStart`; defaults to `false`.
