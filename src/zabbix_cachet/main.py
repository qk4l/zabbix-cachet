#!/usr/bin/env python3
"""
This script populated Cachet of Zabbix IT Services
"""
import sys
import os
import datetime
import json
from typing import List, Dict, Union, Any

import requests
import time
import threading
import logging
import yaml
import pytz
from operator import itemgetter

__author__ = 'Artem Alexandrov <qk4l()tem4uk.ru>'
__license__ = """The MIT License (MIT)"""
__version__ = '2.0.0'

from zabbix_cachet.zabbix import Zabbix, ZabbixService


def client_http_error(url, code, message):
    logging.error('ClientHttpError[%s, %s: %s]' % (url, code, message))


class CachetApiException(Exception):
    def __init__(self, message=None, errors=None):
        if errors:
            message = ', '.join(errors)
        self.errors = errors
        if message:
            logging.error(repr(message).rstrip())
        super(Exception, self).__init__(message)


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
        self.version = self.get_version()

    def _http_post(self, url, params):
        """
        Make POST and return json response
        :param url: str
        :param params: dict
        :return: json
        """
        url = self.server + url
        logging.debug("Sending to {url}: {param}".format(url=url,
                                                         param=json.dumps(params,
                                                                          indent=4,
                                                                          separators=(',', ': '))))
        try:
            r = requests.post(url=url, data=params, headers=self.headers, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code != 200:
            return client_http_error(url, r.status_code, r.text)
        try:
            r_json = json.loads(r.text)
        except ValueError:
            raise CachetApiException(f"Unable to parse json: {r.text}")
        logging.debug("Response Body: %s", json.dumps(r_json,
                                                      indent=4,
                                                      separators=(',', ': ')))
        return r_json

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
        logging.debug("Sending to {url}: {param}".format(url=url,
                                                         param=json.dumps(params,
                                                                          indent=4,
                                                                          separators=(',', ': '))))
        try:
            r = requests.get(url=url, headers=self.headers, params=params, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code == 502:
            client_http_error(url, 502, "Bad Gateway")
            raise CachetApiException(f"Failed to get Cachet version. Probably it is not available")
        elif r.status_code != 200:
            return client_http_error(url, r.status_code, json.loads(r.text)['errors'])
        try:
            r_json = json.loads(r.text)
        except ValueError:
            raise CachetApiException(
                "Unable to parse json: %s" % r.text
            )
        logging.debug("Response Body: %s", json.dumps(r_json,
                                                      indent=4,
                                                      separators=(',', ': ')))
        return r_json

    def _http_put(self, url, params):
        """
        Make PUT and return json response
        :param url: str
        :param params: dict
        :return: json
        """
        url = self.server + url
        logging.debug("Sending to {url}: {param}".format(url=url,
                                                         param=json.dumps(params,
                                                                          indent=4,
                                                                          separators=(',', ': '))))
        try:
            r = requests.put(url=url, json=params, headers=self.headers, verify=self.verify)
        except requests.exceptions.RequestException as e:
            raise client_http_error(url, None, e)
        # r.raise_for_status()
        if r.status_code != 200:
            return client_http_error(url, r.status_code, r.text)
        try:
            r_json = json.loads(r.text)
        except ValueError:
            raise CachetApiException(
                "Unable to parse json: %s" % r.text
            )
        logging.debug("Response Body: %s", json.dumps(r_json,
                                                      indent=4,
                                                      separators=(',', ': ')))
        return r_json

    def get_version(self):
        """
        Get Cachet version for logging
        :return: str
        """
        url = 'version'
        data = self._http_get(url)
        return data['data']

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
        Please note, it name was not defined method returns only last page of data
        :param name: Name of component to search
        :type name: str
        :return: Data =)
        :rtype: dict or list
        """
        url = 'components'
        data = self._http_get(url)
        total_pages = int(data['meta']['pagination']['total_pages'])
        if name:
            components = []
            for page in range(total_pages, 0, -1):
                if page == 1:
                    data_page = data
                else:
                    data_page = self._http_get(url, params={'page': page})
                for component in data_page['data']:
                    if component['name'] == name:
                        components.append(component)
            if len(components) < 1:
                return {'id': 0, 'name': 'Does not exists'}
            else:
                return components
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
        # Do not post empty params to Cachet
        for i in ('link', 'description'):
            # Strip params to avoid empty (' ') values #24
            if str(params[i]).strip() == '':
                params.pop(i)
        # Check if components with same name already exists in same group
        component = self.get_components(name)
        # There are more that one component with same name already
        if isinstance(component, list):
            for i in component:
                if i['group_id'] == params['group_id']:
                    return i
        elif isinstance(component, dict):
            if not component['id'] == 0 and component.get('group_id', None) == params['group_id']:
                return component
        # Create component if it does not exist or exist in other group
        url = 'components'
        # params = {'name': name, 'link': link, 'description': description, 'status': status}
        logging.debug('Creating Cachet component {name}...'.format(name=params['name']))
        data = self._http_post(url, params)
        logging.info('Component {name} was created in group id {group_id}.'.format(name=params['name'],
                                                                                   group_id=data['data'][
                                                                                       'group_id']))
        return data['data']

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
        if data:
            logging.info('Component {name} (id={id}) was updated. Status - {status}'.format(
                name=data['data']['name'],
                id=id,
                status=data['data']['status_name']))
        return data

    def get_components_gr(self, name=None):
        """
        Get all registered components group or return a component group details if name specified
        Please note, it name was not defined method returns only last page of data
        @param name: string
        @return: dict of data
        """
        url = 'components/groups'
        data = self._http_get(url)
        total_pages = int(data['meta']['pagination']['total_pages'])
        if name:
            for page in range(total_pages, 0, -1):
                if page == 1:
                    data_page = data
                else:
                    data_page = self._http_get(url, params={'page': page})
                for group in data_page['data']:
                    if group['name'] == name:
                        return group
            return {'id': 0, 'name': 'Does not exists'}
        return data

    def new_components_gr(self, name: str):
        """
        Create new components group
        @param name: string
        @return: dict of data
        """
        # Check if component's group already exists
        components_gr_id = self.get_components_gr(name)
        if components_gr_id['id'] == 0:
            url = 'components/groups'
            # TODO: make if possible to configure default collapsed value
            params = {'name': name, 'collapsed': 2}
            logging.debug('Creating Component Group {}...'.format(params['name']))
            data = self._http_post(url, params)
            if 'data' in data:
                logging.info('Component Group {} was created ({})'.format(params['name'], data['data']['id']))
            return data['data']
        else:
            return components_gr_id

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
            # Check if Zabbix return trigger
            if 'value' not in trigger:
                logging.error('Cannot get value for trigger {}'.format(i['triggerid']))
                continue
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
                    if str(last_inc['id']) != '0':
                        if resolving_tmpl:
                            inc_msg = resolving_tmpl.format(time=datetime.datetime.now(tz=tz).strftime('%b %d, %H:%M'),
                                                            ) + cachet.get_incident(i['component_id'])['message']
                        else:
                            inc_msg = cachet.get_incident(i['component_id'])['message']
                        cachet.upd_incident(last_inc['id'],
                                            status=4,
                                            component_id=i['component_id'],
                                            component_status=1,
                                            message=inc_msg)
                    # Incident does not exist. Just change component status
                    else:
                        cachet.upd_components(i['component_id'], status=1)
                    continue
            # Trigger in Active state
            elif trigger['value'] == '1':
                zbx_event = zapi.get_event(i['triggerid'])
                inc_name = trigger['description']
                if not zbx_event:
                    logging.warning('Failed to get zabbix event for trigger {}'.format(i['triggerid']))
                    # Mock zbx_event for further usage
                    zbx_event = {'acknowledged': '0',
                                 }
                if zbx_event.get('acknowledged', '0') == '1':
                    inc_status = 2
                    for msg in zbx_event['acknowledges']:
                        # TODO: Add timezone?
                        #       Move format to config file
                        author = msg.get('name', '') + ' ' + msg.get('surname', '')
                        ack_time = datetime.datetime.fromtimestamp(int(msg['clock']), tz=tz).strftime('%b %d, %H:%M')
                        ack_msg = acknowledgement_tmpl.format(
                            message=msg['message'],
                            ack_time=ack_time,
                            author=author
                        )
                        if ack_msg not in inc_msg:
                            inc_msg = ack_msg + inc_msg
                else:
                    inc_status = 1
                if int(trigger['priority']) >= 4:
                    comp_status = 4
                elif int(trigger['priority']) == 3:
                    comp_status = 3
                else:
                    comp_status = 2

                if not inc_msg and investigating_tmpl:
                    if zbx_event:
                        zbx_event_clock = int(zbx_event.get('clock'))
                        zbx_event_time = datetime.datetime.fromtimestamp(zbx_event_clock, tz=tz).strftime('%b %d, %H:%M')
                    else:
                        zbx_event_time = ''
                    inc_msg = investigating_tmpl.format(
                        group=i.get('group_name', ''),
                        component=i.get('component_name', ''),
                        time=zbx_event_time,
                        trigger_description=trigger.get('comments', ''),
                        trigger_name=trigger.get('description', ''),
                    )

                if not inc_msg and trigger.get('comments'):
                    inc_msg = trigger.get('comments')
                elif not inc_msg:
                    inc_msg = trigger.get('description')

                if 'group_name' in i:
                    inc_name = i.get('group_name') + ' | ' + inc_name

                last_inc = cachet.get_incident(i['component_id'])
                # Incident not registered
                if last_inc['status'] in ('-1', '4'):
                    # TODO: added incident_date
                    # incident_date = datetime.datetime.fromtimestamp(
                    # int(trigger['lastchange'])).strftime('%d/%m/%Y %H:%M')
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
            # inc_msg = 'TODO: ServiceID'
            continue

    return True


def triggers_watcher_worker(service_map, interval, event):
    """
    Worker for triggers_watcher. Run it continuously with specific interval
    @param service_map: list of tuples
    @param interval: interval in seconds
    @param event: treading.Event object
    @return:
    """
    logging.info('start trigger watcher')
    while not event.is_set():
        logging.info('Check status of Zabbix triggers')
        # Do not run if Zabbix is not available
        if zapi.get_version():
            try:
                triggers_watcher(service_map)
            except Exception as e:
                logging.error('triggers_watcher() raised an Exception. Something gone wrong')
                logging.error(e, exc_info=True)
        else:
            logging.error('Zabbix is not available. Skip checking...')
        time.sleep(interval)
    logging.info('end trigger watcher')


def init_cachet(services: List[ZabbixService]) -> List[Dict[str, Union[Union[str, int], Any]]]:
    """
    Init Cachet by syncing Zabbix service to it
    Also func create mapping batten Cachet components and Zabbix IT services
    @param services: list of ZabbixService
    @return: list of tuples
    """
    # Zabbix Triggers to Cachet components id map
    data = []
    for zbx_service in services:
        # Check if zbx_service has childes
        zxb2cachet_i = {}
        if zbx_service.children:
            group = cachet.new_components_gr(zbx_service.name)
            for dependency in zbx_service.children:
                # Component without trigger
                if int(dependency.triggerid) != 0:
                    trigger = zapi.get_trigger(dependency.triggerid)
                    if not trigger:
                        logging.error('Failed to get trigger {} from Zabbix'.format(dependency.triggerid))
                        continue
                    component = cachet.new_components(dependency.name, group_id=group['id'],
                                                      link=trigger['url'], description=trigger['description'])
                    # Create a map of Zabbix Trigger <> Cachet IDs
                    zxb2cachet_i = {'triggerid': dependency.triggerid}
                else:
                    component = cachet.new_components(dependency.name, group_id=group['id'])
                    zxb2cachet_i = {'serviceid': dependency.serviceid}
                zxb2cachet_i.update({'group_id': group['id'],
                                     'group_name': group['name'],
                                     'component_id': component['id'],
                                     'component_name': component['name']
                                     })
                data.append(zxb2cachet_i)
        else:
            # Component with trigger
            if zbx_service.triggerid:
                if int(zbx_service.triggerid) == 0:
                    logging.error('Zabbix Service with service id = {} does '
                                  'not have trigger or child service'.format(zbx_service.serviceid))
                    continue
                trigger = zapi.get_trigger(zbx_service.triggerid)
                if not trigger:
                    logging.error('Failed to get trigger {} from Zabbix'.format(zbx_service.triggerid))
                    continue
                component = cachet.new_components(zbx_service.name, link=trigger['url'],
                                                  description=trigger['description'])
                # Create a map of Zabbix Trigger <> Cachet IDs
                zxb2cachet_i = {'triggerid': zbx_service.triggerid,
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
    try:
        return yaml.safe_load(open(config_f, "r"))
    except (yaml.error.MarkedYAMLError, IOError) as e:
        logging.error(f"Failed to parse config file {config_f}: {e}")
    return None


if __name__ == '__main__':

    if os.getenv('CONFIG_FILE') is not None:
        config_file = os.environ['CONFIG_FILE']
    else:
        config_file = os.path.dirname(os.path.realpath(__file__)) + '/config.yml'
    if not os.path.isfile(config_file):
        logging.error(f"Config file {config_file} is absent. Set CONFIG_FILE to change path or create it there.")
        sys.exit(1)
    config = read_config(config_file)
    if not config:
        sys.exit(1)
    ZABBIX = config['zabbix']
    CACHET = config['cachet']
    SETTINGS = config['settings']

    if SETTINGS.get('time_zone'):
        tz = pytz.timezone(SETTINGS['time_zone'])
    else:
        tz = None

    # Templates for incident displaying
    acknowledgement_tmpl_default = "{message}\n\n###### {ack_time} by {author}\n\n______\n"
    templates = config.get('templates')
    if templates:
        acknowledgement_tmpl = templates.get('acknowledgement', acknowledgement_tmpl_default)
        investigating_tmpl = templates.get('investigating', '')
        resolving_tmpl = templates.get('resolving', '')
    else:
        acknowledgement_tmpl = acknowledgement_tmpl_default

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
        logging.info('Zabbix ver: {}. Cachet ver: {}'.format(zapi.version, cachet.version))
        zbxtr2cachet = ''
        while True:
            logging.debug('Getting list of Zabbix IT Services ...')
            it_services = zapi.get_itservices(SETTINGS['root_service'])
            logging.debug('Zabbix IT Services: {}'.format(it_services))
            # Create Cachet components and components groups
            logging.debug('Syncing Zabbix with Cachet...')
            # TODO: refactor market
            zbxtr2cachet_new = init_cachet(it_services)
            if not zbxtr2cachet_new:
                logging.error('Sorry, can not create Zabbix <> Cachet mapping for you. Please check above errors')
                # Exit if it's an initial run
                if not zbxtr2cachet:
                    sys.exit(1)
                else:
                    zbxtr2cachet_new = zbxtr2cachet
            else:
                logging.info('Successfully synced Cachet components with Zabbix Services')
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
                                                args=(zbxtr2cachet, SETTINGS['update_inc_interval'], event))
                inc_update_t.daemon = True
                inc_update_t.start()
            time.sleep(SETTINGS['update_comp_interval'])

    except KeyboardInterrupt:
        event.set()
        logging.info('Shutdown requested. See you.')
    except Exception as error:
        logging.exception(error)
        exit_status = 1
    sys.exit(exit_status)
