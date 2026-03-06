# Ceph Cluster Checkmk Plugin

Checkmk agent plugin for monitoring Ceph clusters.

## Features

Provides 7 services from a single agent plugin:

| Service | Monitors | Thresholds |
|---------|----------|------------|
| Ceph Health | Overall HEALTH_OK/WARN/ERR with detail per check | State-based |
| Ceph OSD Status | OSDs up/in, alerts on down/out | State-based |
| Ceph OSD Latency | Worst-case commit/apply latency, per-OSD graphs | Configurable (default 50/100 ms) |
| Ceph Scrub | Overdue scrub/deep-scrub PG counts, scrub activity | Configurable (default 10/50 PGs) |
| Ceph Pool Usage | Cluster capacity %, per-pool usage graphs | Configurable (default 80/90%) |
| Ceph PG Status | PG state distribution, non-clean PG alerting | State-based |
| Ceph I/O | Client read/write throughput and IOPS (bidirectional graphs) | Info only |

Per-instance metrics (per-OSD latency, per-pool usage) are yielded dynamically
and auto-graphed by Checkmk. Aggregate graphs are provided for cluster I/O,
scrub backlog, and capacity.

## Requirements

- Checkmk 2.3.0p1 or later
- Agent host must have `ceph` CLI access (typically a mon node)

## Installation

### MKP Package (recommended)

Download the latest `.mkp` file from the
[Releases](https://github.com/oposs/cmk-oposs_ceph/releases) page and
install it:

```bash
mkp install oposs_ceph-<version>.mkp
```

### Manual Installation

Copy the plugin files into your Checkmk site:

```
local/lib/python3/cmk_addons/plugins/oposs_ceph/
├── agent_based/
│   └── oposs_ceph.py
├── graphing/
│   └── oposs_ceph.py
└── rulesets/
    └── oposs_ceph.py

local/lib/python3/cmk/base/cee/plugins/bakery/
└── oposs_ceph.py

local/share/check_mk/agents/plugins/
└── oposs_ceph
```

### Bakery Deployment

Enable the "Ceph Monitoring (Linux)" agent bakery rule to automatically deploy
the agent plugin to hosts. The collection interval is configurable (default 60s).

## Cluster Setup

Since all Ceph mon nodes report the same cluster-wide data, the plugin supports
Checkmk's native cluster hosts to avoid duplicate services:

1. **Add each mon node** as a regular host in Checkmk
2. **Deploy the agent plugin** to all mon nodes (via bakery rule or manually)
3. **Create a cluster host** in Setup > Hosts > Create cluster host
   - Add the mon nodes as cluster nodes
4. **Assign the Ceph services to the cluster** in the cluster host's service
   configuration — use "Clustered services" rules to move the 7 Ceph services
   from the individual nodes to the cluster host
5. **Discover services** on the cluster host

The cluster check function picks data from whichever mon node responds. If one
mon goes down, monitoring continues from the remaining nodes.

## Agent Data

The agent plugin runs three commands:

- `ceph status -f json` — health, OSD map, PG states, I/O stats
- `ceph osd perf -f json` — per-OSD commit/apply latency
- `ceph df detail -f json` — cluster and per-pool capacity

## Troubleshooting

Test the agent plugin directly on the mon node:

```bash
/usr/lib/check_mk_agent/plugins/oposs_ceph
```

Verify Ceph CLI access:

```bash
ceph status -f json
```

## License

MIT - OETIKER+PARTNER AG
