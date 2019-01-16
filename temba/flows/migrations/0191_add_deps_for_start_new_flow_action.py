# Generated by Django 2.1.3 on 2018-12-11 14:37
import time
from collections import defaultdict

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import migrations

from temba.utils import chunk_list


def add_deps(Flow, ActionSet, RuleSet):
    # constants
    FlowFlowDeps = Flow.flow_dependencies.through
    startFlowActionType = "flow"
    triggerFlowActionType = "trigger-flow"
    rulesetTypeSubflow = "subflow"

    start_time = time.monotonic()
    print("Collecting flows and dependencies...")

    # inactive flows have their deps cleared out, we only check active flows
    valid_flows = Flow.objects.filter(is_active=True).values_list("id", "uuid")

    valid_flow_map = dict()
    flow_ids = list()

    for valid_flow in valid_flows:
        flow_id, flow_uuid = valid_flow

        valid_flow_map[flow_uuid] = flow_id
        flow_ids.append(flow_id)

    total_flows = len(flow_ids)
    processed_flows = 0

    expected_flow_deps = defaultdict(set)

    print("Processing flow dependencies...")
    for flow_ids_chunk in chunk_list(flow_ids, 1000):
        chunk_start_time = time.monotonic()
        actionsets = (
            ActionSet.objects.filter(flow_id__in=flow_ids_chunk)
            .values("flow_id")
            .annotate(actions=ArrayAgg("actions"))
        )

        for actionset in actionsets:
            flow_id = actionset["flow_id"]
            actionset_actions = actionset["actions"]

            for action_list in actionset_actions:
                for action in action_list:
                    #
                    if action["type"] == startFlowActionType:
                        flow_uuid = action["flow"]["uuid"]

                        # there might be some inactive flows listed as dependencies, ignore
                        if flow_uuid in valid_flow_map:
                            expected_flow_deps[flow_id].add(valid_flow_map[flow_uuid])

                    if action["type"] == triggerFlowActionType:
                        flow_uuid = action["flow"]["uuid"]

                        # there might be some inactive flows listed as dependencies, ignore
                        if flow_uuid in valid_flow_map:
                            expected_flow_deps[flow_id].add(valid_flow_map[flow_uuid])

        rulesets = (
            RuleSet.objects.filter(flow_id__in=flow_ids_chunk, ruleset_type=rulesetTypeSubflow)
            .values("flow_id")
            .annotate(configs=ArrayAgg("config"))
        )

        for ruleset in rulesets:
            flow_id = ruleset["flow_id"]
            ruleset_configs = ruleset["configs"]

            for config in ruleset_configs:

                flow_uuid = config["flow"]["uuid"]

                # there might be some inactive flows listed as dependencies, ignore
                if flow_uuid in valid_flow_map:
                    expected_flow_deps[flow_id].add(valid_flow_map[flow_uuid])

        processed_flows += len(flow_ids_chunk)
        print(f"Processed {processed_flows}/{total_flows} in {time.monotonic() - chunk_start_time}")

    print(f"Collected flows and dependencies in {time.monotonic() - start_time}")

    print("Comparing actual to expected flow dependencies...")
    flow_dep_ids = list(expected_flow_deps.keys())
    total_added_deps = 0

    bulk_deps_to_add = list()

    for from_flow_id in flow_dep_ids:
        actual_flow_dep = (
            FlowFlowDeps.objects.filter(from_flow_id=from_flow_id)
            .values("from_flow_id")
            .annotate(deps=ArrayAgg("to_flow_id"))
        ).first()

        if actual_flow_dep:
            actual_deps = set(actual_flow_dep["deps"])
        else:
            actual_deps = set()

        deps_to_add = expected_flow_deps[from_flow_id].difference(actual_deps)
        total_added_deps += len(deps_to_add)

        for dep in deps_to_add:
            bulk_deps_to_add.append(FlowFlowDeps(from_flow_id=from_flow_id, to_flow_id=dep))

    FlowFlowDeps.objects.bulk_create(bulk_deps_to_add)

    print(f"Total added missing deps: {total_added_deps}")


def apply_migration(apps, schema_editor):
    Flow = apps.get_model("flows", "Flow")
    ActionSet = apps.get_model("flows", "ActionSet")
    RuleSet = apps.get_model("flows", "RuleSet")

    add_deps(Flow, ActionSet, RuleSet)


def apply_manual():
    from temba.flows.models import Flow
    from temba.flows.models import ActionSet
    from temba.flows.models import RuleSet

    add_deps(Flow, ActionSet, RuleSet)


class Migration(migrations.Migration):

    dependencies = [("flows", "0190_make_empty_revisions")]

    operations = [migrations.RunPython(apply_migration, migrations.RunPython.noop)]
