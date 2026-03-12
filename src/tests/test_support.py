"""
Tests fuer das Enterprise Support-System.

Prueft API-Client, Payload-Erstellung, System-Info-Sammlung
und die korrekte Verdrahtung der Komponenten.

Ausfuehrung:
    python -m pytest src/tests/test_support.py -v
"""

import json
import os
import platform
from unittest.mock import MagicMock, patch

import pytest


class TestSupportSystemInfo:
    """Tests fuer die automatische System-Info-Sammlung."""

    def test_collect_system_info_basic(self):
        from api.support import collect_system_info

        info = collect_system_info()

        assert "os" in info
        assert "os_version" in info
        assert "architecture" in info
        assert "python_version" in info
        assert info["os"] == platform.system()

    def test_collect_system_info_without_psutil(self):
        from api.support import collect_system_info

        with patch.dict("sys.modules", {"psutil": None}):
            info = collect_system_info()

        assert "os" in info
        assert info["cpu_count"] is not None or info.get("cpu_count") == os.cpu_count()

    def test_get_client_version(self):
        from api.support import get_client_version

        version = get_client_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_log_file_paths_returns_dict(self):
        from api.support import get_log_file_paths

        paths = get_log_file_paths()
        assert isinstance(paths, dict)
        for key in paths:
            assert key in ("log_main", "log_updater", "log_performance")
            assert os.path.isfile(paths[key])


class TestFeedbackPayload:
    """Tests fuer das Payload-Datenmodell."""

    def test_feedback_payload_defaults(self):
        from ui.feedback_overlay import FeedbackPayload

        p = FeedbackPayload()
        assert p.feedback_type == ""
        assert p.priority == "low"
        assert p.subject == ""
        assert p.content == ""
        assert p.reproduction_steps == ""
        assert p.include_logs is False
        assert p.screenshot_path is None

    def test_feedback_payload_full(self):
        from ui.feedback_overlay import FeedbackPayload

        p = FeedbackPayload(
            feedback_type="bug",
            priority="high",
            subject="Login bricht ab",
            content="Nach dem Klick passiert nichts.",
            reproduction_steps="1. Oeffnen\n2. Klicken",
            include_logs=True,
            screenshot_path="/tmp/screenshot.png",
        )
        assert p.feedback_type == "bug"
        assert p.priority == "high"
        assert p.include_logs is True


class TestSupportAPIClient:
    """Tests fuer die SupportAPI-Klasse (mit gemocktem HTTP-Client)."""

    def _make_api(self):
        from api.support import SupportAPI

        mock_client = MagicMock()
        mock_client.upload_multipart.return_value = {
            "success": True,
            "data": {"id": 42, "feedback_type": "feedback"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": [],
            "pagination": {"page": 1, "per_page": 50, "total": 0, "total_pages": 0},
        }
        mock_client.patch.return_value = {
            "success": True,
            "data": {"id": 1, "changes": {}},
        }
        mock_client.delete.return_value = {"success": True}
        mock_client.get_binary.return_value = b"\x89PNG"
        return SupportAPI(mock_client), mock_client

    def test_submit_feedback_calls_upload_multipart(self):
        api, mock = self._make_api()

        result = api.submit_feedback(
            feedback_type="feedback",
            priority="low",
            content="Test",
        )

        assert result["success"] is True
        mock.upload_multipart.assert_called_once()
        call_args = mock.upload_multipart.call_args
        fields = call_args.kwargs.get("fields") or call_args[1].get("fields")
        assert fields["feedback_type"] == "feedback"
        assert fields["content"] == "Test"

    def test_submit_bug_with_logs(self):
        api, mock = self._make_api()

        api.submit_feedback(
            feedback_type="bug",
            priority="high",
            content="Absturz",
            reproduction_steps="1. Klick\n2. Boom",
            include_logs=True,
        )

        call_args = mock.upload_multipart.call_args
        fields = call_args.kwargs.get("fields") or call_args[1].get("fields")
        assert fields["include_logs"] == "1"
        assert fields["reproduction_steps"] == "1. Klick\n2. Boom"

    def test_get_all_feedback(self):
        api, mock = self._make_api()

        result = api.get_all_feedback(status="open", page=1)

        mock.get.assert_called_once()
        assert "/support/feedback" in str(mock.get.call_args)

    def test_update_feedback(self):
        api, mock = self._make_api()

        api.update_feedback(42, status="review")

        mock.patch.assert_called_once()
        call_args = mock.patch.call_args
        assert "42" in str(call_args)

    def test_get_screenshot(self):
        api, mock = self._make_api()

        data = api.get_screenshot(42)

        assert data == b"\x89PNG"
        mock.get_binary.assert_called_once()

    def test_delete_feedback(self):
        api, mock = self._make_api()

        result = api.delete_feedback(42)

        assert result is True
        mock.delete.assert_called_once()


class TestI18nTexts:
    """Prueft dass alle erwarteten i18n-Konstanten vorhanden sind."""

    def test_feedback_texts_exist(self):
        from i18n import de as texts

        required = [
            "FEEDBACK_BTN_TEXT", "FEEDBACK_BTN_TOOLTIP",
            "FEEDBACK_TITLE", "FEEDBACK_SUBTITLE",
            "FEEDBACK_TYPE_FEEDBACK", "FEEDBACK_TYPE_FEATURE", "FEEDBACK_TYPE_PROBLEM",
            "FEEDBACK_PRIORITY_LOW", "FEEDBACK_PRIORITY_MEDIUM", "FEEDBACK_PRIORITY_HIGH",
            "FEEDBACK_SUBJECT_LABEL", "FEEDBACK_CONTENT_LABEL",
            "FEEDBACK_REPRO_LABEL", "FEEDBACK_LOGS_CHECKBOX",
            "FEEDBACK_SCREENSHOT_TITLE", "FEEDBACK_SCREENSHOT_DROP",
            "FEEDBACK_CANCEL", "FEEDBACK_SUBMIT",
            "FEEDBACK_SUCCESS", "FEEDBACK_ERROR",
        ]

        for name in required:
            assert hasattr(texts, name), f"Missing i18n constant: {name}"
            val = getattr(texts, name)
            assert isinstance(val, str) and len(val) > 0, f"Empty i18n constant: {name}"

    def test_admin_support_texts_exist(self):
        from i18n import de as texts

        required = [
            "ADMIN_SUPPORT_SECTION", "ADMIN_SUPPORT_NAV", "ADMIN_SUPPORT_TITLE",
            "ADMIN_SUPPORT_STATUS_OPEN", "ADMIN_SUPPORT_STATUS_REVIEW", "ADMIN_SUPPORT_STATUS_CLOSED",
            "ADMIN_SUPPORT_PRIORITY_LOW", "ADMIN_SUPPORT_PRIORITY_MEDIUM", "ADMIN_SUPPORT_PRIORITY_HIGH",
            "ADMIN_SUPPORT_COL_STATUS", "ADMIN_SUPPORT_COL_TYPE", "ADMIN_SUPPORT_COL_SUBJECT",
            "ADMIN_SUPPORT_DETAIL_TITLE", "ADMIN_SUPPORT_DETAIL_DESCRIPTION",
            "ADMIN_SUPPORT_DETAIL_ADMIN_NOTES", "ADMIN_SUPPORT_DETAIL_SAVE_NOTE",
            "ADMIN_SUPPORT_TYPE_FEEDBACK", "ADMIN_SUPPORT_TYPE_FEATURE", "ADMIN_SUPPORT_TYPE_BUG",
        ]

        for name in required:
            assert hasattr(texts, name), f"Missing admin i18n constant: {name}"
