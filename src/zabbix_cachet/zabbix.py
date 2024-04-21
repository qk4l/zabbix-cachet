import sys
from dataclasses import dataclass, field
from typing import List, Dict, Union

import requests
import logging
from pyzabbix import ZabbixAPI, ZabbixAPIException

from zabbix_cachet.excepltions import InvalidConfig


def pyzabbix_safe(fail_result=False):

    def wrap(func):
        def wrapperd_f(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (requests.ConnectionError, ZabbixAPIException) as e:
                logging.error('Zabbix Error: {}'.format(e))
                return fail_result
        return wrapperd_f
    return wrap


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


@dataclass
class ZabbixService:
    name: str
    serviceid: str
    status: str
    algorithm: str
    triggerid: str = None
    children: List['ZabbixService'] = field(default_factory=list)
    # TODO: Change to parents in future if will needed
    is_parents: bool = False

    def __repr__(self):
        return f"ZabbixITService with {self.name} in status {self.status}"


class Zabbix:
    def __init__(self, server, user, password, verify=True):
        """
        Init zabbix class for further needs
        :param user: string
        :param password: string
        :return: pyzabbix object
        """
        self.server = server
        self.user = user
        self.password = password
        # Enable HTTP auth
        s = requests.Session()
        s.auth = (user, password)

        self.zapi = ZabbixAPI(server, s)
        self.zapi.session.verify = verify
        self.zapi.login(user, password)
        self.version = self.get_version()
        # Zabbix made significant changes in 6.0 https://support.zabbix.com/browse/ZBXNEXT-6674
        try:
            self.version_major = int(self.version.split('.')[0])
            if self.version_major >= 6:
                self.get_service = self.get_service
            else:
                self.get_service = self.get_service_legacy
        except (TypeError, IndexError) as err:
            logging.error(f"Failed to compare major Zabbix version - {self.version}: {err}")
            sys.exit(1)

    @pyzabbix_safe()
    def get_version(self):
        """
        Get Zabbix API version.
        This method is using to check if Zabbix is available
        :return: str
        """
        version = self.zapi.apiinfo.version()
        return version

    @pyzabbix_safe({})
    def get_trigger(self, triggerid):
        """
        Get trigger information
        @param triggerid: string
        @return: dict of data
        """
        trigger = self.zapi.trigger.get(
            expandComment='true',
            expandDescription='true',
            triggerids=triggerid)
        return trigger[0]

    @pyzabbix_safe({})
    def get_event(self, triggerid):
        """
        Get event information based on triggerid
        @param triggerid: string
        @return: dict of data
        """
        zbx_event = self.zapi.event.get(
            select_acknowledges='extend',
            expandDescription='true',
            object=0,
            value=1,
            objectids=triggerid)
        if len(zbx_event) >= 1:
            return zbx_event[-1]
        return zbx_event

    def get_service(self, name: str = '', serviceid: Union[List, str] = None,
                    parentids: str = '') -> List[Dict]:
        """
        For zabbix 6.0 +
        https://www.zabbix.com/documentation/6.0/en/manual/appendix/services_upgrade
        :return:
        """
        if name:
            services = self.zapi.service.get(selectChildren='extend', filter={'name': name})
        elif serviceid:
            services = self.zapi.service.get(selectChildren='extend', serviceids=serviceid)
        elif parentids:
            services = self.zapi.service.get(selectChildren='extend', parentids=parentids)
        else:
            services = self.zapi.service.get(selectChildren='extend')

        return services

    def get_service_legacy(self, name: str = '', serviceid: Union[List, str] = None,
                           parentids: str = '') -> List[Dict]:
        """
        For old zabbix before 6.0
        :return:
        """
        if name:
            services = self.zapi.service.get(selectDependencies='extend', selectParentDependencies='extend',
                                             filter={'name': name})
        elif serviceid:
            services = self.zapi.service.get(selectDependencies='extend', selectParentDependencies='extend',
                                             serviceids=serviceid)
        elif parentids:
            services = self.zapi.service.get(selectDependencies='extend', selectParentDependencies='extend',
                                             parentids=parentids)
        else:
            services = self.zapi.service.get(selectDependencies='extend', selectParentDependencies='extend')
        for service in services:
            service['children'] = service.pop('dependencies')
            service['parents'] = service.pop('parentDependencies')
        return services

    def _init_zabbix_it_service(self, data: Dict) -> ZabbixService:
        """
        Create ZabbixITService from data returned by service.get
        :param data: Service object
            https://www.zabbix.com/documentation/current/en/manual/api/reference/service/object
        """
        logging.debug(f"Init ZabbixITService for {data.get('name')} ")
        zabbix_it_service = ZabbixService(name=data.get('name'),
                                          serviceid=data.get('serviceid'),
                                          # TODO: Change for zbx 6
                                          triggerid=data.get('triggerid', None),
                                          algorithm=data.get('algorithm'),
                                          status=data.get('status'))
        if 'parents' in data:
            zabbix_it_service.is_parents = True
        if 'children' in data:
            child_services = self.get_service(parentids=zabbix_it_service.serviceid)
            zabbix_it_service.children.extend(map(self._init_zabbix_it_service, child_services))
        return zabbix_it_service

    @pyzabbix_safe([])
    def get_itservices(self, root_name: str = None) -> List[ZabbixService]:
        """
        Return tree of Zabbix IT Services
        root (hidden)
           - service1 (Cachet componentgroup)
             - child_service1 (Cachet component)
             - child_service2 (Cachet component)
           - service2 (Cachet componentgroup)
             - child_service3 (Cachet component)
        :param root_name: Name of service that will be root of tree.
                    Actually it will not be present in return tree.
                    It's using just as a start point , string
        :return: Tree of Zabbix IT Services
        :rtype: list
        """
        monitor_services = []
        if root_name:
            root_service = self.get_service(root_name)
            if not len(root_service) == 1:
                logging.error(f'Can not find uniq "{root_name}" service in Zabbix')
                sys.exit(1)
            monitor_services = self._init_zabbix_it_service(root_service[0]).children
        else:
            if self.version_major < 6:
                services = self.get_service()
                for i in services:
                    # Do not proceed non-root services directly
                    if len(i['parents']) == 0:
                        monitor_services.append(self._init_zabbix_it_service(i))
            else:
                raise InvalidConfig(f"settings.root_service should be defined in you config yaml file because "
                                    f"you use Zabbix version {self.version}")
        return monitor_services

