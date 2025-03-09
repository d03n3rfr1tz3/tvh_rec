# -*- coding: utf-8 -*-

import sys
import time
import requests
import simplejson as j

def fetch_data(a, url, recs):
  d = {
    'start': 0,
    'limit': recs,
    'sort': 'start_real',
    'dir': 'ASC',
    'groupBy': 'false',
    'groupDir': 'ASC',
    'duplicates': 0
  }

  r = requests.post('%s/api/dvr/entry/grid_upcoming' % url, data=d, auth=a)

  if not r.ok:
    return {'status': requests.status_codes._codes[r.status_code][0]}

  s = {
    'count': r.json()['total'],
    'recordings': [],
    'status': 'idle'
  }

  if r.json()['entries']:
    ispreparing = False
    isrecording = False
    currenttime = time.time()
    
    for e in r.json()['entries']:
      if currenttime >= (e.get('start_real') - 300) and currenttime <= (e.get('stop_real') + 300):
        ispreparing = True
      
      if currenttime >= e.get('start_real') and currenttime <= e.get('stop_real'):
        isrecording = True
      
      _s = {
        'status': e.get('status'),
        'channelname': e.get('channelname'),
        'title': e.get('disp_title'),
        'subtitle': e.get('disp_subtitle'),
        'channel_icon': e.get('channel_icon'),
        'start': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('start'))),
        'start_real': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('start_real'))),
        'stop': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('stop'))),
        'stop_real': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('stop_real'))),
        'duration': e.get('duration'),
                                              
        'image': e.get('image'),
      }
      s['recordings'].append(_s)
    
    if ispreparing:
      s['status'] = 'preparing'
    
    if isrecording:
      s['status'] = 'recording'

  return s

if __name__ == '__main__':
  if len(sys.argv) != 4:
    print ('Usage %s <user> <pass> <url>' % sys.argv[0])
    sys.exit(1)
  d = fetch_data(requests.auth.HTTPDigestAuth(sys.argv[1], sys.argv[2]), sys.argv[3], 3)
  print (d)
  sys.exit(0)
else:
  import logging
  import voluptuous as vol
  import homeassistant.helpers.config_validation as cv
  from datetime import timedelta
  from homeassistant.helpers.entity import Entity
  from homeassistant.components.sensor import PLATFORM_SCHEMA
  from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME,
    CONF_URL, CONF_USERNAME, CONF_PASSWORD
  )

  _LOGGER = logging.getLogger(__name__)

  CONF_REC_COUNT = 'count'
  CONF_ATTRIBUTION = 'tvheadend'
  ICON = 'mdi:record-rec'
  SCAN_INTERVAL = timedelta(seconds=300)
  DEFAULT_NAME = 'hts'

  PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_REC_COUNT, default=1): cv.positive_int,
  })

  def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HtsSensor sensor."""
    add_entities([
        HtsSensor(
            config.get(CONF_URL),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            config.get(CONF_NAME),
            config.get(CONF_REC_COUNT),
        ),
    ])

  class HtsSensor(Entity):
    """Representation of a hts sensor."""

    def __init__(self, url, usr, passwd, name, cnt):
      """Initialize the sensor."""
      self._url = url
      self._fetch = fetch_data
      self._name = name
      self._cnt = cnt
      self._auth = requests.auth.HTTPDigestAuth(usr, passwd)
      self._data = {
        'count': 0,
        'recordings': [],
        'status': 'initializing'
      }
      
      try:
        self._data = self._fetch(self._auth, self._url, self._cnt)
        _LOGGER.debug("Data = %s", self._data)
      except requests.exceptions.ConnectionError:
        if self._data['status'] != 'initializing': self._data['status'] = 'offline'
        _LOGGER.error("Could not connect to tvheadend")

    @property
    def should_poll(self):
      """No polling needed for a demo sensor."""
      return True

    @property
    def name(self):
      """Return the name of the sensor."""
      return self._name

    @property
    def state(self):
      """Return the state of the sensor."""
      if self._data['status'] != 'idle' and self._data['status'] != 'preparing' and self._data['status'] != 'recording' and self._data['status'] != 'offline':
        return None;
      
      return str(self._data['count'])

    @property
    def unit_of_measurement(self):
      """Return the unit this state is expressed in."""
      return 'recs'

    @property
    def icon(self):
      """Return icon."""
      return ICON

    @property
    def extra_state_attributes(self):
      """Return the state attributes."""
      attr = {
        ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        'url': self._url,
      }

      _data = self._data
      attr['count'] = _data['count']
      attr['status'] = _data['status']
      
      for i, d in enumerate(_data['recordings']):
        recording = {
          'status': d['status'],
          'title': d['title'],
          'subtitle': d['subtitle'],
          'channelname': d['channelname'],
          'channel_icon': self._url + '/' + d['channel_icon'],
          'start': d['start'],
          'start_real': d['start_real'],
          'stop': d['stop'],
          'stop_real': d['stop_real'],
          'duration': d['duration'],
        }

        if d['image']:
          recording['image'] = self._url + '/' + d['image']
        else:
          recording['image'] = self._url + '/' + d['channel_icon']
        
        attr['recording' + str(i)] = recording

      return attr

    def update(self):
      """Get the latest data from MeteoAlarm API."""
      try:
        self._data = self._fetch(self._auth, self._url, self._cnt)
        _LOGGER.debug("Data = %s", self._data)
      except requests.exceptions.ConnectionError:
        if self._data['status'] != 'initializing': self._data['status'] = 'offline'
        _LOGGER.error("Could not connect to tvheadend")
      except ValueError as err:
        _LOGGER.error("Check tvh %s", err.args)
        raise
