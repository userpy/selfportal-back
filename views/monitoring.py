from aiohttp import web
from aiohttp_jwt import check_permissions, match_any
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET
from scripts.help_functions_zbx import async_zabbix_conn
from aiohttp_validate import validate
import ipaddress
import asyncssh
import jwt
import asyncio
import time
import redis
import json
import logging

MonitoringRoutes = web.RouteTableDef()

def radd(source,item):
    r = redis.Redis(db=1)
    q_name = f'di.{source}'
    q_len = r.lpush(q_name, json.dumps(item))
    if q_len > 10000:
        item = r.rpop(q_name)
        logging.getLogger('monitoring_add').error(
            f"from {source} deleted item {item} due to queue overflow")


async def get_newhost_templates(proxy_type,zabbix):
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(
            f"select templates,parent_templates,groups from configs.zabbix_templates where proxy_type='{proxy_type}' and zabbix='{zabbix}'")
        result = await res.fetchall()
    engine.close()
    return result[0][0], result[0][1], result[0][2]

async def get_default_proxy(source,tag):
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(
            f"select ip,proxy_id from configs.zabbix_proxy where zabbix='{source}' and tag like '%{tag}:default%'")
        result_proxy = await res.fetchall()
    engine.close()
    return result_proxy[0][0],result_proxy[0][1]

async def get_source(env, tag, os):
    if tag == 'os':
        tag = os
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(
            f"select zabbix from configs.zabbix_types where FIND_IN_SET('{env}',env)>0 and type like '%{tag}%'")
        result_proxy = await res.fetchall()
    engine.close()
    return result_proxy[0][0]

async def get_networks_from_zone(zonename):
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(
                f"select ip_networks from configs.network_zones where zonename='{zonename}'")
            sql_results = await res.fetchall()
        results = sql_results[0][0].split(',')
        engine.close()
        return results
    except BaseException as e:
        return False

async def get_proxy_di(data,source,user,logger):
    try:
        user = pwd = ''
        engine = await db_connect('selfportal')
        tag = data['os'] if data['tag'] == 'os' else data['tag']

        async with engine.acquire() as conn:
            res = await conn.execute("select keyword,value from selfportal.app_config where type='monitoring_add_ssh_di'")
            result_ssh = await res.fetchall()

            res = await conn.execute(
                f"select ip,ip_networks,proxy_id from configs.zabbix_proxy where zabbix='{source}' and FIND_IN_SET('{tag}',tag)>0 and ip_networks != ''")
            result_proxy = await res.fetchall()
        for row in result_ssh:
            if row[0] == 'monitoring_add_user_di':
                user = row[1]
            elif row[0] == 'monitoring_add_pwd_di':
                pwd = row[1]
            if row[0] == 'monitoring_add_key_di':
                key_path = row[1]
        engine.close()
        if user == '' or pwd == '':
            return -1
        proxy_for_check = {}
        for row in result_proxy:
            networks = row[1]
            networks = networks.replace(',', ';').split(';')
            while networks:
                net = networks.pop()
                try:
                    if ipaddress.IPv4Address(data['ip']) in ipaddress.ip_network(net):
                        proxy_for_check[row[2]] = row[0]
                        break
                except ValueError:
                    zone_networks = await get_networks_from_zone(net)
                    if zone_networks:
                        networks.extend(zone_networks)
        min_proxy = []
        try:
            zapi = await async_zabbix_conn(source)
            for proxy_id in proxy_for_check:
                items_count = await zapi.item.get(countOutput=True, proxyids=proxy_id)
                min_proxy.append((proxy_id,items_count))
            await zapi.close()
        except BaseException as e:
            logger.error(
                f"Cant get proxy item count for user: {user}, host:{data['ip']}, source: {source} Error: {str(e)}")
            min_proxy = [(proxy_id, 0) for proxy_id in proxy_for_check]
        min_proxy.sort(key=lambda x:x[1])
        for proxy_id, _ in min_proxy:
            proxy_ip = proxy_for_check[proxy_id]
            try:
                ssh_key = asyncssh.read_private_key(key_path)
                conn_context = await asyncio.wait_for(
                    asyncssh.connect(host=proxy_ip, username=user, password=pwd, client_keys=ssh_key, known_hosts=None),
                    timeout=1)
                async with conn_context as conn:
                    #listener =  await conn.forward_local_port('localhost',8010,host_ip,10057)
                    if 'port' not in data:
                        data['port'] = 10050
                    result = await conn.run(f"nc -vw3 -i0.001 {data['ip']} {data['port']}")
                    if 'Connected' in result.stderr:
                        if tag != 'linux':
                            return proxy_ip, proxy_id
                        host_conn_context = await asyncio.wait_for(
                                asyncssh.connect(host=data['ip'],tunnel=conn,username=user, password=pwd, client_keys=ssh_key, known_hosts=None),
                                timeout=1)
                        async with host_conn_context as conn:
                            result = await conn.run(f'nc -vw3 -i0.001 {proxy_ip} 10051')
                            if 'Connected' in result.stderr:
                                return proxy_ip, proxy_id
            except:
                continue
    except BaseException as e:
        logger.error(f"Cant get proxy for user: {user}, host:{data['ip']},source: {source}, tag: {tag}, Error: {str(e)}")
    proxy_ip, proxy_id = await get_default_proxy(source, tag)
    return proxy_ip,proxy_id

@MonitoringRoutes.post('/api/monitoring/get_proxy')
@check_permissions([
    'monitoring_add_di'
], permissions_property = 'role', comparison=match_any)
@validate(request_schema={
        "type": "object",
        "properties": {
            "env": {"type": "string"},
            "tag": {"type": "string"},
            "os": {"type": "string"},
            "ip": {"type": "string"}
        },
        "required": ["env","tag","os","ip"],
        "additionalProperties": True
    })
async def get_proxy(_, request):
    try:
        post_data = await request.json()
        env, tag, os = post_data['env'], post_data['tag'], post_data['os']
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        source = await get_source(env, tag, os)
        proxy_ip,proxy_id = await get_proxy_di(post_data,source,jwtd['user_id'],request.app['monitoring_add_logger'])
        request.app['monitoring_add_logger'].info(f"User {jwtd['user_id']} get proxy ip {proxy_ip} id {proxy_id} for host with params {post_data}")
        return json_response({'result': True, 'ip': proxy_ip,'id':proxy_id})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}, data {post_data}')
        return json_response({'result': False, 'text':str(e)})

@MonitoringRoutes.post('/api/monitoring/change_power')
@check_permissions([
    'monitoring_add_di'
], permissions_property = 'role', comparison=match_any)
@validate(request_schema={
        "type": "object",
        "properties": {
            "env": {"type": "string"},
            "tag": {"type": "string"},
            "os": {"type": "string"},
            "hostname": {"type": "string"},
            "status": {"type": "string"}
        },
        "required": ["env", "tag", "os", "hostname", "status"],
        "additionalProperties": True
    })
async def change_power(_, request):
    try:
        post_data = await request.json()
        env, tag, os = post_data['env'], post_data['tag'], post_data['os']
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        source = await get_source(env, tag, os)

        radd(source, {'post_data': post_data,
                      'method': 'change_power', 'source': source, 'user': jwtd['user_id']})

        return json_response({'result': True})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}, data {post_data}')
        return json_response({'result': False, 'text':str(e)})


@MonitoringRoutes.post('/api/monitoring/delete_host')
@check_permissions([
    'monitoring_add_di'
], permissions_property = 'role', comparison=match_any)
@validate(request_schema={
        "type": "object",
        "properties": {
            "env": {"type": "string"},
            "tag": {"type": "string"},
            "os": {"type": "string"},
            "hostname": {"type": "string"}
        },
        "required": ["env", "tag", "os", "hostname"],
        "additionalProperties": True
    })
async def delete_host(_, request):
    try:
        post_data = await request.json()
        env, tag, os = post_data['env'], post_data['tag'], post_data['os']
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        source = await get_source(env, tag, os)
        radd(source, {'post_data': post_data,
                      'hostname': post_data['hostname'], 'method': 'delete_host', 'source': source, 'user': jwtd['user_id']})
        return json_response({'result': True})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}, data {post_data}')
        return json_response({'result': False, 'text':str(e)})


@MonitoringRoutes.post('/api/monitoring/create_host')
@check_permissions([
    'monitoring_add_di'
], permissions_property = 'role', comparison=match_any)
@validate(request_schema={
        "type": "object",
        "properties": {
            "env": {"type": "string"},
            "tag": {"type": "string"},
            "os": {"type": "string"},
            "diuid": {"type": "string"},
            "macro": {"type": "array"},
            "hostname": {"type": "string"},
            "ip": {"type": "string"},
            "port": {"type": "string"},
            "postfix": {"type": "string"},
            "interfacetypeid": {"type": "integer"}
        },
        "required": ["env", "tag", "os", "diuid", "hostname", "ip"],
        "additionalProperties": True
    })
async def create_host_view(_, request):
    try:
        post_data = await request.json()
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        res = await create_host(post_data, jwtd, request.app['monitoring_add_logger'])
        return json_response(res)
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}, data {post_data}')
        return json_response({'result': False, 'text':str(e)})

async def create_host(post_data,jwtd,logger):
    env, tag, os = post_data['env'], post_data['tag'], post_data['os']

    source = await get_source(env, tag, os)
    if tag == 'os':
        hostname = post_data['hostname']
    elif 'postfix' in post_data:
        hostname = f"{post_data['hostname']}.{tag}.{post_data['postfix']}"
    else:
        hostname = f"{post_data['hostname']}.{tag}"
    result, text = await get_proxy_di(post_data, source, jwtd['user_id'], logger)

    if result:
        radd(source, {'proxyid': text, 'post_data': post_data,
                      'hostname': hostname, 'method': 'create_host', 'source': source, 'user': jwtd['user_id']})
        return {'result': True, 'ip': result}
    else:
        return {'result': False, 'text': text}

@MonitoringRoutes.post('/api/monitoring/add_maintanance')
@check_permissions([
    'monitoring_add_di'
], permissions_property='role', comparison=match_any)
@validate(request_schema={
        "type": "object",
        "properties": {
            "env": {"type": "string"},
            "tag": {"type": "string"},
            "os": {"type": "string"},
            "iplist": {"type": "array"},
            "period": {"type": "integer"},
            "start_main": {"type": "integer"}
        },
        "required": ["env", "tag", "os", "iplist", "period"],
        "additionalProperties": True
    })
async def add_maintanance(_, request):
    try:
        post_data = await request.json()
        iplist = post_data['iplist']
        env, tag, os = post_data['env'], post_data['tag'], post_data['os']
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})

        source = await get_source(env, tag, os)
        post_data['active_since'] = post_data['start_main'] if 'start_main' in post_data else float(time.time())
        period = post_data['period']
        post_data['period'] = float(period) * 60 * 60
        post_data['active_till'] = post_data['active_since'] + period

        radd(source, {'post_data': post_data, 'iplist': iplist,
             'method': 'add_maintanance', 'source': source, 'user': jwtd['user_id']})

        return json_response({'result': True})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}, data {post_data}')
        return json_response({'result': False, 'text': str(e)})