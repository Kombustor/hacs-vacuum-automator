# Configuration Reference

This document describes all configuration options and settings available in the Vacuum Scheduler custom integration.

## Overview

Vacuum Scheduler is a **hub** integration: one config entry holds global settings, and each room is a config **subentry**. All logic is computed locally — there is no external API, host, or credentials to configure.

## Global Configuration

Configured during initial setup (and editable anytime via the integration's **Reconfigure** menu).

| Option                            | Type    | Default | Description                                                                 |
| --------------------------------- | ------- | ------- | --------------------------------------------------------------------------- |
| Notify Entity                     | entity  | -       | Optional notify entity (e.g. `notify.mobile_app_phone`) for batch summaries |
| Global Dry Run Mode               | boolean | Off     | Simulate cleaning: evaluate and report, but never call the vacuum           |
| Max Rooms Per Batch               | number  | 5       | Maximum number of rooms cleaned in a single batch (1-20)                    |
| Allow Cleaning When Window Open   | boolean | Off     | Permit cleaning even when window sensors report open                        |
| Critical Overdue Threshold (days) | number  | 2       | Days beyond the frequency before a room is critically overdue (1-7)         |
| Default Fan Speed                 | text    | -       | Fan speed preset used when a room has no override                           |
| Default Mop Intensity             | select  | -       | Water flow intensity used when a room has no override                       |

### Mop Intensity Options

`off`, `low`, `medium`, `high`, `auto`, `custom` — mapped to `set_water_box_custom_mode` command parameters when mopping.

## Room Configuration (Subentries)

Each room is added and edited via the subentry flow on the **Vacuum Scheduler** integration page.

| Field             | Required | Default | Description                                                           |
| ----------------- | -------- | ------- | --------------------------------------------------------------------- |
| Room Name         | Yes      | -       | Unique room name (duplicates are rejected)                            |
| Vacuum Entity     | Yes      | -       | Vacuum entity for this room                                           |
| Cleaning Area     | Yes      | -       | Home Assistant area(s) to clean (multi-select)                        |
| Vacuum Frequency  | Yes      | 3       | Days between vacuuming (1-30)                                         |
| Mop Frequency     | No       | 0       | Days between mopping; 0 = disabled. Mopping always includes vacuuming |
| Door Sensor       | No       | -       | Binary sensor, `on` = door open                                       |
| Window Sensor     | No       | -       | Binary sensor, `on` = window open                                     |
| Time Window Start | No       | 08:00   | Earliest time cleaning may start                                      |
| Time Window End   | No       | 20:00   | Latest time cleaning may start (overnight windows supported)          |
| Fan Speed         | No       | -       | Room-specific fan speed preset                                        |
| Mop Intensity     | No       | -       | Room-specific water flow intensity                                    |

## Options Flow

After setup, click **Configure** on the integration to adjust:

| Option                    | Default | Description                                                          |
| ------------------------- | ------- | -------------------------------------------------------------------- |
| Door Stabilization Period | 0       | Minutes a door must stay open before auto-triggering cleaning (0-30) |

## How Evaluation Works

The coordinator evaluates all rooms every 60 seconds and updates the overdue binary sensors. A room is overdue when:

- it was never cleaned, or
- the time since the last cleaning exceeds the configured frequency.

Mopping overdue always implies vacuuming overdue.

The `vacuum_scheduler.evaluate_batch` service additionally applies, in order:

1. `{room} Enabled` switch on
2. At least one cleaning area configured
3. Door open (if a door sensor is configured)
4. Windows closed (unless **Allow Cleaning When Window Open** is enabled)
5. Overdue for vacuuming and/or mopping
6. Current time within the room's time window

Overdue rooms are sorted by urgency (most overdue first), capped at **Max Rooms Per Batch**, and grouped by vacuum entity, fan speed, and mopping needs before cleaning is triggered.

## Services

### `vacuum_scheduler.evaluate_batch`

Evaluate all rooms and trigger cleaning for overdue rooms with open doors.

| Field           | Type    | Required | Description                                                                             |
| --------------- | ------- | -------- | --------------------------------------------------------------------------------------- |
| `vacuum_entity` | entity  | No       | Restrict evaluation to rooms using this vacuum entity                                   |
| `dry_run`       | boolean | No       | If true, only report which rooms would be cleaned; overrides the global dry-run setting |

The service response contains `dry_run`, `rooms_evaluated`, `rooms_overdue`, `rooms_skipped_door_closed`, the per-room groups that would be/were cleaned, and any errors.

**Example:**

```yaml
service: vacuum_scheduler.evaluate_batch
data:
  dry_run: false
```

### `vacuum_scheduler.record_cleaning`

Manually record a cleaning for a room.

| Field       | Type   | Required | Description                           |
| ----------- | ------ | -------- | ------------------------------------- |
| `room_name` | string | Yes      | Name of the room that was cleaned     |
| `mode`      | select | Yes      | `vacuum`, `mop`, or `vacuum_and_mop`  |
| `timestamp` | string | No       | ISO format timestamp; defaults to now |

**Example:**

```yaml
service: vacuum_scheduler.record_cleaning
data:
  room_name: Kitchen
  mode: vacuum_and_mop
  timestamp: "2026-06-10T09:30:00"
```

## Events

### `vac_scheduler_critical_overdue`

Fired once per room and mode when the room is overdue by more than the **Critical Overdue Threshold** (default 2 days). Refires only after the room is cleaned and becomes critical again.

| Event data  | Description              |
| ----------- | ------------------------ |
| `room_name` | Name of the overdue room |
| `mode`      | `vacuum` or `mop`        |
| `entry_id`  | The config entry ID      |

## Automatic Triggers

- **Door listeners**: when a configured door sensor turns `on`, batch evaluation runs automatically for the vacuums behind that door after the **Door Stabilization Period** elapses. Timers are cancelled if the door closes again.
- **Coordinator**: overdue state is recomputed every 60 seconds; critical-overdue events and entity updates are driven from there.

## Entity Configuration

### Entity Customization

Customize entities via the UI or `configuration.yaml`:

#### Via Home Assistant UI

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find and click the entity
3. Click the settings icon
4. Modify name, icon, or area assignment

#### Via configuration.yaml

```yaml
homeassistant:
  customize:
    binary_sensor.kitchen_overdue:
      friendly_name: "Kitchen Needs Cleaning"
```

### Disabling Entities

If you don't need a specific entity:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find the entity, click it, then click the settings icon
3. Toggle **Enable entity** off

Note: use the `{room} Enabled` switch to pause scheduling for a room — it does not remove the room configuration.

## Multiple Instances

You can add multiple instances of this integration for different hubs (e.g. upstairs/downstairs vacuums). Each instance has its own global settings, rooms, and entities.

## Diagnostic Data

The integration provides diagnostic data for troubleshooting:

1. Go to **Settings** → **Devices & Services**
2. Find "Vacuum Scheduler"
3. Click on the device
4. Click **Download Diagnostics**

## Troubleshooting Configuration

### Config Entry Fails to Load

1. Check Home Assistant logs for errors
2. Verify you have no duplicate hub names (they are used as unique IDs)
3. Try removing and re-adding the integration

### Options Don't Save

1. Check for validation errors in the UI
2. Ensure values are within allowed ranges
3. Review logs for detailed error messages
4. Try restarting Home Assistant

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) - Installation and initial setup
- [Examples](./EXAMPLES.md) - Automation and dashboard examples
- [GitHub Issues](https://github.com/Kombustor/hacs-vacuum-automator/issues) - Report problems
