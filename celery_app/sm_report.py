import cx_Oracle
import os, sys
from pyzabbix import ZabbixAPI
import sqlalchemy as sa
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn

scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)

def zabbix_ip_array(zabbix_arr):
    dict = []
    for zabbix_host in zabbix_arr:
        zabbix_host_interfaces = zabbix_host['interfaces']
        if len(zabbix_host_interfaces) != 0:
            zabbixHostIP = zabbix_host_interfaces[0]["ip"]
            dict.append(zabbixHostIP)
    return list(set(dict))

def find_host_in_zabbix(all_zabbix_hosts, ip_address, SUBTYPE):
    if SUBTYPE in ['Виртуальный', 'LDOM', 'LPAR', 'Логический', 'nPAR',
                   'Физический'] and ip_address is not None and [x for x in ip_address.split(';') if
                                                                 x in all_zabbix_hosts]:
            return 1
    return 0

def prepare(table_item):
    table_item_str = ""
    if not table_item is None:
        if len(table_item.split(';')) > 10:
            table_item = ','.join(table_item.split(';')[:10])
        else:
            table_item = ','.join(table_item.split(';'))
        table_item_str = table_item #.replace('\n', ' ')
    return table_item_str

def generate_sm_table():
    metadata = sa.MetaData()
    return sa.Table('sm_report', metadata,
                   sa.Column('CI', sa.String(20), primary_key=True),
                   sa.Column('hostname', sa.String(300)),
                    sa.Column('dnsname', sa.String(500)),
                    sa.Column('IP', sa.String(500)),
                    sa.Column('dnsdomain', sa.String(300)),
                    sa.Column('OS', sa.String(300)),
                    sa.Column('env', sa.String(300)),
                    sa.Column('admingroup', sa.String(100)),
                   sa.Column('zabbix', sa.String(100)))

def write_data_to_db(data):
    report_data = data
    table = generate_sm_table()
    engine = db_connect()
    with engine.connect() as conn:
        conn.execute(f'delete from configs.sm_report')
        while report_data:
            try:
                conn.execute(table.insert().values(report_data[:50]))
            except:
                print(report_data[:50])
            report_data = report_data[50:]
        conn.execute(f"update configs.report_date set time=current_timestamp() where reportname='sm_report'")
        conn.execute('commit')
    return True

def generate_sm_report():
    zapi_prom = zabbix_conn('Zabbix Prom')
    zapi_testprom = zabbix_conn('Zabbix Test')
    zapi_test = ZabbixAPI('http://10.116.112.14/zabbix', user='zabbixapi',password='zabbixapi')
    zapi_win = zabbix_conn('Zabbix Prom Win')
    engine = db_connect()
    with engine.connect() as conn:
        res = conn.execute(f"select * from configs.databases where name='ORACLESM'")
        result = res.fetchall()
    hpsm_config = result[0]
    os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
    con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(hpsm_config[4],
                                                    hpsm_config[5],
                                                    hpsm_config[1],
                                                    hpsm_config[2],
                                                    hpsm_config[3]))  # @UndefinedVariable
    cur = con.cursor()

    ci_query_all_servers = '''
    select
      k.LOGICAL_NAME,
      k.TPS_NAME,
      k.DNS_ALIAS_LIST,
      LISTAGG(k.IP_ADDRESS_LIST, '; ') WITHIN GROUP (ORDER BY k.LOGICAL_NAME) as IP_ALIAS_LIST,
      k.SUBTYPE, 
      k.TYPE, 
      k.TPS_DNS_NAME, 
      k.TPS_PLATFORM,
      k.OPERATING_SYSTEM,
      k.HPC_STATUS,
      k.ENVIRONMENT,
      k.SB_ADMIN_GROUP2_NAME
    from  
    (select
      t.LOGICAL_NAME,
      t.TPS_NAME,
      LISTAGG(t.DNS_ALIAS, '; ') WITHIN GROUP (ORDER BY t.LOGICAL_NAME) as DNS_ALIAS_LIST,
      t.IP_ADDRESS_LIST, 
      t.SUBTYPE, 
      t.TYPE, 
      t.TPS_DNS_NAME, 
      t.TPS_PLATFORM,
      t.OPERATING_SYSTEM,
      t.HPC_STATUS,
      t.ENVIRONMENT,
      t.SB_ADMIN_GROUP2_NAME
    from (
    select distinct
        a.LOGICAL_NAME,
        a.TPS_NAME,
        d.DNS_ALIAS,
        (case a.SUBTYPE 
        when 'Виртуальный' then b.IP_ADDRESSES 
        when 'Логический' then  a.IP_ADDRESS 
        else b.IP_ADDRESSES end) as IP_ADDRESS_LIST, 
        a.SUBTYPE, 
        a.TYPE,
        a.TPS_DNS_NAME, 
        a.TPS_PLATFORM,
        a.OPERATING_SYSTEM, 
        a.HPC_STATUS,
        a.ENVIRONMENT,
        a.SB_ADMIN_GROUP2_NAME
    from 
        smprimary.device2m1 a, 
        smprimary.device2a2 b,
        smprimary.device2a5 c,
        smprimary.device2a4 d
    WHERE 
        a.LOGICAL_NAME = b.LOGICAL_NAME and 
        a.LOGICAL_NAME = c.LOGICAL_NAME and
        a.LOGICAL_NAME = d.LOGICAL_NAME and
        a.TYPE IN ('server') and
        a.HPC_STATUS = 'Эксплуатируется'
    ) t
    GROUP BY
      t.LOGICAL_NAME,
      t.TPS_NAME,
      t.IP_ADDRESS_LIST, 
      t.SUBTYPE, 
      t.TYPE, 
      t.TPS_DNS_NAME, 
      t.TPS_PLATFORM, 
      t.OPERATING_SYSTEM,
      t.HPC_STATUS,
      t.ENVIRONMENT,
      t.SB_ADMIN_GROUP2_NAME
    ) k
    GROUP BY
      k.LOGICAL_NAME,
      k.TPS_NAME,
      k.DNS_ALIAS_LIST, 
      k.SUBTYPE, 
      k.TYPE, 
      k.TPS_DNS_NAME, 
      k.TPS_PLATFORM, 
      k.OPERATING_SYSTEM,
      k.HPC_STATUS,
      k.ENVIRONMENT,
      k.SB_ADMIN_GROUP2_NAME
    '''

    cur.execute(ci_query_all_servers)
    ci_list_all_servers = cur.fetchall()
    ci_list_all_servers.sort(key=lambda tup: tup[0])

    cur.close()
    con.close()


    allZabbixHosts_prom = zapi_prom.host.get(output=["hostid", "host", "hostip", "name"],
                                   sortfield=["name"],
                                   selectInterfaces=["interfaceid", "hostid", "ip", "dns"],
                                   selectInventory=True)
    allZabbixHosts_test = zapi_test.host.get(output=["hostid", "host", "hostip", "name"],
                                                     sortfield=["name"],
                                                     selectInterfaces=["interfaceid", "hostid", "ip", "dns"],
                                                     selectInventory=True)
    allZabbixHosts_testprom = zapi_testprom.host.get(output=["hostid", "host", "hostip", "name"],
                                             sortfield=["name"],
                                             selectInterfaces=["interfaceid", "hostid", "ip", "dns"],
                                             selectInventory=True)
    allZabbixHosts_win = zapi_win.host.get(output=["hostid", "host", "hostip", "name"],
                                             sortfield=["name"],
                                             selectInterfaces=["interfaceid", "hostid", "ip", "dns"],
                                             selectInventory=True)
    allZabbixHosts_prom = zabbix_ip_array(allZabbixHosts_prom)
    allZabbixHosts_test = zabbix_ip_array(allZabbixHosts_test)
    allZabbixHosts_testprom = zabbix_ip_array(allZabbixHosts_testprom)
    allZabbixHosts_win = zabbix_ip_array(allZabbixHosts_win)


    report_data = []

    for [LOGICAL_NAME, TITLE, DNS_NAME, IP_ADDRESSES, SUBTYPE, TYPE, TPS_DNS_NAME, TPS_PLATFORM, OPERATING_SYSTEM, HPC_STATUS,
          ENVIRONMENT, SB_ADMIN_GROUP2_NAME] in ci_list_all_servers:

        zabbix_host_located_prom = find_host_in_zabbix(allZabbixHosts_prom, IP_ADDRESSES,SUBTYPE)
        zabbix_host_located_test = find_host_in_zabbix(allZabbixHosts_test, IP_ADDRESSES,SUBTYPE)
        zabbix_host_located_testprom = find_host_in_zabbix(allZabbixHosts_testprom, IP_ADDRESSES, SUBTYPE)
        zabbix_host_located_win = find_host_in_zabbix(allZabbixHosts_win, IP_ADDRESSES,SUBTYPE)


        host_location_result = []

        if zabbix_host_located_prom:
            host_location_result.append("PROM")
        if zabbix_host_located_test:
            host_location_result.append("TEST")
        if zabbix_host_located_testprom:
            host_location_result.append("TESTPROM")
        if zabbix_host_located_win:
            host_location_result.append("WIN")
        if not host_location_result:
            host_location_result.append("NO")
        report_data.append(
                (prepare(LOGICAL_NAME), prepare(TITLE), prepare(DNS_NAME),  prepare(IP_ADDRESSES), prepare(TPS_DNS_NAME), prepare(OPERATING_SYSTEM),
                 prepare(ENVIRONMENT), prepare(SB_ADMIN_GROUP2_NAME),','.join(host_location_result)))
    write_data_to_db(report_data)


if __name__ == '__main__':
    generate_sm_report()