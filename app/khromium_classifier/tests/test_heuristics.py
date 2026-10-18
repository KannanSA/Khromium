import unittest

from khromium_classifier.heuristics import local_decision

WALL = """
<html style="overflow: hidden">
<body style="overflow: hidden">
<div id="ab-modal" style="position: fixed; z-index: 99999; inset: 0">
Please disable your ad blocker to continue
</div>
</body>
</html>
"""

BAIT = """
<div class="adsbox" style="position:fixed; z-index:2147483647; width:100%; height:100%"></div>
"""

CLEAN = "<html><body><p>Hello world. Nothing to see here.</p></body></html>"

SCRIPT = '<script src="https://cdn.example/fuckadblock.js"></script>'


class HeuristicTests(unittest.TestCase):
    def test_anti_adblock_wall(self):
        decision = local_decision(WALL)
        self.assertTrue(decision["block"])
        self.assertIn("#ab-modal", decision["selectors"])
        self.assertTrue(decision["restore_scroll"])

    def test_obfuscated_ad_container(self):
        decision = local_decision(BAIT)
        self.assertTrue(decision["block"])
        self.assertTrue(any("adsbox" in item for item in decision["selectors"]))

    def test_ordinary_page(self):
        decision = local_decision(CLEAN)
        self.assertFalse(decision["block"])
        self.assertEqual(decision["selectors"], [])
        self.assertFalse(decision["restore_scroll"])

    def test_known_script(self):
        decision = local_decision(SCRIPT)
        self.assertTrue(decision["block"])
        self.assertIn("script", decision["reason"].lower())
