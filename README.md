# Home-Assistant Custom component  
HA custom component for bluelink climate control. Currently, it has only been tested with an IONIQ 5 (USA). 

## Prerequisites
- https://www.home-assistant.io server installed

## Install HA custom component

Clone this repository then copy the bluelink_api_hacs folder to your home-assistant config/custom_components folder (create a custom_components folder if you don't have one under /config). Restart Home Assistant, and then the integration can be added and configured through the native integration setup UI (search for bluelink).

- The config for this integration requires the following:
    - username: the username of your bluelink account
    - password: the password of your bluelink account
    - pin: the pin of your bluelink account
    - vin: the vin of your vehicle
 

## Screenshots


<img width="512" alt="Home Assistant Integration Setup" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/800594f7-6269-4460-b287-952196558c12">



<img width="256" alt="Homekit UI" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/5ffca264-9709-4fec-806f-30829abc3b6a">
