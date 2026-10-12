# Batch 2A — Recognition Workflow Migration Audit

## Scope and conclusion

This is a read-only audit.  The existing Industrial Diagnosis product behaviour can
be preserved while separating runtime perception from industrial evidence, but the
work is a **B — Moderate workflow migration**, not the rejected Batch 2 small
extraction.  No database, API, or frontend change is required if
`PerceptionResult` stays internal to RecognitionService/RecognitionActivity.

## EvidenceBundle lifecycle

```text
upload API -> RecognitionService.enqueue -> RecognitionRunRecord (QUEUED)
Temporal RecognitionWorkflow -> RecognitionActivity.execute
RecognitionService.process -> MediaService.read_clean
MultimodalProcessor.process (image or video) -> EvidenceBundle.create
RecognitionService._store_video_keyframes / _complete_run
EvidenceBundleRecord + RecognitionResultRecord + review/correction records
recognition API -> get_evidence / review / confirm -> EvidenceBundle.confirm
Incident.evidence_bundle_id -> DiagnosisService -> DiagnosisRuntime manifest
```

Definition and mutation are in `multimodal/models.py`: `EvidenceBundle.create`
validates perception references and `EvidenceBundle.confirm` applies the human
review/automation transition.  Construction occurs in `multimodal/processor.py`
for image and video.  `application/incidents.py` serializes, deserializes,
persists, reviews and confirms it through `_evidence_record`,
`_to_evidence_bundle`, `EvidenceBundleRepository`, and recognition result/review
records.  `api/routes/recognition.py` serializes it.  `RecognitionActivity` returns
it, while `RecognitionWorkflow` only exposes the completed run/bundle identifiers.
Diagnosis reads the persisted bundle through `EvidenceBundleRepository` in
`application/diagnoses.py`; it relies on the bundle id, confirmation status,
automation eligibility/blockers, processor versions, and normalized evidence
payload used to build the diagnosis manifest.  Existing Golden Path and simulation
smokes are the relevant evaluation coverage.

## Field ownership

| Fields | Owner | Evidence |
| --- | --- | --- |
| `ocr_blocks`, `visual_findings`, `qr_codes`, `asr_segments`, `video_keyframes`, `video_events`, bounding boxes, confidence, model release/provenance | Generic perception | Produced by OCR/VLM/QR/ASR/video providers; no persistence identity is intrinsic. |
| `extracted_entities`, `asset_id`, `draft_id`, `bundle_id`, `source_type`, `automatic_diagnosis_eligible` | Industrial Recognition | Entity extraction uses industrial critical entity rules; asset/draft bind the industrial case; automation is a diagnosis admission decision. |
| `human_corrections`, OCR/finding/QR/transcript/video reviews, `status`, `automation_eligible`, `automation_blockers`, security review | Industrial human review | These are created/validated by EvidenceBundle confirmation and RecognitionService review methods. |
| `tenant_id`, `media_id`, `source_sha256`, `recognition_run_id`, processor versions, timestamps, version | Workflow/persistence metadata | Used for tenant isolation, idempotency, record mapping, activity retry, and provenance. |

## Processor and provider audit

`MultimodalProcessor.process` checks media checksum, selects image/video processing,
and directly creates an EvidenceBundle in both paths.  Image invokes OCR, VLM and
QR.  Video invokes decomposition, OCR/VLM/QR per keyframe, ASR per audio clip and
optional temporal VLM.  Pure perception is decoding plus the resulting generic
blocks/findings/segments/events and provider metadata.

Industrial policy currently embedded in the processor/provider path is: request
identity (`bundle_id`, `draft_id`, `asset_id`), `asset_model`, industrial entity
validation, the `industrial-entity-rules-v2` version, and EvidenceBundle creation.
`VlmProvider.inspect`, `VideoAsrProvider.transcribe`, and
`VideoTemporalProvider.analyze` all require `asset_model`; Gateway/OpenAI VLM and
temporal providers construct industrial asset prompts, while ASR derives asset-model
hotwords.  These are the exact provider-contract changes required.

## RecognitionService and workflow impact

RecognitionService is the natural adapter boundary.  It already resolves the
authorized draft/field context, asset and media; reads clean content; persists video
artifacts; writes the existing records; and exposes review/confirmation.  It should
construct the industrial instruction/hotword context, call a generic processor, then
map `PerceptionResult` to the unchanged EvidenceBundle before `_complete_run`.

`RecognitionActivity.execute` currently returns EvidenceBundle, but
`RecognitionWorkflow` persists/returns identifiers rather than the serialized
bundle.  The activity may keep its public return type by completing the adapter
inside RecognitionService; therefore Temporal workflow input/payload, retry policy,
idempotency key, checkpoint behaviour and API dispatch contract need not change.

## Persistence and API impact

`EvidenceBundleRecord`, `RecognitionRunRecord`, `RecognitionResultRecord`, and the
existing correction/review records already represent the final industrial object.
`PerceptionResult` can be an in-memory/internal activity structure, so no migration
is required.  Upload, recognition-run, evidence review, confirmation and diagnosis
APIs remain unchanged; their response builders still receive EvidenceBundle.  No
frontend modification is required.

## Proposed minimal runtime contracts

`PerceptionRequest`: `tenant_id`, `subject_id`, `trace_id`, `media_id`, content
checksum/type/content, processor profile, and optional generic instruction/hotword
values.  It excludes asset, draft, incident, diagnosis and review state.

`PerceptionResult`: existing `ocr_blocks`, `visual_findings`, `qr_codes`,
`asr_segments`, `video_keyframes`, `video_events`, and provider metadata/security
findings.  It contains no identity, review, confirmation, asset or diagnosis field.

`IndustrialRecognitionContext`: private adapter input containing the current asset
model and the existing industrial instruction/hotwords.  It supplies plain bounded
instructions to VLM/ASR/temporal calls; it is not a prompt framework.

## Exact file impact

| File | Change | Why | Risk |
| --- | --- | --- | --- |
| `multimodal/models.py` | MODIFY | Retain generic primitive models; remove Bundle/review ownership to industrial module. | Medium: imports move. |
| `multimodal/processor.py` | MODIFY | Return PerceptionResult, remove asset/draft/Bundle construction. | Medium: image and video parity. |
| `multimodal/providers.py` | MODIFY | Replace `asset_model` with caller instruction context; remove industrial prompt text. | Medium: output semantic parity. |
| `multimodal/video.py` | MODIFY | Make ASR/temporal inputs generic contexts. | Medium: hotword/temporal prompt parity. |
| `application/industrial_evidence.py` | ADD | Own Bundle/review classes and PerceptionResult-to-Bundle mapping. | Medium: mechanical model move. |
| `application/incidents.py` | MODIFY | RecognitionService constructs industrial context and maps result before persistence. | Medium: core product path. |
| `orchestration/activities.py` | MODIFY only if type import moves | Preserve activity return/API. | Low. |
| `orchestration/workflows.py` | NO CHANGE expected | Activity payload remains identifiers. | Low. |
| `persistence/models.py`, Alembic | NO CHANGE | Existing final Bundle records remain. | Low. |
| `api/routes/recognition.py`, frontend | NO CHANGE expected | Public Bundle representation remains. | Low. |
| `application/diagnoses.py`, `agent/diagnosis_runtime.py` | NO CHANGE expected | Final persisted Bundle parity is mandatory. | Low. |

## Parity requirements

Before/after the adapter must preserve: bundle id allocation location; asset/draft/media
binding; source checksum/type; every OCR/VLM/QR/ASR/video value and provenance;
processor versions; review candidates; confirmation/version conflict semantics;
automation eligibility/blockers; persistence rows; diagnosis manifest eligibility;
citations, trace references and Golden Path outcome.

## TDD sequence

1. **RED 1:** construct a PerceptionResult without asset/draft/review fields.
2. **GREEN 1:** make image/video processor return it with fixture provider parity.
3. **RED 2:** assert Industrial adapter produces byte-for-byte equivalent persisted
   Bundle projection from the same perception fixture.
4. **GREEN 2:** move Bundle construction into RecognitionService/adapter while
   preserving activity return type.
5. **RED 3:** assert VLM/ASR/temporal provider contracts accept bounded instruction
   contexts and have no `asset_model` field.
6. **GREEN 3:** move existing industrial prompt/hotword construction to Recognition.
7. Run recognition/API review smoke and Batch 1 Golden Path parity.

## Stop-condition reassessment

No stop condition is currently proven for the dedicated migration: schema, API,
Temporal payload and diagnosis semantics can remain unchanged.  The earlier stop
applied only because Batch 2 prohibited this moderate coordinated workflow change.
