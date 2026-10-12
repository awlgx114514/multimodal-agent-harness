"""Compose domain-neutral OCR, VLM, QR, ASR and temporal observations."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from hashlib import sha256

from industrial_ops_agent.multimodal.models import (
    AsrSegment,
    BoundingBox,
    EvidenceSchemaError,
    OcrBlock,
    PerceptionRequest,
    PerceptionResult,
    QrCodeCandidate,
    VideoEvent,
    VideoKeyframe,
    VisualFinding,
)
from industrial_ops_agent.multimodal.providers import (
    OcrProvider,
    QrCodeProvider,
    QrProviderResult,
    VlmProvider,
    ensure_supported_image_mime,
)
from industrial_ops_agent.multimodal.video import (
    VideoAsrProvider,
    VideoDecomposer,
    VideoFramePayload,
    VideoTemporalProvider,
    VideoTemporalWindow,
    ensure_supported_video_mime,
)


class MultimodalProcessor:
    def __init__(
        self,
        ocr: OcrProvider,
        vlm: VlmProvider,
        *,
        qr: QrCodeProvider | None = None,
        video: VideoDecomposer | None = None,
        video_asr: VideoAsrProvider | None = None,
        video_temporal: VideoTemporalProvider | None = None,
    ) -> None:
        self._ocr = ocr
        self._vlm = vlm
        self._qr = qr
        self._video = video
        self._video_asr = video_asr
        self._video_temporal = video_temporal

    async def process(self, request: PerceptionRequest) -> PerceptionResult:
        actual_hash = sha256(request.content).hexdigest()
        if actual_hash != request.content_hash:
            raise ValueError("clean media checksum changed before processing")
        normalized_mime = request.mime_type.split(";", 1)[0].strip().casefold()
        if normalized_mime.startswith("video/"):
            return await self._process_video(request, ensure_supported_video_mime(normalized_mime))
        if _temporal_analysis_requested(request.processor_profile):
            raise EvidenceSchemaError("video temporal analysis requires video media")
        return await self._process_image(request, ensure_supported_image_mime(normalized_mime))

    async def _process_image(
        self,
        request: PerceptionRequest,
        mime_type: str,
    ) -> PerceptionResult:
        ocr_result, vlm_result, qr_result = await asyncio.gather(
            self._ocr.recognize(
                request.content,
                mime_type=mime_type,
                tenant_id=request.tenant_id,
                subject_id=request.subject_id,
                trace_id=request.trace_id,
                source_id=request.source_id,
                business_run_id=request.business_run_id,
            ),
            self._vlm.inspect(
                request.content,
                mime_type=mime_type,
                instruction=request.vlm_instruction,
                tenant_id=request.tenant_id,
                subject_id=request.subject_id,
                trace_id=request.trace_id,
                source_id=request.source_id,
                business_run_id=request.business_run_id,
            ),
            self._decode_qr(
                request.content,
                mime_type=mime_type,
                request=request,
                source_id=request.source_id,
            ),
        )
        versions = {
            "ocr": ocr_result.processor_version,
            "vlm": vlm_result.processor_version,
        }
        for key in (
            "model_alias",
            "release_id",
            "deployment_id",
            "manifest_hash",
            "target_environment",
            "request_id",
        ):
            value = getattr(ocr_result, key)
            if value:
                versions[f"ocr.{key}"] = value
        if vlm_result.execution is not None:
            versions.update(vlm_result.execution.as_processor_versions("vlm"))
        if vlm_result.unsupported_model:
            versions["vlm_status"] = "unsupported_model"
        qr_codes: tuple[QrCodeCandidate, ...] = ()
        if qr_result is not None:
            versions["qr"] = qr_result.processor_version
            qr_codes = qr_result.candidates
        return PerceptionResult(
            source_type="image",
            ocr_blocks=ocr_result.blocks,
            visual_findings=vlm_result.findings,
            qr_codes=qr_codes,
            processor_versions=versions,
        )

    async def _decode_qr(
        self,
        content: bytes,
        *,
        mime_type: str,
        request: PerceptionRequest,
        source_id: str,
    ) -> QrProviderResult | None:
        if self._qr is None:
            return None
        return await self._qr.decode(
            content,
            mime_type=mime_type,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            trace_id=request.trace_id,
            source_id=source_id,
        )

    async def _process_video(
        self,
        request: PerceptionRequest,
        mime_type: str,
    ) -> PerceptionResult:
        if self._video is None or self._video_asr is None:
            raise EvidenceSchemaError("video processing profile is not configured")
        decomposition = await self._video.decompose(request.content, mime_type=mime_type)
        audio_track_count = decomposition.audio_track_count or len(
            {clip.source_audio_track_id for clip in decomposition.audio_clips}
        )
        blocks: list[OcrBlock] = []
        findings: list[VisualFinding] = []
        qr_codes: list[QrCodeCandidate] = []
        ocr_versions: set[str] = set()
        vlm_versions: set[str] = set()
        qr_versions: set[str] = set()
        unsupported_model = False
        for page_number, frame in enumerate(decomposition.keyframes, start=1):
            frame_source_id = f"{request.source_id}:{frame.frame_id}"
            ocr_result, vlm_result, qr_result = await asyncio.gather(
                self._ocr.recognize(
                    frame.image_jpeg,
                    mime_type="image/jpeg",
                    tenant_id=request.tenant_id,
                    subject_id=request.subject_id,
                    trace_id=request.trace_id,
                    source_id=frame_source_id,
                    business_run_id=request.business_run_id,
                ),
                self._vlm.inspect(
                    frame.image_jpeg,
                    mime_type="image/jpeg",
                    instruction=request.vlm_instruction,
                    tenant_id=request.tenant_id,
                    subject_id=request.subject_id,
                    trace_id=request.trace_id,
                    source_id=frame_source_id,
                    business_run_id=request.business_run_id,
                ),
                self._decode_qr(
                    frame.image_jpeg,
                    mime_type="image/jpeg",
                    request=request,
                    source_id=frame_source_id,
                ),
            )
            ocr_versions.add(ocr_result.processor_version)
            vlm_versions.add(vlm_result.processor_version)
            unsupported_model = unsupported_model or vlm_result.unsupported_model
            if qr_result is not None:
                qr_versions.add(qr_result.processor_version)
                qr_codes.extend(
                    replace(candidate, source_frame_id=frame.frame_id)
                    for candidate in qr_result.candidates
                )
            blocks.extend(
                OcrBlock(
                    block_id=f"{frame.frame_id}:{item.block_id}",
                    page_number=page_number,
                    text=item.text,
                    bbox=item.bbox,
                    confidence=item.confidence,
                    source_frame_id=frame.frame_id,
                )
                for item in ocr_result.blocks
            )
            findings.extend(
                VisualFinding(
                    finding_id=f"{frame.frame_id}:{item.finding_id}",
                    label=item.label,
                    bbox=item.bbox,
                    confidence=item.confidence,
                    evidence_level=item.evidence_level,
                    model_release_id=item.model_release_id,
                    description=item.description,
                    source_frame_id=frame.frame_id,
                )
                for item in vlm_result.findings
            )

        asr_segments: list[AsrSegment] = []
        asr_versions: set[str] = set()
        asr_hotword_profiles: set[str] = set()
        for clip in decomposition.audio_clips:
            result = await self._video_asr.transcribe(
                clip,
                tenant_id=request.tenant_id,
                subject_id=request.subject_id,
                trace_id=request.trace_id,
                media_id=request.source_id,
                context_terms=((request.asr_context,) if request.asr_context else ()),
            )
            asr_versions.add(result.processor_version)
            asr_hotword_profiles.add(result.hotword_profile_id)
            asr_segments.append(
                AsrSegment(
                    segment_id=clip.segment_id,
                    start_ms=clip.start_ms,
                    end_ms=clip.end_ms,
                    text=result.text,
                    language=result.language,
                    confidence=result.confidence,
                    model_release_id=result.processor_version,
                    source_audio_track_id=clip.source_audio_track_id,
                    hotword_profile_id=result.hotword_profile_id,
                )
            )

        keyframes = tuple(
            VideoKeyframe(
                frame_id=item.frame_id,
                timestamp_ms=item.timestamp_ms,
                image_sha256=item.image_sha256,
                sampling_reason=item.sampling_reason,
                image_jpeg=item.image_jpeg,
            )
            for item in decomposition.keyframes
        )
        sampling_events = tuple(
            VideoEvent(
                event_id=f"event-{item.frame_id}",
                event_type=(
                    "scene_change"
                    if item.sampling_reason == "scene_change"
                    else "periodic_observation"
                ),
                start_ms=item.timestamp_ms,
                end_ms=item.timestamp_ms,
                keyframe_ids=(item.frame_id,),
                confidence=1.0,
                description=(
                    "画面变化采样点" if item.sampling_reason == "scene_change" else "周期采样点"
                ),
            )
            for item in decomposition.keyframes
        )
        temporal_events: tuple[VideoEvent, ...] = ()
        temporal_versions: set[str] = set()
        temporal_unsupported = False
        if _temporal_analysis_requested(request.processor_profile):
            if self._video_temporal is None:
                raise EvidenceSchemaError("video temporal analysis profile is unavailable")
            temporal_rows: list[VideoEvent] = []
            frame_timestamps = {item.frame_id: item.timestamp_ms for item in keyframes}
            for window in _temporal_windows(decomposition.keyframes):
                temporal_result = await self._video_temporal.analyze(
                    window,
                    tenant_id=request.tenant_id,
                    subject_id=request.subject_id,
                    trace_id=request.trace_id,
                    media_id=request.source_id,
                    instruction=request.temporal_instruction or request.vlm_instruction,
                )
                temporal_versions.add(temporal_result.processor_version)
                if temporal_result.unsupported_model:
                    temporal_unsupported = True
                    break
                for candidate in temporal_result.candidates:
                    ordered_frame_ids = tuple(
                        sorted(
                            candidate.keyframe_ids,
                            key=lambda frame_id: (frame_timestamps[frame_id], frame_id),
                        )
                    )
                    event_source = "\0".join(
                        (
                            request.event_identity or request.source_id,
                            candidate.candidate_type,
                            *ordered_frame_ids,
                            candidate.description,
                        )
                    )
                    temporal_rows.append(
                        VideoEvent(
                            event_id=(
                                f"temporal-event-{sha256(event_source.encode()).hexdigest()[:20]}"
                            ),
                            event_type=candidate.candidate_type,
                            start_ms=frame_timestamps[ordered_frame_ids[0]],
                            end_ms=frame_timestamps[ordered_frame_ids[-1]],
                            keyframe_ids=ordered_frame_ids,
                            confidence=candidate.confidence,
                            description=candidate.description,
                            model_release_id=temporal_result.processor_version,
                        )
                    )
            temporal_events = _deduplicate_temporal_events(temporal_rows)
        events = tuple(
            sorted(
                (
                    *sampling_events,
                    *_fuse_visual_candidate_events(
                        request.event_identity or request.source_id,
                        keyframes,
                        findings,
                    ),
                    *temporal_events,
                ),
                key=lambda item: (item.start_ms, item.end_ms, item.event_type, item.event_id),
            )
        )
        versions = {
            "video_decomposer": decomposition.processor_version,
            "ocr": _one_version(ocr_versions, "OCR"),
            "vlm": _one_version(vlm_versions, "VLM"),
            "asr": (
                _one_version(asr_versions, "ASR")
                if asr_versions
                else "no_speech_detected"
                if decomposition.has_audio
                else "no_audio_track"
            ),
            "audio_layout": (
                f"{audio_track_count}-track-separated-v1"
                if decomposition.has_audio
                else "no-audio-track"
            ),
            "asr_hotwords": (
                _one_version(asr_hotword_profiles, "ASR hotword profile")
                if asr_hotword_profiles
                else "no_asr_segments"
            ),
        }
        if unsupported_model:
            versions["vlm_status"] = "unsupported_model"
        if self._qr is not None:
            versions["qr"] = _one_version(qr_versions, "QR")
        if _temporal_analysis_requested(request.processor_profile):
            versions["video_vlm"] = (
                _one_version(temporal_versions, "Video VLM")
                if temporal_versions
                else "no_eligible_temporal_window"
            )
            if temporal_unsupported:
                versions["video_vlm_status"] = "unsupported_model"
        return PerceptionResult(
            source_type="video",
            ocr_blocks=tuple(blocks),
            asr_segments=tuple(asr_segments),
            visual_findings=tuple(findings),
            video_keyframes=keyframes,
            video_events=events,
            qr_codes=tuple(qr_codes),
            processor_versions=versions,
        )


_VISUAL_EVENT_MAX_GAP_MS = 3_000
_VISUAL_EVENT_MIN_IOU = 0.1
_TEMPORAL_WINDOW_MAX_FRAMES = 6
_TEMPORAL_WINDOW_MAX_SPAN_MS = 12_000
_TEMPORAL_WINDOW_MAX_COUNT = 4


def _temporal_analysis_requested(processor_profile: str) -> bool:
    return processor_profile in {"video-temporal-v1", "local-video-temporal-v1"}


def _temporal_windows(
    frames: tuple[VideoFramePayload, ...],
) -> tuple[VideoTemporalWindow, ...]:
    windows: list[VideoTemporalWindow] = []
    start = 0
    while start < len(frames) and len(windows) < _TEMPORAL_WINDOW_MAX_COUNT:
        first_timestamp = frames[start].timestamp_ms
        end = start
        while (
            end < len(frames)
            and end - start < _TEMPORAL_WINDOW_MAX_FRAMES
            and frames[end].timestamp_ms - first_timestamp <= _TEMPORAL_WINDOW_MAX_SPAN_MS
        ):
            end += 1
        selected = frames[start:end]
        if len(selected) >= 3:
            windows.append(
                VideoTemporalWindow(
                    window_id=(
                        f"temporal-window-{len(windows) + 1:02d}-"
                        f"{selected[0].timestamp_ms}-{selected[-1].timestamp_ms}"
                    ),
                    frames=selected,
                )
            )
            start = end
        else:
            start += 1
    return tuple(windows)


def _deduplicate_temporal_events(events: list[VideoEvent]) -> tuple[VideoEvent, ...]:
    unique: dict[tuple[str, tuple[str, ...], str], VideoEvent] = {}
    for event in events:
        key = (event.event_type, event.keyframe_ids, event.description.casefold())
        existing = unique.get(key)
        if existing is None or event.confidence > existing.confidence:
            unique[key] = event
    return tuple(unique.values())


def _fuse_visual_candidate_events(
    bundle_id: str,
    keyframes: tuple[VideoKeyframe, ...],
    findings: list[VisualFinding],
) -> tuple[VideoEvent, ...]:
    """Fuse repeated candidate labels into reviewable, frame-anchored time ranges."""

    frame_timestamps = {item.frame_id: item.timestamp_ms for item in keyframes}
    by_label: dict[str, list[VisualFinding]] = {}
    for finding in findings:
        if finding.source_frame_id is None:
            raise EvidenceSchemaError("video visual finding is missing its frame anchor")
        by_label.setdefault(finding.label.strip().casefold(), []).append(finding)

    events: list[VideoEvent] = []
    for normalized_label, label_findings in sorted(by_label.items()):
        ordered = sorted(
            label_findings,
            key=lambda item: (
                frame_timestamps[item.source_frame_id or ""],
                item.source_frame_id or "",
                item.finding_id,
            ),
        )
        runs: list[list[VisualFinding]] = []
        for finding in ordered:
            timestamp_ms = frame_timestamps[finding.source_frame_id or ""]
            candidates: list[tuple[float, int, list[VisualFinding]]] = []
            for run in runs:
                previous = run[-1]
                previous_frame_id = previous.source_frame_id or ""
                previous_ms = frame_timestamps[previous_frame_id]
                overlap = _bbox_iou(previous.bbox, finding.bbox)
                if (
                    previous_frame_id != finding.source_frame_id
                    and timestamp_ms - previous_ms <= _VISUAL_EVENT_MAX_GAP_MS
                    and overlap >= _VISUAL_EVENT_MIN_IOU
                ):
                    candidates.append((overlap, previous_ms, run))
            if candidates:
                max(candidates, key=lambda item: (item[0], item[1]))[2].append(finding)
            else:
                runs.append([finding])

        for run in runs:
            run_frame_ids = tuple(dict.fromkeys(item.source_frame_id or "" for item in run))
            run_finding_ids = tuple(item.finding_id for item in run)
            start_ms = frame_timestamps[run_frame_ids[0]]
            end_ms = frame_timestamps[run_frame_ids[-1]]
            label = run[0].label
            event_key = "\0".join(
                (bundle_id, normalized_label, str(start_ms), str(end_ms), *run_finding_ids)
            )
            events.append(
                VideoEvent(
                    event_id=f"visual-event-{sha256(event_key.encode()).hexdigest()[:20]}",
                    event_type="visual_candidate",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    keyframe_ids=run_frame_ids,
                    finding_ids=run_finding_ids,
                    confidence=sum(item.confidence for item in run) / len(run),
                    description=(
                        f"候选现象“{label}”在 {len(run_frame_ids)} 个采样帧中出现；"
                        "仍需人工逐帧复核。"
                    ),
                )
            )
    return tuple(events)


def _bbox_iou(first: BoundingBox, second: BoundingBox) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if intersection == 0:
        return 0.0
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union


def _one_version(values: set[str], component: str) -> str:
    if len(values) != 1:
        raise EvidenceSchemaError(f"{component} processor changed during one video run")
    return next(iter(values))
