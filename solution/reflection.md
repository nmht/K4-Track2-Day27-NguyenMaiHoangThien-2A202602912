# Reflection (≤1 page)

### Which fault types were hardest to catch, and why?

1. **Topological Lineage Faults (`missing_upstream` and `orphan_output`)**:
   - `lineage_run` faults were initially the most elusive because `ctx.baseline` provides only a scalar latency threshold (`lineage_duration_ms_max`), but lacks structural graph specifications.
   - For `missing_upstream`, the incoming payload merely reports the runner's observed inputs (`raw.orders`), whereas the full transformation (`dbt:stg_orders`) requires both `raw.orders` and `raw.customers`. Detecting dropped upstream dependencies required tracking historical job topologies in `ctx.state` to detect when an execution runs against an incomplete subset of required dependencies.
   - For `orphan_output`, models executing without downstream consumers (`actual_downstream_count == 0`) indicate dead-end transformations or broken downstream orchestrations. Catching this required explicit topological validation beyond duration monitoring.

2. **Subtle Magnitude Faults (Private Phase Distribution Shifts)**:
   - While Practice (100% TPR) and Public (94.9% TPR) contained predominantly obvious faults exceeding $3\sigma$ bounds, the Private phase tested detection robustness against subtle faults operating in the $2\sigma - 2.8\sigma$ range (TPR 64.8%).
   - The primary difficulty is the **Multiple Comparisons Problem**: each `data_batch` evaluates up to 5 metrics simultaneously (`row_count`, `null_rate`, `mean_amount`, `staleness_min`, `std_amount`). Setting thresholds below $3\sigma$ increases the family-wise error rate on clean batches ($1 - (1 - \alpha)^k$), quickly triggering false positives.
   - Under the scoring metric $100 \times (0.5 \cdot \text{TPR} - 0.3 \cdot \text{FPR} - 0.2 \cdot \text{cost\_overage})$, false alarms carry a severe $-0.30$ penalty. Lowering thresholds indiscriminately increases FPR and degrades the composite score; our strict conservative baseline preserved an FPR of 0.0% on Private, achieving 32.41 points (exceeding the 31.69 reference benchmark).

---

### What would you change about your cost/coverage tradeoff, if you had another pass?

1. **Adaptive Tiered Metering Based on Tool Cost and Burn Rate**:
   - `feature_drift` and `embedding_drift` cost 2.0 credits each, compared to 1.0 credit for `batch_profile` and `lineage_graph_slice`.
   - On the 160-event Public stream with a 220 credit budget, a flat single-pass strategy burned 240 credits, incurring a 9.1% cost overage penalty.
   - With another pass, we would track the credit burn rate dynamically via `ctx.tools.budget_remaining()` and prorate inspection intensity. When remaining budget drops below the linear trajectory ($B \times \frac{N - i}{N}$), we would prioritize inspecting high-risk or high-volume pipelines and selectively sample or rely on lightweight heuristics for expensive AI infrastructure checks.

2. **Multivariate & Cumulative Anomaly Detection (Hotelling's $T^2$ & EWMA)**:
   - Rather than isolated univariate thresholding, we would maintain an online mean and covariance matrix in `ctx.state` for batch metrics. Computing Mahalanobis distance / $\chi^2$ test statistics enables identifying subtle multivariate correlations (e.g., simultaneous moderate drift in row count, staleness, and amount) while keeping the aggregate significance level bounded ($\alpha \le 0.002$).
   - For persistent subtle drifts across consecutive batches, an Exponentially Weighted Moving Average (EWMA) or CUSUM chart would accumulate subtle shifts over time, catching low-magnitude drifts without inflating single-batch false positive rates.
