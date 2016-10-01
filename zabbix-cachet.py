#!/usr/bin/env python3
"""
This script populated Cachet of Zabbix IT Services
"""
import sys
import os
import datetime
import json
import requests
import time
import threading
import logging
import yaml
from pyzabbix import ZabbixAPI
from operator import itemgetter

__author__ = 'Artem Alexandrov <qk4l()tem4uk.ru>'
__license__ = """The MIT License (MIT)"""
__version__ = '0.1'


def client_http_error(url, code, message):
    logging.error('ClientHttpError[%s, %s: %s]' % (url, code, message))
    sys.exit(1)


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
        if len(zbx_event) > 1:
            return zbx_event[-1]
        return zbx_event

    def get_itservices(self, root=None):
        """
        Return tree of Zabbix IT Services
        root (hidden)
           - service1 (Cachet componentgroup)
             - child_service1 (Cachet component)
             - child_service2 (Cachet component)
           - service2 (Cachet componentgroup)
             - child_service3 (Cachet component)
        :param root: Name of service that will be root of tree.
                    Actually it will not be present in return tree.
                    It's using just as a start point , string
        :return: Tree of Zabbix IT Services, List
        """
        if root:
            root_service = self.zapi.service.get(
                selectDependencies='extend',
                filter={'name': root})
            root_service = root_service[0]
            services = []
            for dependency in root_service['dependencies']:
                services.append(dependency['serviceid'])
            services = self.zapi.service.get(
                selectDependencies='extend',
                serviceids=services)
        else:
            services = self.zapi.service.get(
                selectDependencies='extend',
                output='extend')
        for idx, service in enumerate(services):
            child_services = []
            for dependency in service['dependencies']:
                child_services.append(dependency['serviceid'])
            child_services = self.zapi.service.get(
                    selectDependencies='extend',
                    serviceids=child_services)
            services[idx]['dependencies'] = child_services
        return services


class Cachet:
    def __init__(self, server, token, verify=True):
        """
        Init Cachet class for further needs
        : param server: string
        :param token: string
        :return: object
        """
        self.server = server + '/api/v1/'
        self.token = token
        self.headers = {'X-Cachet-Token': self.token, 'Accept': 'application/json; indent=4'}
        self.verify = verify

    def _http_post(self, url, params):
        """
        Make POST and return json response
        :param url: str
        :param params: dict
        :return: json
        """
        url = self.server + url
        try:
            r = requests.post(url=url, data=params, headers=self.headers, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code != 200:
            return client_http_error(url, r.status_code, r.text)
        data = json.loads(r.text)
        # TODO: check data
        return data

    def _http_get(self, url, params=None):
        """
        Helper for HTTP GET request
        :param: url: str
        :param: params:
        :return: json data
        """
        if params is None:
            params = {}
        url = self.server + url
        try:
            r = requests.get(url=url, headers=self.headers, params=params, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code != 200:
            return client_http_error(url, r.status_code, json.loads(r.text)['errors'])
        data = json.loads(r.text)
        # TODO: check data
        return data

    def _http_put(self, url, params):
        """
        Make PUT and return json response
        :param url: str
        :param params: dict
        :return: json
        """
        url = self.server + url
        try:
            r = requests.put(url=url, json=params, headers=self.headers, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code != 200:
            return client_http_error(url, r.status_code, r.text)
        data = json.loads(r.text)
        # TODO: check data
        return data

    def get_component(self, id):
        """
        Get component params based its id
        @param id: string
        @return: dict
        """
        url = 'components/' + str(id)
        data = self._http_get(url)
        return data

    def get_components(self, name=None):
        """
        Get all registered components or return a component details if name specified
        @param name: string
        @return: dict of data or list
        """
        url = 'components'
        data = self._http_get(url)
        if name:
            components = {'data': []}
            for component in data['data']:
                if component['name'] == name:
                    components['data'].append(component)
            if len(components['data']) < 1:
                return {'id': 0, 'name': 'Does not exists'}
            elif len(components['data']) == 1:
                return components['data'][0]
        return data

    def new_components(self, name, **kwargs):
        """
        Create new components
        @param name: string
        @param kwargs: various additional values =)
        @return: dict of data
        """
        # Get values for new component
        params = {'name': name, 'link': '', 'description': '', 'status': '1', 'group_id': 0}
        params.update(kwargs)
        # Check if components with same name already exists in same group
        component = self.get_components(name)
        # There are more that one component with same name already
        if 'data' in component:
            for i in component['data']:
                if i['group_id'] == params['group_id']:
                    return i
            else:
                component = {'id': 0}
        # print(component['name'], component['id'], component['group_id'], params['group_id'])
        # Create component if it does not exist or exist in other group
        if component['id'] == 0 or component['group_id'] != params['group_id']:
            url = 'components'
            # params = {'name': name, 'link': link, 'description': description, 'status': status}
            data = self._http_post(url, params)
            logging.info('Component {name} was created in group id {group_id}.'.format(name=params['name'],
                                                                                       group_id=data['data'][
                                                                                           'group_id']))
            return data['data']
        else:
            return component

    def upd_components(self, id, **kwargs):
        """
        Update component
        @param id: string
        @param kwargs: various additional values =)
        @return: boolean
        """
        url = 'components/' + str(id)
        params = self.get_component(id)['data']
        params.update(kwargs)
        data = self._http_put(url, params)
        logging.info('Component {name} (id={id}) was updated. Status - {status}'.format(
            name=data['data']['name'],
            id=id,
            status=data['data']['status_name']))
        return data

    def get_components_gr(self, name=None):
        """
        Get all registered components group or return a component group details if name specified
        @param name: string
        @return: dict of data
        """
        url = 'components/groups'
        data = self._http_get(url)
        if name:
            for group in data['data']:
                if group['name'] == name:
                    return group
            else:
                return {'id': 0, 'name': 'Does not exists'}
        return data

    def new_components_gr(self, name):
        """
        Create new components group
        @param name: string
        @return: dict of data
        """
        # Check if component's group already exists
        componenets_gr_id = self.get_components_gr(name)
        if componenets_gr_id['id'] == 0:
            url = 'components/groups'
            # TODO: make if possible to configure default collapsed value
            params = {'name': name, 'collapsed': 2}
            data = self._http_post(url, params)
            logging.info('Component Group {} was created.'.format(params['name']))
            return data['data']
        else:
            return componenets_gr_id

    def get_incident(self, component_id):
        """
        Get last incident for component_id
        @param component_id: string
        @return: dict of data
        """
        # TODO: make search by name
        url = 'incidents'
        data = self._http_get(url)
        total_pages = int(data['meta']['pagination']['total_pages'])
        for page in range(total_pages, 0, -1):
            data = self._http_get(url, params={'page': page})
            data_sorted = sorted(data['data'], key=itemgetter('id'), reverse=True)
            for incident in data_sorted:
                if str(incident['component_id']) == str(component_id):
                    # Convert status to str
                    incident['status'] = str(incident['status'])
                    return incident
        return {'id': '0', 'name': 'Does not exist', 'status': '-1'}

    def new_incidents(self, **kwargs):
        """
        Create a new incident.
        @param kwargs: various additional values =)
                        name, message, status,
                        component_id, component_status
        @return: dict of data
        """
        params = {'visible': 1, 'notify': 'true'}
        url = 'incidents'
        params.update(kwargs)
        data = self._http_post(url, params)
        logging.info('Incident {name} (id={incident_id}) was created for component id {component_id}.'.format(
            name=params['name'],
            incident_id=data['data']['id'],
            component_id=params['component_id']))
        return data['data']

    def upd_incident(self, id, **kwargs):
        """
        Update incident
        @param id: string
        @param kwargs: various additional values =)
                message, status,
                component_status
        @return: boolean
        """
        url = 'incidents/' + str(id)
        params = kwargs
        data = self._http_put(url, params)
        logging.info('Incident ID {id} was updated. Status - {status}.'.format(id=id,
                                                                               status=data['data']['human_status']))
        return data


def triggers_watcher(service_map):
    """
    Check zabbix triggers and update Cachet components
    Zabbix Priority:
        0 - (default) not classified;
        1 - information;
        2 - warning;
        3 - average;
        4 - high;
        5 - disaster.
    Cachet Incident Statuses:
        0 - Scheduled - This status is used for a scheduled status.
        1 - Investigating - You have reports of a problem and you're currently looking into them.
        2 - Identified - You've found the issue and you're working on a fix.
        3 - Watching - You've since deployed a fix and you're currently watching the situation.
        4 - Fixed
    @param service_map: list of tuples
    @return: boolean
    """
    for i in service_map:
        # inc_status = 1
        # comp_status = 1
        # inc_name = ''
        inc_msg = ''

        if 'triggerid' in i:
            trigger = zapi.get_trigger(i['triggerid'])
            # Check if incident already registered
            # Trigger non Active
            if str(trigger['value']) == '0':
                component_status = cachet.get_component(i['component_id'])['data']['status']
                # And component in operational mode
                if str(component_status) == '1':
                    continue
                else:
                    # And component not operational mode
                    last_inc = cachet.get_incident(i['component_id'])
                    # print(last_inc)
                    if str(last_inc['id']) != '0':
                        cachet.upd_incident(last_inc['id'], status=4, component_id=i['component_id'],
                                            component_status=1)
                    # Incident does not exist. Just change component status
                    else:
                        cachet.upd_components(i['component_id'], status=1)
                    continue
            # Trigger in Active state
            elif trigger['value'] == '1':
                zbx_event = zapi.get_event(i['triggerid'])
                inc_name = trigger['description']
                if zbx_event['acknowledged'] == '1':
                    inc_status = 2
                    for msg in zbx_event['acknowledges']:
                        # TODO: Add timezone?
                        #       Move format to config file
                        ack_time = datetime.datetime.fromtimestamp(int(msg['clock'])).strftime('%b %d, %H:%M')
                        inc_msg += '{message} \n###### {ack_time} {name} {surname}\n'.format(
                                ack_time=ack_time, name=msg['name'],
                                surname=msg['surname'], message=msg['message'])
                else:
                    inc_status = 1
                if int(trigger['priority']) >= 4:
                    comp_status = 4
                elif int(trigger['priority']) == 3:
                    comp_status = 3
                else:
                    comp_status = 2

                if not inc_msg and trigger['comments']:
                    inc_msg = trigger['comments']
                elif not inc_msg:
                    inc_msg = trigger['description']
                if 'group_name' in i:
                    inc_name = i['group_name'] + ' | ' + inc_name

                last_inc = cachet.get_incident(i['component_id'])
                # Incident not registered
                if last_inc['status'] in ('-1', '4'):
                    # TODO: added incident_date
                    # incident_date = datetime.datetime.fromtimestamp(int(trigger['lastchange'])).strftime('%d/%m/%Y %H:%M')
                    cachet.new_incidents(name=inc_name, message=inc_msg, status=inc_status,
                                         component_id=i['component_id'], component_status=comp_status)

                # Incident already registered
                elif last_inc['status'] not in ('-1', '4'):
                    # Only incident message can change. So check if this have happened
                    if last_inc['message'].strip() != inc_msg.strip():
                        cachet.upd_incident(last_inc['id'], message=inc_msg, status=inc_status,
                                            component_status=comp_status)

        else:
            # TODO: ServiceID
            inc_msg = 'TODO: ServiceID'
            continue

    return True


def triggers_watcher_worker(service_map, interval, e):
    """
    Worker for triggers_watcher. Run it continuously with specific interval
    @param service_map: list of tuples
    @param interval: interval in seconds
    @param e: treading.Event object
    @return:
    """
    logging.info('start trigger watcher')
    while not e.is_set():
        logging.debug('check Zabbix triggers')
        triggers_watcher(service_map)
        time.sleep(interval)
    logging.info('end trigger watcher')


def init_cachet(services):
    """
    Init Cachet by syncing Zabbix service to it
    Also func create mapping batten Cachet components and Zabbix IT services
    @param services: list
    @return: list of tuples
    """
    # Zabbix Triggers to Cachet components id map
    data = []
    for zbx_service in services:
        # Check if zbx_service has childes
        zxb2cachet_i = {}
        if zbx_service['dependencies']:
            group = cachet.new_components_gr(zbx_service['name'])
            for dependency in zbx_service['dependencies']:
                # Component without trigger
                if int(dependency['triggerid']) != 0:
                    trigger = zapi.get_trigger(dependency['triggerid'])
                    component = cachet.new_components(dependency['name'], group_id=group['id'],
                                                      link=trigger['url'], description=trigger['description'])
                    # Create a map of Zabbix Trigger <> Cachet IDs
                    zxb2cachet_i = {'triggerid': dependency['triggerid']}
                else:
                    component = cachet.new_components(dependency['name'], group_id=group['id'])
                    zxb2cachet_i = {'serviceid': dependency['serviceid']}
                zxb2cachet_i.update({'group_id': group['id'],
                                     'group_name': group['name'],
                                     'component_id': component['id'],
                                     'component_name': component['name']
                                     })
                data.append(zxb2cachet_i)
        else:
            # Component with trigger
            if zbx_service['triggerid']:
                trigger = zapi.get_trigger(zbx_service['triggerid'])
                component = cachet.new_components(zbx_service['name'], link=trigger['url'],
                                                  description=trigger['description'])
                # Create a map of Zabbix Trigger <> Cachet IDs
                zxb2cachet_i = {'triggerid': zbx_service['triggerid'],
                                'component_id': component['id'],
                                'component_name': component['name']}
            data.append(zxb2cachet_i)
    return data


def read_config(config_f):
    """
    Read config file
    @param config_f: strung
    @return: dict of data
    """
    config = yaml.load(open(config_f, "r"))
    return config


if __name__ == '__main__':
    if os.getenv('CONFIG_FILE') is not None:
        CONFIG_F = os.environ['CONFIG_FILE']
    else:
        CONFIG_F = os.path.dirname(os.path.realpath(__file__)) + '/config.yml'
    config = read_config(CONFIG_F)
    ZABBIX = config['zabbix']
    CACHET = config['cachet']
    SETTINGS = config['settings']
    exit_status = 0
    # Set Logging
    log_level = logging.getLevelName(SETTINGS['log_level'])
    log_level_requests = logging.getLevelName(SETTINGS['log_level_requests'])
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s: (%(threadName)s) %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )
    logging.getLogger("requests").setLevel(log_level_requests)
    logging.info('Zabbix Cachet v.{} started'.format(__version__))
    inc_update_t = threading.Thread()
    event = threading.Event()
    try:
        zapi = Zabbix(ZABBIX['server'], ZABBIX['user'], ZABBIX['pass'], ZABBIX['https-verify'])
        cachet = Cachet(CACHET['server'], CACHET['token'], CACHET['https-verify'])
        zbxtr2cachet = ''
        while True:
            itservices = (zapi.get_itservices(SETTINGS['root_service']))
            # Create Cachet components and components groups
            zbxtr2cachet_new = init_cachet(itservices)
            # Restart triggers_watcher_worker
            if zbxtr2cachet != zbxtr2cachet_new:
                zbxtr2cachet = zbxtr2cachet_new
                logging.info('Restart triggers_watcher worker')
                logging.debug('List of watching triggers {}'.format(str(zbxtr2cachet)))
                event.set()
                # Wait until tread die
                while inc_update_t.is_alive():
                    time.sleep(1)
                event.clear()
                inc_update_t = threading.Thread(name='Trigger Watcher',
                                                target=triggers_watcher_worker,
                                                daemon=True,
                                                args=(zbxtr2cachet, SETTINGS['update_inc_interval'], event))
                inc_update_t.start()
            time.sleep(SETTINGS['update_comp_interval'])

    except KeyboardInterrupt:
        event.set()
        logging.info('Shutdown requested. See you.')
    except Exception as e:
        logging.error(e)
        exit_status = 1
    sys.exit(exit_status)
