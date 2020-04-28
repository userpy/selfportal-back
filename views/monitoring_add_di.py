from aiohttp import web
from aiohttp_jwt import check_permissions, match_any
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET
from scripts.help_functions_zbx import async_zabbix_conn
import ipaddress
import asyncssh
import jwt
import asyncio

MonitoringAddDiRoutes = web.RouteTableDef()

async def change_power_di(host_ip,source,tag,status,user,logger):
    try:
        zapi = await async_zabbix_conn(source)
        ip_hosts = await zapi.hostinterface.get(output=['ip'], selectHosts=['hostid'], filter={'ip': host_ip})

        status = status.lower() == 'true'

        host_ids_ip = [x['hosts'][0]['hostid'] for x in ip_hosts]
        if host_ids_ip:
            result = await zapi.host.massupdate(hosts=[{'hostid': x} for x in host_ids_ip], status=int(not status))
            await zapi.close()
            return True, result['hostids']
        else:
            await zapi.close()
            return False, f'No such host: {host_ip}'

    except BaseException as e:
        return False, str(e)

@MonitoringAddDiRoutes.post('/api/monitoring_add_di/change_power')
@check_permissions([
    'monitoring_add_di'
], permissions_property = 'role', comparison=match_any)
async def change_power(request):
    try:
        post_data = await request.json()
        ip = post_data['ip']
        env = post_data['env']
        tag = post_data['tag']
        status = post_data['status']
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        result, text = await change_power_di(ip,env,tag,status,jwtd['user_id'],request.app['monitoring_add_logger'])
        if result:
            request.app['monitoring_add_logger'].info(f"User {jwtd['user_id']} change power for host with ip {ip},env: {env},tag: {tag}. Status: {status}")
            return json_response({'result': True, 'ids': text})
        else:
            return json_response({'result': False, 'text': text})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})