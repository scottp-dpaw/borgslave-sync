import traceback
from slave_sync_env import (
    SKIP_AUTH,SKIP_GS,SKIP_DB,SKIP_RULES,
    FEATURE_FILTER,WMS_FILTER,LAYERGROUP_FILTER,now
)

TASK_TYPE_INDEX = 0
JOB_DEF_INDEX = 1
TASK_FILTER_INDEX = 2
TASK_NAME_INDEX = 3
TASK_HANDLER_INDEX = 4

JOB_TYPE_INDEX = 0
JOB_NAME_INDEX = 1
CHANNEL_SUPPORT_INDEX = 2
JOB_FOLDER_INDEX = 3
JOB_ACTION_INDEX = 4
IS_JOB_INDEX = 5
IS_VALID_JOB_INDEX = 6

json_task = lambda file_name: len(file_name.split("/")) == 1 and file_name.endswith(".json")
taskname = lambda task,task_metadata: task_metadata[TASK_NAME_INDEX](task) if hasattr(task_metadata[TASK_NAME_INDEX],"__call__") else task_metadata[TASK_NAME_INDEX]
jobname = lambda task,task_metadata: task_metadata[JOB_DEF_INDEX][JOB_NAME_INDEX](task) if hasattr(task_metadata[JOB_DEF_INDEX][JOB_NAME_INDEX],"__call__") else task_metadata[JOB_DEF_INDEX][JOB_NAME_INDEX]

sync_tasks = {
    "update_auth": {},
    "update_access_rules": {},
    
    "create_postgis_extension": {},
    "create_db_schema": {},
    "load_table_dumpfile": {},
    "move_outdated_table": {},
    "restore_table": {},
    "create_access_view": {},
    "drop_outdated_table": {},
    "drop_table": {},

    "load_gs_stylefile": {},
    "create_workspace": {},
    "create_datastore": {},
    "delete_feature": {},
    "delete_style": {},
    "create_feature":{},
    "create_style":{},

    "update_feature": {},
    "remove_feature": {},

    "update_wmsstore": {},
    "remove_wmsstore": {},

    "update_wmslayer": {},
    "remove_wmslayer": {},

    "update_layergroup": {},
    "remove_layergroup": {},

    "update_gwc":{},
    "empty_gwc":{},

    "geoserver_reload":{},

    "get_layer_preview":{},
    "send_layer_preview":{},

    "update_catalogues":{},

}
ordered_sync_task_type = [
            "update_auth",
            "update_access_rules",
            "load_table_dumpfile","load_gs_stylefile",
            "create_postgis_extension","create_db_schema","move_outdated_table","restore_table","create_access_view","drop_outdated_table",
            "create_workspace",
            "create_datastore","delete_feature","delete_style",
            "update_wmsstore","update_wmslayer","update_layergroup","remove_layergroup","remove_wmslayer","remove_wmsstore",
            "geoserver_reload",
            "create_feature","create_style",
            "update_gwc","empty_gwc",
            "drop_table",
            "get_layer_preview","send_layer_preview",
            "update_catalogues",
]

#predefined sync_job filters
gs_task_filter = lambda sync_job: not SKIP_GS

gs_spatial_task_filter = lambda sync_job: not SKIP_GS and sync_job.get("sync_geoserver_data",True) and sync_job.get("spatial_data",False)
gs_feature_task_filter = lambda sync_job: not SKIP_GS and sync_job.get("sync_geoserver_data",True)
gs_style_task_filter = lambda sync_job : not SKIP_GS and sync_job.get("sync_geoserver_data",True) and "style_path" in sync_job

db_task_filter = lambda sync_job: not SKIP_DB
db_feature_task_filter = lambda sync_job: not SKIP_DB and sync_job.get("sync_postgres_data",True)


#task definition for update access rules
valid_rules = lambda sync_job: not SKIP_RULES
update_access_rules_job = ("access rules","geoserver access rules",True,None,"publish",lambda file_name: file_name == "layers.properties",valid_rules)

#task definition for update auth
valid_auth = lambda sync_job: not SKIP_AUTH
update_auth_job = ("auth","postgres and geoserver auth",False,None,"publish",lambda file_name: file_name == "slave_roles.sql",valid_auth)

#task definition for wms store and layers
required_store_attrs = ("name", "workspace","capability_url","username","password","action")
valid_store = lambda l: WMS_FILTER(l) and all(key in l for key in required_store_attrs)
required_store_remove_attrs = ("name", "workspace","action")
valid_store_remove = lambda l: WMS_FILTER(l) and all(key in l for key in required_store_remove_attrs)

required_layer_attrs = ("name", "workspace", "store","title","abstract","action")
valid_layer = lambda l: WMS_FILTER(l) and all(key in l for key in required_layer_attrs)
required_layer_remove_attrs = ("name", "workspace", "store","action")
valid_layer_remove = lambda l: WMS_FILTER(l) and all(key in l for key in required_layer_remove_attrs)

update_wmsstore_job = ("wms store",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"wms_stores","publish",json_task,valid_store)
update_wmslayer_job = ("wms layer",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"wms_layers","publish",json_task,valid_layer)
remove_wmslayer_job = ("wms layer",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"wms_layers","remove",json_task,valid_layer_remove)
remove_wmsstore_job = ("wms store",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"wms_stores","remove",json_task,valid_store_remove)

#task definition for layergroup
required_group_attrs = ("name", "workspace","title","abstract","srs","layers","action")
valid_group = lambda l: LAYERGROUP_FILTER(l) and all(key in l for key in required_group_attrs)

required_group_remove_attrs = ("name", "workspace","action")
valid_group_remove = lambda l: LAYERGROUP_FILTER(l) and all(key in l for key in required_group_remove_attrs)

update_layergroup_job = ("layergroup",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layergroups","publish",json_task,valid_group)
remove_layergroup_job = ("layergroup",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layergroups","remove",json_task,valid_group_remove)

required_empty_gwc_layer_attrs = ("name", "workspace","store","action")
valid_empty_gwc_layer = lambda l: WMS_FILTER(l) and all(key in l for key in required_empty_gwc_layer_attrs)
required_empty_gwc_group_attrs = ("name", "workspace","action")
valid_empty_gwc_group = lambda l: LAYERGROUP_FILTER(l) and all(key in l for key in required_empty_gwc_group_attrs)

empty_gwc_layer_job = ("wms layer",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"wms_layers","empty_gwc",json_task,valid_empty_gwc_layer)
empty_gwc_group_job = ("layergroup",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layergroups","empty_gwc",json_task,valid_empty_gwc_group)

#task definition for features
required_feature_attrs = ("name", "schema", "data_schema", "outdated_schema", "workspace", "dump_path","action")
valid_feature = lambda l: FEATURE_FILTER(l) and not l["job_file"].endswith(".meta.json") and all(key in l for key in required_feature_attrs)

update_feature_job = ("feature",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layers","publish",json_task,valid_feature)
remove_feature_job = ("feature",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layers","remove",json_task,valid_feature)

#task definition for feature's metadata
required_metadata_feature_attrs = ("name","workspace","schema","action")
valid_metadata_feature_job = lambda l: FEATURE_FILTER(l) and l["job_file"].endswith(".meta.json") and all(key in l for key in required_metadata_feature_attrs)

update_metadata_feature_job = ("feature",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layers","meta",json_task,valid_metadata_feature_job)

#task definition for empty feature's gwc
required_empty_gwc_feature_attrs = ("name","workspace","action")
valid_empty_gwc_feature_job = lambda l: FEATURE_FILTER(l) and all(key in l for key in required_empty_gwc_feature_attrs)

empty_gwc_feature_job = ("feature",lambda j:"{0}:{1}".format(j["workspace"],j["name"]),True,"layers","empty_gwc",json_task,valid_empty_gwc_feature_job)

def get_http_response_exception(http_response):
    """
    return http response exception for logging
    """
    if hasattr(http_response,"reason"):
        if hasattr(http_response,"_content"):
            return "{0}({1})".format(http_response.reason,http_response._content)
        else:
            return http_response.reason
    elif hasattr(http_response,"content"):
        return http_response.content
    else:
        return ""


def get_task(task_type,task_name):
    """
    get task with specific type and name;
    return None if not found
    """
    try:
        return sync_tasks[task_type].get(task_name,None)
    except:
        return None

def execute_task(sync_job,task_metadata,task_logger):
    """
    execute the task, based on tasks_metadata
    """
    task_name = taskname(sync_job,task_metadata)
    task_status = sync_job['status'].get_task_status(task_metadata[TASK_TYPE_INDEX])

    if task_status.is_succeed: 
        #this task has been executed successfully
        return

    if task_status.is_processed:
        #this task is already processed, maybe triggered by other tasks
        sync_job['status'].execute_succeed = False
        return

    if not sync_job['status'].execute_succeed:
        #some proceding task are failed,so can't execute this task
        if task_status.shared:
            #this task is shared, but this task can't executed for this job, change the task's status object to a private status object
            from slave_sync_status import SlaveSyncTaskStatus
            sync_job['status'].set_task_status(task_metadata[TASK_TYPE_INDEX],SlaveSyncTaskStatus())
        return

    task_logger.info("Begin to process the {3}task ({0} - {1} {2}).".format(task_metadata[TASK_TYPE_INDEX],task_name,sync_job["job_file"],"shared" if task_status.shared else ""))
    sync_job['status'].last_process_time = now()
    task_status.last_process_time = now()
    try:
        task_metadata[TASK_HANDLER_INDEX](sync_job,task_metadata,task_status)
        if not task_status.get_message("message"):
            task_status.set_message("message","succeed")
        task_status.succeed()
        task_logger.info("Succeed to process the {3}task ({0} - {1} {2}).".format(task_metadata[TASK_TYPE_INDEX],task_name,sync_job["job_file"],"shared" if task_status.shared else ""))
    except:
        task_status.failed()
        sync_job['status'].execute_succeed = False
        message = traceback.format_exc()
        task_status.set_message("message",message)
        task_logger.error("Failed to Process the {4}task ({0} - {1} {2}).{3}".format(task_metadata[TASK_TYPE_INDEX],task_name,sync_job["job_file"],message,"shared" if task_status.shared else ""))

