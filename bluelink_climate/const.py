# custom_components/bluelink_climate/const.py

DOMAIN = "bluelink_climate"

# max bluelink climate control can run is 10 minutes (600 seconds)
BLUELINK_CLIMATE_MAX_TIMER = 600

# prevent bluelink switch from toggle too quick (Hyundai's API will reject if calling it in quick successions)
BLUELINK_SWITCH_TOGGLE_TIMEOUT = 60  