-- MySQL dump 10.17  Distrib 10.3.22-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: 127.0.0.1    Database: configs
-- ------------------------------------------------------
-- Server version	10.4.12-MariaDB-1:10.4.12+maria~bionic

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `Hostgroup_Template_table`
--

DROP TABLE IF EXISTS `Hostgroup_Template_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `Hostgroup_Template_table` (
  `id` mediumint(9) NOT NULL AUTO_INCREMENT,
  `HostGroupName` varchar(255) NOT NULL,
  `TemplateName` varchar(1000) NOT NULL,
  `OS_type` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM AUTO_INCREMENT=13 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `IRtype_to_Group`
--

DROP TABLE IF EXISTS `IRtype_to_Group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `IRtype_to_Group` (
  `HostGroupName` varchar(255) NOT NULL,
  `IRtype` varchar(255) NOT NULL,
  PRIMARY KEY (`HostGroupName`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `celery_periodic_tasks`
--

DROP TABLE IF EXISTS `celery_periodic_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `celery_periodic_tasks` (
  `id` int(10) NOT NULL AUTO_INCREMENT,
  `hour` tinyint(4) NOT NULL,
  `minute` tinyint(4) NOT NULL,
  `task_name` varchar(500) NOT NULL,
  `args` varchar(500) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM AUTO_INCREMENT=50 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `databases`
--

DROP TABLE IF EXISTS `databases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `databases` (
  `name` varchar(30) NOT NULL,
  `host` varchar(30) NOT NULL,
  `port` varchar(5) NOT NULL,
  `sid` varchar(30) NOT NULL,
  `login` varchar(30) NOT NULL,
  `password` varchar(30) NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `eventdashboard_filters`
--

DROP TABLE IF EXISTS `eventdashboard_filters`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `eventdashboard_filters` (
  `author` varchar(100) NOT NULL,
  `name` varchar(128) NOT NULL,
  `query` varchar(500) NOT NULL,
  `time` varchar(128) NOT NULL,
  `row_count` varchar(30) NOT NULL,
  `severities` varchar(500) NOT NULL,
  `selected_cols` varchar(500) NOT NULL,
  `colors` varchar(1000) NOT NULL,
  `width` varchar(500) NOT NULL,
  PRIMARY KEY (`author`,`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping`
--

DROP TABLE IF EXISTS `host_group_mapping`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_app`
--

DROP TABLE IF EXISTS `host_group_mapping_app`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_app` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_ci`
--

DROP TABLE IF EXISTS `host_group_mapping_ci`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_ci` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_ci_win`
--

DROP TABLE IF EXISTS `host_group_mapping_ci_win`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_ci_win` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_di`
--

DROP TABLE IF EXISTS `host_group_mapping_di`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_di` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_tdi`
--

DROP TABLE IF EXISTS `host_group_mapping_tdi`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_tdi` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_testprom`
--

DROP TABLE IF EXISTS `host_group_mapping_testprom`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_testprom` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `host_group_mapping_ts_win`
--

DROP TABLE IF EXISTS `host_group_mapping_ts_win`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `host_group_mapping_ts_win` (
  `groupid` int(10) NOT NULL,
  `groupname` varchar(100) NOT NULL,
  `CIs` varchar(200) NOT NULL,
  PRIMARY KEY (`groupid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mssql_users`
--

DROP TABLE IF EXISTS `mssql_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `mssql_users` (
  `dsn` varchar(50) NOT NULL,
  `UserID` varchar(30) NOT NULL,
  `Password` varchar(100) NOT NULL,
  PRIMARY KEY (`dsn`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `network_zones`
--

DROP TABLE IF EXISTS `network_zones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `network_zones` (
  `zonename` varchar(100) NOT NULL,
  `ip_networks` text DEFAULT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oracle_users`
--

DROP TABLE IF EXISTS `oracle_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `oracle_users` (
  `dsn` varchar(50) NOT NULL,
  `UserID` varchar(30) NOT NULL,
  `Password` varchar(100) NOT NULL,
  PRIMARY KEY (`dsn`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `report_date`
--

DROP TABLE IF EXISTS `report_date`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `report_date` (
  `reportname` varchar(20) NOT NULL,
  `time` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`reportname`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sm_report`
--

DROP TABLE IF EXISTS `sm_report`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sm_report` (
  `CI` varchar(20) NOT NULL DEFAULT '',
  `hostname` varchar(300) DEFAULT NULL,
  `dnsname` varchar(500) DEFAULT NULL,
  `IP` varchar(500) DEFAULT NULL,
  `dnsdomain` varchar(200) DEFAULT NULL,
  `OS` varchar(100) DEFAULT NULL,
  `env` varchar(100) DEFAULT NULL,
  `admingroup` varchar(500) DEFAULT NULL,
  `zabbix` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`CI`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `zabbix`
--

DROP TABLE IF EXISTS `zabbix`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `zabbix` (
  `name` varchar(30) NOT NULL,
  `url` varchar(50) NOT NULL,
  `api_url` varchar(50) NOT NULL,
  `search_url` varchar(100) NOT NULL,
  `user_name` varchar(50) DEFAULT NULL,
  `login` varchar(30) NOT NULL,
  `password` varchar(30) NOT NULL,
  `group_table` varchar(100) NOT NULL,
  `email_media_type` int(10) DEFAULT NULL,
  `phone_media_type` int(10) DEFAULT NULL,
  `default_user_group` int(10) DEFAULT NULL,
  `SelectShow` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `zabbix_proxy`
--

DROP TABLE IF EXISTS `zabbix_proxy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `zabbix_proxy` (
  `zabbix` varchar(30) NOT NULL,
  `proxy_id` varchar(6) NOT NULL,
  `tag` varchar(200) DEFAULT NULL,
  `ip` varchar(15) NOT NULL,
  `ip_networks` varchar(300) DEFAULT NULL,
  PRIMARY KEY (`zabbix`,`proxy_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `zabbix_templates`
--

DROP TABLE IF EXISTS `zabbix_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `zabbix_templates` (
  `zabbix` varchar(30) NOT NULL,
  `proxy_type` varchar(20) NOT NULL,
  `templates` varchar(200) NOT NULL,
  `parent_templates` varchar(200) NOT NULL,
  `groups` varchar(200) NOT NULL,
  PRIMARY KEY (`zabbix`,`proxy_type`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `zabbix_types`
--

DROP TABLE IF EXISTS `zabbix_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `zabbix_types` (
  `zabbix` varchar(100) NOT NULL,
  `env` varchar(100) NOT NULL,
  `type` varchar(200) NOT NULL,
  PRIMARY KEY (`zabbix`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2020-03-20 13:12:39
