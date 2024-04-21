import pytest
import logging

from zabbix_cachet.zabbix import Zabbix

SERVICE_WITH_DEP_NAME = 'Service with dependencies'
SERVICE_WO_DEP_NAME = 'Single Service'
SERVICE_SEPARATE_ROOT = 'Separate service under root'

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

log_level = logging.getLevelName('DEBUG')
log_level_requests = logging.getLevelName('DEBUG')
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s: (%(threadName)s) %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S %Z'
)
logging.getLogger("requests").setLevel(log_level_requests)


@pytest.fixture(name='zabbix', scope='class')
def zabbix_init(config):

    zabbix_config = config['zabbix']
    setting_config = config['settings']
    zabbix = Zabbix(zabbix_config['server'], zabbix_config['user'], zabbix_config['pass'],
                    zabbix_config['https-verify'])
    root_service = zabbix.zapi.service.get(filter={'name': setting_config['root_service']})
    root_separate = zabbix.zapi.service.get(filter={'name': SERVICE_SEPARATE_ROOT})

    zabbix_service_template = {'name': '', 'algorithm': 0, 'sortorder': 0}
    if not root_separate:
        service = dict.copy(zabbix_service_template)
        service.update({'name': SERVICE_SEPARATE_ROOT})
        if zabbix.version_major < 6:
            service.update({'showsla': 0})
        zabbix.zapi.service.create(**service)

    if not root_service:
        # root_service
        service = dict.copy(zabbix_service_template)
        service.update({'name': setting_config['root_service']})
        if zabbix.version_major < 6:
            service.update({'showsla': 0})
        root_service = zabbix.zapi.service.create(**service)
        root_service_id = int(root_service['serviceids'][0])

        # SERVICE_WO_DEP_NAME
        service = dict.copy(zabbix_service_template)
        service.update({'name': SERVICE_WO_DEP_NAME})
        if zabbix.version_major < 6:
            service.update({'showsla': 0, 'triggerid': TRIGGER_ID, 'parentid': str(root_service_id)})
        else:
            service.update({
                'parents': [{'serviceid': root_service_id}],
                'problem_tags': [{'tag': 'scope', 'value': 'availability'}],
            })
        a = zabbix.zapi.service.create(**service)
        print(a)
        # SERVICE_WITH_DEP_NAME
        service = dict.copy(zabbix_service_template)
        service.update({'name': SERVICE_WITH_DEP_NAME})
        if zabbix.version_major < 6:
            service.update({'showsla': 0, 'parentid': str(root_service_id)})
        else:
            service.update({'parents': [{'serviceid': root_service_id}]})

        second_service = zabbix.zapi.service.create(**service)
        second_service_id = int(second_service['serviceids'][0])

        # Dependency services
        for service_name in ('dependency1', 'dependency2'):
            service = dict.copy(zabbix_service_template)
            service.update({'name': service_name})
            if zabbix.version_major < 6:
                service.update({'showsla': 0, 'triggerid': TRIGGER_ID, 'parentid': str(second_service_id)})
            else:
                service.update({
                    'parents': [{'serviceid': second_service_id}],
                    'problem_tags': [{'tag': 'scope', 'value': 'availability'}],
                })
            zabbix.zapi.service.create(**service)

    return zabbix


def test_get_version(zabbix):
    assert isinstance(zabbix.version, str)


def test_get_itservices_with_root(zabbix, config):
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
    if zabbix.version_major < 6:
        assert service_with_dep.children[1].triggerid == TRIGGER_ID
    # print(it_services)


def test_get_itservices_wo_root(zabbix, config):
    # Not supported after 6.0
    if zabbix.version_major >= 6:
        return True
    it_services = zabbix.get_itservices()
    assert len(it_services) == 2
    service_cachet = it_services[1]
    service_separate = it_services[0]
    assert service_cachet.name == config['settings']['root_service']
    assert service_separate.name == SERVICE_SEPARATE_ROOT
    assert len(service_cachet.children) == 2
    assert len(service_separate.children) == 0
