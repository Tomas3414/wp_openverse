"""
# Create filtered index DAG factory

This module creates the filtered index creation DAGs for each media type
using a factory function.

Filtered index creation is handled by the ingestion server. The DAGs generated
by the ``create_filtered_index_creation_dag`` function in this module are
responsible for triggering the ingestion server action to create and populate
the filtered index for a given media type. The DAG awaits the completion
of the filtered index creation and then points the filtered index alias for the
media type to the newly created index. They make use of the
``create_filtered_index_creation_task_groups`` factory, which is also used by the
data refreshes to perform the same functions. The purpose of these DAGs is to allow
the filtered index creation steps to be run in isolation from the data refresh.

## When this DAG runs

The DAGs generated by the ``create_filtered_index_creation_dag`` can be used
to manually run the filtered index creation and promotion steps described above in
isolation from the rest of the data refresh. These DAGs also include checks to ensure
that race conditions with the data refresh DAGs are not encountered (see ``Race
conditions`` section below).

The DAGs generated in this module are on a `None` schedule and are only triggered
manually. This is primarily useful in two cases: for testing changes to the filtered
index creation; and for re-running filtered index creation if an urgent change to the
sensitive terms calls for an immediate recreation of the filtered indexes.

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
"""
from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from es.create_new_es_index.create_new_es_index_types import CREATE_NEW_INDEX_CONFIGS

from common.constants import DAG_DEFAULT_ARGS, PRODUCTION
from common.sensors.utils import prevent_concurrency_with_dags
from data_refresh.create_filtered_index import (
    create_filtered_index_creation_task_groups,
)
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
def create_filtered_index_creation_dag(data_refresh: DataRefresh):
    """
    Create a DAG for the given DataRefresh that performs filtered index
    creation and promotion, preventing concurrency with the data refreshes.
    """
    media_type = data_refresh.media_type

    with DAG(
        dag_id=data_refresh.filtered_index_dag_id,
        default_args=DAG_DEFAULT_ARGS,
        schedule=None,
        start_date=datetime(2023, 4, 1),
        tags=["data_refresh"],
        max_active_runs=1,
        catchup=False,
        doc_md=__doc__,
        params={
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
        # Immediately fail if the associated data refresh is running, or the
        # create_new_production_es_index DAG is running. This prevents multiple
        # DAGs from reindexing from a single production index simultaneously.
        prevent_concurrency = prevent_concurrency_with_dags(
            external_dag_ids=[
                data_refresh.dag_id,
                CREATE_NEW_INDEX_CONFIGS[PRODUCTION].dag_id,
            ]
        )

        # Once the concurrency check has passed, actually create the filtered
        # index.
        (
            create_filtered_index,
            promote_filtered_index,
        ) = create_filtered_index_creation_task_groups(
            data_refresh,
            "{{ params.origin_index_suffix }}",
            "{{ params.destination_index_suffix }}",
        )

        prevent_concurrency >> create_filtered_index >> promote_filtered_index

    return dag


for data_refresh in DATA_REFRESH_CONFIGS.values():
    create_filtered_index_dag = create_filtered_index_creation_dag(data_refresh)
