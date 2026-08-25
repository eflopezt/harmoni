from django.test import TestCase
from django.urls import reverse


class PublicLandingTests(TestCase):
    def setUp(self):
        self.response = self.client.get('/', HTTP_HOST='harmoni.pe')

    def test_public_landing_renders_hallmark_flow(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertContains(self.response, '<h1 id="hero-title">Harmoni</h1>', html=True)
        self.assertContains(self.response, '0.0 · PREPARA')
        self.assertContains(self.response, '3.0 · DECIDE')
        self.assertContains(self.response, 'images/brand/png/harmoni-mark-512.png')
        self.assertNotContains(self.response, 'img/landing-hallmark/')

    def test_public_landing_keeps_conversion_and_login(self):
        self.assertContains(self.response, reverse('login'))
        self.assertContains(self.response, '51977538028')
        self.assertContains(self.response, 'S/149')
        self.assertContains(self.response, 'S/349')

    def test_public_landing_keeps_seo_contract(self):
        self.assertContains(self.response, 'https://harmoni.pe/')
        self.assertContains(self.response, 'SoftwareApplication')
        self.assertContains(self.response, 'index,follow,max-image-preview:large')
