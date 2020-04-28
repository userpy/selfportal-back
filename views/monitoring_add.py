from aiohttp import web
from aiohttp_jwt import check_permissions, match_any
import re
import json
import sqlalchemy as sa
import datetime
from scripts.help_functions_zbx import async_zabbix_conn, zabbix_conn
from views.ws import sio
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET
from views.monitoring import get_proxy_di, get_source, create_host
import jwt
import pymysql
import asyncio
import cx_Oracle
import os
import asyncssh

MonitoringAddRoutes = web.RouteTableDef()

metadata = sa.MetaData()
tbl_oracle_users = sa.Table('oracle_users', metadata,
                sa.Column('dsn', sa.String(50), primary_key=True),
                sa.Column('UserID', sa.String(30)),
                sa.Column('Password', sa.String(100))
                )


def get_sm_query(ci):
    query = u"""
    with res as
(SELECT
 srvr.logical_name as ci,
 ir.tps_name as ir,
 m.OPERATOR_ID as account,
 m.CONTACT_NAME as userid

FROM SMPRIMARY.DEVICE2M1 srvr
--Связь с КЭ "Экземпляр СУБД"
left JOIN SMPRIMARY.CIRELATIONSM1 rel ON REL.TPS_RELATED_CIS = srvr.LOGICAL_NAME
left JOIN SMPRIMARY.DEVICE2M1 ci ON ci.LOGICAL_NAME = rel.logical_name AND ci.TYPE = 'dbmsinstance'
--Связь с КЭ ИР
left JOIN SMPRIMARY.CIRELATIONSM1 rel2 ON (rel2.TPS_RELATED_CIS = srvr.LOGICAL_NAME OR rel2.TPS_RELATED_CIS = ci.logical_name)
left JOIN SMPRIMARY.DEVICE2M1 ir ON ir.LOGICAL_NAME = rel2.LOGICAL_NAME AND ir.TYPE = 'infresource'

inner JOIN smprimary.device2a5 admir ON admir.logical_name = ir.logical_name
inner JOIN smprimary.contctsm1 m ON admir.tps_support_groups = m.full_name

WHERE srvr.type in ('server', 'sbvirtcluster', 'cluster')
        AND srvr.hpc_status != 'Выведен'
    AND (
        srvr.LOGICAL_NAME = '{}'
      )
ORDER BY srvr.LOGICAL_NAME)
select account,userid from res
group by res.ci,res.account,res.userid  having count(distinct res.ir) = (select count(distinct res.ir) from res where ci=res.ci)
    """.format(ci)
    return query

async def get_macroses(source,hostname):
    """
    :param data: array from zabbix server
    :return:  array where params text in items ( el #16) replaced with macros.
    """
    zapi = await async_zabbix_conn(source)
    host = await zapi.host.get(output=['host'], filter={'host': hostname}, selectInterfaces='extend',
                               selectParentTemplates=['host'], selectMacros='extend')
    port = host[0]['interfaces'][0]['port']


    if host:
        host=host[0]

    temp_macro = {'port':port}
    for hosttemplate in host['parentTemplates']:
        host_template = await zapi.template.get(output=['host'], filter={'host': hosttemplate['host']}, selectMacros='extend')
        for hostmacros in host_template[0]['macros']:
            if hostmacros['macro'] not in temp_macro:
                temp_macro[hostmacros['macro']] = hostmacros['value']

    for macro in host['macros']:
        temp_macro[macro['macro']] = macro['value']
    await zapi.close()
    return temp_macro

async def check_sm_admin(username,ci,admin_status):
    if admin_status:
        return True
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(f"select * from configs.databases where name='ORACLESM'")
        db_config = await res.fetchall()
    engine.close()
    db_config = db_config[0].as_tuple()
    os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
    con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(db_config[4],
                                                    db_config[5],
                                                    db_config[1],
                                                    db_config[2],
                                                    db_config[3]))
    cur = con.cursor()
    ci_query = get_sm_query(ci)
    cur.execute(ci_query)
    admins = [row[0] for row in cur.fetchall()]
    cur.close()
    if username in admins:
        return True
    else:
        return False

async def get_parenthost_data(hostname,source):
    zapi = await async_zabbix_conn(source)
    host = await zapi.host.get(output=['host', 'hostid'], filter={'host': hostname}, selectInventory=['tag'], selectTags='extend', selectInterfaces='extend')
    await zapi.close()
    ci = host[0]['inventory']['tag']
    ip = host[0]['interfaces'][0]['ip']
    tags = host[0]['tags']
    return ip,tags,host[0]['hostid'],ci

async def get_proxy_after_checks(ip,proxy_id,ci,port,username,source,type,admin_status,action):
    if await check_sm_admin(username, ci,admin_status):
        new_proxy_id = await get_proxy_di(ip,port,proxy_id,source,type)
        if action == 'delete' or new_proxy_id != -1:
            return True, str(new_proxy_id)
        else:
            return False, 'Сервис не доступен с прокси'
    else:
        return False,'Вы не администратор всех ИР-ов сервера!'

async def create_dsn_if_not_exist(action,dsn,login,password):
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        if action == 'delete':
            await conn.execute(tbl_oracle_users.delete().where(tbl_oracle_users.c.dsn==dsn))
            await conn.execute("commit")
        else:
            try:
                await conn.execute(tbl_oracle_users.insert().values(dsn=dsn,UserID=login,Password=password))
                await conn.execute("commit")
            except pymysql.err.IntegrityError:
                await conn.execute(tbl_oracle_users.update().values(UserID=login,Password=password).where(tbl_oracle_users.c.dsn == dsn))
                await conn.execute("commit")
            except:
                raise
    engine.close()

@MonitoringAddRoutes.post('/api/monitoringadd/apply')
@check_permissions([
    'monitoring_add'
], permissions_property='role', comparison=match_any)
async def apply(request):
    post_data = await request.json()
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})

    try:
        parent_source = await get_source(post_data['env'], 'os', post_data['os'])
        parent_ip, parent_tags, parent_id, parent_ci = await get_parenthost_data(post_data['hostdata']['hostname'],
                                                                                 parent_source)
    except BaseException:
        return json_response({'result': False, 'text': 'В мониторинге отсутствует родительский хост'})

    if 'monitoring_add_admin' not in jwtd['role'].split(';'):
        check = await check_sm_admin(jwtd['user_id'], parent_ci, False)
        if not check:
            return json_response({'result': False, 'text': 'Вы не администратор всех ИР-ов сервера!'})
    if post_data['type'] == 'oracle':
        data_func = oracle_data
    elif  post_data['type'] == 'wf':
        data_func = wf_data
    else:
        return json_response({'result': False, 'text': 'Неверный тип приложения'})
    try:
        api_request = await data_func(post_data, parent_ip)
        result = await create_host(api_request, jwtd, request.app['monitoring_add_logger'])
        print(result)
        request.app['monitoring_add_logger'].info(f"User: {jwtd['user_id']} created host "
                                                  f"type:{ post_data['type']} hostdata: {post_data['hostdata']}")
        return json_response({'result': True})
    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error {type(e)} in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})

async def oracle_data(post_data, parent_ip):
    if post_data['hostdata']['dsn'] != 'DSN':
        await create_dsn_if_not_exist('create', post_data['hostdata']['dsn'], post_data['hostdata']['login'],
                                      post_data['hostdata']['pwd'])

    host_macro = [
                    {'macro':'{$DSN_PORT}','value': post_data['hostdata']['port']},
                    {'macro':'{$DSN}','value': post_data['hostdata']['dsn']},
                    {'macro': '{$ORA_SID}', 'value': post_data['hostdata']['sid']}
                ]
    di_request = {'hostname': post_data['hostdata']['hostname'],
                    'env': post_data['env'],
                    'os': post_data['os'],
                    'tag' : 'oracle',
                    'diuid': 'selfportal',
                    'macro' : host_macro,
                    'ip': parent_ip,
                    'port': post_data['hostdata']['port'],
                    'postfix' :  post_data['hostdata']['sid'],
                    'interfacetypeid' : 1
                  }
    return di_request


async def wf_data(post_data, parent_ip):
    host_macro = [
        {'macro': '{$MONITOR_USER}', 'value': post_data['hostdata']['login']},
        {'macro': '{$JMXPORT}', 'value': post_data['hostdata']['port']},
        {'macro': '{$MONITOR_PASS}', 'value': post_data['hostdata']['pwd']}
    ]
    di_request = {'hostname': post_data['hostdata']['hostname'],
                  'env': post_data['env'],
                  'os': post_data['os'],
                  'tag': 'wf',
                  'diuid': 'selfportal',
                  'macro': host_macro,
                  'ip': parent_ip,
                  'port': post_data['hostdata']['port'],
                  'postfix': post_data['hostdata']['port'],
                  'interfacetypeid': 4
                  }


@MonitoringAddRoutes.post('/api/monitoringadd/check_admins')
@check_permissions([
    'monitoring_checkadmins'
], permissions_property = 'role', comparison=match_any)
async def check_admins(request):
    try:
        post_data = await request.json()
        query = post_data['query']
        query = query.replace(',',' ').replace(';','')
        hosts = query.split()
        admins = []
        admins_dict = {}
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(f"select * from configs.databases where name='ORACLESM'")
            db_config = await res.fetchall()
        engine.close()
        db_config = db_config[0].as_tuple()
        os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
        con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(db_config[4],
                                                        db_config[5],
                                                        db_config[1],
                                                        db_config[2],
                                                        db_config[3]))
        cur = con.cursor()
        for ci in hosts:


            ci_query = get_sm_query(ci)
            cur.execute(ci_query)
            res_admins = [row[1] for row in cur.fetchall()]
            admins_dict[ci] = ','.join(res_admins)
            if admins:
                admins = admins & set(res_admins)
            else:
                admins = set(res_admins)
        cur.close()
        return json_response({'result': True, 'admins': list(admins), 'admins_dict':admins_dict})

    except BaseException as e:
        request.app['monitoring_add_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text': str(e)})

