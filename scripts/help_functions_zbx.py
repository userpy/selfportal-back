from pyzabbix import ZabbixAPI
from aiozabbix import ZabbixAPI as AsyncAPI
import aiohttp
from scripts.help_functions import db_connect
import sqlalchemy as sa

metadata = sa.MetaData()
tbl_zabbix = sa.Table('zabbix', metadata,
                sa.Column('name', sa.Integer, primary_key=True),
                sa.Column('url', sa.String(50)),
                sa.Column('api_url', sa.String(50)),
                sa.Column('search_url', sa.String(50)),
                sa.Column('user_name', sa.String(50)),
                sa.Column('login', sa.String(30)),
                sa.Column('password', sa.String(30)),
                sa.Column('group_table', sa.String(100)),
                sa.Column('email_media_type', sa.Integer),
                sa.Column('phone_media_type', sa.Integer),
                sa.Column('default_user_group', sa.Integer),
                sa.Column('SelectShow', sa.String(30)))

async def generate_table(name):
    metadata = sa.MetaData()
    return sa.Table(name, metadata,
                   sa.Column('groupid', sa.Integer, primary_key=True),
                   sa.Column('groupname', sa.String(100)),
                   sa.Column('CIs', sa.String(200)))

async def get_zabbix_conf(type='infra'):
    ZabbixConfig = {}
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        query = tbl_zabbix.select().where(tbl_zabbix.c.SelectShow == type)
        res = await conn.execute(query)
        result = await res.fetchall()
    engine.close()
    cols = res.keys()
    for el in result:
        ZabbixConfig[el[0]] = {}
        for col in cols:
            ZabbixConfig[el[0]][col] = el[col]
    return ZabbixConfig

async def zabbix_conn(source, type='infra'):
    ZabbixConfig = await get_zabbix_conf(type)
    zapi = ZabbixAPI(ZabbixConfig[source]['api_url'], user=ZabbixConfig[source]['login'],
                     password=ZabbixConfig[source]['password'])
    return zapi

async def get_allowed_grps(source,with_id = False):
    ZabbixConfig = await get_zabbix_conf()
    grp_table_name = ZabbixConfig[source]['group_table']
    grp_table = await generate_table(grp_table_name)
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(sa.select([grp_table.c.groupid,grp_table.c.groupname]))
        result = await res.fetchall()
    engine.close()
    allowed_groups_id = [item[0] for item in result]
    zapi = await async_zabbix_conn(source)
    allowed_groups_zabbix = await zapi.hostgroup.get(output=['name'], groupids=allowed_groups_id)
    await zapi.close()
    if with_id:
        allowed_groups = {}
        for el in allowed_groups_zabbix:
            allowed_groups[el['name']]=el['groupid']
    else:
        allowed_groups = [el['name'] for el in allowed_groups_zabbix]
    return allowed_groups

async def get_showed_zabbix():
    engine = await db_connect('configs')
    async with engine.acquire() as conn:
        res = await conn.execute(tbl_zabbix.select().with_only_columns([tbl_zabbix.c.name,tbl_zabbix.c.url,tbl_zabbix.c.user_name,tbl_zabbix.c.search_url,tbl_zabbix.c.SelectShow]).where(tbl_zabbix.c.SelectShow != '0'))
        result = await res.fetchall()
    engine.close()
    return result

class AsyncZabbixAPI(AsyncAPI):
    def __init__(self,url):
        client_sess = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
        super().__init__(server=url,client_session=client_sess)
    async def close(self):
        await self.client_session.close()


async def async_zabbix_conn(source,type = 'infra'):
    ZabbixConfig = await get_zabbix_conf(type)
    zapi = AsyncZabbixAPI(ZabbixConfig[source]['api_url'])
    await zapi.login(ZabbixConfig[source]['login'],ZabbixConfig[source]['password'])
    return zapi