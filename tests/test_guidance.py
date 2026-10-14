"""Tests for guidance.py checklists and FSSAI resource links."""

import unittest

from services import guidance


class TestChecklists(unittest.TestCase):
    def test_packaging_checklist_items(self):
        self.assertGreaterEqual(len(guidance.PACKAGING_CHECKLIST), 6)
        for item in guidance.PACKAGING_CHECKLIST:
            self.assertEqual(len(item), 2)
            title, detail = item
            self.assertTrue(title.strip())
            self.assertTrue(detail.strip())

    def test_process_checklist_items(self):
        self.assertGreaterEqual(len(guidance.PROCESS_CHECKLIST), 6)
        titles = [title for title, _ in guidance.PROCESS_CHECKLIST]
        self.assertIn("Cooling before packing", titles)

    def test_trial_checklist_items(self):
        self.assertGreaterEqual(len(guidance.TRIAL_CHECKLIST), 6)
        titles = [title for title, _ in guidance.TRIAL_CHECKLIST]
        self.assertIn("Change only one thing", titles)

    def test_no_shelf_life_claims_in_packaging_text(self):
        combined = " ".join(detail for _, detail in guidance.PACKAGING_CHECKLIST).lower()
        self.assertNotIn("guaranteed shelf life", combined)


class TestResources(unittest.TestCase):
    def test_all_links_official_fssai_domains(self):
        allowed_prefixes = (
            "https://www.fssai.gov.in/",
            "https://foscos.fssai.gov.in/",
        )
        for title, url, detail in guidance.FSSAI_RESOURCES:
            self.assertTrue(url.startswith(allowed_prefixes), f"Unexpected URL: {url}")
            self.assertTrue(title.strip())
            self.assertTrue(detail.strip())

    def test_contains_licensing_and_home(self):
        urls = [url for _, url, _ in guidance.FSSAI_RESOURCES]
        self.assertIn("https://www.fssai.gov.in/", urls)
        self.assertTrue(any("licensing-registration" in url for url in urls))
        self.assertTrue(any("foscos" in url for url in urls))


class TestMarkdownHelpers(unittest.TestCase):
    def test_checklist_markdown_has_checkboxes(self):
        text = guidance.checklist_as_markdown(guidance.PACKAGING_CHECKLIST)
        self.assertIn("- [ ] **", text)
        self.assertIn("Barrier against moisture", text)

    def test_resources_markdown_has_links(self):
        text = guidance.resources_as_markdown()
        self.assertIn("](https://www.fssai.gov.in/", text)

    def test_disclaimer_present(self):
        self.assertIn("not legal advice", guidance.DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
