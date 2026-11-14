# Bluelink Climate Control

A custom Home Assistant integration for Hyundai USA remote climate control, distributed through HACS / Marketplace. Originally tested with an IONIQ 5 in the USA. Other countries, Kia accounts, and combustion-engine remote start are not supported.

Requires Home Assistant 2025.12 or newer. Home Assistant 2026.11 incorporates HACS as **Marketplace** under Settings; existing custom repositories carry over. See the [2026.11 release notes](https://www.home-assistant.io/blog/2026/11/04/release-202611/).

## Installation

1. In Home Assistant 2026.11+, open **Settings > Marketplace > Add from link**, enter `https://github.com/TaiPhamD/ha-bluelink`, and connect GitHub when prompted. On earlier supported versions, add the URL through HACS's **Custom repositories** menu as an **Integration**.
2. Find **Bluelink Climate Control** and select **Install**. Marketplace opens the setup flow automatically. When updating an existing installation, restart Home Assistant when prompted.
3. Enter your MyHyundai email, password, and Bluelink remote command PIN, then select your vehicle. Add the integration again for another vehicle.
4. With older HACS, restart after downloading, then open **Settings > Devices & services > Add integration** and search for **Bluelink Climate Control**.

For a manual installation, copy `custom_components/bluelink_api_hacs` to `/config/custom_components/bluelink_api_hacs`, restart Home Assistant, and add the integration under **Settings > Devices & services**.

## Authentication and token expiry

The integration renews an expired token before setup or a climate command, using the refresh token and falling back to account login. Renewed tokens are saved in the existing config entry. A token rejected during a command starts Home Assistant's reauthentication flow; follow the prompt under **Settings > Devices & services**. You can also use **Reconfigure** on the integration entry to update credentials. Both flows retain the same vehicle and entity unique IDs.

**SMS verification is not implemented yet.** MyHyundai website/app 2FA and this integration's USA telematics token endpoint are different login paths. The maintained [Hyundai USA client](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api/blob/master/hyundai_kia_connect_api/HyundaiBlueLinkApiUSA.py) currently uses username/password login and refresh-token exchange. Hyundai's [website login](https://owners.hyundaiusa.com/us/en/login.html) uses device-bound MFA and reCAPTCHA. The integration cannot currently submit website/app SMS codes or exchange those MFA tokens for a telematics token. The remote command PIN field is not an SMS code field.

If integration login fails for an account requiring 2FA, report the error and whether it occurs during initial setup or token renewal. Remove usernames, VINs, passwords, PINs, SMS codes, and tokens from anything you share. For a local check, run `python -m scripts.check_auth` in an environment with Home Assistant installed. It prompts for credentials locally, makes one login request, and prints HTTP status and response field types with all values omitted. It does not send vehicle commands. A verified telematics challenge/verification exchange is needed before direct SMS code entry can be supported.

## Controls and Hyundai feedback

Use the **Climate control** entity to choose a temperature (default 72 °F, range 62–82 °F) and start/stop climate. The compatibility switch sends the same commands and keeps its existing unique ID. Temperature changes are saved for the **next start**; they do not silently send another command while climate is running. **Reported climate target** shows Hyundai's setpoint separately, when available. Neither temperature is a cabin-temperature measurement.

The climate entity and switch show **Hyundai-reported state**, including changes made in the MyHyundai app. Before the first vehicle response they show unknown. Sending a command does not immediately change the reported on/off state, and the integration no longer assumes the car turned off after ten minutes.

### Command progress

**Last climate command** follows Sending → Accepted → Waiting for vehicle → Completed / Failed / Completion timed out. Command tracking uses Hyundai's transaction ID and checks completion every five seconds for up to approximately two minutes. If Hyundai returns no tracking ID, the result is **Completion unconfirmed**. A network timeout also leaves the result unconfirmed: the car might still receive the request. The integration never automatically resends a vehicle command.

Completion is Hyundai's command result, independent of the vehicle snapshot. You can see Completed with an older climate state until Hyundai's cache catches up. **Next command available** shows when the 60-second command cooldown ends; it clears when the cooldown is over. Repeated starts while the same command is pending do not send duplicates. Opposite commands wait until tracking finishes and the cooldown ends.

### Vehicle status and freshness

The vehicle device includes:

| Entity | Meaning |
| --- | --- |
| Vehicle battery | Hyundai-reported EV battery percentage |
| Charging / Defrost | Hyundai-reported charging and defrost state |
| Vehicle last updated | The timestamp in Hyundai's vehicle snapshot, not the last HTTP request |
| Vehicle feedback | Current, stale/unreachable, or waiting for the first update |
| Reported climate target | The setpoint reported by Hyundai, when numeric and in a recognized unit |
| Last climate command | Command progress, action, start/finish time, and a readable error |
| Next command available | End of the command cooldown |

Missing fields remain unknown. Snapshots older than 15 minutes, with an unknown/invalid timestamp, or retained after a failed status fetch are marked stale. Entity attributes include the vehicle timestamp, the time the cache response was received, and whether the latest status fetch succeeded. An older response cannot overwrite a newer snapshot.

Automatic polling reads Hyundai's cache every five minutes. After a command, a few additional cache checks at 15, 30, and 60 seconds allow telemetry to catch up; these stop making requests once fresh matching feedback is available. **Refresh cached status** checks the cloud cache. **Request fresh vehicle status** explicitly asks Hyundai to contact the car and is limited to once per minute. A returned snapshot can still be old; its timestamp remains visible. Background polling and command tracking never force a vehicle refresh.

The protocol follows the maintained [Hyundai USA client](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api/blob/master/hyundai_kia_connect_api/HyundaiBlueLinkApiUSA.py). Field availability and update latency depend on the vehicle and Hyundai's service; live status and command completion need testing on your car.

### Dashboard

[Copy the native dashboard card](examples/dashboard.yaml) into a **Manual** card. Replace its sample entity IDs with the ones on your vehicle's device page; existing installations keep their older climate/switch entity IDs. It uses built-in cards only: temperature and HVAC controls, command progress, timestamped feedback, a cooldown indicator, and separate cache/vehicle refresh buttons. No additional frontend plugin is needed.

## Updating from 0.1.0

Existing config entries and entity unique IDs are retained. Temperature storage is now per vehicle; the previous shared temperature is copied on first load. The old credential options flow is replaced by **Reconfigure** and native reauthentication. HVAC on/off now sends the remote commands and stays synchronized with the switch.

## Updating from 0.2.0

Version 0.3.0 replaces assumed command state with vehicle telemetry and adds feedback sensors and refresh buttons. Entity unique IDs and saved temperatures are retained. On/off may remain unknown until Hyundai supplies status, and a successful command may appear before a fresh snapshot. Command results are session-only; restarting Home Assistant starts with no tracked command and fetches vehicle status.

## Development

Use Python 3.14 for the current test environment:

```sh
uv venv --python 3.14
uv pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
```

The custom-component pytest harness pins its own Home Assistant version. CI also runs a separate smoke check against the latest Home Assistant release to catch import and lifecycle API changes. Network calls and vehicle commands are mocked in tests; live Hyundai authentication and vehicle operation require account testing.

## Removal

Remove the vehicle integration under **Settings > Devices & services**, then remove the downloaded integration through Marketplace/HACS and restart Home Assistant. To remove saved setpoints, delete only `.storage/bluelink_api_hacs.<entry_id>` for the removed entries while Home Assistant is stopped.
