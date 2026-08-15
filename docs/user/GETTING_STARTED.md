# Getting Started with Vacuum Scheduler

This guide will help you install and set up the Vacuum Scheduler custom integration for Home Assistant.

## Prerequisites

- Home Assistant 2026.4.0 or newer
- HACS (Home Assistant Community Store) 2.0.5 or newer
- A vacuum entity that supports the `vacuum.clean_area` service (e.g. Roborock, Dreame, etc.)
- Optional: binary sensors for doors and windows, a `notify` entity

## Installation

### Via HACS (Recommended)

The easiest way is the one-click button from the [README](../README.md). Alternatively:

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/Kombustor/hacs-vacuum-automator`
6. Set category to "Integration"
7. Click "Add"
8. Find "Vacuum Scheduler" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/Kombustor/hacs-vacuum-automator/releases)
2. Extract the `custom_components/vacuum_scheduler/` folder from the archive
3. Copy it to `custom_components/vacuum_scheduler/` in your Home Assistant configuration directory
4. Restart Home Assistant

## Initial Setup

After installation, add the integration:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Vacuum Scheduler"
4. Follow the configuration steps:

### Step 1: Hub Name

Enter a name for the hub (default: "Vacuum Scheduler"). Click **Submit**.

### Step 2: Global Configuration

Configure global settings for the scheduler:

| Option                            | Default | Description                                                                 |
| --------------------------------- | ------- | --------------------------------------------------------------------------- |
| Notify Entity                     | -       | Optional notify entity (e.g. `notify.mobile_app_phone`) for batch summaries |
| Global Dry Run Mode               | Off     | Simulate cleaning without calling the vacuum                                |
| Max Rooms Per Batch               | 5       | Maximum rooms cleaned in a single batch (1-20)                              |
| Allow Cleaning When Window Open   | Off     | Permit cleaning even when window sensors report open                        |
| Critical Overdue Threshold (days) | 2       | Days beyond frequency before a room is critically overdue (1-7)             |
| Default Fan Speed                 | -       | Fan speed preset applied when a room has no override                        |
| Default Mop Intensity             | -       | Water flow intensity applied when a room has no override                    |

Click **Submit** to complete setup.

### Step 3: Add Rooms

The integration does nothing until you add rooms. Rooms are added as config subentries on the **Vacuum Scheduler** integration page.

For each room, you configure:

| Field             | Required | Description                                                          |
| ----------------- | -------- | -------------------------------------------------------------------- |
| Room Name         | Yes      | Unique name (e.g. "Kitchen")                                         |
| Vacuum Entity     | Yes      | The vacuum used for this room                                        |
| Cleaning Area     | Yes      | Home Assistant area(s) to clean (one or more)                        |
| Vacuum Frequency  | Yes      | Days between vacuuming (1-30, default 3)                             |
| Mop Frequency     | No       | Days between mopping; 0 disables mopping (mopping implies vacuuming) |
| Door Sensor       | No       | Binary sensor that is `on` when the door is open                     |
| Window Sensor     | No       | Binary sensor that is `on` when a window is open                     |
| Time Window Start | No       | Earliest cleaning time (default 08:00)                               |
| Time Window End   | No       | Latest cleaning time (default 20:00)                                 |
| Fan Speed         | No       | Room-specific fan speed preset (overrides global default)            |
| Mop Intensity     | No       | Room-specific water flow intensity (overrides global default)        |

> [!NOTE]
> Door sensors are optional but recommended: a room is only considered for batch cleaning while its door is open, and opening the door automatically triggers an evaluation for the rooms behind it.

## What Gets Created

### Device

One hub device named after your hub name. All room entities belong to it.

### Entities (per room)

| Entity                         | Type          | Purpose                                  |
| ------------------------------ | ------------- | ---------------------------------------- |
| `binary_sensor.<room>_overdue` | binary_sensor | On when the room is overdue for cleaning |
| `switch.<room>_enabled`        | switch        | Enables/disables scheduling for the room |

## First Steps

### Dashboard Cards

Add your rooms' overdue binary sensors to a dashboard:

```yaml
type: entities
title: Vacuum Scheduler
entities:
  - binary_sensor.kitchen_overdue
  - binary_sensor.living_room_overdue
  - switch.kitchen_enabled
```

### Automations

The typical setup is a daily batch evaluation:

```yaml
automation:
  - alias: "Vacuum Scheduler - Daily batch"
    trigger:
      - trigger: time
        at: "10:00:00"
    action:
      - action: vacuum_scheduler.evaluate_batch
```

Test it first with `dry_run: true` and check the service response to see which rooms would be cleaned.

See [EXAMPLES.md](./EXAMPLES.md) for more automation examples.

## Troubleshooting

### Rooms Never Get Cleaned

1. Check that the `{room} Enabled` switch is on
2. Verify the room has at least one cleaning area configured
3. Door closed? Batch evaluation skips rooms with a closed door
4. Window open? Cleaning is blocked unless "Allow Cleaning When Window Open" is enabled
5. Check the room's time window — cleaning only runs within it
6. Verify the vacuum supports `vacuum.clean_area`

Run `vacuum_scheduler.evaluate_batch` with `dry_run: true` and inspect the service response for the number of evaluated, overdue, and door-skipped rooms.

### Door-Triggered Cleaning Does Not Start

- The door sensor must be configured on the room and report `on` when open
- Check the **Door Stabilization Period** option (Configure) — evaluation only runs after the door stayed open that long
- The room must be overdue and inside its time window

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: warning
  logs:
    custom_components.vacuum_scheduler: debug
```

Add this to `configuration.yaml`, restart, and reproduce the issue. Check logs for detailed information.

## Next Steps

- See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options
- See [EXAMPLES.md](./EXAMPLES.md) for more automation examples
- Report issues at [GitHub Issues](https://github.com/Kombustor/hacs-vacuum-automator/issues)

## Support

For help and discussion:

- [GitHub Issues](https://github.com/Kombustor/hacs-vacuum-automator/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
