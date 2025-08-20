# -*- coding: utf-8 -*-
import re
import asyncio
from typing import Any, Dict, List, Optional, Tuple

import frappe
import httpx
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

DEEPGRAM_API_KEY: Optional[str] = frappe.conf.get("deepgram_api_key")
DEEPGRAM_API_URL: str = "https://api.deepgram.com/v1/listen?summarize=v2&punctuate=true"
AUDIO_CONTENT_TYPE: str = "audio/mp3"


def summarize_transcript(text: str) -> str:
    """Fallback summarizer if Deepgram doesn't return a summary."""
    sentences = re.split(r'(?<=[.!?]) +', text)
    return "\n".join(f"- {s.strip()}" for s in sentences[:3] if s.strip())


class CreateNotesFromCallLogs(BaseTool):
    def parse_prompt_to_args(self, prompt: str) -> Dict[str, Any]:
        """
        Parse natural language prompt to argument dict for note creation.
        Supported prompts:
        - create note for call log <id>
        - create note for call log <id> and link it to <doctype> <docname>
        - create notes for last <N> call logs
        - create notes for call logs <id1>, <id2>, ...
        """
        prompt = prompt.strip().lower()
        if prompt.startswith("create note for call log"):
            parts = prompt.split("and link it to")
            call_log = parts[0].replace("create note for call log", "").strip()
            args = {"call_logs": [call_log]}
            if len(parts) > 1:
                link = parts[1].strip().split()
                if len(link) >= 2:
                    args["reference_doctype"] = link[0]
                    args["reference_name"] = link[1]
            return args
        elif prompt.startswith("create notes for last"):
            n = int(prompt.split("create notes for last")[1].split("call logs")[0].strip())
            return {"count_last": n}
        elif prompt.startswith("create notes for call logs"):
            logs = prompt.split("create notes for call logs")[1].strip()
            call_logs = [log.strip() for log in logs.split(",") if log.strip()]
            return {"call_logs": call_logs}
        else:
            raise ValueError("Prompt not recognized")

    def __init__(self):
        super().__init__()
        self.name = "generate_notes_from_calls"
        self.description = _("Create Notes from one or multiple CRM Call Logs using Deepgram transcription.")
        self.requires_permission = "Note"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "call_logs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _("List of Call Log names to process."),
                },
                "count_last": {
                    "type": "integer",
                    "description": _("Take the last N completed call logs instead of specifying call_logs."),
                },
                "reference_doctype": {
                    "type": "string",
                    "description": _("Optional: Doctype to link notes to (CRM Lead, Deal, or Customer)."),
                },
                "reference_name": {
                    "type": "string",
                    "description": _("Optional: Document name to link notes to."),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _("Whether to overwrite existing note if one exists."),
                    "default": False
                },
            },
            "oneOf": [
                {"required": ["call_logs"]},
                {"required": ["count_last"]},
            ],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method: validate access, process call logs asynchronously, and create notes.
        """
        from frappe_assistant_core.core.security_config import validate_document_access, audit_log_tool_access

        validation_result = validate_document_access(
            user=frappe.session.user, doctype="FCRM Note", name=None, perm_type="create"
        )
        if not validation_result["success"]:
            audit_log_tool_access(frappe.session.user, self.name, arguments, validation_result)
            return validation_result

        call_log_names = self._resolve_call_logs(arguments)

        # Run asynchronous processing
        processed, skipped = asyncio.run(
            self._process_call_logs_async(
                call_log_names,
                arguments.get("reference_doctype"),
                arguments.get("reference_name"),
                arguments.get("overwrite", False)
            )
        )

        summary = {"success": True, "processed": processed, "skipped": skipped}
        audit_log_tool_access(frappe.session.user, self.name, arguments, summary)
        return summary

    def _resolve_call_logs(self, args: Dict[str, Any]) -> List[str]:
        call_logs = args.get("call_logs") or args.get("call_log")
        if call_logs:
            return [call_logs] if isinstance(call_logs, str) else call_logs

        if args.get("count_last"):
            logs = frappe.get_all(
                "CRM Call Log", fields=["name"], order_by="creation desc", limit=args["count_last"]
            )
            return [d.name for d in logs]

        return []

    async def _process_call_logs_async(
        self, call_log_names: List[str], ref_dt: Optional[str], ref_name: Optional[str], overwrite: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        processed, skipped = [], []

        async def process(cl_name: str):
            result = await self._process_call_log_async(cl_name, ref_dt, ref_name, overwrite)
            if result.get("success"):
                processed.append(result)
            else:
                skipped.append({"call_log": cl_name, "reason": result.get("error")})

        # Run all call logs concurrently
        await asyncio.gather(*(process(name) for name in call_log_names))
        return processed, skipped

    async def _process_call_log_async(
        self, call_log_name: str, forced_ref_dt: Optional[str], forced_ref_name: Optional[str], overwrite: bool = False
    ) -> Dict[str, Any]:
        """Async version to process a single call log and create a note from its transcription."""
        try:
            call_log = frappe.get_doc("CRM Call Log", call_log_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Call Log not found"), "call_log": call_log_name}

        if call_log.status != "Completed":
            return {"success": False, "error": _("Call Log is not Completed"), "call_log": call_log_name}

        existing_note = getattr(call_log, "note", None)
        if existing_note and not overwrite:
            return {"success": False, "error": _("Note already exists. Use overwrite=True to recreate."), "call_log": call_log_name}
        
        if existing_note:
            try:
                frappe.delete_doc("FCRM Note", existing_note)
            except Exception as e:
                return {"success": False, "error": _("Could not remove existing note: {0}").format(str(e)), "call_log": call_log_name}

        recording_url = call_log.get("recording_url")
        if not recording_url:
            return {"success": False, "error": _("No recording URL found"), "call_log": call_log_name}

        ref_dt = forced_ref_dt or call_log.get("reference_doctype")
        ref_name = forced_ref_name or call_log.get("reference_name")

        # Async HTTP call to Deepgram
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", recording_url) as audio_response:
                    audio_response.raise_for_status()
                    dg_response = await client.post(
                        DEEPGRAM_API_URL,
                        headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": AUDIO_CONTENT_TYPE},
                        content=audio_response.aiter_bytes(),
                    )
            dg_response.raise_for_status()
            response_data = dg_response.json()
        except httpx.RequestError as e:
            return {"success": False, "error": _("Failed to process audio: {0}").format(e), "call_log": call_log_name}

        transcription, short_summary = self._extract_summary(response_data)

        # Create note
        note = frappe.new_doc("FCRM Note")
        note.title = _("Note from Call on {0}").format(frappe.utils.format_date(call_log.creation))
        note.content = f"📌 Call Summary for {call_log.caller}\n\n{short_summary}"
        if ref_dt and ref_name:
            note.reference_doctype = ref_dt
            note.reference_docname = ref_name
        note.insert(ignore_permissions=True)

        # Link back
        if hasattr(call_log, "note"):
            call_log.note = note.name
            if ref_dt and ref_name:
                call_log.reference_doctype = ref_dt
                call_log.reference_docname = ref_name
            call_log.save(ignore_permissions=True)

        return {"success": True, "note": note.name, "call_log": call_log_name}

    @staticmethod
    def _extract_summary(response_data: Dict[str, Any]) -> Tuple[str, str]:
        results = response_data.get("results", {})
        channels = results.get("channels", [])
        alternatives = channels[0].get("alternatives", []) if channels else []

        transcription = alternatives[0].get("transcript", "") if alternatives else ""
        summary = alternatives[0].get("summary", {}).get("short") if alternatives else None

        if not transcription:
            transcription = _("No speech detected in the recording.")

        if summary:
            summary_points = re.split(r'\.\s*', summary.strip())
            short_summary = "\n".join(f"- {s.capitalize()}" for s in summary_points if s)
        else:
            short_summary = summarize_transcript(transcription)

        return transcription, short_summary


create_notes_from_call_logs = CreateNotesFromCallLogs()
