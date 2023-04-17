--
-- Table structure for table `solar5`
--

DROP TABLE IF EXISTS `solar5`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `solar5` (
  `year` int NOT NULL,
  `month` int NOT NULL,
  `day` int NOT NULL,
  `hour` int NOT NULL,
  `minute` int NOT NULL,
  `powerUsed` float NOT NULL DEFAULT '0',
  `gridIn` float NOT NULL DEFAULT '0',
  `solarIn` float NOT NULL DEFAULT '0',
  `batteryIn` float NOT NULL DEFAULT '0',
  `batteryPer` float NOT NULL DEFAULT '0',
  `solarInToday` float NOT NULL DEFAULT '0',
  `gridInToday` float NOT NULL DEFAULT '0',
  `gridOutToday` float NOT NULL DEFAULT '0',
  `updated_timstm` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

