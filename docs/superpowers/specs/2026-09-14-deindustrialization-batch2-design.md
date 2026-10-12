# Deindustrialization Batch 2 Design

## Goal

Separate domain-neutral multimodal perception, knowledge applicability, and tool
governance from Industrial Diagnosis assumptions while preserving the current
Industrial Diagnosis Golden Path.

## Multimodal boundary

`multimodal` will own generic media inputs, OCR/VLM/ASR/video findings, provenance,
confidence, and bounded provider transport.  Its processor will return a generic
processing result and providers will receive caller-supplied `InspectionContext` or
`TranscriptionContext`; neither contract will contain `asset_model` or industrial
prompt text.

Industrial Evidence will own `EvidenceBundle`, review states, human corrections,
industrial entity validation, and the prompt/context construction using the known
asset model.  `RecognitionService` will compose the generic processor with this
adapter and persist exactly the existing EvidenceBundle projection.  No generic
prompt framework is introduced: the context is one small immutable value object.

## Retrieval boundary

`knowledge.applicability` will define a small mapping-based applicability filter.
The sole supported matching rule is: each populated query key must match at least
one value for that document key; an absent document key is unrestricted.  Industrial
Diagnosis maps its device family/model to `equipment.family` and `equipment.model`.

Migration `0088` will add JSON applicability to knowledge version/index records,
backfill it from device columns, and retain the old columns.  New ingestion writes
both, but generic retrieval and Search Profile paths read only applicability.  Thus
applicability is the source of truth; the retained device columns are a compatibility
projection and may not form a second runtime filtering path.

## Tool boundary

The generic registry/governance remains unchanged in responsibility.  The Industrial
Diagnosis side owns a catalog containing only `asset.get`, `warranty.get`,
`parts.availability`, `schedule.availability`, and `work_orders.history`.  The
existing default registry remains the fulfillment catalog.  Composition builds two
`ToolGateway` instances over the same class and governance rules: diagnosis receives
the readonly catalog/adapter; existing fulfillment routes retain the full catalog.

## Error handling and compatibility

Adapters reject unknown generic applicability keys only where an Industrial
conversion is requested.  Generic providers continue to validate bounded media and
structured output.  Existing tool schemas, authorization, audit, response shapes,
citation identifiers, tenant/ACL filters, and EvidenceBundle persistence remain
unchanged.

## Verification

Add three focused smoke scripts before their production changes: generic multimodal
processing without an asset context, retrieval parity plus a non-industrial
applicability filter, and a five-tool diagnosis catalog without fulfillment adapters.
Run them alongside all Batch 1 smokes, lint, compilation, focused mypy, migration
head check, and import scans.  No PostgreSQL infrastructure is created.
