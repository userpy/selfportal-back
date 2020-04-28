from aiohttp import web
from aiohttp_jwt import check_permissions, match_any
import re
import os
import sqlalchemy as sa
from scripts.help_functions import json_response, tbl_app_config
import codecs

allowed_logs = ('fileuz','app','config','monitoring_add','maintenance','zabbix_wan', 'eventdashboard')
ServiceRoutes = web.RouteTableDef()

def readlines_reverse(filename, buffer = 0x20000):
    with codecs.open(filename,'r',encoding='utf8',errors='ignore') as qfile:
        qfile.seek(0, os.SEEK_END)
        size = qfile.tell()
        lines = ['']
        rem = size % buffer
        position = max(0, (size // buffer - 1) * buffer)
        while position >= 0:
            qfile.seek(position, os.SEEK_SET)
            data = qfile.read(rem+buffer) + lines[0]
            rem = 0
            lines = re.findall('[^\n]*\n?', data)
            ix = len(lines) - 2
            while ix > 0:
                yield lines[ix]
                ix -= 1
            position -= buffer
        else:
            yield lines[0]


@ServiceRoutes.post('/api/get_log')
@check_permissions([
    'logsview'
], permissions_property = 'role', comparison=match_any)
async def get_log(request):
    try:
        post_data = await request.json()
        limit = int(post_data['limit']) if post_data['limit'] else 100
        conf = request.app['app_config']
        engine = sa.create_engine(
            f"mysql+pymysql://{conf['database']['user']}:{conf['database']['password']}@"
            f"{conf['database']['ip']}/selfportal")
        with engine.connect() as conn:
            res = conn.execute(
                tbl_app_config.select().with_only_columns([tbl_app_config.c.value]).where(sa.and_(tbl_app_config.c.keyword == post_data['source'],tbl_app_config.c.type =='logging')))
            result = res.fetchall()
        path = result[0][0]
        count = 0
        result = []
        if post_data['source'] in allowed_logs:
            for line in readlines_reverse(path):
                if count < limit:
                    if re.findall(post_data['filter'],line):
                        datetime = ' '.join(line.split()[:2]).split(',')[0]
                        msg = ' '.join(line.split()[6:])
                        result.append({'datetime':datetime,'msg':msg})
                        count += 1
                else:
                    break
        return json_response({'result': True, 'rows' : result })
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


