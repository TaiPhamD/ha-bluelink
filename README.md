# Home-Assistant Custom component  
HA custom component for bluelink climate control. This is to be used with: https://github.com/TaiPhamD/bluelink_proxy_server. It currently only supports Farenheit in the controls which I plan to add support for changing to Celsius in the future.

## Installation
- setup [blue link proxy](https://github.com/TaiPhamD/bluelink_proxy_server) with a valid SSL cert (no self signed)
- Install this HA custom component and fill out the config:
    - host: the hostname of the blue link proxy server
    - port: the port of the blue link proxy server
    - api_key: the api key of the blue link proxy server


