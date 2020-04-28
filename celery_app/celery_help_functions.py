from scripts.help_functions_zbx import tbl_zabbix
from scripts.help_functions import create_config
import sqlalchemy as sa
from pyzabbix import ZabbixAPI

def db_connect():
    conf = create_config('app.conf')
    conn = sa.create_engine(f"mysql+pymysql://{conf['database']['user']}:{conf['database']['password']}@{conf['database']['ip']}/configs")
    return conn

def get_zabbix_conf():
    ZabbixConfig = {}
    engine = db_connect()
    with engine.connect() as conn:
        res = conn.execute(tbl_zabbix.select())
        result = res.fetchall()
    cols = res.keys()
    for el in result:
        ZabbixConfig[el[0]] = {}
        for col in cols:
            ZabbixConfig[el[0]][col] = el[col]
    return ZabbixConfig

def zabbix_conn(source, config=None):
    if config is None:
        ZabbixConfig = get_zabbix_conf()
    else:
        ZabbixConfig = config
    zapi = ZabbixAPI(ZabbixConfig[source]['url'], user=ZabbixConfig[source]['login'],
                     password=ZabbixConfig[source]['password'])
    return zapi