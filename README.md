# Home-Assistant Custom component  
HA custom component for bluelink climate control. This is to be used with: https://github.com/TaiPhamD/bluelink_proxy_server. It currently only supports Farenheit in the controls which I plan to add support for changing to Celsius in the future.

## Prerequisites
- setup [blue link proxy](https://github.com/TaiPhamD/bluelink_proxy_server) with a valid SSL cert (no self signed)

## Install HA custom component

Clone this repository then copy the bluelink_climate folder to your home-assistant config/custom_components folder (create one if you don't have one under /config). Restart Home Assistant, and then the integration can be added and configured through the native integration setup UI (search for bluelink).

- The config for this integration requires the following:
    - host: the hostname of the blue link proxy server
    - port: the port of the blue link proxy server
    - api_key: the api key of the blue link proxy server


