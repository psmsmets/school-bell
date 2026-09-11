JSON Schema
===========

School Bell's Pydantic model is the authoritative definition of
``config.json``. From that model the project can generate a standard JSON
Schema. The schema lets an editor, CI job or Ansible controller detect most
mistakes before a configuration reaches a bell.

Schema validation and ``--check`` serve different purposes:

* JSON Schema checks structure, required fields, types, allowed values and
  many numeric constraints without starting School Bell;
* ``school-bell CONFIG --check`` additionally checks runtime context, including
  local WAVE files and configured external calendar services;
* neither check activates GPIO outputs, plays audio or starts the scheduler.

Generate the schema
-------------------

Generate it from the installed version that will run on the bells:

.. code-block:: console

   python -c 'import json; from school_bell.config import config_json_schema; print(json.dumps(config_json_schema(), indent=2))' > school-bell.schema.json

Regenerate the file after changing the pinned School Bell release. A schema
from another version may accept fields the deployed version does not know, or
reject fields that have since been introduced.

Use it in an editor
-------------------

Editors such as Visual Studio Code can associate a local schema with a file by
adding a top-level ``$schema`` property. School Bell deliberately rejects
unknown configuration fields, including ``$schema`` itself, so do **not** add
that property to the deployed JSON. Configure the filename-to-schema mapping
in the editor settings instead.

For Visual Studio Code, a workspace setting can look like this:

.. code-block:: json

   {
       "json.schemas": [
           {
               "fileMatch": ["/configs/*.json"],
               "url": "./school-bell.schema.json"
           }
       ]
   }

This provides completion, structural guidance, allowed-value selection and
immediate feedback on unknown fields.

Use it in CI
------------

Any validator supporting JSON Schema 2020-12 can validate configuration files.
The exact command depends on the chosen validator. Run schema validation first
for fast structural feedback, then run ``school-bell CONFIG --check`` in an
environment containing the referenced WAVE files.

Use it with Ansible
-------------------

The included playbooks currently verify that a controller-side configuration
is valid JSON and contains an object. The installed School Bell process then
performs full Pydantic validation. For an earlier controller-side gate, generate
the schema for the pinned application version and validate configurations in
CI before running ``configure.yml``.

If an Ansible collection providing JSON Schema validation is used, keep that
dependency explicit in ``requirements.yml`` and pin it. Do not silently make a
third-party collection a runtime requirement for the autonomous bell nodes;
validation belongs on the controller.

Limits of a generated schema
----------------------------

Some checks depend on relationships or runtime resources and cannot be fully
expressed by editor hints alone. Examples include verifying that every schedule
or relay key selects an existing ``wav`` entry, that a manual input does not
reuse an output pin, that a WAVE file exists, and that a remote calendar responds.
Pydantic and ``--check`` remain the final authority.
