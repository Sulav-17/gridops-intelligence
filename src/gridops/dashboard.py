"""Read-only query adapters for the M07 dashboard contract."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.models import (
    Alert,
    AlertEvaluationRun,
    BaselineForecastRun,
    BaselineMetricResult,
    BriefingRun,
    ForecastPeakOutput,
    ForecastRampOutput,
    IesoHourlyDemand,
    IngestionRun,
    ModelDriftSummary,
    ModelPerformanceSummary,
    ProductionForecastPrediction,
    ProductionForecastRun,
    QualityRun,
)
from gridops.quality.source_health import summarize_source_health


def latest_forecast_run(session: Session) -> ProductionForecastRun | None:
    """Return the latest successful persisted production forecast run."""

    return session.scalar(
        select(ProductionForecastRun)
        .where(ProductionForecastRun.status == "succeeded")
        .order_by(
            ProductionForecastRun.forecast_issue_time_utc.desc(),
            ProductionForecastRun.id.desc(),
        )
    )


def forecast_response(session: Session, run: ProductionForecastRun) -> dict[str, object]:
    """Serialize only persisted forecast fields and joined persisted actual demand."""

    predictions = list(
        session.scalars(
            select(ProductionForecastPrediction)
            .where(ProductionForecastPrediction.production_forecast_run_id == run.id)
            .order_by(ProductionForecastPrediction.target_interval_start_utc)
        ).all()
    )
    actuals = {
        row.interval_start_utc: row.demand_mw
        for row in session.scalars(
            select(IesoHourlyDemand).where(
                IesoHourlyDemand.is_current.is_(True),
                IesoHourlyDemand.interval_start_utc.in_(
                    [prediction.target_interval_start_utc for prediction in predictions]
                ),
            )
        ).all()
    }
    peak = session.scalar(
        select(ForecastPeakOutput).where(ForecastPeakOutput.production_forecast_run_id == run.id)
    )
    ramps = list(
        session.scalars(
            select(ForecastRampOutput)
            .where(ForecastRampOutput.production_forecast_run_id == run.id)
            .order_by(ForecastRampOutput.target_interval_start_utc)
        ).all()
    )
    horizon_start = predictions[0].target_interval_start_utc if predictions else None
    horizon_end = predictions[-1].target_interval_end_utc if predictions else None
    return {
        "forecast_run_id": run.id,
        "forecast_issue_time_utc": run.forecast_issue_time_utc,
        "horizon_start_utc": horizon_start,
        "horizon_end_utc": horizon_end,
        "horizon_interval_count": len(predictions),
        "model_artifact_id": run.model_artifact_id,
        "model_name": run.model_name,
        "model_type": run.model_type,
        "model_version": run.model_version,
        "feature_version": run.feature_version,
        "quality_status": run.quality_status,
        "intervals_available": any(
            prediction.p10_demand_mw is not None or prediction.p90_demand_mw is not None
            for prediction in predictions
        ),
        "predictions": [
            {
                "prediction_id": prediction.id,
                "target_interval_start_utc": prediction.target_interval_start_utc,
                "target_interval_end_utc": prediction.target_interval_end_utc,
                "lead_hour": prediction.lead_hour,
                "p10_demand_mw": prediction.p10_demand_mw,
                "p50_demand_mw": (
                    prediction.p50_demand_mw
                    if prediction.p50_demand_mw is not None
                    else prediction.point_forecast_demand_mw
                ),
                "p90_demand_mw": prediction.p90_demand_mw,
                "actual_demand_mw": actuals.get(prediction.target_interval_start_utc),
                "prediction_type": prediction.prediction_type,
            }
            for prediction in predictions
        ],
        "peak": None
        if peak is None
        else {
            "peak_output_id": peak.id,
            "peak_demand_mw": peak.peak_demand_mw,
            "peak_target_interval_start_utc": peak.peak_target_interval_start_utc,
            "peak_target_interval_end_utc": peak.peak_target_interval_end_utc,
            "peak_lead_hour": peak.peak_lead_hour,
        },
        "ramps": [
            {
                "ramp_output_id": ramp.id,
                "target_interval_start_utc": ramp.target_interval_start_utc,
                "previous_target_interval_start_utc": ramp.previous_target_interval_start_utc,
                "forecast_ramp_mw": ramp.forecast_ramp_mw,
                "absolute_ramp_mw": ramp.absolute_ramp_mw,
            }
            for ramp in ramps
        ],
        "limitations": {
            "true_prediction_intervals_guaranteed": False,
            "p10_p90_may_be_null": True,
        },
    }


def overview_response(session: Session) -> dict[str, object]:
    """Build the compact dashboard overview from persisted evidence."""

    run = latest_forecast_run(session)
    forecast = forecast_response(session, run) if run is not None else None
    active_alerts = list(
        session.scalars(
            select(Alert).where(Alert.state.in_(("open", "acknowledged"))).order_by(Alert.id)
        ).all()
    )
    severity_order = {"info": 0, "watch": 1, "warning": 2, "critical": 3}
    worst_alert = max(active_alerts, key=lambda alert: severity_order[alert.severity], default=None)
    source_health = summarize_source_health(session)
    briefing = session.scalar(
        select(BriefingRun)
        .where(BriefingRun.status == "succeeded")
        .order_by(BriefingRun.generated_at_utc.desc(), BriefingRun.id.desc())
    )
    return {
        "forecast": forecast,
        "active_alert_count": len(active_alerts),
        "worst_current_alert_severity": worst_alert.severity if worst_alert else None,
        "source_health": [
            {
                "dataset_name": item.dataset_name,
                "latest_quality_run_status": item.latest_quality_run_status,
                "worst_severity": item.worst_severity,
                "is_blocked": item.is_blocked,
            }
            for item in source_health
        ],
        "latest_briefing": None
        if briefing is None
        else {
            "briefing_run_id": briefing.id,
            "generated_at_utc": briefing.generated_at_utc,
            "summary": briefing.summary_json,
        },
    }


def model_performance_response(session: Session) -> dict[str, object]:
    """Return latest persisted M04 baseline and M05 monitoring evidence."""

    latest_performance_at = session.scalar(
        select(ModelPerformanceSummary.created_at_utc)
        .order_by(ModelPerformanceSummary.created_at_utc.desc())
        .limit(1)
    )
    performance = (
        []
        if latest_performance_at is None
        else list(
            session.scalars(
                select(ModelPerformanceSummary)
                .where(ModelPerformanceSummary.created_at_utc == latest_performance_at)
                .order_by(ModelPerformanceSummary.metric_name)
            ).all()
        )
    )
    baseline_run = session.scalar(
        select(BaselineForecastRun)
        .where(BaselineForecastRun.status == "succeeded")
        .order_by(BaselineForecastRun.completed_at_utc.desc(), BaselineForecastRun.id.desc())
    )
    baseline_metrics = (
        []
        if baseline_run is None
        else list(
            session.scalars(
                select(BaselineMetricResult)
                .where(BaselineMetricResult.baseline_forecast_run_id == baseline_run.id)
                .order_by(BaselineMetricResult.metric_name)
            ).all()
        )
    )
    latest_drift_at = session.scalar(
        select(ModelDriftSummary.created_at_utc)
        .order_by(ModelDriftSummary.created_at_utc.desc())
        .limit(1)
    )
    drift = (
        []
        if latest_drift_at is None
        else list(
            session.scalars(
                select(ModelDriftSummary)
                .where(ModelDriftSummary.created_at_utc == latest_drift_at)
                .order_by(ModelDriftSummary.feature_name)
            ).all()
        )
    )
    return {
        "production_metrics": [_metric_dict(row) for row in performance],
        "baseline": None
        if baseline_run is None
        else {
            "baseline_forecast_run_id": baseline_run.id,
            "baseline_name": baseline_run.baseline_name,
            "metrics": [_metric_dict(row) for row in baseline_metrics],
        },
        "drift_summaries": [
            {
                "drift_summary_id": row.id,
                "model_artifact_id": row.model_artifact_id,
                "model_name": row.model_name,
                "model_version": row.model_version,
                "feature_version": row.feature_version,
                "feature_name": row.feature_name,
                "drift_metric_name": row.drift_metric_name,
                "drift_score": row.drift_score,
                "baseline_window_start_utc": row.baseline_window_start_utc,
                "baseline_window_end_utc": row.baseline_window_end_utc,
                "comparison_window_start_utc": row.comparison_window_start_utc,
                "comparison_window_end_utc": row.comparison_window_end_utc,
                "summary": row.summary_json,
                "created_at_utc": row.created_at_utc,
            }
            for row in drift
        ],
        "limitations": {
            "metrics_are_persisted_not_presentation_calculated": True,
            "peak_error_available": False,
            "ramp_error_available": False,
        },
    }


def system_status_response(session: Session, *, demo_mode: bool) -> dict[str, object]:
    """Return safe operational status without infrastructure internals."""

    forecast = latest_forecast_run(session)
    ingestion = session.scalar(
        select(IngestionRun).order_by(IngestionRun.started_at_utc.desc(), IngestionRun.id.desc())
    )
    quality = session.scalar(
        select(QualityRun).order_by(QualityRun.started_at_utc.desc(), QualityRun.id.desc())
    )
    alert_evaluation = session.scalar(
        select(AlertEvaluationRun).order_by(
            AlertEvaluationRun.started_at_utc.desc(), AlertEvaluationRun.id.desc()
        )
    )
    briefing = session.scalar(
        select(BriefingRun).order_by(BriefingRun.generated_at_utc.desc(), BriefingRun.id.desc())
    )
    return {
        "status": "ready",
        "database": "ready",
        "demo_mode": demo_mode,
        "latest_runs": {
            "ingestion": (
                ingestion.finished_at_utc or ingestion.started_at_utc if ingestion else None
            ),
            "quality": quality.completed_at_utc or quality.started_at_utc if quality else None,
            "forecast": forecast.completed_at_utc or forecast.started_at_utc if forecast else None,
            "alert_evaluation": (
                alert_evaluation.completed_at_utc or alert_evaluation.started_at_utc
                if alert_evaluation
                else None
            ),
            "briefing": briefing.generated_at_utc if briefing else None,
        },
    }


def _metric_dict(
    row: ModelPerformanceSummary | BaselineMetricResult,
) -> dict[str, object]:
    return {
        "metric_result_id": row.id,
        "metric_name": row.metric_name,
        "metric_value": row.metric_value,
        "metric_unit": row.metric_unit,
        "evaluation_window_start_utc": row.evaluation_window_start_utc,
        "evaluation_window_end_utc": row.evaluation_window_end_utc,
        "created_at_utc": row.created_at_utc,
        **(
            {
                "row_count": row.row_count,
                "model_artifact_id": row.model_artifact_id,
                "model_name": row.model_name,
                "model_version": row.model_version,
                "feature_version": row.feature_version,
            }
            if isinstance(row, ModelPerformanceSummary)
            else {}
        ),
    }
