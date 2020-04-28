from aiohttp import web
import aiohttp.multipart
from scripts.help_functions import json_response, db_connect, tbl_users, JWT_ALGORITHM, JWT_SECRET
from scripts.help_functions_zbx import get_allowed_grps, zabbix_conn, get_zabbix_conf
from scripts.help_functions_stand_check import get_proxy_ip, getsearch
from scripts.add_user import add_user
from aiohttp_jwt import  check_permissions, match_any
import re
import jwt
import datetime
from celery_app.app import run_test,run_sm_report

SM_Routes = web.RouteTableDef()

column_mapping = {'КЭ':'CI','Имя хоста':'hostname','Имя в DNS':'dnsname','IP':'IP','Домен в DNS':'dnsdomain',
                  'Операционная система':'OS','Класс среды':'env','Сопровождение ОС':'admingroup','Zabbix':'zabbix',
                  ';':'1=0','update':'','delete':'','drop':'','select':'','create':''}

@SM_Routes.post('/api/sm_report/get_time')
@check_permissions([
    'smreport'
], permissions_property = 'role', comparison=match_any)
async def get_time(request):
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res_time = await conn.execute("select time from report_date where reportname='sm_report'")
            time = await res_time.fetchall()
            time = time[0][0]
            if time> datetime.datetime.now() - datetime.timedelta(days=1):
                color = 'green'
            else:
                color= 'red'
            time = datetime.datetime.strftime(time,'%Y-%m-%d %H:%M:%S')
        return json_response(
            {'result': 'True', 'time': time, 'color': color})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

@SM_Routes.post('/api/sm_report/get_data')
@check_permissions([
    'smreport'
], permissions_property = 'role', comparison=match_any)
async def get_data(request):
    post_data = await request.json()
    page_length = int(post_data['params']['page_length']) if post_data['params']['page_length'] else 10
    page_number = int(post_data['params']['page_number']) if post_data['params']['page_number']>0 else 1
    query_filter = post_data['params']['filter'] if post_data['params']['filter'] else ''
    if query_filter:
        for key in column_mapping:
            query_filter = query_filter.replace(f"'{key}'", column_mapping[key].lower())
            query_filter = query_filter.replace(f"'{key.lower()}'",column_mapping[key].lower())
        query_filter = 'where ' + query_filter
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res_count = await conn.execute(f'select count(*) from configs.sm_report {query_filter}')
            result_count = await res_count.fetchall()
            result_count = result_count[0][0]
            result_count = result_count if result_count > 0 else 1
            res = await conn.execute(f"select * from configs.sm_report {query_filter} limit {(page_number-1) * page_length},{page_length}")
            columns = [column[0] for column in res.cursor.description]
            result = await res.fetchall()
        engine.close()
        result_temp = []
        for index in range(len(result)):
            tmp_dict = {}
            for col_index in range(len(columns)):
                tmp_dict[columns[col_index]] = result[index][col_index]
            result_temp.append(tmp_dict)
        return json_response({'result': 'True', 'rows':result_temp, 'pages': result_count})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'rows': [], 'pages': 1 })


@SM_Routes.post('/api/sm_report/get_csv')
@check_permissions([
    'smreport'
], permissions_property = 'role', comparison=match_any)
async def get_csv(request):
    post_data = await request.json()
    query_filter = post_data['params']['filter'] if post_data['params']['filter'] else ''
    if query_filter:
        for key in column_mapping:
            query_filter = query_filter.replace(f"'{key}'", column_mapping[key].lower())
            query_filter = query_filter.replace(f"'{key.lower()}'", column_mapping[key].lower())
        query_filter = 'where ' + query_filter
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(f"select * from configs.sm_report {query_filter}")
            result = await res.fetchall()
        engine.close()
        csv = 'CI;hostname;dnsname;IP;dnsdomain;OS;env;admingroup;zabbix\n'
        for line in result:
            csv += ';'.join(line.as_tuple()) + '\n'
        resp = web.Response(body=csv, headers=aiohttp.multipart.CIMultiDict({'CONTENT-DISPOSITION': 'attachment; filename:"sm_report_%s"' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}))
        resp.content_type = 'text/csv'
        return resp
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


@SM_Routes.post('/api/sm_report/run_task')
@check_permissions([
    'smreport_run'
], permissions_property = 'role', comparison=match_any)
async def run_task(request):
    run_sm_report()
    return json_response({'result': False})

@SM_Routes.post('/api/sm_report/get_filters')
@check_permissions([
    'smreport'
], permissions_property = 'role', comparison=match_any)
async def get_filters(request):
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            os_res = await conn.execute("select distinct(OS) from sm_report")
            os_filter = await os_res.fetchall()
            env_res = await conn.execute("select distinct(env) from sm_report")
            env_filter = await env_res.fetchall()
            zabbix_res = await conn.execute("select distinct(zabbix) from sm_report")
            zabbix_filter = await zabbix_res.fetchall()
        os_filter = [line[0] for line in os_filter]
        env_filter = [line[0] for line in env_filter]
        zabbix_filter = [line[0] for line in zabbix_filter]
        return json_response(
            {'result': 'True', 'os': os_filter, 'env': env_filter, 'zabbix': zabbix_filter})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})