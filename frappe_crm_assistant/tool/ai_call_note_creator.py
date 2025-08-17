# -*- coding: utf-8 -*-
# Frappe Assistant Core - AI Assistant integration for Frappe Framework (Deepgram version)
# License: GNU Affero GPL v3

import frappe
import requests
from frappe import _
from typing import Dict, Any, List, Optional
from frappe_assistant_core.core.base_tool import BaseTool

DEEPGRAM_API_KEY: Optional[str] = frappe.conf.get("deepgram_api_key")
DEEPGRAM_API_URL: str = "https://api.deepgram.com/v1/listen"
AUDIO_CONTENT_TYPE: str = "audio/mp3"

class CreateNotesFromCallLogs(BaseTool):
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
                    "description": _("List of Call Log names to process.")
                },
                "count_last": {
                    "type": "integer",
                    "description": _("If set, take the last N completed call logs instead of specifying call_logs.")
                },
                "reference_doctype": {
                    "type": "string",
                    "description": _("Optional: The doctype to link notes to (CRM Lead, Deal, or Customer).")
                },
                "reference_name": {
                    "type": "string",
                    "description": _("Optional: The document name to link notes to.")
                }
            },
            "oneOf": [
                {"required": ["call_logs"]},
                {"required": ["count_last"]}
            ]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from frappe_assistant_core.core.security_config import validate_document_access, audit_log_tool_access

        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype="FCRM Note",
            name=None,
            perm_type="create"
        )
        if not validation_result["success"]:
            audit_log_tool_access(frappe.session.user, self.name, arguments, validation_result)
            return validation_result

        call_log_names = self._resolve_call_logs(arguments)
        processed = []
        skipped = []
        for cl_name in call_log_names:
            res = self._process_call_log(
                cl_name,
                arguments.get("reference_doctype"),
                arguments.get("reference_name")
            )
            if res.get("success"):
                processed.append(res)
            else:
                skipped.append({"call_log": cl_name, "reason": res.get("error")})

        summary = {"success": True, "processed": processed, "skipped": skipped}
        audit_log_tool_access(frappe.session.user, self.name, arguments, summary)
        return summary

    def _resolve_call_logs(self, args: Dict[str, Any]) -> List[str]:
        call_logs = args.get("call_logs") or args.get("call_log")
        if call_logs:
            if isinstance(call_logs, str):
                return [call_logs]
            return call_logs

        if args.get("count_last"):
            logs = frappe.get_all(
                "CRM Call Log",
                fields=["name"],
                order_by="creation desc",
                limit=args["count_last"]
            )
            return [d.name for d in logs]

        return []

    def _process_call_log(self, call_log_name: str,
                          forced_ref_dt: Optional[str],
                          forced_ref_name: Optional[str]) -> Dict[str, Any]:
        try:
            call_log = frappe.get_doc("CRM Call Log", call_log_name)
        except frappe.DoesNotExistError:
            return {"success": False, "error": _("Call Log not found"), "call_log": call_log_name}

        if call_log.status != "Completed":
            return {"success": False, "error": _("Call Log is not Completed"), "call_log": call_log_name}

        recording_url = call_log.get("recording_url")
        if not recording_url:
            return {"success": False, "error": _("No recording URL found"), "call_log": call_log_name}

        ref_dt = forced_ref_dt or call_log.get("reference_doctype")
        ref_name = forced_ref_name or call_log.get("reference_name")

        # download audio
        audio_data = requests.get(recording_url, stream=True).content

        # Deepgram transcription
        dg_response = requests.post(
            DEEPGRAM_API_URL,
            headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": AUDIO_CONTENT_TYPE},
            data=audio_data
        )
        dg_response.raise_for_status()
        transcription = dg_response.json().get("results", {}).get("channels", [{}])[0] \
            .get("alternatives", [{}])[0].get("transcript", "")

        if not transcription:
            transcription = _("No speech detected in the recording.")

        # create note
        note = frappe.new_doc("FCRM Note")
        note.title = _("Note from Call on {0}").format(frappe.utils.format_date(call_log.creation))
        note.content = f"Call Summary for {call_log.caller}\n\n{transcription}"
        if ref_dt and ref_name:
            note.reference_doctype = ref_dt
            note.reference_docname = ref_name
        note.insert(ignore_permissions=True)

        # link back
        if hasattr(call_log, "note"):
            call_log.note = note.name
            call_log.save(ignore_permissions=True)

        return {"success": True, "note": note.name, "call_log": call_log_name}

create_notes_from_call_logs = CreateNotesFromCallLogs()
