# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### New

### Changed

### Fixed

## 0.1.0 - 2026-03-06
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
