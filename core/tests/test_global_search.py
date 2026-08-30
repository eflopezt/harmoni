from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class GlobalSearchProcessShortcutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="rrhh",
            email="rrhh@example.com",
            password="secret",
            is_staff=True,
        )

    def test_process_intent_results_appear_before_record_matches(self):
        self.client.force_login(self.user)

        response = self.client.get("/buscar/", {"q": "planilla"})

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertGreaterEqual(len(results), 4)
        self.assertEqual(
            [item["titulo"] for item in results[:4]],
            ["Workflow mes", "Pre-planilla", "Boletas", "SUNAT y bancos"],
        )
        self.assertEqual(results[0]["url"], reverse("workflow_mes"))
        self.assertEqual(results[1]["url"], reverse("pre_planilla"))
