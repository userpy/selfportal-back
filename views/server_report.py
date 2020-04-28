from aiohttp import web
from scripts.help_functions import json_response
from aiohttp_jwt import  check_permissions, match_any
from scripts.help_functions_zbx import async_zabbix_conn
from scripts.server_report import get_host_result


ServerReport_Routes = web.RouteTableDef()

@ServerReport_Routes.post('/api/server_report/get_host')
@check_permissions([
    'serverreport'
], permissions_property = 'role', comparison=match_any)
async def get_template(request):
    try:
        post_data = await request.json()
        res = await get_host_result(post_data['hostname'],post_data['source'])
        return json_response({'result': True, 'host': res})
    except BaseException as e:
        raise
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})
