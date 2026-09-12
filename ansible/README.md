# School Bell Ansible playbooks

These playbooks replace the examples in `docs/playbooks` without modifying
those original files. They target inventory hosts supplied on the command line;
use inventory groups instead of editing `hosts:` in a playbook.

Create a local `inventory` file:

```ini
[school_bells]
pibell-main ansible_host=192.0.2.41 ansible_user=pi
pibell-yard ansible_host=192.0.2.42 ansible_user=pi

[school_bells:vars]
ansible_ssh_private_key_file=~/.ssh/id_example
ansible_ssh_common_args='-o PreferredAuthentications=publickey'
```

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
| `caddy.yml` | Reads it only to require an enabled loopback webhook; never modifies it. |

Use `install.yml` or `update.yml` for application deployments. Use
`configure.yml` only when changing a device's schedule intentionally.
The optional `caddy.yml` playbook configures HTTPS independently and does not
change `schema.json`.

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
  --limit pibell-main \
  -e school_bell_version=35-preserve-existing-schema \
  -e school_bell_config_src=/absolute/path/schema-main.json \
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
  --limit pibell-main \
  -e school_bell_config_src=/absolute/path/schema-main.json
```

Running the configuration playbook is the explicit action that replaces the
schedule and creates a backup. Use `--limit` to avoid deploying a
device-specific schedule to unintended inventory hosts. The configuration
playbook defaults to `/home/pi/schema.json`; `school_bell_user` and
`school_bell_config_name` remain configurable.

### Quick rollback without a controller-side backup

`configure.yml` already asks Ansible to keep the previous configuration on the
Raspberry Pi whenever it replaces `schema.json`. Ansible gives each saved copy
a unique timestamped name next to the active file, instead of continually
overwriting a single `schema.json.back`. This provides a flexible short-term
rollback option even when no backup has first been downloaded to the
controller.

These on-device copies are deliberately not created by `backup.yml`: that
playbook must leave the bell unchanged. They should also not be treated as a
full backup. A damaged or lost SD card, accidental deletion, or filesystem
corruption can remove both the active configuration and all copies stored next
to it. Use `backup.yml` when disaster recovery is required.

For an urgent rollback, an administrator can select a timestamped copy on the
bell, validate that it contains a JSON object, and then deploy that file as the
new `schema.json`. Keep this as an explicit administrative action: validate the
selected copy before replacing anything, preserve the current configuration,
and restart School Bell only if the restored contents differ. If remote
rollback becomes a regular operation, prefer a separate guarded `rollback.yml`
playbook with those checks over maintaining one ambiguous `schema.json.back`.

## Back up configurations and samples

`backup.yml` always downloads `schema.json`. It groups controller-side backups
under `backups/<timestamp>/<inventory-hostname>/` and never writes to the bell.
The timestamp is generated once in UTC for the entire playbook run:

```sh
ansible-playbook -i inventory ansible/backup.yml --limit school_bells
```

Include `/home/pi/samples/` explicitly when needed:

```sh
ansible-playbook -i inventory ansible/backup.yml \
  --limit school_bells \
  -e school_bell_backup_samples=true
```

For a predictable timestamp (for example in automation), set it explicitly:

```sh
ansible-playbook -i inventory ansible/backup.yml \
  --limit pibell-main \
  -e school_bell_backup_timestamp=20260831T120000Z
```

The playbook refuses to run for a host if that host's destination directory
already exists. It also rejects missing configurations and, when requested,
missing sample directories before creating local backup directories. `backup.yml`
uses only read operations on managed hosts; backup directories are created only
on the Ansible controller.

## Restore a backup

Restore requires all three safety inputs: an existing backup timestamp, a
targeted `--limit` other than `all`, and explicit confirmation. The playbook
validates every selected host's local `schema.json` as a non-empty JSON object
before it starts changing any selected bell:

```sh
ansible-playbook -i inventory ansible/restore.yml \
  --limit pibell-main \
  -e school_bell_backup_timestamp=20260831T120000Z \
  -e school_bell_restore_confirm=true
```

Configuration is restored by default. Samples are restored only with
`school_bell_restore_samples=true`. To restore samples independently without
changing the configuration, also set `school_bell_restore_config=false`:

```sh
ansible-playbook -i inventory ansible/restore.yml \
  --limit pibell-main \
  -e school_bell_backup_timestamp=20260831T120000Z \
  -e school_bell_restore_confirm=true \
  -e school_bell_restore_samples=true \
  -e school_bell_restore_config=false
```

When samples are requested, the backup must contain a `samples/` directory or
the restore is rejected before any remote change. Restoring samples copies the
backed-up files into the bell's samples directory; it does not remove unrelated
files already on the bell. School Bell is restarted only if restored file
contents, ownership, or modes actually changed.

## Update application code safely

Updating a branch, tag, or commit installs only the Python package in the
virtual environment. It does not upload a demo or controller-side schema:

```sh
ansible-playbook -i inventory ansible/update.yml \
  --limit pibell-yard \
  -e school_bell_version=my-feature-branch
```

If `pibell-yard` is configured as a host in `~/.ssh/config`, update it without
an inventory file by using an inline host list. Keep the trailing comma:

```sh
ansible-playbook -i pibell-yard, ansible/update.yml \
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
ansible-playbook -i inventory ansible/restart.yml --limit pibell-yard
```

## Configure optional HTTPS webhooks

`caddy.yml` is an explicit, optional deployment. Neither `init.yml` nor
`install.yml` installs Caddy or enables HTTPS. Before running it:

1. Give every node a fixed DHCP reservation.
2. Create an internal DNS A record for every `caddy_hostname`.
3. Enable the School Bell webhook on `127.0.0.1` in `schema.json`.
4. Issue a distinct leaf certificate for every hostname from one controlled
   internal CA.

Keep the CA private key outside this repository and off every bell node. The
playbook requires only the public CA certificate plus the selected node's own
certificate and private key.

The following YAML inventory variables are easier to audit than long inline
host entries. Store them in `host_vars/pibell-yard.yml`, or encrypt the file
with Ansible Vault when appropriate:

```yaml
caddy_hostname: pibell-yard.school-bell.internal
school_bell_caddy_ca_cert_src: /secure/pki/root.crt
school_bell_caddy_cert_src: /secure/pki/pibell-yard-fullchain.crt
school_bell_caddy_key_src: /secure/pki/pibell-yard.key
```

When internal DNS is unavailable, define a controlled hosts-file fallback on
the nodes that must call other bells:

```yaml
school_bell_caddy_hosts:
  - address: 192.0.2.41
    hostname: pibell-main.school-bell.internal
  - address: 192.0.2.42
    hostname: pibell-yard.school-bell.internal
```

Ansible maintains a marked block in `/etc/hosts`. When the Raspberry Pi uses a
cloud-init-managed hosts file, it updates
`/etc/cloud/templates/hosts.debian.tmpl` as well so the entries survive
regeneration. Prefer DNS and leave this list empty when DNS is reliable.

The leaf certificate must contain `caddy_hostname` as a DNS subject alternative
name. If it was signed by an intermediate, the certificate source must contain
the leaf followed by its intermediate chain. The source paths are on the
Ansible controller. Apply the playbook to one receiving node first:

```sh
ansible-playbook -i inventory ansible/caddy.yml --limit pibell-yard
```

The playbook:

- checks the controller-side certificate inputs before changing the node;
- refuses a webhook that is disabled, non-loopback, or on an unexpected port;
- installs Caddy from its official stable repository;
- installs `bind9-dnsutils` for immediate DNS troubleshooting;
- installs the public root in the operating-system trust store;
- deploys the leaf key as `root:caddy` with mode `0640`;
- validates the certificate hostname and Caddy configuration;
- adds a School Bell systemd drop-in pointing Python `requests` at
  `/etc/ssl/certs/ca-certificates.crt`;
- verifies that systemd loaded the CA bundle environment setting;
- checks DNS with the system resolver;
- verifies `GET /bell` returns `405` without ringing the bell;
- repeats the HTTPS check with School Bell's service user and virtualenv.

Remote webhook URLs use the standard HTTPS port and must not retain the local
backend port:

```text
https://pibell-yard.school-bell.internal/bell
```

For DNS diagnosis, compare the direct and system-resolver results:

```sh
dig +noall +answer pibell-yard.school-bell.internal A
getent ahostsv4 pibell-yard.school-bell.internal
```

An A record returns an address such as `192.0.2.42`; a CNAME whose target is
`192.0.2.42.` is incorrect. Ensure every DNS server advertised by DHCP knows
the same private records. See `docs/remote-bells.rst` for the complete manual
procedure, CA fingerprint verification and runtime troubleshooting.

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
- `caddy_hostname`: required by `caddy.yml`; HTTPS DNS name present in the
  node's certificate.
- `school_bell_caddy_ca_cert_src`: controller-side public CA certificate.
- `school_bell_caddy_cert_src`: controller-side host certificate.
- `school_bell_caddy_key_src`: controller-side host private key.
- `school_bell_caddy_hosts`: optional address and hostname mappings maintained
  in `/etc/hosts`; default empty.
- `school_bell_webhook_port`: loopback backend port; defaults to `8081`.
- `school_bell_ca_bundle`: CA bundle exposed to Python `requests`; defaults to
  `/etc/ssl/certs/ca-certificates.crt`.
