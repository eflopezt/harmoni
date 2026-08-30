from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.process_map import (
    build_process_bridge,
    current_stage_for_path,
    get_process_stages,
)


class ProcessMapTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_all_process_links_resolve_without_hash_or_legacy_tareo(self):
        stages = get_process_stages()

        self.assertEqual(len(stages), 6)
        for stage in stages:
            self.assertTrue(stage["url"].startswith("/"))
            self.assertNotIn("#", stage["url"])
            self.assertNotIn("/tareo/", stage["url"])
            self.assertGreaterEqual(len(stage["actions"]), 3)
            self.assertGreaterEqual(len(stage["peru_focus"]), 3)
            for action in stage["actions"]:
                self.assertTrue(action["url"].startswith("/"))
                self.assertNotIn("#", action["url"])
                self.assertNotIn("/tareo/", action["url"])
            for item in stage["peru_focus"]:
                self.assertTrue(item["url"].startswith("/"))
                self.assertNotIn("#", item["url"])
                self.assertNotIn("/tareo/", item["url"])

    def test_current_stage_uses_the_most_specific_process_prefix(self):
        self.assertEqual(current_stage_for_path("/asistencia/")["id"], "operacion")
        self.assertEqual(current_stage_for_path("/nominas/workflow-mes/")["id"], "nomina")
        self.assertEqual(current_stage_for_path("/documentos/laborales/")["id"], "comunicacion")
        self.assertEqual(current_stage_for_path("/documentos/boletas/")["id"], "nomina")
        self.assertEqual(current_stage_for_path("/documentos/")["id"], "ingreso")

    def test_bridge_is_hidden_outside_admin_processes(self):
        request = self.factory.get(reverse("portal_home"))
        bridge = build_process_bridge(request, puede_ver_admin=True)

        self.assertFalse(bridge["show"])

    def test_bridge_marks_current_process_and_next_step(self):
        request = self.factory.get(reverse("asistencia_dashboard"))
        bridge = build_process_bridge(request, puede_ver_admin=True)

        self.assertTrue(bridge["show"])
        self.assertEqual(bridge["current"]["id"], "operacion")
        self.assertEqual(bridge["next_stage"]["id"], "nomina")
        self.assertEqual(
            [stage["id"] for stage in bridge["stages"] if stage["is_current"]],
            ["operacion"],
        )
        self.assertGreaterEqual(len(bridge["actions"]), 3)
        self.assertGreaterEqual(len(bridge["peru_focus"]), 3)

    def test_bridge_is_hidden_when_admin_permission_is_false(self):
        request = self.factory.get(reverse("asistencia_dashboard"))
        bridge = build_process_bridge(request, puede_ver_admin=False)

        self.assertFalse(bridge["show"])
