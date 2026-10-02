from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.views import taobao_parser_proxy


class TaobaoParserProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff = SimpleNamespace(is_staff=True, is_active=True, is_authenticated=True)

    @override_settings(TAOBAO_PARSER_URL="http://parser:18765")
    @patch("core.views.requests.request")
    def test_root_page_and_assets_use_subdomain_root_paths(self, request_upstream):
        request_upstream.return_value = SimpleNamespace(
            content=b'<script src="/assets/app.js"></script><link href="/static/app.css"><a href="/api/browser/">API</a>',
            encoding="utf-8",
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        request = self.factory.get("/taobao/")
        request.user = self.staff

        response = taobao_parser_proxy(request, path="")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/assets/app.js", response.content)
        self.assertIn(b"/taobao-parser-static/app.css", response.content)
        self.assertIn(b"/api/browser/", response.content)
        request_upstream.assert_called_once()
        self.assertEqual(request_upstream.call_args.args[:2], ("GET", "http://parser:18765/"))

    def test_non_staff_user_is_rejected(self):
        request = self.factory.get("/taobao/")
        request.user = SimpleNamespace(is_staff=False, is_active=True, is_authenticated=True)

        response = taobao_parser_proxy(request, path="")

        self.assertEqual(response.status_code, 302)