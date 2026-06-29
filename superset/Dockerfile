# Superset image for the IDS BI layer. The stock image has no driver for some of
# our sources, so we add the SQLAlchemy dialects Superset needs to reach them:
#   - presto://             -> Cassandra (through PrestoDB)  via pyhive[presto]
#   - hive://               -> Hive (HiveServer2)            via pyhive[hive]
#   - mysql+pymysql://      -> MariaDB                       via PyMySQL
#   - druid://              -> Apache Druid                  via pydruid
FROM apache/superset:3.1.3

USER root
RUN pip install --no-cache-dir \
      "pyhive[presto,hive]==0.7.0" \
      "thrift>=0.16.0" \
      "thrift-sasl>=0.4.3" \
      "PyMySQL>=1.1.0" \
      "pydruid[sqlalchemy]>=0.6.5" \
      "requests>=2.31"

# Bootstrap script (db upgrade + admin + init + serve); see compose `command`.
COPY superset-bootstrap.sh /app/superset-bootstrap.sh
RUN chmod +x /app/superset-bootstrap.sh
USER superset
