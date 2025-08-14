# -*- coding: utf-8 -*-
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Tool to create a Note from a Call Log.
"""

import frappe
from frappe import _
from typing import Dict, Any
from frappe_assistant_core.frappe_assistant_core.core.base_tool import BaseTool


class CreateNoteFromCall(BaseTool):
    """
    Tool for creating a Note from a Call Log and linking it to a Lead, Deal, or Customer.
    """

    def __init__(self):
        super().__init__()
        self.name = "create_note_from_call"
        self.description = _("Create a note based on a call record for a Lead, Deal, or Customer.")
        self.requires_permission = "Note"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "call_log": {
                    "type": "string",
                    "description": _("The name of the Call Log to summarize.")
                },
                "reference_doctype": {
                    "type": "string",
                    "description": _("The doctype to link the note to (Lead, Deal, or Customer).")
                },
                "reference_name": {
                    "type": "string",
                    "description": _("The name of the document to link the note to.")
                }
            },
            "required": ["call_log", "reference_doctype", "reference_name"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a Note from a Call Log.
        """
        call_log_name = arguments.get("call_log")
        reference_doctype = arguments.get("reference_doctype")
        reference_name = arguments.get("reference_name")

        # Import security validation
        from frappe_assistant_core.frappe_assistant_core.core.security_config import validate_document_access, audit_log_tool_access

        # Validate document access with comprehensive permission checking
        validation_result = validate_document_access(
            user=frappe.session.user,
            doctype='Note',
            name=None,  # No specific document for create operation
            perm_type="create"
        )
        
        if not validation_result["success"]:
            audit_log_tool_access(frappe.session.user, self.name, arguments, validation_result)
            return validation_result

        try:
            # Get the call log
            call_log = frappe.get_doc("Call Log", call_log_name)

            # Create the note content
            content = _("Call Summary: {0}").format(call_log.subject)
            if call_log.get("recording_url"):
                content += _("\nRecording URL: {0}").format(call_log.recording_url)

            # Create the note
            note = frappe.new_doc("Note")
            note.title = _("Note from Call on {0}").format(frappe.utils.format_date(call_log.creation))
            note.content = content
            note.add_link(reference_doctype, reference_name)
            note.insert(ignore_permissions=True) # Note is created with admin rights

            result = {
                "success": True,
                "note_name": note.name,
                "message": _("Note '{0}' created successfully.").format(note.name)
            }
            audit_log_tool_access(frappe.session.user, self.name, arguments, result)
            return result

        except frappe.DoesNotExistError:
            result = {
                "success": False,
                "error": _("Call Log '{0}' not found.").format(call_log_name)
            }
            audit_log_tool_access(frappe.session.user, self.name, arguments, result)
            return result
        except Exception as e:
            frappe.log_error(
                title=_("Create Note From Call Error"),
                message=str(e)
            )
            result = {
                "success": False,
                "error": str(e)
            }
            audit_log_tool_access(frappe.session.user, self.name, arguments, result)
            return result

create_note_from_call = CreateNoteFromCall
