# Deindustrialization Batch 2 Follow-ups

Batch 2A, Batch 2B, and Batch 2C structural goals are complete.  The Batch 2A
evidence provenance bridge, Batch 2B generic Knowledge applicability migration,
and Batch 2C Diagnosis runtime/tool boundary are resolved.  Fulfillment
deletion remains out of scope until separately authorized.

## Diagnosis runtime composition

Status: resolved in Batch 2C.  The Diagnosis worker now receives a dedicated
five-tool read-only catalog through a separate `ToolGateway` instance, while
the legacy Fulfillment/API composition retains its mixed catalog.  Both use
the same generic governance implementation.  Runtime isolation and mutation
rejection are covered by the Batch 2C smoke and dependency scan.

## Recognition workflow extraction

Status: resolved in Batch 2A.  The Multimodal → PerceptionResult → Industrial
Recognition → EvidenceBundle boundary is implemented and verified.

Before a future batch extracts generic multimodal perception, it must explicitly
scope a recognition-workflow migration that separates EvidenceBundle construction,
review transitions, persistence projection, and image/video processing results.
Do not paper over this boundary with a generic wrapper around the existing processor.
