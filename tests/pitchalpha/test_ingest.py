import httpx

from pitchalpha.api import ApiFootballClient
from pitchalpha.ingest import EPLIngestor
from pitchalpha.raw_store import RawStore


def test_injuries_endpoint_does_not_send_page(tmp_path):
    def handler(request):
        assert "page" not in request.url.params
        assert request.url.params["league"] == "39"
        return httpx.Response(200, json={"errors": [], "response": []})

    with ApiFootballClient("secret", RawStore(tmp_path), min_request_interval=0, transport=httpx.MockTransport(handler)) as client:
        payload, _ = EPLIngestor(client).injuries(2025)
    assert payload["response"] == []
