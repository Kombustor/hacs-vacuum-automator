# Examples

This page provides ready-to-use examples for automations and dashboards with the Vacuum Scheduler custom integration.

Replace entity IDs like `binary_sensor.kitchen_overdue` with your actual entity IDs (they are derived from your room names).

## Automations

### Daily batch cleaning

Evaluate all rooms every morning and clean overdue rooms with open doors:

```yaml
automation:
  - alias: "Vacuum Scheduler - Daily batch"
    trigger:
      - trigger: time
        at: "10:00:00"
    action:
      - action: vacuum_scheduler.evaluate_batch
```

### Daily batch with notification

The integration notifies via the **Notify Entity** configured during setup, so no extra service call is needed:

```yaml
automation:
  - alias: "Vacuum Scheduler - Daily batch with notification"
    trigger:
      - trigger: time
        at: "10:00:00"
    action:
      - action: vacuum_scheduler.evaluate_batch
```

### Weekly dry run report

Preview which rooms would be cleaned, without triggering the vacuum:

```yaml
automation:
  - alias: "Vacuum Scheduler - Weekly dry run"
    trigger:
      - trigger: time
        at: "09:00:00"
    condition:
      - condition: time
        weekday:
          - mon
    action:
      - action: vacuum_scheduler.evaluate_batch
        data:
          dry_run: true
```

### Notify when a room becomes critically overdue

The integration fires `vac_scheduler_critical_overdue` (once per room and mode) when a room is overdue by more than the critical threshold:

```yaml
automation:
  - alias: "Vacuum Scheduler - Critical overdue alert"
    trigger:
      - trigger: event
        event_type: vac_scheduler_critical_overdue
    action:
      - action: notify.notify
        data:
          title: "Vacuum Scheduler"
          message: >-
            {{ trigger.event.data.room_name }} is critically overdue for
            {{ trigger.event.data.mode }}!
```

### Record cleaning after a manual vacuum run

Use `record_cleaning` to keep the scheduler accurate when you clean manually:

```yaml
automation:
  - alias: "Record manual kitchen cleaning"
    trigger:
      - trigger: state
        entity_id: vacuum.roborock
        to: "docked"
    condition:
      - condition: template
        value_template: >
          {{ trigger.from_state.state in ['cleaning', 'returning'] }}
    action:
      - action: vacuum_scheduler.record_cleaning
        data:
          room_name: Kitchen
          mode: vacuum
```

### Pause scheduling for a room while on vacation

```yaml
automation:
  - alias: "Disable kitchen scheduling on vacation"
    trigger:
      - trigger: state
        entity_id: input_boolean.vacation_mode
        to: "on"
    action:
      - action: switch.turn_off
        target:
          entity_id: switch.kitchen_enabled
```

```yaml
automation:
  - alias: "Re-enable kitchen scheduling after vacation"
    trigger:
      - trigger: state
        entity_id: input_boolean.vacation_mode
        to: "off"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.kitchen_enabled
```

### Only evaluate a single vacuum

```yaml
service: vacuum_scheduler.evaluate_batch
data:
  vacuum_entity: vacuum.roborock
```

## Dashboard Cards

### Room status — entities card

```yaml
type: entities
title: Vacuum Scheduler
entities:
  - binary_sensor.kitchen_overdue
  - binary_sensor.living_room_overdue
  - switch.kitchen_enabled
  - switch.living_room_enabled
```

### Overdue badge — glance card

```yaml
type: glance
title: Overdue Rooms
entities:
  - binary_sensor.kitchen_overdue
  - binary_sensor.living_room_overdue
  - binary_sensor.bathroom_overdue
show_state: true
```

### Last cleaned attributes

The overdue binary sensors expose `last_vacuumed`, `last_mopped`, `days_since_vacuum`, `days_since_mop`, and `overdue_details` attributes — usable in templates:

```jinja
{{ state_attr('binary_sensor.kitchen_overdue', 'days_since_vacuum') }} days
```

## Related Documentation

- [Configuration Reference](./CONFIGURATION.md) - All configuration options
- [Getting Started](./GETTING_STARTED.md) - Installation and initial setup
- [GitHub Issues](https://github.com/Kombustor/hacs-vacuum-automator/issues) - Report problems
