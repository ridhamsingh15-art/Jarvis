# Performance Analysis

| ID | Latency | LLM | Tools | ExecBrain | ReasonLoop |
|---|---|---|---|---|---|
| A-CHAT | 23.7s | 1 | 0 | True | True |
| B-AMBIG | 60.4s | 0 | 1 | True | True |
| C-MEM-WRITE | 0.0s | 0 | 0 | True | True |
| C-MEM-RECALL | 26.8s | 1 | 0 | True | True |
| D-TOOL | 27.9s | 1 | 0 | True | True |
| E-MULTI | 273.1s | 1 | 1 | True | True |
| F-RECOVER | 15.5s | 1 | 1 | True | True |
| G-MISSION | 52.4s | 0 | 0 | True | True |
| H-SWE | 663.9s | 0 | 3 | True | True |
| I-T1 | 48.3s | 1 | 0 | True | True |
| I-T2 | 20.3s | 1 | 0 | True | True |
| I-T3 | 23.6s | 1 | 0 | True | True |
| J-INJECT | 27.2s | 1 | 1 | True | True |
| K-TINJECT | 1231.2s | 1 | 1 | True | True |
| L-VERIFY | 13.8s | 1 | 1 | True | True |
| M-SECURITY | 0.0s | 0 | 0 | False | False |
| N-ESCALATE | 62.3s | 0 | 1 | True | True |

Average latency: 151.2s