# Home-Assistant Custom component  
HA custom component for bluelink climate control. Currently, it has only been tested with an IONIQ 5 (USA). 

## Prerequisites
- https://www.home-assistant.io server installed

## Installation

### Automatic using HACS
- install HACS integration: https://hacs.xyz/docs/setup/download/
- enable HACS integration on in HA assistant. Then add custom repository.
   - Fill out repository url and Category: Integration

   ```
   https://github.com/TaiPhamD/ha-bluelink.git
   ``` 

<img width="512" alt="Screenshot 2023-12-13 at 1 50 52 AM" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/d736b350-81f1-4629-a687-c28f75320103">
<img width="512" alt="Screenshot 2023-12-13 at 1 53 53 AM" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/e6cfef44-a522-4ae2-b622-0767453dda91">


### Manual

Clone this repository then copy the bluelink_api_hacs folder to your home-assistant config/custom_components folder (create a custom_components folder if you don't have one under /config). Restart Home Assistant, and then the integration can be added and configured through the native integration setup UI (search for bluelink).

## Configuration
- The config for this integration requires the following:
    - username: the username of your bluelink account
    - password: the password of your bluelink account
- Once you log in then it will allow you to select a vehicle associated with your account. 

## Usage

1. Setting the Desired Temperature: Adjust the climate control device to your preferred temperature. The default setting is 72°F.
2. Activating Climate Control:
   - To start the climate control, use the provided switch. This will initiate the climate control at the temperature set in step 1.
   - Note that the switch will automatically return to the "off" position in two scenarios:
       - Manually turning it off.
       - Automatically after 10 minutes, as Bluelink's system automatically deactivates climate control after this duration.
   - To ensure smooth operation and prevent errors from Bluelink, the system restricts rapid toggling of the switch. There must be a minimum interval of 60 seconds between each toggle.

## Screenshots


<img width="512" alt="Home Assistant Integration Setup" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/800594f7-6269-4460-b287-952196558c12">



<img width="256" alt="Homekit UI" src="https://github.com/TaiPhamD/ha-bluelink/assets/10516699/5ffca264-9709-4fec-806f-30829abc3b6a">
