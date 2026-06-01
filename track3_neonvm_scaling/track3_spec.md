# Sovereign System Specification: Serverless Kubernetes NeonVM Cgroups Monitor

**Classification**: Sovereign Architecture Design Specification (VP-Ready)  
**Status**: Approved for Design  
**Target Path**: `/home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track3_neonvm_scaling/track3_spec.md`

---

## 1. Executive Summary & Hardware Topology

This specification defines the architecture, event loop, and monitoring parameters for the **Serverless Kubernetes NeonVM Cgroups Monitor**. Designed for zero-delay scaling of database enclaves, this daemon bypasses standard Kubernetes metric polling (which typically has a 10s–60s latency window) by listening directly to Linux cgroups v2 filesystem event descriptors. 

Under bursty agentic workloads, database servers running inside NeonVMs experience sudden memory allocation spikes. Rather than waiting for horizontal pod autoscalers to trigger, this monitor detects cgroup-level page-fault and memory pressure events in real-time, executing instant vertical memory adjustments (cgroup limits reallocation) to mitigate Out-Of-Memory (OOM) termination risk.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PROXMOX COMPUTE NODE                            │
│  - Simulates Databricks Serverless Worker Host                         │
│  - Runs NeonVM Cgroups Monitor Daemon (Process)                       │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Linux cgroups v2 Namespace (/sys/fs/cgroup/neonvm/)              │  │
│  │  - Monitors: 'memory.events' (low/high memory event indicators)   │  │
│  │  - Adjusts:  'memory.max' (Maximum memory limit allocation)       │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
│                                    │ Detects Events & Scales           │
│                                    ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Simulated NeonVM Instance (Bursty Database workload)              │  │
│  │  - Experiencing sudden agentic load spikes                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Hardware Constraints:
1. **Host Node**: Runs as a localized Python background service on the **Proxmox Virtualization Node** host, mimicking a Databricks Serverless compute cluster worker.
2. **Linux Kernel**: Requires Linux kernel supporting cgroups v2 (`/sys/fs/cgroup/`) with memory controllers enabled.
3. **Target Database VM**: Simulated Postgres/NeonVM container instance whose resource metrics are isolated within a sub-cgroup.

---

## 2. Core Logic: Cgroups v2 Event-Driven Autoscale

### 2.1 The Slow Polling Vulnerability
Standard orchestration engines (e.g. Kubernetes Metrics Server, Prometheus) query memory metrics from `/proc` or container APIs at periodic intervals (e.g., every 15 seconds). Under heavy agentic execution (e.g., a multi-agent vector search aggregation or massive batch transactional ingestion), memory consumption can scale from 20% to 100% in milliseconds. This results in the Linux OOM Killer terminating the database process (`OOM-Killed`) before the monitoring plane is even aware of the spike.

### 2.2 Event-Driven Escalation Flow
To solve this, the monitor binds directly to cgroups v2 event descriptors:
1. **Event Watcher**: Listens to changes in `/sys/fs/cgroup/<target>/memory.events`. The daemon monitors file attributes specifically tracking:
   - `low`: Number of times memory usage entered the lower-threshold zone.
   - `high`: Number of times memory usage exceeded the upper-threshold zone.
   - `oom`: Number of times the OOM Killer was triggered (or would be triggered).
2. **Pressure Detection**: In addition to polling `memory.current`, the daemon polls `memory.pressure` (PSI - Pressure Stall Information) to measure scheduler latency caused by memory starvation.
3. **Instant Mitigation**: When event thresholds are breached, the daemon instantly raises the memory ceiling `memory.max` by a pre-configured multiplier (e.g., $1.5\times$ or a fixed $+256\text{MB}$ delta), ensuring the kernel does not invoke the OOM Killer.

---

## 3. Required Python Modules & Dependencies

The daemon runs natively within the host namespace and requires:
- **`psutil`**: For reading host-level process telemetry and memory utilization metrics.
- **`os` / `sys`**: For filesystem operations and cgroups file manipulation.
- **`time` / `threading`**: For running the event loop and simulated workload generator concurrently.
- **`logging`**: High-frequency structured logging of scaling events and memory footprints.

---

## 4. Workload Simulator Design
To validate the architecture, the package includes a workload simulator:
- **Memory Consumer**: A thread that spawns memory-intensive payloads (e.g., large data arrays or memory-mapped buffers) to mimic a database performing a sudden query execution.
- **Scale Trigger**: Rapidly consumes up to 95% of the initial cgroup memory limits to trigger memory event descriptors.

---

## 5. Performance Invariants & Policy Invariants

### Invariant 01: Sub-Millisecond Event Response
> The monitor must detect memory limit thresholds and execute the limit adjustment in $<50\text{ms}$ of the kernel recording the event in `memory.events`.

### Invariant 02: Hard Limit Boundaries (Ceiling Safeguard)
> The daemon must never raise the cgroup memory limit beyond a configured **Hard Max Ceiling** (e.g., 85% of host memory), protecting the host node from starvation and cascade failures.

### Invariant 03: Cool-Down Period
> After a vertical scale-up event, the daemon must enforce a **Cool-Down window** (e.g., 5 seconds) before allowing subsequent scale-up adjustments to prevent unstable loop oscillation.
