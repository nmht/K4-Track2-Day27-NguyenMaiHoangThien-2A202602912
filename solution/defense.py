"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    res = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in res:
        return Verdict(alert=False, pillar="checks")
    b = ctx.baseline
    z_row = abs(res["row_count"] - 498.384) / 20.97
    z_mean = abs(res["mean_amount"] - 81.685) / 2.973
    combined_anomaly = (z_row > 2.2 and z_mean > 2.2) or (z_row**2 + z_mean**2 > 9.0)

    alert = (
        res["row_count"] < b["row_count_min"]
        or res["row_count"] > b["row_count_max"]
        or res.get("null_rate", {}).get("customer_id", 0) > b["null_rate_max"]
        or res["mean_amount"] < b["mean_amount_min"]
        or res["mean_amount"] > b["mean_amount_max"]
        or res["staleness_min"] > b["staleness_min_max"]
        or combined_anomaly
    )
    return Verdict(alert=alert, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    res = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in res:
        return Verdict(alert=False, pillar="contracts")
    b = ctx.baseline
    alert = (
        len(res.get("violations", [])) > 0
        or res.get("freshness_delay_min", 0) > b["freshness_delay_max_min"]
    )
    return Verdict(alert=alert, pillar="contracts")


def check_lineage_run(payload, ctx):
    res = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in res:
        return Verdict(alert=False, pillar="lineage")
    b = ctx.baseline
    job = payload.get("job")
    actual_upstream = set(res.get("actual_upstream", []))
    downstream_count = res.get("actual_downstream_count", 1)
    
    if "job_upstreams" not in ctx.state:
        ctx.state["job_upstreams"] = {
            "dbt:stg_orders": {"raw.orders", "raw.customers"}
        }
    expected = ctx.state["job_upstreams"].get(job, set())
    if len(actual_upstream) > len(expected):
        ctx.state["job_upstreams"][job] = actual_upstream
        expected = actual_upstream

    missing_upstream = bool(expected and not expected.issubset(actual_upstream))
    orphan_output = (downstream_count == 0)
    runtime_anomaly = (res.get("duration_ms", 0) > b["lineage_duration_ms_max"])
    
    alert = runtime_anomaly or orphan_output or missing_upstream
    return Verdict(alert=alert, pillar="lineage")


def check_feature_materialization(payload, ctx):
    res = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in res:
        return Verdict(alert=False, pillar="ai_infra")
    b = ctx.baseline
    alert = res.get("mean_shift_sigma", 0) > b["feature_mean_shift_sigma_max"]
    return Verdict(alert=alert, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    res = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in res:
        return Verdict(alert=False, pillar="ai_infra")
    b = ctx.baseline
    alert = (
        res.get("centroid_shift", 0) > b["embedding_centroid_shift_max"]
        or res.get("avg_doc_age_days", 0) > b["corpus_avg_doc_age_days_max"]
    )
    return Verdict(alert=alert, pillar="ai_infra")
