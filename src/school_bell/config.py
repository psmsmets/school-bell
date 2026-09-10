"""Typed, central validation for the JSON configuration."""

import calendar
import logging.handlers
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import pytz
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def _legacy_int(value):
    """Retain the integer coercion supported by the pre-1.0 runtime."""
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _legacy_float(value):
    """Retain the numeric coercion supported by manual bell settings."""
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


LegacyInt = Annotated[int, BeforeValidator(_legacy_int)]
PositiveLegacyInt = Annotated[
    int, BeforeValidator(_legacy_int), Field(gt=0)
]
Port = Annotated[
    int, BeforeValidator(_legacy_int), Field(ge=0, le=65535)
]
PositiveNumber = Annotated[
    float, BeforeValidator(_legacy_float), Field(gt=0)
]
NonNegativeNumber = Annotated[
    float, BeforeValidator(_legacy_float), Field(ge=0)
]


class ConfigModel(BaseModel):
    """Common strict behaviour for every configuration object."""

    model_config = ConfigDict(extra='forbid', strict=True)


class RemoteAuthConfig(ConfigModel):
    type: Literal['bearer', 'basic']
    token: str | None = None
    username: str | None = None
    password: str | None = None

    @field_validator('type', mode='before')
    @classmethod
    def normalize_type(cls, value):
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode='after')
    def validate_credentials(self):
        if self.type == 'bearer':
            if not self.token:
                raise ValueError('a non-empty token is required for bearer auth')
            if self.username is not None or self.password is not None:
                raise ValueError('username and password are not valid for bearer auth')
        else:
            if not self.username or not self.password:
                raise ValueError(
                    'non-empty username and password are required for basic auth'
                )
            if self.token is not None:
                raise ValueError('token is not valid for basic auth')
        return self


class RemoteBellBase(ConfigModel):
    transport: Literal['ssh', 'webhook']


class RemoteSshBellConfig(RemoteBellBase):
    transport: Literal['ssh'] = 'ssh'
    host: str
    user: str | None = None
    command: str | list[str]
    timeout: PositiveLegacyInt = 10

    @field_validator('host', 'user')
    @classmethod
    def non_empty_string(cls, value):
        if value is not None and not value.strip():
            raise ValueError('must be a non-empty string')
        return value.strip() if value is not None else value

    @field_validator('command')
    @classmethod
    def valid_command(cls, value):
        command = [value] if isinstance(value, str) else value
        if not command or any(not argument for argument in command):
            raise ValueError('must contain non-empty strings')
        return command


class RemoteWebhookBellConfig(RemoteBellBase):
    transport: Literal['webhook']
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    auth: RemoteAuthConfig | None = None
    timeout: PositiveNumber = 5

    @field_validator('url')
    @classmethod
    def http_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('must be an HTTP(S) URL')
        return value


RemoteBellConfig = Annotated[
    RemoteSshBellConfig | RemoteWebhookBellConfig,
    Field(discriminator='transport'),
]


class ManualBellConfig(ConfigModel):
    gpio: int
    wav_key: str
    mode: Literal['once', 'hold'] = 'once'
    pull: Literal['up', 'down', 'floating'] = 'up'
    bounce_time: NonNegativeNumber = .05
    remote_bells: list[RemoteBellConfig] = Field(default_factory=list)

    @field_validator('gpio')
    @classmethod
    def gpio_is_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError('must be an integer')
        return value

    @field_validator('wav_key', mode='before')
    @classmethod
    def normalize_wav_key(cls, value):
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value

    @field_validator('mode', 'pull', mode='before')
    @classmethod
    def normalize_literal(cls, value):
        return value.lower() if isinstance(value, str) else value

    @field_validator('remote_bells', mode='before')
    @classmethod
    def default_ssh_transport(cls, value):
        if not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            item = dict(item)
            item.setdefault('transport', 'ssh')
            if isinstance(item['transport'], str):
                item['transport'] = item['transport'].lower()
            normalized.append(item)
        return normalized


class SyslogConfig(ConfigModel):
    host: str
    port: Port = 514
    protocol: Literal['udp', 'tcp'] = 'udp'
    facility: str = 'daemon'

    @field_validator('host')
    @classmethod
    def non_empty_host(cls, value):
        if not value:
            raise ValueError('must be a non-empty string')
        return value

    @field_validator('protocol', mode='before')
    @classmethod
    def normalize_protocol(cls, value):
        return value.lower() if isinstance(value, str) else value

    @field_validator('facility')
    @classmethod
    def known_facility(cls, value):
        if value not in logging.handlers.SysLogHandler.facility_names:
            raise ValueError('must be a known syslog facility')
        return value


class MonitoringStatusConfig(ConfigModel):
    enabled: bool = False
    host: str = '127.0.0.1'
    port: Port = 8080
    token: str | None = None
    include_systemd: bool = True

    @field_validator('host')
    @classmethod
    def non_empty_host(cls, value):
        if not value:
            raise ValueError('must be a non-empty string')
        return value


class MonitoringConfig(ConfigModel):
    device_id: str | None = None
    labels: dict[str, Any] = Field(default_factory=dict)
    heartbeat_interval: PositiveLegacyInt = 300
    syslog: SyslogConfig | None = None
    status: MonitoringStatusConfig | None = None

    @field_validator('device_id')
    @classmethod
    def non_empty_device_id(cls, value):
        if value is not None and not value:
            raise ValueError('must be a non-empty string')
        return value

    @field_validator('labels')
    @classmethod
    def valid_labels(cls, value):
        invalid = [
            key for key in value
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', key) is None
        ]
        if invalid:
            raise ValueError(
                'names must start with a letter and contain only letters, '
                'numbers and underscores'
            )
        return value


class WebhookConfig(ConfigModel):
    enabled: bool = False
    host: str = '127.0.0.1'
    port: Port = 8081
    token: str | None = None
    rate_limit: PositiveLegacyInt = 10
    rate_window: PositiveLegacyInt = 60

    @model_validator(mode='after')
    def validate_enabled_webhook(self):
        if self.enabled and not self.host:
            raise ValueError('host must be a non-empty string when enabled')
        if self.enabled and not self.token:
            raise ValueError('token must be a non-empty string when enabled')
        return self


class SchoolBellConfig(ConfigModel):
    """Complete user-controlled ``config.json`` contract."""

    schedule: dict[str, dict[str, str]]
    wav: dict[str, str]
    root: str | None = None
    device: str | None = None
    buzz_gpio: int | list[int] | None = None
    buzz_active_high: bool = True
    timeout: LegacyInt | None = None
    holidays: str | None = None
    trigger: dict[str, str] | None = None
    timezone: str = 'Europe/Brussels'
    disable_calendar: str | None = None
    manual_bell: ManualBellConfig | None = None
    webhook: WebhookConfig | None = None
    monitoring: MonitoringConfig | None = None

    @field_validator('schedule', mode='before')
    @classmethod
    def normalize_schedule_references(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = {}
        for day, times in value.items():
            if not isinstance(times, dict):
                normalized[day] = times
                continue
            normalized[day] = {
                time: str(wav_key)
                if isinstance(wav_key, int) and not isinstance(wav_key, bool)
                else wav_key
                for time, wav_key in times.items()
            }
        return normalized

    @field_validator('schedule')
    @classmethod
    def valid_schedule(cls, value):
        time_pattern = re.compile(
            r'^(([0-1]?\d)|(2[0-3]))(:[0-5]?\d)(:[0-5]?\d)?$'
        )
        valid_days = set(calendar.day_abbr)
        for configured_day, times in value.items():
            if configured_day.capitalize() not in valid_days:
                raise ValueError(f'invalid weekday {configured_day!r}')
            for configured_time in times:
                if time_pattern.fullmatch(configured_time) is None:
                    raise ValueError(
                        f'invalid time {configured_time!r} for {configured_day!r}'
                    )
        return value

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        if value not in pytz.all_timezones_set:
            raise ValueError('must be a known timezone')
        return value

    @field_validator('disable_calendar')
    @classmethod
    def valid_disable_calendar(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc:
            raise ValueError('must be an HTTP(S) URL')
        return value

    @field_validator('holidays')
    @classmethod
    def valid_holiday_group(cls, value):
        parts = value.split('-', 1) if value is not None else None
        if parts is not None and (len(parts) != 2 or not all(parts)):
            raise ValueError(
                'must contain a country and language separated by -'
            )
        return value

    @field_validator('buzz_gpio')
    @classmethod
    def valid_gpio_outputs(cls, value):
        pins = [value] if isinstance(value, int) else (value or [])
        if any(isinstance(pin, bool) for pin in pins):
            raise ValueError('pins must be integers')
        return value

    @model_validator(mode='after')
    def validate_references(self):
        wav_keys = set(self.wav)
        for day, times in self.schedule.items():
            for configured_time, wav_key in times.items():
                if wav_key not in wav_keys:
                    raise ValueError(
                        f'schedule.{day}.{configured_time} refers to unknown '
                        f'WAV key {wav_key!r}'
                    )
        if self.manual_bell is not None:
            if self.manual_bell.wav_key not in wav_keys:
                raise ValueError(
                    'manual_bell.wav_key refers to an unknown WAV key'
                )
            outputs = (
                [self.buzz_gpio] if isinstance(self.buzz_gpio, int)
                else (self.buzz_gpio or [])
            )
            if self.manual_bell.gpio in outputs:
                raise ValueError(
                    'manual_bell.gpio must not also be a buzz_gpio output'
                )
        return self


def validate_config(config: object) -> SchoolBellConfig:
    """Validate an entire parsed JSON document in one operation."""
    return SchoolBellConfig.model_validate(config)


def config_json_schema() -> dict:
    """Return the generated schema used by editors and deployment tooling."""
    return SchoolBellConfig.model_json_schema()
