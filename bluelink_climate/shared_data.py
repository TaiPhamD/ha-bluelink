from homeassistant.helpers.storage import Store
import logging

_LOGGER = logging.getLogger(__name__)
class SharedData:
    def __init__(self, hass):
        self.storage = Store(hass, 1, 'bluelink_climate.json')

    async def load_data(self):
        data = await self.storage.async_load()
        if data:      
            self.temperature = data.get('temperature')
            _LOGGER.info("Bluelink Climate: found previous stored temp: ", self.temperature)
            # Load other data fields as needed
        else:
            _LOGGER.info("Did not find store temperature from storage, setting to default 72 F")
            self.temperature = 72

    async def store_data(self, temperature):
        self.temperature = temperature
        data_to_save = {'temperature': self.temperature}
        # Include other data fields as needed
        await self.storage.async_save(data_to_save)

    def get_data(self):
        return self.temperature
        
