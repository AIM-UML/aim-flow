"""Meeting recording and summarization workflow."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from .audio import AudioRecorder, RecordingResult
from .config import MEETING_OUTPUT_DIR
from .ollama_client import ensure_model_available, start_ollama_service, summarize_meeting
from .transcription import WhisperEngine

logger = logging.getLogger(__name__)


def is_transcript_valid(transcript: str) -> bool:
    """Basic sanity check for transcript quality."""
    words = transcript.split()

    if len(words) < 20:
        return False

    def _letters_only(word: str) -> str:
        return "".join(ch for ch in word if ch.isalpha())

    def _alpha_ratio(word: str) -> float:
        if not word:
            return 0.0
        letters = sum(1 for ch in word if ch.isalpha())
        return letters / len(word)

    gibberish_count = 0
    for word in words:
        stripped = word.strip(".,!?;:\"'()[]{}<>")
        cleaned = _letters_only(stripped)
        ratio = _alpha_ratio(stripped)

        # Treat common tokens as valid: normal words, contractions, and hyphenated terms.
        if cleaned and len(cleaned) <= 24 and ratio >= 0.5:
            continue

        # Flag likely garbage: mostly symbols/numbers, empty alphabetic content,
        # or suspiciously long alpha runs that are uncommon in natural speech.
        if not cleaned or len(cleaned) > 24 or ratio < 0.5:
            gibberish_count += 1

    if gibberish_count / len(words) > 0.45:
        return False

    return True


class MeetingRecorder:
    """Manage long-form recording, transcription, and local summarization."""

    def __init__(self) -> None:
        self.is_recording = False
        self.audio_recorder: Optional[AudioRecorder] = None
        self.whisper = WhisperEngine()
        self.last_warning: Optional[str] = None
        self.capture_note: Optional[str] = None

        Path(MEETING_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    def start_recording(
        self,
        device_index: int | None = None,
        capture_note: str | None = None,
    ) -> bool:
        """Start a long-form meeting recording session."""
        if self.is_recording:
            logger.warning("Meeting recording already in progress")
            return False

        try:
            self.audio_recorder = AudioRecorder(device_index=device_index)
            self.audio_recorder.start()
            self.is_recording = True
            self.capture_note = capture_note
            logger.info("Meeting recording started")
            return True
        except Exception as exc:
            logger.error("Failed to start meeting recording: %s", exc)
            self.is_recording = False
            self.audio_recorder = None
            return False

    def stop_recording(self) -> Optional[RecordingResult]:
        """Stop recording and return captured audio frames."""
        if not self.is_recording or self.audio_recorder is None:
            logger.warning("No meeting recording in progress")
            return None

        try:
            result = self.audio_recorder.stop()
            self.is_recording = False
            self.audio_recorder = None
            logger.info("Meeting recording stopped")
            return result
        except Exception as exc:
            logger.error("Failed to stop meeting recording: %s", exc)
            self.is_recording = False
            self.audio_recorder = None
            return None

    def process_meeting(self, recording: RecordingResult) -> Optional[str]:
        """Transcribe meeting audio and save summary PDF output."""
        try:
            self.last_warning = None
            transcript = self.whisper.transcribe_frames(recording.frames, recording.sample_width)
            return self._process_transcript(transcript)
        except Exception as exc:
            logger.error("Meeting processing failed: %s", exc, exc_info=True)
            return None

    def process_audio_file(self, audio_path: str) -> Optional[str]:
        """Transcribe an existing audio file and generate a summary PDF."""
        try:
            self.last_warning = None
            self.capture_note = None
            transcript = self.whisper.transcribe_file(audio_path)
            return self._process_transcript(transcript)
        except Exception as exc:
            logger.error("Audio import processing failed: %s", exc, exc_info=True)
            return None

    def process_transcript_text(self, transcript: str) -> Optional[str]:
        """Generate a summary PDF from an existing text transcript."""
        try:
            self.last_warning = None
            self.capture_note = None
            return self._process_transcript(transcript)
        except Exception as exc:
            logger.error("Transcript processing failed: %s", exc, exc_info=True)
            return None

    def _process_transcript(self, transcript: str) -> Optional[str]:
        if not transcript or len(transcript.strip()) < 50:
            logger.error("Transcription too short or empty")
            return None

        if not is_transcript_valid(transcript):
            self.last_warning = (
                "Transcript quality appears low; saved transcript only. "
                "Use clearer audio and retry."
            )
            logger.warning(self.last_warning)
            return self._save_transcript_only(
                transcript,
                "Recorded from distance - accuracy may be lower.",
            )

        if not start_ollama_service():
            self.last_warning = (
                "Could not start Ollama automatically; saved transcript only. "
                "Install Ollama to enable summaries."
            )
            logger.error("Could not start Ollama service")
            return self._save_transcript_only(
                transcript,
                "Summary generation unavailable - Ollama could not be started.",
            )

        if not ensure_model_available():
            self.last_warning = (
                "Required model is unavailable; saved transcript only. "
                "Run: ollama pull llama3.2:3b"
            )
            logger.error("Could not ensure model llama3.2:3b")
            return self._save_transcript_only(
                transcript,
                "Summary generation unavailable - model llama3.2:3b not ready.",
            )

        summary = summarize_meeting(transcript)
        if not summary:
            logger.error("Summary generation failed")
            return self._save_transcript_only(
                transcript,
                "Summary generation failed in Ollama.",
            )

        output_path = self._save_summary(summary, transcript)
        logger.info("Meeting summary saved: %s", output_path)
        return output_path

    def _save_summary(self, summary: str, transcript: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Meeting_Summary_{timestamp}.pdf"
        output_path = os.path.join(MEETING_OUTPUT_DIR, filename)

        self._write_summary_pdf(output_path, summary, transcript, self.capture_note)

        return output_path

    def _save_transcript_only(self, transcript: str, reason: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Meeting_Transcript_{timestamp}.pdf"
        output_path = os.path.join(MEETING_OUTPUT_DIR, filename)

        self._write_transcript_pdf(output_path, transcript, reason, self.capture_note)

        return output_path

    def _write_summary_pdf(
        self,
        output_path: str,
        summary: str,
        transcript: str,
        capture_note: str | None,
    ) -> None:
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "MeetingTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111111"),
            spaceAfter=10,
            alignment=TA_LEFT,
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#8a1f11"),
            spaceAfter=10,
        )
        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#111111"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
        )
        transcript_style = ParagraphStyle(
            "Transcript",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            borderPadding=6,
            backColor=colors.whitesmoke,
            spaceBefore=4,
            spaceAfter=8,
        )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = [
            Paragraph(
                f"Meeting Summary - {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                title_style,
            ),
            Paragraph(
                "⚠️ This summary was generated by AI and may contain errors. Always verify against the full transcript below.",
                disclaimer_style,
            ),
        ]

        if capture_note:
            story.append(Paragraph(self._escape_text(capture_note), disclaimer_style))

        sections = self._parse_summary_sections(summary)
        section_order = ["Key Decisions", "Discussion Topics", "Action Items", "Next Steps"]
        for section_name in section_order:
            content = sections.get(section_name, "None identified")
            story.append(Paragraph(section_name, heading_style))
            story.extend(self._render_section_content(content, body_style))

        story.append(Paragraph("Full Transcript", heading_style))
        story.append(Paragraph("The transcript below is included for reference.", body_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(self._escape_text(transcript), transcript_style))

        doc.build(story)

    def _write_transcript_pdf(
        self,
        output_path: str,
        transcript: str,
        reason: str,
        capture_note: str | None,
    ) -> None:
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TranscriptTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111111"),
            spaceAfter=10,
        )
        note_style = ParagraphStyle(
            "TranscriptNote",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#8a1f11"),
            spaceAfter=10,
        )
        transcript_style = ParagraphStyle(
            "TranscriptBody",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            borderPadding=6,
            backColor=colors.whitesmoke,
        )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = [
            Paragraph(
                f"Meeting Transcript - {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                title_style,
            ),
            Paragraph(reason, note_style),
        ]

        if capture_note:
            story.append(Paragraph(self._escape_text(capture_note), note_style))

        story.append(Paragraph(self._escape_text(transcript), transcript_style))

        doc.build(story)

    def _parse_summary_sections(self, summary: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_section: Optional[str] = None

        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current_section = line[3:].strip()
                sections.setdefault(current_section, [])
                continue
            if current_section is None:
                continue
            sections.setdefault(current_section, []).append(line)

        return {name: "\n".join(lines).strip() for name, lines in sections.items()}

    def _render_section_content(self, content: str, body_style: ParagraphStyle) -> list:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return [Paragraph("None identified.", body_style)]

        if len(lines) == 1 and lines[0].lower() == "none identified.":
            return [Paragraph("None identified.", body_style)]

        if any(line.startswith("-") for line in lines):
            bullets = []
            for line in lines:
                if line.startswith("-"):
                    bullets.append(ListItem(Paragraph(self._escape_text(line.lstrip("- ")), body_style)))
                else:
                    bullets.append(ListItem(Paragraph(self._escape_text(line), body_style)))
            return [ListFlowable(bullets, bulletType="bullet", start="circle", leftPadding=18)]

        rendered = []
        for line in lines:
            rendered.append(Paragraph(self._escape_text(line), body_style))
        return rendered

    def _escape_text(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
