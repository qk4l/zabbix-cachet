import pytest

from zabbix_cachet.zabbix import Zabbix

SERVICE_WITH_DEP_NAME = 'Service with dependencies'
SERVICE_WO_DEP_NAME = 'Single Service'

TRIGGER_ID = '16199'
SERVICES = [
    {'serviceid': '3', 'name': 'Second Service', 'status': '3', 'algorithm': '1', 'triggerid': '0', 'showsla': '0',
     'goodsla': '99.9', 'sortorder': '0',
     'dependencies': [
         {'serviceid': '4', 'name': '1', 'status': '3', 'algorithm': '1', 'triggerid': '16199', 'showsla': '0',
          'goodsla': '99.9', 'sortorder': '0', 'dependencies': []},
         {'serviceid': '5', 'name': '2', 'status': '0', 'algorithm': '1', 'triggerid': '16046', 'showsla': '0',
          'goodsla': '99.9', 'sortorder': '0', 'dependencies': []}]},
    {'serviceid': '2', 'name': 'First Service', 'status': '3', 'algorithm': '1', 'triggerid': '16199', 'showsla': '0',
     'goodsla': '99.9', 'sortorder': '0', 'dependencies': []},
    {'serviceid': '6', 'name': 'Third Service', 'status': '0', 'algorithm': '1', 'triggerid': '0', 'showsla': '0',
     'goodsla': '99.9', 'sortorder': '0', 'dependencies': []}
]


@pytest.fixture(name='zabbix', scope='class')
def zabbix_init(config):

    zabbix_config = config['zabbix']
    setting_config = config['settings']
    zabbix = Zabbix(zabbix_config['server'], zabbix_config['user'], zabbix_config['pass'],
                    zabbix_config['https-verify'])
    root_service = zabbix.zapi.service.get(filter={'name': setting_config['root_service']})
    if not root_service:
        root_service = zabbix.zapi.service.create(
            name=setting_config['root_service'],
            algorithm=0,
            sortorder=0,
            showsla=0,
        )
        root_service_id = root_service['serviceids'][0]
        zabbix.zapi.service.create(
            name=SERVICE_WO_DEP_NAME,
            algorithm=1,
            sortorder=0,
            showsla=0,
            triggerid=TRIGGER_ID,
            parentid=root_service_id
        )
        second_service = zabbix.zapi.service.create(
            name=SERVICE_WITH_DEP_NAME,
            algorithm=1,
            sortorder=0,
            showsla=0,
            parentid=root_service_id,
        )
        second_service_id = second_service['serviceids'][0]
        for service_name in ('dependency1', 'dependency2'):
            zabbix.zapi.service.create(
                name=service_name,
                algorithm=1,
                sortorder=0,
                showsla=0,
                triggerid=TRIGGER_ID,
                parentid=second_service_id,
            )
    return zabbix


def test_get_version(zabbix):
    assert isinstance(zabbix.version, str)


def test_get_itservices(zabbix, config):
    """
    :return:
    """
    it_services = zabbix.get_itservices(config['settings']['root_service'])
    assert len(it_services) == 2
    service_with_dep = it_services[1]
    service_wo_dep = it_services[0]
    assert service_wo_dep.name == SERVICE_WO_DEP_NAME
    assert service_with_dep.name == SERVICE_WITH_DEP_NAME
    assert len(service_wo_dep.children) == 0
    assert len(service_with_dep.children) == 2
    assert service_with_dep.children[0].name == 'dependency1'
    assert service_with_dep.children[1].name == 'dependency2'
    assert service_with_dep.children[1].triggerid == TRIGGER_ID
    # print(it_services)
