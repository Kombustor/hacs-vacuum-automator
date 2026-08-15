# Vacuum Scheduler

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

<!--
Uncomment and customize these badges if you want to use them:

[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]
[![Discord][discord-shield]][discord]
-->

**✨ Develop in the cloud:** Want to contribute or customize this integration? Open it directly in GitHub Codespaces - no local setup required!

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Kombustor/hacs-vacuum-automator?quickstart=1)

## ✨ Features

- **Room-based scheduling**: Configure per-room vacuum and mop frequencies — the scheduler tracks when each room was last cleaned
- **Overdue detection**: Binary sensors flag rooms that are overdue for vacuuming or mopping, with days-since-last-cleaned attributes
- **Door & window gating**: Rooms are only cleaned when their door is open and windows are closed (configurable)
- **Time windows**: Cleaning only runs within each room's configured time window (supports overnight windows)
- **Batch cleaning**: `evaluate_batch` evaluates all rooms and triggers `vacuum.clean_area` for overdue rooms, grouped by vacuum and cleaning settings
- **Dry run mode**: Simulate a batch evaluation to see which rooms would be cleaned, without touching your vacuum
- **Critical overdue events**: Fires `vac_scheduler_critical_overdue` once per room/mode when overdue exceeds the critical threshold
- **Door-triggered evaluation**: When a monitored door opens, batch evaluation runs automatically for the vacuums behind that door (after a configurable stabilization period)
- **Notifications**: Optional notify entity for dry-run summaries and cleaning-started messages
- **Per-room enable switch**: Disable scheduling for individual rooms without removing their configuration
- **Mopping support**: Separate mop frequencies, mop intensity (water flow) presets, and `set_water_box_custom_mode` support
- **No cloud or external API**: Everything is computed locally from your Home Assistant state (`iot_class: calculated`)

**This integration will set up the following platforms.**

| Platform        | Description                                                                                        |
| --------------- | -------------------------------------------------------------------------------------------------- |
| `binary_sensor` | Per-room overdue indicator (`problem` class), on when the room is overdue for vacuuming or mopping |
| `switch`        | Per-room scheduling enable/disable switch                                                          |

## 🚀 Quick Start

### Step 1: Install the Integration

**Prerequisites:** [HACS](https://hacs.xyz/) (Home Assistant Community Store) 2.0.5 or newer, Home Assistant 2026.4.0 or newer.

Click the button below to open the integration directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Kombustor&repository=hacs-vacuum-automator&category=integration)

Then:

1. Click "Download" to install the integration
2. **Restart Home Assistant** (required after installation)

> [!NOTE]
> The My Home Assistant redirect will first take you to a landing page. Click the button there to open your Home Assistant instance.

<details>
<summary><strong>Manual Installation (Advanced)</strong></summary>

If you prefer not to use HACS:

1. Download the latest release from the [releases page][releases]
2. Extract the `custom_components/vacuum_scheduler/` folder from the archive
3. Copy it to your Home Assistant's `custom_components/` directory
4. Restart Home Assistant

</details>

### Step 2: Add and Configure the Integration

**Important:** You must have installed the integration first (see Step 1) and restarted Home Assistant!

#### Option 1: One-Click Setup (Quick)

Click the button below to open the configuration dialog:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vacuum_scheduler)

Follow the setup wizard:

1. Enter a **Hub Name** (e.g. "Vacuum Scheduler")
2. Configure the **global settings** (see table below)
3. Click Submit

#### Option 2: Manual Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for "Vacuum Scheduler"
4. Follow the same setup steps as Option 1

### Step 3: Add Rooms

After setup, each room is added as a config **subentry** on the integration page:

1. Go to **Settings** → **Devices & Services**
2. Find **Vacuum Scheduler** and add a room
3. For each room, configure:

| Name              | Required | Description                                                        |
| ----------------- | -------- | ------------------------------------------------------------------ |
| Room Name         | Yes      | Unique name for the room (e.g. "Kitchen")                          |
| Vacuum Entity     | Yes      | The vacuum entity used to clean this room                          |
| Cleaning Area     | Yes      | Home Assistant area(s) to clean                                    |
| Vacuum Frequency  | Yes      | How often to vacuum (1-30 days, default 3)                         |
| Mop Frequency     | No       | How often to mop (0 = disabled; mopping always includes vacuuming) |
| Door Sensor       | No       | Binary sensor for the room door (must be open to clean)            |
| Window Sensor     | No       | Binary sensor for the window (blocks cleaning when open)           |
| Time Window Start | No       | Earliest time cleaning may run (default 08:00)                     |
| Time Window End   | No       | Latest time cleaning may run (default 20:00)                       |
| Fan Speed         | No       | Fan speed preset for this room (overrides global default)          |
| Mop Intensity     | No       | Water flow intensity (off/low/medium/high/auto/custom)             |

> [!TIP]
> Rooms are evaluated every 60 seconds. A room counts as **overdue** when it was
> never cleaned or its last cleaning is older than the configured frequency.

### Step 4: Adjust Settings (Optional)

After setup, you can adjust options:

1. Go to **Settings** → **Devices & Services**
2. Find **Vacuum Scheduler**
3. Click **Configure** to adjust the **Door Stabilization Period** (minimum time a door must be open before auto-triggering cleaning, 0-30 minutes, default 0)

You can also **Reconfigure** global settings or edit individual rooms anytime — no need to remove the integration.

### Step 5: Start Using!

- Add the **Overdue** binary sensors of your rooms to your dashboard
- Call `vacuum_scheduler.evaluate_batch` from an automation (e.g. daily at 10:00) or trigger it manually in **Developer Tools** → **Services**
- Or rely on the automatic door-trigger: when a monitored door opens, overdue rooms behind that door are evaluated automatically

## Available Entities

One device is created per hub; each room gets two entities:

### Binary Sensor: `{room} Overdue`

- **On**: The room is overdue for vacuuming and/or mopping
- **Off**: The room is up to date
- Attributes:
  - `last_vacuumed` / `last_mopped`: timestamps of the last cleaning
  - `days_since_vacuum` / `days_since_mop`: days since the last cleaning
  - `overdue_details`: `{"vacuum": true/false, "mop": true/false}`

### Switch: `{room} Enabled` (Configuration category)

- Turns scheduling for the room on or off without deleting its configuration
- Disabled rooms are excluded from batch evaluation and door triggers

## Custom Services

### `vacuum_scheduler.evaluate_batch`

Evaluate all rooms and trigger cleaning for overdue rooms with open doors.

| Field           | Required | Description                                                                                            |
| --------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `vacuum_entity` | No       | Only evaluate rooms using this vacuum entity                                                           |
| `dry_run`       | No       | If `true`, return the list of rooms without triggering cleaning (overrides the global dry-run setting) |

For each room the evaluation checks, in order:

1. Scheduling enabled (via the `{room} Enabled` switch)
2. At least one cleaning area configured
3. Door open (if a door sensor is configured)
4. Windows closed (unless "Allow Cleaning When Window Open" is enabled)
5. Overdue for vacuuming or mopping
6. Within the room's time window

Overdue rooms are sorted by urgency (most overdue first), capped at **Max Rooms Per Batch**, then grouped by vacuum entity, fan speed, and mopping needs. For each group the service:

- Sets the mop intensity via `vacuum.send_command` (`set_water_box_custom_mode`) when mopping is needed
- Sets the fan speed via `vacuum.set_fan_speed` when configured
- Starts area cleaning via `vacuum.clean_area`
- Records the cleaning timestamps (so the room is no longer overdue)

**Example:**

```yaml
service: vacuum_scheduler.evaluate_batch
data:
  dry_run: false
```

**Dry-run example:**

```yaml
service: vacuum_scheduler.evaluate_batch
data:
  dry_run: true
```

### `vacuum_scheduler.record_cleaning`

Manually record that a room has been cleaned — useful after manual cleaning runs.

| Field       | Required | Description                           |
| ----------- | -------- | ------------------------------------- |
| `room_name` | Yes      | The name of the room that was cleaned |
| `mode`      | Yes      | `vacuum`, `mop`, or `vacuum_and_mop`  |
| `timestamp` | No       | ISO format timestamp; defaults to now |

**Example:**

```yaml
service: vacuum_scheduler.record_cleaning
data:
  room_name: Kitchen
  mode: vacuum_and_mop
```

## Events

### `vac_scheduler_critical_overdue`

Fired once per room and mode when the room is overdue by more than the **Critical Overdue Threshold** (default 2 days). It fires again only after the room is cleaned and becomes critical again.

Event data:

- `room_name`: the room name
- `mode`: `vacuum` or `mop`
- `entry_id`: the config entry ID

**Example automation:**

```yaml
automation:
  - alias: "Vacuum Scheduler - Notify on critical overdue"
    trigger:
      - trigger: event
        event_type: vac_scheduler_critical_overdue
    action:
      - action: notify.notify
        data:
          title: "Vacuum Scheduler"
          message: "{{ trigger.event.data.room_name }} is critically overdue for {{ trigger.event.data.mode }}!"
```

## Troubleshooting

### Enable Debug Logging

Add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.vacuum_scheduler: debug
```

### Rooms Never Get Cleaned

Check these, in order:

1. The `{room} Enabled` switch is on
2. The room has at least one cleaning area configured
3. The door sensor is open (if configured) — closed doors block batch evaluation
4. Window sensors are closed (unless "Allow Cleaning When Window Open" is enabled)
5. The current time is within the room's time window
6. The vacuum entity supports `vacuum.clean_area`

Run `vacuum_scheduler.evaluate_batch` with `dry_run: true` and check the returned service response for the evaluated/skipped rooms — then review the debug logs for the skip reason.

### Door-Triggered Cleaning Does Not Start

- The door sensor must be configured on the room and report `on` when open
- Check the **Door Stabilization Period** option — the evaluation only runs after the door has been open that long
- Verify the vacuum entity is set to a value the room config expects and the room is overdue within its time window

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request if you have suggestions or improvements.

You have two options to set up a development environment — expand below for full details.

<details>
<summary><strong>Development Setup</strong></summary>

Both options provide the same fully-configured environment with Home Assistant, Python 3.14, Node.js LTS, and all necessary tools.

### Option 1: GitHub Codespaces (Recommended) ☁️

Develop directly in your browser without installing anything locally!

1. Click the green **"Code"** button in this repository
2. Switch to the **"Codespaces"** tab
3. Click **"Create codespace on main"**
4. **Wait for setup** (2-3 minutes first time) — everything installs automatically
5. **Review and commit** your changes in the Source Control panel (`Ctrl+Shift+G`)

> [!TIP]
> Codespaces gives you **60 hours/month free** for personal accounts. When you start Home Assistant (`script/develop`), port 8123 forwards automatically.

### Option 2: Local Development with VS Code 💻

#### Prerequisites

You'll need these installed locally:

- **A Docker-compatible container engine** — see options by platform:

  | Option                                                                                                                   | 🍎 macOS | 🐧 Linux | 🪟 Windows | Notes                                                                                                                                                                                                                                     |
  | ------------------------------------------------------------------------------------------------------------------------ | :------: | :------: | :--------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | [Docker Desktop](https://www.docker.com/products/docker-desktop/)                                                        |    ✅    |    ✅    |     ✅     | **Easiest starting point for all platforms.** GUI-based, well-documented, one installer. Uses WSL2 as default backend on Windows (Hyper-V also available). Installation requires admin rights; daily use does not. Free for personal use. |
  | [OrbStack](https://orbstack.dev/) ⭐                                                                                     |    ✅    |    —     |     —      | **Recommended for macOS** once Docker Desktop feels slow. Starts in ~2s, much lighter on RAM/CPU, full Docker API compatibility. Free for personal use.                                                                                   |
  | [Docker CE](https://docs.docker.com/engine/install/) (native) ⭐                                                         |    —     |    ✅    |     —      | **Recommended for Linux.** Install directly via your package manager — no VM, no overhead. Free.                                                                                                                                          |
  | [WSL2](https://learn.microsoft.com/windows/wsl/install) + [Docker CE](https://docs.docker.com/engine/install/ubuntu/) ⭐ |    —     |    —     |     ✅     | **Recommended for Windows** once you're comfortable with WSL2. Docker runs natively inside WSL2 — no GUI overhead. Requires one-time WSL2 setup. Free.                                                                                    |
  | [Rancher Desktop](https://rancherdesktop.io/)                                                                            |    ✅    |    ✅    |     ✅     | Open source by SUSE. GUI-based, uses WSL2 on Windows. Good alternative to Docker Desktop. Free.                                                                                                                                           |
  | [Colima](https://github.com/abiosoft/colima)                                                                             |    ✅    |    ✅    |     —      | CLI-only, very lightweight. Good for terminal-focused workflows. Free.                                                                                                                                                                    |

- **VS Code** with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- **Git** — macOS and Linux usually have it already; see below if not, or to get a newer version:
  - **🍎 macOS:** The system Git (`xcode-select --install`) works fine. Recommended: `brew install git` ([Homebrew](https://brew.sh/)) for a current version.
  - **🐧 Linux:** Usually pre-installed. If not: `sudo apt install git` (or your distro's equivalent).
  - **🪟 Windows + WSL2 ⭐:** Install Git _inside WSL2_ with `sudo apt install git`. Git on Windows itself is not needed — VS Code clones and operates entirely within WSL2.
  - **🪟 Windows + Docker Desktop:** Install via `winget install Git.Git` or download [Git for Windows](https://git-scm.com/download/win).
- **Hardware** — the devcontainer runs a full Home Assistant instance including Python tooling:

  |          | Minimum    | Recommended                           |
  | -------- | ---------- | ------------------------------------- |
  | **RAM**  | 8 GB       | 16 GB or more                         |
  | **CPU**  | 4 cores    | 8 cores or more                       |
  | **Disk** | 10 GB free | 20 GB free (SSD strongly recommended) |

> [!TIP]
> **Not sure which Docker option to pick?** Start with [Docker Desktop](https://www.docker.com/products/docker-desktop/) — it works on all platforms, has a GUI, and needs no extra setup. The ⭐ options are faster alternatives once you're comfortable. macOS and Linux offer the best devcontainer experience — containers run with no extra VM layer and file I/O is fast. Windows works well too; this integration uses named container volumes (files live inside WSL2, not on the Windows drive) to keep performance acceptable.

> [!NOTE]
> **New to Dev Containers?** See the [VS Code Dev Containers documentation](https://code.visualstudio.com/docs/devcontainers/containers#_system-requirements) for system requirements and how to install the extension. **Once the extension is installed, you're done** — this repository already ships a complete devcontainer configuration. You don't need to follow the rest of the VS Code guide; the setup steps below are all that's needed.

#### Setup Steps

1. **Clone in a Dev Container:**

   **🍎 macOS / 🐧 Linux:** Clone the repository and open the folder in VS Code → click **"Reopen in Container"** when prompted (or `F1` → **"Dev Containers: Reopen in Container"**).

   **🪟 Windows:** In VS Code, press `F1` → **"Dev Containers: Clone Repository in Named Container Volume..."** and enter the repository URL. This keeps files inside WSL2 for best I/O performance.

2. Wait for the container to build (2-3 minutes first time)

3. **Review and commit** changes in Source Control (`Ctrl+Shift+G`)

4. **Start developing**:

   ```bash
   script/develop  # Home Assistant runs at http://localhost:8123
   ```

> [!NOTE]
> Both Codespaces and local DevContainer provide the exact same experience. The only difference is where the container runs (GitHub's cloud vs. your machine).

</details>

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by [@Kombustor][user_profile]**

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/Kombustor/hacs-vacuum-automator.svg?style=for-the-badge
[commits]: https://github.com/Kombustor/hacs-vacuum-automator/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/Kombustor/hacs-vacuum-automator.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40Kombustor-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/Kombustor/hacs-vacuum-automator.svg?style=for-the-badge
[releases]: https://github.com/Kombustor/hacs-vacuum-automator/releases
[user_profile]: https://github.com/Kombustor

<!-- Optional badge definitions - uncomment if needed:
[buymecoffee]: https://www.buymeacoffee.com/Kombustor
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
-->
