import os, sys, time
import sqlalchemy as sa
from pandas import read_sql
scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn
from celery.utils.log import get_logger

excluded_groups = ['Sigma servers', 'IS SAN/ТБ', 'IS SHD/SHD']

def softly_remove_hosts(hostids, zapi):
    splitted_list = []
    for i in range(len(hostids)):
        if i % 50 == 0:
            splitted_list.append([])
        splitted_list[-1].append(hostids[i])
    for part in splitted_list:
        print("deleted from ", zapi.host.delete(*part))
        time.sleep(3)

# fill the non-exception lists:
## input (hostids): ['45621']
## output: True/False
def check_if_latest_data_more_than_week_old(hostid, local_timestamp, zapi, duration_of_nodata_days = 7):
    all_item_of_host = zapi.item.get(hostids = hostid, monitored = True, output = ['type', 'lastclock'])
    lastvalue_OK = False
    for item in all_item_of_host:
        if (item['type'] != '15' and item['type'] != '3' and item['type'] != '5'): ### if not equal calculated|zabbix internal| simple check
            if int(item['lastclock']) < int(local_timestamp):
                if (int(local_timestamp) - int(item['lastclock']))/86400 < duration_of_nodata_days:
                    lastvalue_OK = True
    return lastvalue_OK

# filtered excluded groups
# input:  ['1488','1489'], ['57843']
## output: ['1489']
def filter_hostids_by_group(hostids, groupid,zapi):
    all_group_hosts = [x['hostid'] for x in zapi.host.get(hostids = hostids, groupids = groupid, output = 'hostid')]
    return all_group_hosts

def remove_deleted_hosts(source):
    logger = get_logger('config')
    ZabbixConfig = get_zabbix_conf()
    zapi = zabbix_conn(source, ZabbixConfig)

    excluded_groupids = [group['groupid'] for group in
                         zapi.hostgroup.get(output=['groupid', 'name'], filter={'name': excluded_groups})]
    all_hosts = zapi.host.get(output=['hostid', 'inventory_mode'], selectInventory=['serialno_a', 'url_c'],
                              selectInterfaces=['ip', 'useip'])
    # exceptions processing
    host_with_disabled_inventory = []
    host_with_empty_inventory = []
    host_with_empty_url_c = []
    host_with_empty_serialno_a = []
    host_with_UNKNOWN_fields_inventory = []
    host_for_work = []
    for host in all_hosts:
        if type(host["inventory"]) == list:
            host_with_empty_inventory.append(host['hostid'])
            continue
        if host["inventory_mode"] == "-1":
            host_with_disabled_inventory.append(host['hostid'])
            continue
        if host["inventory"]["url_c"] == "":
            host_with_empty_url_c.append(host['hostid'])
            continue
        if host["inventory"]["serialno_a"] == "":
            host_with_empty_serialno_a.append(host['hostid'])
            continue
        if (host["inventory"]["serialno_a"] == "UNKNOWN" or host["inventory"]["url_c"] == "UNKNOWN"):
            host_with_UNKNOWN_fields_inventory.append(host['hostid'])
            continue
        host_for_work.append(host)

    hosts_with_ip_localhost = []
    hosts_not_active_with_weekly_latest_data = []
    hosts_not_active_without_weekly_latest_data = []
    local_timestamp = time.time()
    for host in host_for_work:
        for interface in host['interfaces']:
            if (interface['useip'] == '1' and interface['ip'] == '127.0.0.1'):
                hosts_with_ip_localhost.append(host['hostid'])
        if host['inventory']['url_c'] == 'Deleted':
            if check_if_latest_data_more_than_week_old([host['hostid']],local_timestamp,zapi):
                hosts_not_active_with_weekly_latest_data.append(host['hostid'])
            else:
                hosts_not_active_without_weekly_latest_data.append(host['hostid'])

    hostids_from_excluded_groups = filter_hostids_by_group(hosts_not_active_without_weekly_latest_data, excluded_groupids,zapi)
    HostidsForRemove = list(set(hosts_not_active_without_weekly_latest_data) - set(hostids_from_excluded_groups))
    softly_remove_hosts(HostidsForRemove,zapi)
    logger.info(f"Completed remove_deleted_hosts on source: {source}")

if __name__ == '__main__':
    remove_deleted_hosts('Zabbix Prom')