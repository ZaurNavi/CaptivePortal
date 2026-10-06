import app.web.web as web


def test_explicit_factory_injection_never_reads_settings(monkeypatch):
    def forbidden():
        raise AssertionError("get_settings called despite injection")
    monkeypatch.setattr(web, "get_settings", forbidden)
    settings = {"portal_counter_enabled": False, "public_traffic_enabled": False,
                "auth_telemetry_enabled": False, "capport_enabled": False,
                "secret_key": "synthetic-injection-proof"}
    app = web.create_app(settings=settings, controller=object(), portal_counter_service=None,
                         public_traffic_service=None, public_traffic_worker=None,
                         portal_evidence_sink=None, client_hints_probe=None)
    assert app is not None
