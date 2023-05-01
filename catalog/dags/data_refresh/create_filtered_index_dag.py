"""
# Create filtered index DAG factory

This module creates the filtered index creation DAGs for each media type
using a factory function.

Filtered index creation is handled by the ingestion server. The DAGs generated
by the ``build_create_filtered_index_dag`` function in this module are
responsible for triggering the ingestion server action to create and populate
the filtered index for a given media type. The DAG awaits the completion
of the filtered index creation and then points the filtered index alias for the
media type to the newly created index.

## When this DAG runs

The DAGs generated in this module are triggered by the data refresh DAGs.
Maintaining this process separate from the data refresh DAGs, while still
triggering it there, allows us to run filtered index creation independently
of the full data refresh. This is primarily useful in two cases: for testing
changes to the filtered index creation; and for re-running filtered index
creation if an urgent change to the sensitive terms calls for an immediate
recreation of the filtered indexes.

## Race conditions

Because filtered index creation employs the ``reindex`` Elasticsearch API
to derive the filtered index from an existing index, we need to be mindful
of the race condition that potentially exists between the data refresh DAG
and this DAG. The race condition is caused by the fact that the data refresh
DAG always deletes the previous index once the new index for the media type
is finished being created. Consider the situation where filtered index creation
is triggered to run during a data refresh. The filtered index is being derived
from the previous index for the media type. Once the data refresh is finished,
it will delete that index, causing the reindex to halt because suddenly it has
no data source from which to pull documents.

There are two mechanisms that prevent this from happening:

1. The filtered index creation DAGs are not allowed to run if a data refresh
for the media type is already running.
2. The data refresh DAGs will wait for any pre-existing filtered index creation
DAG runs for the media type to finish before continuing.

This ensures that neither are depending on or modifying the origin indexes
critical for the creation of the filtered indexes.

Because the data refresh DAG triggers the filtered index creation DAG, we do
allow a ``force`` param to be passed to the DAGs generated by this module.
This parameter is only for use by the data refresh DAG and should not be
used when manually triggering the DAG unless you are absolutely certain
of what you are doing.
"""
import uuid
from datetime import datetime

from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowSensorTimeout
from airflow.models.param import Param
from airflow.sensors.external_task import ExternalTaskSensor

from common import ingestion_server
from common.constants import DAG_DEFAULT_ARGS, XCOM_PULL_TEMPLATE
from common.sensors.utils import get_most_recent_dag_run
from data_refresh.data_refresh_types import DATA_REFRESH_CONFIGS, DataRefresh


# Note: We can't use the TaskFlow `@dag` DAG factory decorator
# here because there's no way to set the media type as a static
# variable in the context of the DAG because all arguments
# passed to the DAG factory decorated by `@dag` are thrown
# away: `@dag` decorated functions' arguments are treated
# merely as DAG param aliases. We could use `@dag` inside
# this factory function, but it would require a redundant
# call to the decorated function and doesn't look like it would
# provide any additional value whatsoever.
def filtered_index_creation_dag_factory(data_refresh: DataRefresh):
    media_type = data_refresh.media_type
    target_alias = f"{media_type}-filtered"

    @task(
        task_id=f"prevent_concurrency_with_{media_type}_data_refresh",
    )
    def prevent_concurrency_with_data_refresh(force: bool, **context):
        if force:
            return

        data_refresh_dag_id = f"{media_type}_data_refresh"
        wait_for_filtered_index_creation = ExternalTaskSensor(
            task_id="check_for_running_data_refresh",
            external_dag_id=data_refresh_dag_id,
            # Set timeout to 0 to prevent retries. If the data refresh DAG is running,
            # immediately fail the filtered index creation DAG.
            timeout=0,
            # Wait for the whole DAG, not just a part of it
            external_task_id=None,
            check_existence=False,
            execution_date_fn=lambda _: get_most_recent_dag_run(data_refresh_dag_id),
            mode="reschedule",
        )
        try:
            wait_for_filtered_index_creation.execute(context)
        except AirflowSensorTimeout:
            raise ValueError(
                f"{media_type} data refresh concurrency check failed. "
                "Filtered index creation cannot start during a data refresh."
            )

    @task()
    def generate_index_suffix(default_suffix: str):
        return default_suffix or uuid.uuid4().hex

    def create_and_populate_filtered_index(
        origin_index_suffix: str | None,
        destination_index_suffix: str | None,
    ):
        create_payload = {}
        if origin_index_suffix:
            create_payload["origin_index_suffix"] = origin_index_suffix
        if destination_index_suffix:
            create_payload["destination_index_suffix"] = destination_index_suffix

        return ingestion_server.trigger_and_wait_for_task(
            action="CREATE_AND_POPULATE_FILTERED_INDEX",
            model=media_type,
            data=create_payload or None,
            timeout=data_refresh.create_filtered_index_timeout,
        )

    def point_alias(destination_index_suffix: str):
        point_alias_payload = {
            "alias": target_alias,
            "index_suffix": f"{destination_index_suffix}-filtered",
        }

        return ingestion_server.trigger_task(
            action="POINT_ALIAS",
            model=media_type,
            data=point_alias_payload,
        )

    with DAG(
        dag_id=f"create_filtered_{media_type}_index",
        default_args=DAG_DEFAULT_ARGS,
        schedule=None,
        start_date=datetime(2023, 4, 1),
        tags=["data_refresh"],
        max_active_runs=1,
        catchup=False,
        doc_md=__doc__,
        params={
            "force": Param(
                default=False,
                type="boolean",
                description=(
                    "Bypass data refresh concurrency check. "
                    "Should only ever be used by the data_refresh "
                    "DAGs when triggering filtered index creation "
                    "at the end of a data refresh. This should not "
                    "be used when manually running this DAG "
                    "unless you're absolutely sure of what you're "
                    "doing. This check exists to prevent race "
                    "conditions and should not be ignored lightly."
                ),
            ),
            "origin_index_suffix": Param(
                default=None,
                type=["string", "null"],
                description=(
                    "See ``Indexer::create_and_populate_filtered_index`` in the "
                    "Openverse ingestion server project. "
                    "For manual runs this can be left out if the new "
                    f"filtered alias should be based on the {media_type} alias."
                ),
            ),
            "destination_index_suffix": Param(
                default=None,
                type=["string", "null"],
                description=(
                    "See ``Indexer::create_and_populate_filtered_index`` in the "
                    "Openverse ingestion server project. "
                    "For manual runs this should be left out. This setting should "
                    "not conflict with another existing suffix or index creation "
                    "will fail."
                ),
            ),
        },
        render_template_as_native_obj=True,
    ) as dag:
        prevent_concurrency = prevent_concurrency_with_data_refresh(
            force="{{ params.force }}",
        )

        # If a destination index suffix isn't provided, we need to generate
        # one so that we know where to point the alias
        destination_index_suffix = generate_index_suffix(
            "{{ params.destination_index_suffix }}"
        )

        get_current_index = ingestion_server.get_current_index(target_alias)

        do_create = create_and_populate_filtered_index(
            origin_index_suffix="{{ params.origin_index_suffix }}",
            destination_index_suffix=destination_index_suffix,
        )

        do_point_alias = point_alias(destination_index_suffix=destination_index_suffix)

        delete_old_index = ingestion_server.trigger_task(
            action="DELETE_INDEX",
            model=data_refresh.media_type,
            data={
                "index_suffix": XCOM_PULL_TEMPLATE.format(
                    get_current_index.task_id, "return_value"
                ),
            },
        )

        (
            prevent_concurrency
            >> destination_index_suffix
            >> get_current_index
            >> do_create
            >> do_point_alias
            >> delete_old_index
        )

    return dag


for data_refresh in DATA_REFRESH_CONFIGS:
    create_filtered_index_dag = filtered_index_creation_dag_factory(data_refresh)
