import json
from aiohttp import web
from aiomysql.sa import create_engine
import sqlalchemy as sa
import configparser
import logging
from logging.handlers import RotatingFileHandler



JWT_SECRET = 'sbertechsecret'
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 3600
JWT_IATEXP_DELTA_SECONDS = 3600 * 24 * 7

metadata = sa.MetaData()
tbl_views = sa.Table('views', metadata,
               sa.Column('view', sa.String(20), primary_key=True),
               sa.Column('groups', sa.String(20)))

host_counter_zabbix_wan = sa.Table('host_counter_zabbix_wan', metadata,
                                   sa.Column('id', sa.Integer, primary_key=True),
                                   sa.Column('zabbix_name', sa.VARCHAR(255)),
                                   sa.Column('wan', sa.Integer),
                                   sa.Column('ext', sa.Integer),
                                   sa.Column('inet', sa.Integer))

tbl_users = sa.Table('users', metadata,
               sa.Column('id', sa.Integer, primary_key=True),
               sa.Column('login', sa.String(20)),
               sa.Column('pw_hash', sa.String(100)),
               sa.Column('firstname', sa.String(20)),
               sa.Column('mail', sa.String(100)),
               sa.Column('mail-sigma', sa.String(100), key='mail_sigma'),
               sa.Column('groups', sa.String(100)),
               sa.Column('enable', sa.Boolean))

tbl_app_config = sa.Table('app_config', metadata,
               sa.Column('keyword', sa.String(20), primary_key=True),
               sa.Column('type', sa.String(100)),
               sa.Column('value', sa.String(100)))

async def get_table_list(db):
    engine = await db_connect(db)
    async with engine.acquire() as conn:
        exec = await conn.execute(f"show tables")
        res = await exec.fetchall()
    engine.close()
    result = set()
    for item in res:
        result.add('.'.join([db,item[0]]))
    return result



def get_role(conf,role):
    engine = sa.create_engine(
        f"mysql+pymysql://{conf['database']['user']}:{conf['database']['password']}@"
        f"{conf['database']['ip']}/selfportal")
    with engine.connect() as conn:
        res = conn.execute(tbl_views.select().with_only_columns([tbl_views.c.view]).where(sa.or_(tbl_views.c.groups.contains(role),tbl_views.c.groups.contains('all'))))
        result = res.fetchall()
    roles = [el[0] for el in result]
    return ';'.join(roles)

def json_response(body='', **kwargs):
    kwargs['body'] = json.dumps(body).encode('utf-8')
    kwargs['content_type'] = 'text/json'
    return web.Response(**kwargs)

async def db_connect(db='selfportal'):
    conf = create_config('app.conf')
    conn = await create_engine(user=conf['database']['user'],password=conf['database']['password'], db=db,
                                 host=conf['database']['ip'])
    return conn

def create_config(path):
    conf = configparser.ConfigParser()
    conf.read(path)
    return conf

def create_logger(conf, filename, rotating = 0):
    engine = sa.create_engine(f"mysql+pymysql://{conf['database']['user']}:{conf['database']['password']}@{conf['database']['ip']}/selfportal")
    with engine.connect() as conn:
        res = conn.execute(tbl_app_config.select().with_only_columns([tbl_app_config.c.value]).where(sa.and_(tbl_app_config.c.keyword == filename,tbl_app_config.c.type =='logging')))
        result = res.fetchall()
    path = result[0][0]
    if rotating:
        file_handler =  logging.handlers.RotatingFileHandler(path, maxBytes=rotating,
                                         backupCount=0)
        log_formatter = logging.Formatter(
            "%(asctime)s [%(filename)s] [%(funcName)s] [%(levelname)s] [%(lineno)d] [%(funcName)s] %(message)s")
    else:
        file_handler = logging.FileHandler(path)
        log_formatter = logging.Formatter(
            "%(asctime)s [%(filename)s] [%(funcName)s] [%(levelname)s] [%(lineno)d] %(message)s")
    file_handler.setFormatter(log_formatter)
    logger = logging.getLogger(filename)
    logger.addHandler(file_handler)
    logger.setLevel('INFO')
    logger.propagate = False
    return logger

def get_ldap_params(conf):
    engine = sa.create_engine(
        f"mysql+pymysql://{conf['database']['user']}:{conf['database']['password']}@"
        f"{conf['database']['ip']}/selfportal")
    with engine.connect() as conn:
        res = conn.execute(tbl_app_config.select().with_only_columns([tbl_app_config.c.keyword,tbl_app_config.c.value])
            .where(tbl_app_config.c.type == 'ldap'))
        result = res.fetchall()
    return dict(result)



