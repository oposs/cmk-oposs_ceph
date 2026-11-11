# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### New

### Changed

### Fixed
- A Ceph monitor or mgr that stopped answering kept the agent plugin waiting
  forever, so the host sent no Ceph data at all. Each ceph command now gets
  30 seconds; a command that runs out of time leaves only its own service
  UNKNOWN with "No data from agent".

## 0.2.0 - 2026-11-06
### New
- The package carries the release version in its check plugin (`__version__`).
- The agent plugin from the MKP carries the release version in
  `PLUGIN_VERSION`.

### Changed
- Licence is now GNU General Public License v2, aligning this plugin
  with the rest of the OPOSS Checkmk plugin set. The `LICENSE` file
  previously held the MIT text.

### Fixed
- "Ceph OSD Latency" showed "Worst commit latency (OSD -1)" and "Worst
  apply latency (OSD -1)" on an idle cluster where every OSD reports 0 ms. It
  now names a real OSD.
- "Ceph PG Status" stayed OK with "N/N PGs clean" while scrub had found an
  inconsistent PG (state `active+clean+inconsistent`). Such PGs, and those
  under repair or with a failed repair or snaptrim error, now count as
  problematic and make the service WARN.

## 0.1.1 - 2026-03-06
### Fixed
- The GitHub release carries the MKP file `oposs_ceph-0.1.1.mkp`; release
  0.1.0 was tagged, but its package build failed and it was never published.

## 0.1.0 - 2026-03-06
### New
- Initial release with 7 monitoring services:
  Health, OSD Status, OSD Latency, Scrub, Pool Usage, PG Status, I/O
- Agent plugin collecting ceph status, osd perf, and df as JSON
- Per-OSD latency and per-pool usage metrics with auto-graphing
- Bidirectional throughput and IOPS graphs
- Scrub backlog and activity tracking
- Configurable thresholds for OSD latency, scrub counts, and pool usage
- Bakery integration for agent deployment with configurable interval
- MKP packaging via oposs/mkp-builder GitHub Action
