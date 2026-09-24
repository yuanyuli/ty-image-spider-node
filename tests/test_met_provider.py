from threading import Barrier

from ty_image_spider.domain import DownloadResult, SearchRequest
from ty_image_spider.providers.collections.met import MetClient, MetProvider
from ty_image_spider.providers.collections.met.normalizer import normalize_artwork
from ty_image_spider.providers.shared.public_json_client import JsonResponse


OBJECT = {
    "objectID": 436535,
    "isPublicDomain": True,
    "title": "Wheat Field with Cypresses",
    "artistDisplayName": "Vincent van Gogh",
    "objectDate": "1889",
    "department": "European Paintings",
    "medium": "Oil on canvas",
    "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/DP-42549-001.jpg",
    "primaryImageSmall": "https://images.metmuseum.org/CRDImages/ep/web-large/DP-42549-001.jpg",
    "objectURL": "https://www.metmuseum.org/art/collection/search/436535",
    "tags": [{"term": "Landscapes"}],
}


class FakeClient:
    def __init__(self):
        self.search_calls = []
        self.object_calls = []
        self.batch_calls = []

    def search(self, query, department_id):
        self.search_calls.append((query, department_id))
        return [436535, 999999]

    def object(self, object_id):
        self.object_calls.append(object_id)
        return (
            OBJECT
            if object_id == 436535
            else {"objectID": object_id, "isPublicDomain": False}
        )

    def objects(self, object_ids):
        self.batch_calls.append(list(object_ids))
        return [self.object(object_id) for object_id in object_ids]


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/met/{item_id}.jpg",))


def make_provider(client=None, downloader=None):
    return MetProvider(client or FakeClient(), downloader or FakeDownloader())


def test_met_search_only_returns_public_domain_images():
    client = FakeClient()
    page = make_provider(client).search(
        SearchRequest("met", "van gogh", {"category": "paintings"})
    )

    assert client.search_calls == [("van gogh", 11)]
    assert client.batch_calls == [[436535, 999999]]
    assert len(page.items) == 1
    assert page.items[0].id == "436535"
    assert page.items[0].author == "Vincent van Gogh"
    assert page.items[0].metadata["rights"] == "Public Domain"


def test_met_normalizer_preserves_public_domain_artwork():
    item = normalize_artwork(OBJECT)

    assert item is not None
    assert item.id == "436535"
    assert item.author == "Vincent van Gogh"
    assert item.metadata["rights"] == "Public Domain"
    assert item.metadata["original_url"].endswith("/DP-42549-001.jpg")


def test_met_detail_and_download_reverify_public_domain_object(tmp_path):
    downloader = FakeDownloader()
    provider = make_provider(downloader=downloader)
    item = provider.search(SearchRequest("met")).items[0]

    detail = provider.detail(item)
    assert detail.images == (
        "https://images.metmuseum.org/CRDImages/ep/original/DP-42549-001.jpg",
    )
    provider.download(item, tmp_path)
    assert downloader.calls[0][0] == detail.images[0]


def test_met_descriptor_uses_collection_group():
    descriptor = make_provider().descriptor()
    assert descriptor.presentation.group_id == "collections"
    assert descriptor.capabilities.cache is True


def test_met_blank_search_uses_browsable_default_query():
    client = FakeClient()

    make_provider(client).search(SearchRequest("met", "", {"category": "all"}))

    assert client.search_calls == [("masterpiece", None)]


def test_met_client_fetches_object_batch_concurrently():
    barrier = Barrier(4)

    class Client:
        def get(self, path, params):
            barrier.wait(timeout=1)
            object_id = int(path.rsplit("/", 1)[1])
            return JsonResponse({"objectID": object_id})

    rows = MetClient(Client()).objects([4, 3, 2, 1])
    assert [row["objectID"] for row in rows] == [4, 3, 2, 1]
