import sys
import logging

from dataclasses import dataclass, field
from typing import List, Dict, Union

import requests

import urllib3
from pyzabbix import ZabbixAPI, ZabbixAPIException

from zabbix_cachet.excepltions import InvalidConfig, ZabbixNotAvailable, ZabbixCachetException, ZabbixServiceNotFound


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


@dataclass
class ZabbixService:
    name: str
    serviceid: str
    status: int
    zabbix_version_major: int
    triggerid: str = None
    children: List['ZabbixService'] = field(default_factory=list)
    problem_tags: List[dict] = field(default_factory=list)
    description: str = ''
    # TODO: Change to parents in future if will needed
    is_parents: bool = False

    def __repr__(self):
        if self.is_status_ok:
            status_str = 'OK'
        else:
            status_str = 'Failed'
        return f"ZabbixITService {self.name} in status {status_str} ({self.status})"

    @property
    def is_status_ok(self) -> bool:
        if self.zabbix_version_major < 6:
            if self.status == 0:
                return True
        else:
            if self.status == -1:
                return True
        return False


class Zabbix:
    def __init__(self, server: str, user: str, password: str, verify: bool = True):
        """
        Init zabbix class for further needs
        :return: pyzabbix object
        """
        self.server = server
        self.user = user
        self.password = password
        # Enable basic HTTP auth, some installations can use it
        # s = requests.Session()
        # s.auth = (user, password)
        # self.zapi = ZabbixAPI(server, s)

        self.zapi = ZabbixAPI(server)
        self.zapi.session.verify = verify
        if not verify:
            urllib3.disable_warnings()
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
    def get_trigger(self, triggerid: str = '', tags: List = None) -> List[dict]:
        """
        Get trigger information by trigger_id or tags
        https://www.zabbix.com/documentation/6.0/en/manual/api/reference/trigger/get
        """
        if triggerid:
            trigger = self.zapi.trigger.get(
                expandComment='true',
                expandDescription='true',
                triggerids=triggerid)
        else:
            trigger = self.zapi.trigger.get(
                expandComment='true',
                expandDescription='true',
                tags=tags,
                only_true=True)
        return trigger

    @pyzabbix_safe({})
    def get_event(self, triggerid):
        """
        https://www.zabbix.com/documentation/current/en/manual/api/reference/event/get
        Get event information based on triggerid
        @param triggerid: string
        @return: dict of data
        """
        zbx_event = self.zapi.event.get(
            select_acknowledges='extend',
            object=0,
            value=1,
            objectids=triggerid,
            sortfield=['clock']
        )
        if len(zbx_event) >= 1:
            return zbx_event[-1]
        return zbx_event

    @pyzabbix_safe([])
    def get_service(self, name: str = '', serviceid: Union[List, str] = None,
                    parentids: str = '') -> List[Dict]:
        """
        For zabbix 6.0 +
        https://www.zabbix.com/documentation/6.0/en/manual/appendix/services_upgrade
        :return:
        """
        query = {
            'output': 'extend',
            'selectChildren': 'extend',
            'selectProblemTags': 'extend',
        }
        if name:
            services = self.zapi.service.get(**query, filter={'name': name})
        elif serviceid:
            services = self.zapi.service.get(**query, serviceids=serviceid)
        elif parentids:
            services = self.zapi.service.get(**query, parentids=parentids)
        else:
            services = self.zapi.service.get(**query)
        return services

    @pyzabbix_safe([])
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
                                          zabbix_version_major=self.version_major,
                                          description=data.get('description', ''),
                                          status=int(data.get('status')),
                                          # Does not support by Zbx < 6.0
                                          problem_tags=data.get('problem_tags', []),
                                          # Does not support by Zbx 6.0+
                                          triggerid=data.get('triggerid', None),
                                          )
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
            if not self.get_version():
                raise ZabbixNotAvailable('Zabbix is not available...')
            root_service = self.get_service(root_name)
            if not len(root_service) == 1:
                raise ZabbixCachetException(f'Can not find uniq "{root_name}" service in Zabbix')
            monitor_services = self._init_zabbix_it_service(root_service[0]).children
        else:
            if self.version_major >= 6:
                services = self.get_service()
                for i in services:
                    if len(i['children']) > 0:
                        monitor_services.append(self._init_zabbix_it_service(i))
            elif self.version_major < 6:
                services = self.get_service()
                for i in services:
                    # Do not proceed non-root services directly
                    if len(i['parents']) == 0:
                        monitor_services.append(self._init_zabbix_it_service(i))
            else:
                raise InvalidConfig(f"settings.root_service should be defined in you config yaml file because "
                                    f"you use Zabbix version {self.version}")
        return monitor_services

    def get_zabbix_service(self, serviceid: str) -> ZabbixService:
        """
        Method which primary should be used in zabbix-cachet code
        :param serviceid:
        :return:
        """
        service = self.get_service(serviceid=serviceid)
        if len(service) < 1:
            raise ZabbixServiceNotFound(f"No one service returned by serviceid - {serviceid}")
        return self._init_zabbix_it_service(service[0])
