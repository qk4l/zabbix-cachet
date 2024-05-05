import os
import pytest as pytest

from zabbix_cachet.main import read_config

CONFIG_FILE = os.getenv("CONFIG_FILE")


@pytest.fixture(name='config', scope='module')
def zabbix_cachet_read_config():
    return read_config(CONFIG_FILE)
