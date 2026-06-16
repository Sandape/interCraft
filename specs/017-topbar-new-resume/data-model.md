# Data Model: Topbar New Resume Branch

**Phase**: 1 (Design & Contracts)
**Date**: 2026-06-16

This feature introduces no new data entities, database tables, or API schemas. All changes are frontend-only interaction wiring.

## Entities

No changes. The existing `ResumeBranch` entity (from Phase 1) and its create mutation are reused.

## URL State

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `new` | `string \| null` | URL search params (`?new=true`) | Triggers auto-open of create branch modal on ResumeList mount; cleaned up on modal close |
