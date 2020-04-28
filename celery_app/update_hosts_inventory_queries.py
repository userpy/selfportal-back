ci_query_all_servers = '''
select
  t.LOGICAL_NAME,
  t.TPS_NAME, 
  t.IP_ADDRESS_LIST, 
  t.SUBTYPE, 
  t.TYPE, 
  t.TPS_ASSIGNEE_NAME,
  t.TPS_DNS_NAME, 
  t.TPS_PLATFORM, 
  t.HPC_STATUS, 
  t.SB_RESPONSIBILITY_WG_NAME, 
  t.ASSIGNMENT,
  t.SB_SERVICE_LEVEL,
  t.ENVIRONMENT,
  t.SB_ADMIN_GROUP2_NAME,
  LISTAGG(t.TPS_SUPPORT_GROUPS, '; ') WITHIN GROUP (ORDER BY t.LOGICAL_NAME) as ADMINISTRATOR_LIST
from (
select distinct
    a.LOGICAL_NAME,
    a.TPS_NAME, 
    (case a.SUBTYPE 
    when 'Виртуальный' then b.IP_ADDRESSES 
    when 'Логический' then  a.IP_ADDRESS 
    else b.IP_ADDRESSES end) as IP_ADDRESS_LIST, 
    a.SUBTYPE, 
    a.TYPE, 
    a.TPS_ASSIGNEE_NAME,
    a.TPS_DNS_NAME, 
    a.TPS_PLATFORM, 
    a.HPC_STATUS, 
    a.SB_RESPONSIBILITY_WG_NAME, 
    a.ASSIGNMENT,
    a.SB_SERVICE_LEVEL,
    a.ENVIRONMENT,
    a.SB_ADMIN_GROUP2_NAME,
    c.TPS_SUPPORT_GROUPS,
    ROW_NUMBER() OVER (PARTITION BY a.LOGICAL_NAME ORDER BY c.TPS_SUPPORT_GROUPS) as ROW_NUM
from 
    smprimary.device2m1 a, 
    smprimary.device2a2 b,
    smprimary.device2a5 c
WHERE 
    a.LOGICAL_NAME = b.LOGICAL_NAME and 
    a.LOGICAL_NAME = c.LOGICAL_NAME and
    a.TYPE IN ('server', 'cluster')
) t
where t.row_num <= 5
GROUP BY
  t.LOGICAL_NAME,
  t.TPS_NAME, 
  t.IP_ADDRESS_LIST, 
  t.SUBTYPE, 
  t.TYPE, 
  t.TPS_ASSIGNEE_NAME,
  t.TPS_DNS_NAME, 
  t.TPS_PLATFORM, 
  t.HPC_STATUS, 
  t.SB_RESPONSIBILITY_WG_NAME, 
  t.ASSIGNMENT,
  t.SB_SERVICE_LEVEL,
  t.ENVIRONMENT,
  t.SB_ADMIN_GROUP2_NAME
'''

ci_ir_group_email = '''
select
    a.HPC_NAME_NAME,
    a.HPC_EMAIL
from
    smprimary.assignmentm1 a
where a.HPC_EMAIL is not null
'''

ci_query_all_services = '''
select
  t.LOGICAL_NAME,
  t.TPS_NAME, 
  t.SUBTYPE, 
  t.TYPE, 
  t.TPS_ASSIGNEE_NAME,
  t.TPS_DNS_NAME, 
  t.TPS_PLATFORM, 
  t.HPC_STATUS, 
  t.SB_RESPONSIBILITY_WG_NAME, 
  t.ASSIGNMENT,
  t.SB_ADMINISTRATOR_GROUP,
  t.SB_SERVICE_LEVEL,
  t.ENVIRONMENT,
  t.SB_ADMIN_GROUP2_NAME,
  LISTAGG(t.TPS_SUPPORT_GROUPS, '; ') WITHIN GROUP (ORDER BY t.LOGICAL_NAME) as ADMINISTRATOR_LIST
from (
select distinct
    a.LOGICAL_NAME,
    a.TPS_NAME, 
    a.SUBTYPE, 
    a.TYPE, 
    a.TPS_ASSIGNEE_NAME,
    a.TPS_DNS_NAME, 
    a.TPS_PLATFORM, 
    a.HPC_STATUS, 
    a.SB_RESPONSIBILITY_WG_NAME, 
    a.ASSIGNMENT,
    a.SB_ADMINISTRATOR_GROUP,
    a.SB_SERVICE_LEVEL,
    a.ENVIRONMENT,
    a.SB_ADMIN_GROUP2_NAME,
    c.TPS_SUPPORT_GROUPS,
    ROW_NUMBER() OVER (PARTITION BY a.LOGICAL_NAME ORDER BY c.TPS_SUPPORT_GROUPS) as ROW_NUM
from 
    smprimary.device2m1 a,
    smprimary.device2a5 c
WHERE 
    a.LOGICAL_NAME = c.LOGICAL_NAME and
    a.TYPE IN ('collection', 'sbvirtcluster', 'environmenttype', 'infresource', 'dbmsinstance','bizservice', 'cluster') 
) t
where t.row_num <= 100
GROUP BY
  t.LOGICAL_NAME,
  t.TPS_NAME, 
  t.SUBTYPE, 
  t.TYPE, 
  t.TPS_ASSIGNEE_NAME,
  t.TPS_DNS_NAME, 
  t.TPS_PLATFORM, 
  t.HPC_STATUS, 
  t.SB_RESPONSIBILITY_WG_NAME, 
  t.ASSIGNMENT,
  t.SB_ADMINISTRATOR_GROUP,
  t.SB_SERVICE_LEVEL,
  t.ENVIRONMENT,
  t.SB_ADMIN_GROUP2_NAME
'''

ci_relations_query_all = '''
                        select 
                            LOGICAL_NAME,
                            TPS_RELATED_CIS
                        from 
                            smprimary.CIRELATIONSM1
                            '''


contact_query_all = '''
                    select 
                        FULL_NAME, 
                        EMAIL, 
                        TITLE, 
                        HPC_DEPT_NAME, 
                        FIRST_NAME, 
                        LAST_NAME 
                    from 
                        smprimary.contctsm1
                    '''
