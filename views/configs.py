from aiohttp import web
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET, get_table_list
from aiohttp_jwt import  check_permissions, match_any
import jwt

ConfigsRoutes = web.RouteTableDef()
AdminAllowedConfigs={'selfportal.app_config', 'configs.zabbix', 'configs.databases',
                     'selfportal.views'}
BlacklistedConfigs={'configs.report_date', 'configs.sm_report', 'configs.eventdashboard_filters'}



@ConfigsRoutes.post('/api/configs/get_allowed_configs')
@check_permissions([
    'configs'
], permissions_property = 'role', comparison=match_any)
async def getAllowedConfigs(request):
    try:
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        result = await get_table_list('configs')
        result = result - BlacklistedConfigs
        if 'admin' not in jwtd['role'].split(';'):
            result = result - AdminAllowedConfigs
        else:
            result = result | AdminAllowedConfigs
        return json_response({'result': 'True', 'rows': sorted(list(result))})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False })

async def AllowedConfigs(request):
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
    result = await get_table_list('configs')
    result = result - BlacklistedConfigs
    if 'admin' not in jwtd['role'].split(';'):
        result = result - AdminAllowedConfigs
    else:
        result = result | AdminAllowedConfigs
    return result

@ConfigsRoutes.post('/api/configs/get_data')
@check_permissions([
    'configs'
], permissions_property = 'role', comparison=match_any)
async def get_data(request):
    try:
        post_data = await request.json()
        config_name = post_data['config_source']
        allowed = await AllowedConfigs(request)
        if config_name in allowed:
            db_name, tbl_name =config_name.split('.')
            engine = await db_connect(db_name)
            async with engine.acquire() as conn:
                res = await conn.execute(f'select * from {config_name}')
                columns = [column[0] for column in res.cursor.description]
                result = await res.fetchall()
            engine.close()
            result_temp = []
            for index in range(len(result)):
                tmp_dict = {}
                for col_index in range(len(columns)):
                    tmp_dict[columns[col_index]] = result[index][col_index]
                result_temp.append(tmp_dict)
            return json_response({'result': 'True', 'rows': result_temp, 'columns': columns})
        else:
            return json_response({'result': False})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False })

@ConfigsRoutes.post('/api/configs/update_data')
@check_permissions([
    'configs'
], permissions_property = 'role', comparison=match_any)
async def update_data(request):
    post_data = await request.json()
    row = post_data['row']
    if 'new' in row:
        row.pop('new')
    if '' in row:
        row.pop('')
    index_cols = post_data['index']
    #print(index_cols)
    config_name = post_data['config_source']
    allowed = await AllowedConfigs(request)
    if config_name in allowed:
        db_name, tbl_name = config_name.split('.')
        try:
            engine = await db_connect(db_name)
            set_str = index_str = ''
            for key in row:
                if key != '':
                    if set_str != '':
                        set_str += f',{key}="{row[key]}"'
                    else:
                        set_str = f'{key}="{row[key]}"'
            for key in index_cols:
                if key != '':
                    if index_str != '':
                        index_str += f' and {key}="{row[key]}"'
                    else:
                        index_str = f'{key}="{row[key]}"'
            async with engine.acquire() as conn:
                #print(f'update {config_name} set {set_str} where {index_str}')
                await conn.execute(f'update {config_name} set {set_str} where {index_str}')
                await conn.execute("commit")
            engine.close()

            token = request.headers.get('authorization', None).split()[1]
            jwtd = jwt.decode(token, JWT_SECRET,
                              algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
            user_login = jwtd['user_id']
            request.app['config_logger'].info(f'{user_login} updated in {config_name} row: {row}')
            return json_response({'result': True})
        except BaseException as e:
            request.app['config_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

@ConfigsRoutes.post('/api/configs/remove_data')
@check_permissions([
    'configs'
], permissions_property = 'role', comparison=match_any)
async def remove_data(request):
    post_data = await request.json()
    row = post_data['row']
    index_cols = post_data['index']
    #print(index_cols)
    config_name = post_data['config_source']
    allowed = await AllowedConfigs(request)
    if config_name in allowed:
        db_name, tbl_name = config_name.split('.')
        try:
            index_str = ''
            for key in index_cols:
                if key != '':
                    if index_str != '':
                        index_str += f' and {key}="{row[key]}"'
                    else:
                        index_str = f'{key}="{row[key]}"'
            engine = await db_connect(db_name)
            async with engine.acquire() as conn:
                await conn.execute(f'delete from {config_name} where {index_str}')
                await conn.execute("commit")
            engine.close()
            token = request.headers.get('authorization', None).split()[1]
            jwtd = jwt.decode(token, JWT_SECRET,
                              algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
            user_login = jwtd['user_id']
            request.app['config_logger'].info(f'{user_login} removed in {config_name} row: {row}')
            return json_response({'result': True})
        except BaseException as e:
            request.app['config_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

@ConfigsRoutes.post('/api/configs/add_data')
@check_permissions([
    'configs'
], permissions_property = 'role', comparison=match_any)
async def add_data(request):
    post_data = await request.json()
    row = post_data['row']
    index_col = post_data['index']
    config_name = post_data['config_source']
    if 'new' in row:
        row.pop('new')
    if '' in row:
        row.pop('')
    r = "\'"

    allowed = await AllowedConfigs(request)
    if config_name in allowed:
        db_name, tbl_name = config_name.split('.')
        try:
            engine = await db_connect(db_name)
            async with engine.acquire() as conn:
                await conn.execute(f'insert into {config_name} {str(tuple(row.keys())).replace(r,"")} values {tuple(row.values())}')
                await conn.execute("commit")
            engine.close()
            token = request.headers.get('authorization', None).split()[1]
            jwtd = jwt.decode(token, JWT_SECRET,
                              algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
            user_login = jwtd['user_id']
            request.app['config_logger'].info(f'{user_login} added in {config_name} row: {row}')
            return json_response({'result': True})
        except BaseException as e:
            request.app['config_logger'].error(f'Error: {str(e)}')
    return json_response({'result': False})