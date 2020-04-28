import os
import sys
import sqlalchemy as sa
from pandas import read_sql
scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn
from celery.utils.log import get_logger
import time

# DISCLAIMER: field "site_address_a" in zabbix contain a IR (informational resource) type from servicemanager

def generate_table(name):
    metadata = sa.MetaData()
    return sa.Table(name, metadata,
                   sa.Column('HostGroupName', sa.String(255), unique=True),
                   sa.Column('IRtype', sa.String(255), unique=False))

def get_host_group_mapping_list_sql(grp_table_name):
    grp_table = generate_table(grp_table_name)
    engine = db_connect()
    with engine.connect() as conn:
        df = read_sql(grp_table.select(),conn)
    return df

# input: ['88005']
def softly_clear_group(groupid,zapi):
    list_of_hosts = [host["hostid"] for host in zapi.host.get(groupids = groupid,output = ["hostid"])]
    splitted_list = []
    for i in range(len(list_of_hosts)):
        if i % 200 == 0:
            splitted_list.append([])
        splitted_list[-1].append(list_of_hosts[i])
    for part in splitted_list:
        print("deleted from ", zapi.hostgroup.massremove(groupids = groupid, hostids = part))
        time.sleep(1)

# input: ['88005'],['553535','553536','553537']
def softly_fill_group(groupid,list_of_hosts,zapi):
    splitted_list = []
    for i in range(len(list_of_hosts)):
        if i % 200 == 0:
            splitted_list.append([])
        splitted_list[-1].append(list_of_hosts[i])
    for part in splitted_list:
        print("addedd in ", zapi.hostgroup.massadd(groups=groupid, hosts=part))
        time.sleep(1)

def reallocate_hosts_in_base_groups(source):
    logger = get_logger('config')
    ZabbixConfig = get_zabbix_conf()
    zapi = zabbix_conn(source,ZabbixConfig)

    # WARNING! this script can processing OS-groups only! For that purpose there will be "/OS" prefix, but in further
    # exploitation script can be modified for processing other suffixes, such as "/App"
    suffix = "/OS"
    groups_array = {}
    Group_table_mapping = get_host_group_mapping_list_sql('IRtype_to_Group')
    for element in range(len(Group_table_mapping)):
        key = Group_table_mapping.iloc[element]['HostGroupName'] + suffix
        value = Group_table_mapping.iloc[element]['IRtype'].split(",")
        groups_array[key] = value

    # define initial OS groups
    # output: [{"groupid1":"groupname1"},{"groupid2":"groupname2"}]
    list_of_os_groups = ["IS OS HP-UX", "IS OS Solaris", "IS OS Linux", "IS OS AIX", "IS OS Windows"]
    base_group_ids = zapi.hostgroup.get(output=["groupid", "name"], filter={"name": list_of_os_groups})

    # get all hosts (only groups and "address A" properties)
    all_zabbix_hosts = zapi.host.get(output=["hostid", "groupids", "inventory_mode"],
                                     selectInventory=True, groupids=[x["groupid"] for x in base_group_ids])

    # exceptions processing
    host_with_disabled_inventory = []
    host_with_empty_inventory = []
    host_with_empty_address_a = []
    host_for_work = []
    for host in all_zabbix_hosts:
        if type(host["inventory"]) == list:
            host_with_empty_inventory.append(host)
            continue
        if host["inventory_mode"] == "-1":
            host_with_disabled_inventory.append(host)
            continue
        if host["inventory"]["site_address_a"] == "":
            host_with_empty_address_a.append(host)
            continue
        host_for_work.append([host["hostid"], host["inventory"]["site_address_a"]])

    # check if dictionary of APP groups is consistent
    individual_address_a = []
    for item in host_for_work:
        if len(item[1].split(";")) > 1:
            item_array = item[1].split(";")
            for array_element in item_array:
                if array_element not in individual_address_a:
                    individual_address_a.append(array_element)
        else:
            if item[1] not in individual_address_a:
                individual_address_a.append(item[1])
    address_a_in_array = []
    address_a_not_in_array = []
    for address in individual_address_a:
        found = False
        for array_key, array_value in groups_array.items():
            if address in array_value:
                found = True
        if found == True:
            address_a_in_array.append(address)
        else:
            address_a_not_in_array.append(address)

    # create base_group:hosts array
    GroupToHosts = {}
    for item, value in groups_array.items():
        GroupToHosts[item] = []
    for host in host_for_work:
        host_address_a = host[1].split(";")
        for host_separate_address_a in host_address_a:
            for hostgroup, address_a_massive in groups_array.items():
                if host_separate_address_a in address_a_massive:
                    GroupToHosts[hostgroup].append(host[0])

    # search groups in current instance and creating if it's not exist
    groupname_array = [groupname for groupname in GroupToHosts]
    application_group_ids = zapi.hostgroup.get(output=["groupid", "name"], filter={"name": groupname_array})
    if len(groupname_array) != len(application_group_ids):
        summary_array = set(groupname_array)
        founded_groups = set([x["name"] for x in application_group_ids])
        not_founded_groups = list(summary_array - founded_groups)
        for not_founded_group in not_founded_groups:
            print("I AM CREATE GROUP " + not_founded_group + " !!!")
            zapi.hostgroup.create(name=not_founded_group)
            new_application_group = \
            zapi.hostgroup.get(output=["groupid", "name"], filter={"name": [not_founded_group]})[0]
            application_group_ids.append(new_application_group)

    # reassign hosts on groups
    for groupname in application_group_ids:
        logger.info(f'Reallocating hosts in base OS-groups for {source} groupsUpdated:{groupname["name"]}')
        softly_clear_group([groupname["groupid"]],zapi)
        softly_fill_group([groupname["groupid"]], GroupToHosts[groupname["name"]],zapi)

if __name__ == '__main__':
    reallocate_hosts_in_base_groups('Zabbix Prom')