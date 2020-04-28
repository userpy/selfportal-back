
db name : users table base:

create table `users` (
`id` int(10) NOT NULL AUTO_INCREMENT,
`login` varchar(20) NOT NULL,
`pw_hash` varchar(100) NOT NULL,
`firstname` varchar(100) NOT NULL,
`mail` varchar(100) NOT NULL,
`mail-sigma` varchar(100) NOT NULL,
`groups` varchar(100) NOT NULL,
`enable` tinyint(1),
PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

eventdashboard action:

Тело
```
[name]:{EVENT.NAME}
[itemid]:{ITEM.ID1}
[inventory]:{INVENTORY.TAG}
[severity]:{TRIGGER.NSEVERITY}
[groups]:{TRIGGER.HOSTGROUP.NAME}
[host]:{HOST.NAME1}
[eventid]:{EVENT.ID}
[date]:{EVENT.DATE}
[time]:{EVENT.TIME}
[tags]:{EVENT.TAGS}
[criticalLevel]:{INVENTORY.URL.B}
[acknowledged]:{EVENT.ACK.STATUS}
[updateaction]:
[updatemessage]:
```
