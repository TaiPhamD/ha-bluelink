# Bluelink Climate Control

A custom Home Assistant integration for Hyundai USA remote climate control, distributed through HACS / Marketplace. Originally tested with an IONIQ 5 in the USA. Other countries, Kia accounts, and combustion-engine remote start are not supported.

Requires Home Assistant 2025.12 or newer. Home Assistant 2026.11 incorporates HACS as **Marketplace** under Settings; existing custom repositories carry over. See the [2026.11 release notes](https://www.home-assistant.io/blog/2026/11/04/release-202611/).

## Installation

1. In Home Assistant 2026.11+, open **Settings > Marketplace**, then **Custom repositories**. On earlier supported versions, open HACS and its Custom repositories menu.
2. Add `https://github.com/TaiPhamD/ha-bluelink` as an **Integration** repository.
3. Find **Bluelink Climate Control** and download it, then restart Home Assistant.
4. Open **Settings > Devices & services > Add integration**, search for **Bluelink Climate Control**, and enter your MyHyundai email, password, and Bluelink remote command PIN.
5. Select your enrolled vehicle. Add the integration again for another vehicle.

For a manual installation, copy `custom_components/bluelink_api_hacs` to `/config/custom_components/bluelink_api_hacs`, restart Home Assistant, and follow step 4.

## Authentication and token expiry

The integration renews an expired token before setup or a climate command, using the refresh token and falling back to account login. Renewed tokens are saved in the existing config entry. A token rejected during a command starts Home Assistant's reauthentication flow; follow the prompt under **Settings > Devices & services**. You can also use **Reconfigure** on the integration entry to update credentials. Both flows retain the same vehicle and entity unique IDs.

**SMS verification is not implemented yet.** MyHyundai website/app 2FA and this integration's USA telematics token endpoint are different login paths. The maintained [Hyundai USA client](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api/blob/master/hyundai_kia_connect_api/HyundaiBlueLinkApiUSA.py) currently uses username/password login and refresh-token exchange. Hyundai's [website login](https://owners.hyundaiusa.com/us/en/login.html) uses device-bound MFA and reCAPTCHA. The integration cannot currently submit website/app SMS codes or exchange those MFA tokens for a telematics token. The remote command PIN field is not an SMS code field.

If integration login fails for an account requiring 2FA, report the error and whether it occurs during initial setup or token renewal. Remove usernames, VINs, passwords, PINs, SMS codes, and tokens from anything you share. For a local check, run `python -m scripts.check_auth` in an environment with Home Assistant installed. It prompts for credentials locally, makes one login request, and prints HTTP status and response field types with all values omitted. It does not send vehicle commands. A verified telematics challenge/verification exchange is needed before direct SMS code entry can be supported.

## Usage

- Set the desired temperature on the climate entity (default 72 °F, range 62–82 °F).
- Turn the climate entity on/off, or use the compatibility switch. Both controls share the same command state.
- Hyundai limits climate sessions to ten minutes. The integration resets its local state after that interval and enforces 60 seconds between commands.
- Commands run outside Home Assistant's event loop. Rejected commands leave the previous state intact and show an error.

The API accepting a command does not confirm that the car completed it. State is assumed from accepted commands; the integration does not poll vehicle status. The target temperature is not a cabin-temperature measurement. Changing the setpoint saves the value for the next start command.

## Updating from 0.1.0

Existing config entries and entity unique IDs are retained. Temperature storage is now per vehicle; the previous shared temperature is copied on first load. The old credential options flow is replaced by **Reconfigure** and native reauthentication. HVAC on/off now sends the remote commands and stays synchronized with the switch.

## Development

Use Python 3.14 for the current test environment:

```sh
uv venv --python 3.14
uv pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

The custom-component pytest harness pins its own Home Assistant version. CI also runs a separate smoke check against the latest Home Assistant release to catch import and lifecycle API changes. Network calls and vehicle commands are mocked in tests; live Hyundai authentication and vehicle operation require account testing.

## Removal

Remove the vehicle integration under **Settings > Devices & services**, then remove the downloaded integration through Marketplace/HACS and restart Home Assistant. To remove saved setpoints, delete only `.storage/bluelink_api_hacs.<entry_id>` for the removed entries while Home Assistant is stopped.
