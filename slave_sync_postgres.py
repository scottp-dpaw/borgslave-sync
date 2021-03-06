import logging
import os
import tempfile
import subprocess

from slave_sync_env import (
    GEOSERVER_PGSQL_HOST,GEOSERVER_PGSQL_PORT,GEOSERVER_PGSQL_DATABASE,GEOSERVER_PGSQL_USERNAME,
    CACHE_PATH,
    env
)
from slave_sync_task import (
    update_auth_job,update_feature_job,db_feature_task_filter,remove_feature_job
)

logger = logging.getLogger(__name__)

schema_name = lambda sync_job: "{0}_{1}_{2}".format(sync_job["schema"],sync_job["data_schema"],sync_job["outdated_schema"])
table_name = lambda sync_job: "{0}:{1}".format(sync_job["schema"],sync_job["name"])

psql_cmd = ["psql","-h",GEOSERVER_PGSQL_HOST,"-p",GEOSERVER_PGSQL_PORT,"-d",GEOSERVER_PGSQL_DATABASE,"-U",GEOSERVER_PGSQL_USERNAME,"-w","-c",None]

def update_auth(sync_job,task_metadata,task_status):
    with tempfile.NamedTemporaryFile(mode="w+b", suffix=".sql") as sql_file:
        sql_file.file.write(sync_job['job_file_content'])
        sql_file.file.close()
        
        psql_cmd[len(psql_cmd) - 2] = "-f"
        psql_cmd[len(psql_cmd) - 1] = sql_file.name

        logger.info("Executing {}...".format(repr(psql_cmd)))
        psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        psql_output = psql.communicate()
        if psql_output[1] and psql_output[1].strip():
            logger.info("stderr: {}".format(psql_output[1]))
            task_status.set_message("message",psql_output[1])
        if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
            raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))


def create_postgis_extension(sync_job,task_metadata,task_status):
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) - 1] = "CREATE EXTENSION IF NOT EXISTS postgis;"
    
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))

def create_schema(sync_job,task_metadata,task_status):
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) - 1] = ";".join(["CREATE SCHEMA IF NOT EXISTS \"{0}\"".format(s) for s in [sync_job["schema"],sync_job["data_schema"],sync_job["outdated_schema"]] if s])
    
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))

def move_outdated_table(sync_job,task_metadata,task_status):

    #move table to outdated schema
    #1.if data table does not exist, no need to move
    #2.if outdated table does not exist, move the data table to outdated schema
    #3.if view  does not exist, drop the outdated table, and move the data table to outdated schema
    #4.if view does not depend on the outdated schema, drop the outdated table and move the data table to outdated schema
    #5.if view depends on the outdated schema, drop the data table
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) -1] = """
DO 
$$BEGIN
    IF EXISTS (SELECT 1 FROM pg_class a join pg_namespace b on a.relnamespace = b.oid WHERE a.relname='{1}' and b.nspname='{0}') THEN
        IF EXISTS (SELECT 1 FROM pg_class a join pg_namespace b on a.relnamespace = b.oid WHERE a.relname='{1}' and b.nspname='{2}') THEN
            IF EXISTS (SELECT 1 FROM pg_class a join pg_namespace b on a.relnamespace = b.oid WHERE a.relname='{1}' and b.nspname='{3}') THEN
                IF EXISTS (SELECT 1 FROM (SELECT a1.* FROM pg_depend a1 JOIN (SELECT oid FROM pg_class WHERE relname='pg_class') a2 ON a1.refclassid = a2.oid JOIN (SELECT b1.oid FROM pg_class b1 JOIN pg_namespace b2 ON b1.relnamespace = b2.oid WHERE b1.relname='{1}' and b2.nspname='{3}') a3 ON a1.refobjid = a3.oid JOIN (SELECT oid FROM pg_class WHERE relname='pg_rewrite') a4 ON a1.classid = a4.oid) t1 JOIN (SELECT d1.* FROM pg_depend d1 JOIN (SELECT oid FROM pg_class WHERE relname='pg_class') d2 ON d1.refclassid = d2.oid JOIN (SELECT e1.oid FROM pg_class e1 JOIN pg_namespace e2 ON e1.relnamespace = e2.oid WHERE e1.relname='{1}' and e2.nspname='{2}') d3 ON d1.refobjid = d3.oid JOIN (SELECT oid FROM pg_class WHERE relname='pg_rewrite') d4 ON d1.classid = d4.oid) t2 ON t1.classid = t2.classid and t2.objid = t2.objid) THEN
                    DROP TABLE "{0}"."{1}";
                ELSE
                    DROP TABLE "{2}"."{1}";
                    ALTER TABLE "{0}"."{1}" SET SCHEMA "{2}";  
                END IF;
            ELSE
                DROP TABLE "{2}"."{1}";
                ALTER TABLE "{0}"."{1}" SET SCHEMA "{2}";  
            END IF;        
        ELSE
            ALTER TABLE "{0}"."{1}" SET SCHEMA "{2}";  
        END IF;
    END IF;
END$$;
""".format(sync_job["data_schema"],sync_job["name"],sync_job["outdated_schema"],sync_job["schema"])
    logger.info("Executing {}...".format(repr(psql_cmd)))
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))


restore_cmd = ["pg_restore", "-w", "-h", GEOSERVER_PGSQL_HOST, "-p" , GEOSERVER_PGSQL_PORT , "-d", GEOSERVER_PGSQL_DATABASE, "-U", GEOSERVER_PGSQL_USERNAME, "-F", "T","-O","-x","--no-tablespaces",None]
def restore_table(sync_job,task_metadata,task_status):
    # load PostgreSQL dump into db with pg_restore
    output_name = os.path.join(CACHE_PATH, "{}.tar".format(sync_job["name"]))
    restore_cmd[len(restore_cmd) - 1] = output_name
    logger.info("Executing {}...".format(repr(restore_cmd)))
    restore = subprocess.Popen(restore_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    restore_output = restore.communicate()
    if restore_output[1] and restore_output[1].strip():
        logger.info("stderr: {}".format(restore_output[1]))
        task_status.set_message("message",restore_output[1])

    if restore.returncode != 0 or restore_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(restore.returncode,task_status.get_message("message")))


def create_access_view(sync_job,task_metadata,task_status):
    #create a view to access the new layer data.
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) -1] = "DROP VIEW IF EXISTS \"{0}\".\"{1}\" CASCADE;CREATE VIEW \"{0}\".\"{1}\" AS SELECT * FROM \"{2}\".\"{1}\";".format(sync_job["schema"],sync_job["name"],sync_job["data_schema"])
    logger.info("Executing {}...".format(repr(psql_cmd)))
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))


def drop_outdated_table(sync_job,task_metadata,task_status):
    #drop the outdated table
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) -1] = "DROP TABLE IF EXISTS \"{0}\".\"{1}\";".format(sync_job["outdated_schema"],sync_job["name"])
    logger.info("Executing {}...".format(repr(psql_cmd)))
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))

def drop_table(sync_job,task_metadata,task_status):
    #drop the table
    psql_cmd[len(psql_cmd) - 2] = "-c"
    psql_cmd[len(psql_cmd) -1] = "DROP VIEW IF EXISTS \"{0}\".\"{1}\" CASCADE;DROP TABLE IF EXISTS \"{2}\".\"{1}\" CASCADE;DROP TABLE IF EXISTS \"{3}\".\"{1}\" CASCADE;".format(sync_job["schema"], sync_job["name"],sync_job["data_schema"],sync_job["outdated_schema"])
    logger.info("Executing {}...".format(repr(psql_cmd)))
    psql = subprocess.Popen(psql_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    psql_output = psql.communicate()
    if psql_output[1] and psql_output[1].strip():
        logger.info("stderr: {}".format(psql_output[1]))
        task_status.set_message("message",psql_output[1])

    if psql.returncode != 0 or psql_output[1].find("ERROR") >= 0:
        raise Exception("{0}:{1}".format(psql.returncode,task_status.get_message("message")))

tasks_metadata = [
                    ("update_auth"                      , update_auth_job   , None      , "update_roles", update_auth),
                    ("create_postgis_extension"         , update_feature_job, db_feature_task_filter, "postgis_extension"   , create_postgis_extension),
                    ("create_db_schema"                 , update_feature_job, db_feature_task_filter, schema_name   , create_schema),
                    ("move_outdated_table"              , update_feature_job, db_feature_task_filter, table_name    , move_outdated_table),
                    ("restore_table"                    , update_feature_job, db_feature_task_filter, table_name    , restore_table),
                    ("create_access_view"               , update_feature_job, db_feature_task_filter, table_name    , create_access_view),
                    ("drop_outdated_table"              , update_feature_job, db_feature_task_filter, table_name    , drop_outdated_table),
                    ("drop_table"                       , remove_feature_job, db_feature_task_filter, table_name    , drop_table),
]

