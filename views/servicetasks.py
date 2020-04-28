from aiohttp import web
from scripts.help_functions import json_response
from aiohttp_jwt import  check_permissions, match_any
from celery_app.app import run_update_mapping,run_update_hosts_in_groups,run_update_inventory, \
    run_reallocate_hosts_in_base_groups, run_remove_deleted_hosts, run_link_correct_template_to_hosts_by_hostgroups

ServiceTasksRoutes = web.RouteTableDef()

tasks = {
    'mapping_task': run_update_mapping,
    'group_task': run_update_hosts_in_groups,
    'inventory_task': run_update_inventory,
    'reallocate_hosts_in_base_groups': run_reallocate_hosts_in_base_groups,
    'remove_deleted_hosts': run_remove_deleted_hosts,
    'link_correct_template_to_hosts_by_hostgroups': run_link_correct_template_to_hosts_by_hostgroups
}

@ServiceTasksRoutes.post('/api/servicetasks/run_task')
@check_permissions([
    'servicetasks'
], permissions_property = 'role', comparison=match_any)
async def run_task(request):
    try:
        post_data = await request.json()
        config_name = post_data['source']
        task_name = post_data['task']
        tasks[task_name](config_name)
        return json_response({'result': True})
    except:
        return json_response({'result': False})

@ServiceTasksRoutes.post('/api/servicetasks/run_mapping_task')
@check_permissions([
    'servicetasks'
], permissions_property = 'role', comparison=match_any)
async def run_mapping_task(request):
    try:
        post_data = await request.json()
        config_name = post_data['source']
        run_update_mapping(config_name)
        return json_response({'result': True})
    except:
        return json_response({'result': False})

@ServiceTasksRoutes.post('/api/servicetasks/run_group_task')
@check_permissions([
    'servicetasks'
], permissions_property = 'role', comparison=match_any)
async def run_group_task(request):
    try:
        post_data = await request.json()
        config_name = post_data['source']
        run_update_hosts_in_groups(config_name)
        return json_response({'result': True})
    except:
        return json_response({'result': False})

@ServiceTasksRoutes.post('/api/servicetasks/run_inventory_task')
@check_permissions([
    'servicetasks'
], permissions_property = 'role', comparison=match_any)
async def run_inventory_task(request):
    try:
        post_data = await request.json()
        config_name = post_data['source']
        run_update_inventory(config_name)
        return json_response({'result': True})
    except:
        return json_response({'result': False})