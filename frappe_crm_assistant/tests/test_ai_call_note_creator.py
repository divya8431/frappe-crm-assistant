import unittest
from frappe_crm_assistant.frappe_crm_assistant.tool.ai_call_note_creator import AICallNoteCreator

class TestAICallNoteCreator(unittest.TestCase):
    """Test the AI Call Note Creator tool."""

    def test_tool_instantiation(self):
        """Test that the tool can be instantiated without errors."""
        try:
            tool = AICallNoteCreator(user_prompt="test prompt")
            self.assertIsInstance(tool, AICallNoteCreator)
            self.assertEqual(tool.name, "ai_call_note_creator")
            self.assertEqual(tool.source_app, "frappe_crm_assistant")
        except Exception as e:
            self.fail(f"Tool instantiation failed with an error: {e}")

if __name__ == "__main__":
    unittest.main()
