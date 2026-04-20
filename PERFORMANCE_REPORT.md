# Performance Evaluation Report: Distributed Semantic Retrieval System

This report summarizes the performance testing results for the Distributed Semantic Retrieval System, conducted on **April 20, 2026**.

## 1. Test Environment & Methodology

- **Hardware Specs**: 16 Logical CPUs, 30.47 GB RAM ([Full Hardware Log](file:///home/johnny/seng468-semantic-retrieval-group13/test_results/hardware_info_20260420_002829.txt)).
- **Duration**: Each test scenario was run for exactly **1 minute**.
- **Optimization**: API Gateway utilizing **2 Gunicorn workers** to manage resource contention during high-CPU embedding tasks.

## 2. Baseline Test Run (Stable Load)

- **Scenario**: 10 users, 2 users/sec spawn rate.
- **Reports**: [HTML](file:///home/johnny/seng468-semantic-retrieval-group13/test_results/report_20260420_002727.html) | [Logs](file:///home/johnny/seng468-semantic-retrieval-group13/test_results/container_stats_20260420_002727.txt)

| Endpoint                | Request Count | Avg Latency | P95 Latency |   RPS    |
| :---------------------- | :-----------: | :---------: | :---------: | :------: |
| `POST /auth/signup`     |      10       |  1,312 ms   |  3,600 ms   |   0.17   |
| `POST /documents` (5MB) |      19       |   125 ms    |   250 ms    |   0.32   |
| `GET /search`           |      89       |   179 ms    |   180 ms    |   1.51   |
| **Aggregated**          |    **200**    | **186 ms**  | **250 ms**  | **3.39** |

## 3. Stress Test Run (High Load)

- **Scenario**: 50 users, 5 users/sec spawn rate.
- **Reports**: [HTML](file:///home/johnny/seng468-semantic-retrieval-group13/test_results/report_20260420_002829.html) | [Logs](file:///home/johnny/seng468-semantic-retrieval-group13/test_results/container_stats_20260420_002829.txt)

| Endpoint                | Request Count | Avg Latency | P95 Latency |    RPS    |
| :---------------------- | :-----------: | :---------: | :---------: | :-------: |
| `POST /auth/signup`     |      50       |   181 ms    |   320 ms    |   0.85    |
| `POST /documents` (5MB) |      151      |    84 ms    |   150 ms    |   2.56    |
| `GET /search`           |      484      |    36 ms    |   150 ms    |   8.20    |
| **Aggregated**          |   **1,026**   |  **53 ms**  | **220 ms**  | **17.38** |

## 4. Key Findings & Data Interpretation

The system demonstrates excellent scalability. Even with a **17.38 Requests Per Second** load, P95 latencies remained significantly under the **2,000ms target limit**.

### Bottleneck Analysis

- **Worker Saturation**: During the stress test, the `worker` service reached **791.70% CPU**, confirming it is the primary compute bottleneck.
- **API Efficiency**: Despite the worker load, the API remained responsive, peaking at **507.24% CPU** during concurrent search vectorization.

## 5. Conclusion

The system successfully handles concurrent document management and semantic search tasks under sustained load without service degradation or request failures (0.00% failure rate).
