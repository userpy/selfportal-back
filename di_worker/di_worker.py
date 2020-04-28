import redis
import json
import time
import asyncio
import logging

import sys
import os

sys.path.append(os.getcwd())

from scripts.help_functions_zbx import async_zabbix_conn
from views.monitoring import get_source, get_newhost_templates, radd
from scripts.help_functions import create_logger, create_config
from aiozabbix import ZabbixAPIException




class DiMethods:
    @staticmethod
    async def change_power_di_by_host(data):
        try:
            zapi = await async_zabbix_conn(data['source'])
            status = data['status'].lower() == 'true'
            await zapi.host.update(hostid=data['hostid'], status=int(not status))
            await zapi.close()
            logger = logging.getLogger('monitoring_add')
            logger.info(
                f"User {data['user']} change power for host {data['post_data']['hostname']} at: {data['source']} Status: {status}")
        except BaseException as e:
            raise

    @staticmethod
    async def change_power(data):
        zapi = await async_zabbix_conn(data['source'])
        parenthost = await zapi.host.get(output=['host', 'hostid'], filter={'host': data['post_data']['hostname']},
                                         selectTags='extend')
        if len(parenthost) == 0:
            await zapi.close()
            logger = logging.getLogger('monitoring_add')
            logger.info(
                f"User {data['user']} change power Status: {data['post_data']['status']} for host {data['post_data']['hostname']} on {data['source']} error: no such host")
            return
        parenthostid, parenttags = parenthost[0]['hostid'], parenthost[0]['tags']
        await zapi.close()
        data['method'] = 'change_power_di_by_host'
        radd(data['source'], {'hostid': parenthostid, 'method': 'change_power_di_by_host',
                              'source': data['source'], 'status': data['post_data']['status'],
                              'user':data['user'], 'post_data': data['post_data']})
        if data['post_data']['tag'] == 'os':
            for tag in parenttags:
                if tag['tag'].startswith('app_'):
                    app_source, app_id = tag['value'].split(':')
                    radd(app_source, {'hostid':app_id, 'method': 'change_power_di_by_host',
                                      'source':app_source, 'status': data['post_data']['status'],
                                      'user':data['user'], 'post_data': data['post_data']})

    @staticmethod
    async def add_maintanance_by_zbx(data):
        zapi = await async_zabbix_conn(data['source'])
        await zapi.maintenance.create(name=f"DI Maintanence {data['post_data']['active_since']}",
                                      active_since=int(data['post_data']['active_since']),
                                      active_till=int(data['post_data']['active_till']),
                                      tags_evaltype=0,
                                      timeperiods=[{'timeperiods_type': 0, 'every': 1,
                                                    'start_date': int(data['post_data']['active_since']),
                                                    'period': int(data['post_data']['period'])}],
                                      hostids=data['hostids'])
        await zapi.close()
        logger = logging.getLogger('monitoring_add')
        logger.info(
            f"User {data['user']} add maintance at {data['source']} for hosts with {data['hostids']}")

    @staticmethod
    async def add_maintanance(data):
        zapi = await async_zabbix_conn(data['source'])
        hostids_by_zbx = {}
        hostids_by_zbx[data['source']] = []
        hosts = await zapi.hostinterface.get(output=['ip'], selectHosts=['hostid'],
                                                  filter={'ip': data['iplist']})
        hostlist = [item['hosts'][0]['hostid'] for item in hosts]
        parenthost_list = await zapi.host.get(output=['hostid'], hostids=hostlist, selectTags='extend')
        for parenthost in parenthost_list:
            parenthostid, parenttags = parenthost[0]['hostid'], parenthost[0]['tags']
            hostids_by_zbx[data['source']].append(parenthostid)
            for tag in parenttags:
                if tag['tag'].startswith('app_'):
                    app_source, app_id = tag['value'].split(':')
                    if app_source not in hostids_by_zbx:
                        hostids_by_zbx[app_source] = []
                    hostids_by_zbx[app_source].append(app_id)
        await zapi.close()

        for app_source in hostids_by_zbx:
            radd(app_source, {'source': app_source,
                              'hostids': hostids_by_zbx[app_source],
                              'method': 'add_maintanance_by_zbx',
                              'postdata': data['post_data'],
                              'user': data['user']})

    @staticmethod
    async def delete_host(data):
        zapi = await async_zabbix_conn(data['source'])
        parenthost = await zapi.host.get(output=['host', 'hostid'], filter={'host': data['post_data']['hostname']},
                                         selectTags='extend')
        if not len(parenthost):
            return
        parenthostid, parenttags = parenthost[0]['hostid'], parenthost[0]['tags']
        await zapi.host.delete(parenthostid)
        await zapi.close()
        logger = logging.getLogger('monitoring_add')
        if data['post_data']['tag'] == 'os':
            for tag in parenttags:
                if tag['tag'].startswith('app_'):
                    app_source, app_id = tag['value'].split(':')
                    radd(app_source, {'source': app_source, 'app_id': app_id, 'method': 'delete_host_app'})
        logger.info(f"User {data['user']} deleted hosts with name {data['post_data']['hostname']}")

    @staticmethod
    async def delete_host_app(data):
        try:
            app_zapi = await async_zabbix_conn(data['source'])
            await app_zapi.host.delete(data['app_id'])
            await app_zapi.close()
        except BaseException as e:
            raise

    @staticmethod
    async def create_host(data):
        try:
            host_macro = [{'macro': '{$DIUID}', 'value': data['post_data']['diuid']}]
            if 'macro' in data['post_data']:
                host_macro.extend(data['post_data']['macro'])
            host_interface = {'dns': '',
                              'ip': data['post_data']['ip'],
                              'port': data['post_data']['port'] if 'port' in data['post_data'] else '10050',
                              'main': '1',
                              'type': data['post_data']['interfacetypeid'] if 'interfacetypeid' in data['post_data'] else '1',
                              'useip': '1'}
            host_templates, parent_templates, host_groups = await get_newhost_templates(data['post_data']['os'] if data['post_data']['tag'] == 'os' else data['post_data']['tag'] , data['source'])
            zapi = await async_zabbix_conn(data['source'])
            exist_host = await zapi.host.get(output=['hostid'], filter={'host': data['hostname']})
            if len(exist_host):
                await zapi.host.delete(exist_host[0]['hostid'])
            created_id = await zapi.host.create(
                {'host': f"{data['hostname']}",
                 'templates': [{'templateid': value} for value in host_templates.split(',')],
                 'groups': [{'groupid': value} for value in host_groups.split(',')],
                 'macros': host_macro,
                 'interfaces': [host_interface],
                 'proxy_hostid': data['proxyid'],
                 'inventory_mode': '1'})
            created_id = created_id['hostids'][0]
            if data['post_data']['tag'] != 'os':
                parent_source = await get_source(data['post_data']['env'], 'os', data['post_data']['os'])
                data['app_source'] = data['source']
                data['created_id'] = created_id
                data['source'] = parent_source
                data['method'] = 'create_host_step2'
                data['parent_templates'] = parent_templates
                radd(data['source'], data)
            logger = logging.getLogger('monitoring_add')
            logger.info(
                f"User {data['user']} added host proxy id {data['proxyid']} \
                           for host with id {created_id} ip {data['post_data']['ip']},env:\
                            {data['post_data']['env']},tag:\
                            {data['post_data']['tag']} hostname {data['hostname']}")
            await zapi.close()
        except BaseException as e:
            raise


    @staticmethod
    async def create_host_step2(data):
            try:
                zapi = await async_zabbix_conn(data['source'])
                templates_to_add = data['parent_templates']
                hostid = await zapi.host.get(output=['host', 'hostid'],
                                             filter={'host':data['post_data']['hostname']},
                                             selectTags='extend',selectParentTemplates=['templateid'])
                hostid, tags, templates = hostid[0]['hostid'], hostid[0]['tags'], hostid[0]['parentTemplates']
                if templates_to_add:
                    for template in templates_to_add.split(','):
                        templates.append({'templateid': template})
                    await zapi.host.update(hostid=hostid, templates=templates)
                tags.append({'tag': f"app_{data['post_data']['tag']}", 'value':f"{data['app_source']}:{data['created_id']}"})
                await zapi.host.update(hostid=hostid, tags=tags)
                await zapi.close()
            except IndexError as e:
                logger = logging.getLogger('monitoring_add')
                logger.error(f"Error on create_host_step2 item: {data} with text: {str(e)}")
            except BaseException as e:
                raise

async def daemon_start():
    r = redis.Redis(db=1)
    create_logger(create_config('app.conf'), 'monitoring_add')
    logger = logging.getLogger('monitoring_add')
    while True:
        for lname in r.keys('di.*'):
            item = r.rpop(lname)
            while item is not None:
                try:
                    params = json.loads(item)
                    await getattr(DiMethods, params['method'])(params)
                except ZabbixAPIException as e:
                    logger.error(f"Incorrect api request on item: {item} type {type(e)} with text: {str(e)}")
                except KeyError as e:
                    logger.error(f"Error on item: {item} type {type(e)} with text: {str(e)}")
                except BaseException as e:
                    r.rpush(lname, item)
                    logger.error(f"Error on item: {item} type {type(e)} with text: {str(e)}")
                    break
                item = r.rpop(lname)
        time.sleep(5)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(daemon_start())