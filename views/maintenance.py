from aiohttp import web
from aiohttp_jwt import check_permissions, match_any
from scripts.help_functions_zbx import async_zabbix_conn
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET
import time
import jwt
MaintenanceRoutes = web.RouteTableDef()

@MaintenanceRoutes.post('/api/maintenance/get_hostlist_lite')
@check_permissions([
    'maintenance'
], permissions_property = 'role', comparison=match_any)
async def get_hostlist_lite(request):
    post_data = await request.json()
    try:
        hostlist = await get_hostlist('host',post_data['hostname'], post_data['source'])
        return json_response({'result': True, 'hostnamelist': hostlist})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})

@MaintenanceRoutes.post('/api/maintenance/get_hostlist_expert')
@check_permissions([
    'maintenance_full'
], permissions_property = 'role', comparison=match_any)
async def get_hostlist_expert(request):
    post_data = await request.json()
    try:
        hostlist = await get_hostlist(post_data['mode'],post_data['value'], post_data['source'])
        return json_response({'result': True, 'hostnamelist': hostlist})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})


@MaintenanceRoutes.post('/api/maintenance/get_maintenance')
@check_permissions([
    'maintenance',
    'maintenance_full'
], permissions_property = 'role', comparison=match_any)
async def get_maintenance(request):
    post_data = await request.json()
    try:
        zapi = await async_zabbix_conn(post_data['source'], 'net')
        if post_data['type'] == 'host':
            host = await zapi.host.get(output=['host','hostid'], selectGroups=['groupid'], filter={'name': post_data['value']}, limit=1)
            host_grps = [group['groupid'] for group in host[0]['groups']]
            maintenances = await zapi.maintenance.get(hostids=host[0]['hostid'],groupids=host_grps,
                                                      selectTags='extend',
                                                      selectHosts=['host','name'],
                                                      selectGroups=['name'],
                                                      selectTimeperiods='extend', limit=30)
            maintenances = [maintenance for maintenance in maintenances if int(maintenance['active_till']) > int(time.time())]
        else:
            grp = await zapi.hostgroup.get(output=['groupid'], filter={'name': post_data['value']}, limit=1)
            maintenances = await zapi.maintenance.get(groupids=grp[0]['groupid'],
                                                      selectTags='extend',
                                                      selectHosts=['host','name'],
                                                      selectGroups=['name'],
                                                      selectTimeperiods='extend', limit=30)
            maintenances = [maintenance for maintenance in maintenances if
                            int(maintenance['active_till']) > int(time.time())]
        await zapi.close()
        return json_response({'result': True, 'maintenances': maintenances})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})


@MaintenanceRoutes.post('/api/maintenance/add_maintenance_expert')
@check_permissions([
    'maintenance_full',
], permissions_property = 'role', comparison=match_any)
async def add_maintenance_expert(request):
    post_data = await request.json()
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
    try:
        zapi = await async_zabbix_conn(post_data['source'], 'net')
        if post_data['value']['mode'] == 'host':
            res = await zapi.host.get(output=['hostid'], filter={'name': post_data['value']['value']}, limit=30)
            objid = [host['hostid'] for host in res]
            objkey = 'hostids'
            mode_str = '_h'
        else:
            res = await zapi.hostgroup.get(output=['groupid'], filter={'name': post_data['value']['value']}, limit=30)
            objid = [host['groupid'] for host in res]
            objkey = 'groupids'
            mode_str = '_g'
        fromtime = int( post_data['value']['date']/1000)
        res = await zapi.maintenance.create(name=jwtd['user_id'] + mode_str + objid[0] + '_' + str(fromtime),
                                            **{objkey: objid},
                                            timeperiods=[{
                                                "timeperiod_type": 0,
                                                "start_date": fromtime,
                                                "period": post_data['value']['time']
                                            }],
                                            active_since=fromtime,
                                            active_till=fromtime + int(post_data['value']['time']),
                                            tags_evaltype= 0 if post_data['value']['tags_mode'] == 'And/Or' else 2,
                                            tags= post_data['value']['tags'],
                                            description=post_data['value']['description'])
        await zapi.close()
        request.app['maintenance_logger'].info(
            f"Created maintenance on {post_data['source']} by {jwtd['user_id']} for object {mode_str + objid[0]} with period from {fromtime} for {int(post_data['value']['time'])} seconds")
        return json_response({'result': True})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})

@MaintenanceRoutes.post('/api/maintenance/add_maintenance')
@check_permissions([
    'maintenance',
], permissions_property = 'role', comparison=match_any)
async def add_maintenance_lite(request):
    post_data = await request.json()
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
    try:
        zapi = await async_zabbix_conn(post_data['source'], 'net')
        host = await zapi.host.get(output=['host','hostid'], filter={'name': post_data['value']['hostname']}, limit=1)
        now = int(time.time())
        res = await zapi.maintenance.create(name=jwtd['user_id']+'_h'+host[0]['hostid']+'_'+str(now),
                                            hostids=[host[0]['hostid']],
                                            timeperiods=[{
                                                "timeperiod_type": 0,
                                                "period": post_data['value']['time']
                                            }],
                                            active_since=now,
                                            active_till=now+int(post_data['value']['time']),
                                            description=post_data['value']['description'])
        await zapi.close()
        request.app['maintenance_logger'].info(f"Created simple maintenance on {post_data['source']} by {jwtd['user_id']} for hostid {host[0]['hostid']} with period from now for {int(post_data['value']['time'])} seconds")
        return json_response({'result': True})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})

@MaintenanceRoutes.post('/api/maintenance/delete_maintenance')
@check_permissions([
    'maintenance',
    'maintenance_full'
], permissions_property = 'role', comparison=match_any)
async def delete_maintenance(request):
    post_data = await request.json()
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
    try:
        zapi = await async_zabbix_conn(post_data['source'], 'net')
        await zapi.maintenance.delete(post_data['data']['maintenanceid'])
        await zapi.close()
        request.app['maintenance_logger'].info(f"Deleted maintenance on {post_data['source']} by {jwtd['user_id']} with name {post_data['data']['name']}")
        return json_response({'result': True})
    except BaseException as e:
        request.app['maintenance_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})


async def get_hostlist(type,value,source):
    zapi = await async_zabbix_conn(source, 'net')
    # groups = await zapi.hostgroup.get(output=['name'],search={'name':'IS OS'})
    # groupsids = [group['groupid'] for group in groups]
    if type == 'host':

        res = await zapi.host.get(output=['name'], search={'name': value}, limit=30)
        hostlist = [host['name'] for host in res]
    else:
        res = await zapi.hostgroup.get(output=['name'], search={'name': value}, limit=30)
        hostlist = [host['name'] for host in res]
    await zapi.close()
    return hostlist