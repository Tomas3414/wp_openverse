"""
# Data Refresh TaskGroup Factory
This file generates the data refresh TaskGroup using a factory function.
This TaskGroup initiates a data refresh for a given media type and awaits the
success or failure of the refresh. Importantly, it is also configured to
ensure that no two remote data refreshes can run concurrently, as required by
the server.

A data refresh occurs on the data refresh server in the openverse-api project.
This is a task which imports data from the upstream Catalog database into the
API, copies contents to a new Elasticsearch index, and makes the index "live".
This process is necessary to make new content added to the Catalog by our
provider DAGs available on the frontend. You can read more in the [README](
https://github.com/WordPress/openverse-api/blob/main/ingestion_server/README.md
)

The TaskGroup generated by this factory allows us to schedule those refreshes through
Airflow. Since no two refreshes can run simultaneously, all tasks are initially
funneled through a special `data_refresh` pool with a single worker slot. To ensure
that tasks run in an acceptable order (ie the trigger step for one DAG cannot run if a
previously triggered refresh is still running), each DAG has the following
steps:

1. The `wait_for_data_refresh` step uses a custom Sensor that will wait until
none of the `external_dag_ids` (corresponding to the other data refresh DAGs)
are 'running'. A DAG is considered to be 'running' if it is itself in the
RUNNING state __and__ its own `wait_for_data_refresh` step has completed
successfully. The Sensor suspends itself and frees up the worker slot if
another data refresh DAG is running.

2. The `trigger_data_refresh` step then triggers the data refresh by POSTing
to the `/task` endpoint on the data refresh server with relevant data. A
successful response will include the `status_check` url used to check on the
status of the refresh, which is passed on to the next task via XCom.

3. Finally the `wait_for_data_refresh` task waits for the data refresh to be
complete by polling the `status_url`. Note this task does not need to be
able to suspend itself and free the worker slot, because we want to lock the
entire pool on waiting for a particular data refresh to run.

You can find more background information on this process in the following
issues and related PRs:

- [[Feature] Data refresh orchestration DAG](
https://github.com/WordPress/openverse-catalog/issues/353)
"""
import logging
import os
import uuid
from collections.abc import Sequence

from airflow.models.baseoperator import chain
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.state import State
from airflow.utils.task_group import TaskGroup

from common import ingestion_server
from common.constants import XCOM_PULL_TEMPLATE
from common.sensors.single_run_external_dags_sensor import SingleRunExternalDAGsSensor
from common.sensors.utils import get_most_recent_dag_run
from data_refresh.data_refresh_types import DataRefresh


logger = logging.getLogger(__name__)


DATA_REFRESH_POOL = os.getenv("DATA_REFRESH_POOL", "data_refresh")


def create_data_refresh_task_group(
    data_refresh: DataRefresh, external_dag_ids: Sequence[str]
):
    """
    Create the data refresh tasks.

    This factory method instantiates a DAG that will run the data refresh for
    the given `media_type`.

    A data refresh runs for a given media type in the API DB. It refreshes popularity
    data for that type, imports the data from the upstream DB in the Catalog, reindexes
    the data, and updates and reindex Elasticsearch.

    A data refresh can only be performed for one media type at a time, so the DAG
    must also use a Sensor to make sure that no two data refresh tasks run
    concurrently.

    It is intended that the data_refresh tasks, or at least the initial
    `wait_for_data_refresh` tasks, should be run in a custom pool with 1 worker
    slot. This enforces that no two `wait_for_data_refresh` tasks can start
    concurrently and enter a race condition.

    Required Arguments:

    data_refresh:     dataclass containing configuration information for the
                      DAG
    external_dag_ids: list of ids of the other data refresh DAGs. This DAG
                      will not run concurrently with any dependent DAG.
    """

    poke_interval = int(os.getenv("DATA_REFRESH_POKE_INTERVAL", 60 * 15))
    target_alias = data_refresh.media_type  # TODO: Change when using versioned aliases

    with TaskGroup(group_id="data_refresh") as data_refresh_group:
        tasks = []
        # Wait to ensure that no other Data Refresh DAGs are running.
        wait_for_data_refresh = SingleRunExternalDAGsSensor(
            task_id="wait_for_data_refresh",
            external_dag_ids=external_dag_ids,
            check_existence=True,
            poke_interval=poke_interval,
            mode="reschedule",
            pool=DATA_REFRESH_POOL,
        )

        # If filtered index creation was manually triggered before the data refresh
        # started, we need to wait for it to finish or the data refresh could destroy
        # the origin index. Realistically the data refresh is too slow to beat the
        # filtered index creation process, even if it was triggered immediately after
        # filtered index creation. However, it is safer to avoid the possibility
        # of the race condition altogether.
        # ``execution_date_fn`` is used to find the most recent run becuase
        # the filtered index createion DAGs are unscheduled so we can't derive
        # anything from the execution date of the current data refresh DAG.
        create_filtered_index_dag_id = (
            f"create_filtered_{data_refresh.media_type}_index"
        )
        wait_for_filtered_index_creation = ExternalTaskSensor(
            task_id="wait_for_create_and_populate_filtered_index",
            external_dag_id=create_filtered_index_dag_id,
            # Wait for the whole DAG, not just a part of it
            external_task_id=None,
            check_existence=False,
            poke_interval=poke_interval,
            execution_date_fn=lambda _: get_most_recent_dag_run(
                create_filtered_index_dag_id
            ),
            mode="reschedule",
            # Any "finished" state is sufficient for us to continue.
            allowed_states=[State.SUCCESS, State.FAILED],
        )

        tasks.append([wait_for_data_refresh, wait_for_filtered_index_creation])

        # Get the index currently mapped to our target alias, to delete later.
        get_current_index = ingestion_server.get_current_index(target_alias)
        tasks.append(get_current_index)

        # Generate a UUID suffix that will be used by the newly created index.
        generate_index_suffix = PythonOperator(
            task_id="generate_index_suffix", python_callable=lambda: uuid.uuid4().hex
        )
        tasks.append(generate_index_suffix)

        # Trigger the 'ingest_upstream' task on the ingestion server and await its
        # completion. This task copies the media table for the given model from the
        # Catalog into the API DB and builds the elasticsearch index. The new table
        # and index are not promoted until a later step.
        with TaskGroup(group_id="ingest_upstream") as ingest_upstream_tasks:
            ingestion_server.trigger_and_wait_for_task(
                action="ingest_upstream",
                model=data_refresh.media_type,
                data={
                    "index_suffix": XCOM_PULL_TEMPLATE.format(
                        generate_index_suffix.task_id, "return_value"
                    ),
                },
                timeout=data_refresh.data_refresh_timeout,
            )
            tasks.append(ingest_upstream_tasks)

        # Await healthy results from the newly created elasticsearch index.
        index_readiness_check = ingestion_server.index_readiness_check(
            media_type=data_refresh.media_type,
            index_suffix=XCOM_PULL_TEMPLATE.format(
                generate_index_suffix.task_id, "return_value"
            ),
            timeout=data_refresh.index_readiness_timeout,
        )
        tasks.append(index_readiness_check)

        # Trigger the `promote` task on the ingestion server and await its completion.
        # This task promotes the newly created API DB table and elasticsearch index.
        with TaskGroup(group_id="promote") as promote_tasks:
            ingestion_server.trigger_and_wait_for_task(
                action="promote",
                model=data_refresh.media_type,
                data={
                    "index_suffix": XCOM_PULL_TEMPLATE.format(
                        generate_index_suffix.task_id, "return_value"
                    ),
                    "alias": target_alias,
                },
                timeout=data_refresh.data_refresh_timeout,
            )
            tasks.append(promote_tasks)

        # Delete the alias' previous target index, now unused.
        delete_old_index = ingestion_server.trigger_task(
            action="DELETE_INDEX",
            model=data_refresh.media_type,
            data={
                "index_suffix": XCOM_PULL_TEMPLATE.format(
                    get_current_index.task_id, "return_value"
                ),
            },
        )
        tasks.append(delete_old_index)

        # ``tasks`` contains the following tasks and task groups:
        # wait_for_data_refresh
        # └─ get_current_index
        #    └─ ingest_upstream (trigger_ingest_upstream + wait_for_ingest_upstream)
        #       └─ promote (trigger_promote + wait_for_promote)
        #          └─ delete_old_index
        chain(*tasks)

    return data_refresh_group
