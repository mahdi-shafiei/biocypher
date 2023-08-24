from datetime import datetime, timedelta
import os
import json

from hypothesis import given
from hypothesis import strategies as st
import pytest

from biocypher._get import Resource, Downloader


@pytest.fixture
def downloader():
    return Downloader(cache_dir=None)


@given(
    st.builds(
        Resource,
        name=st.text(),
        url_s=st.text(),
        lifetime=st.integers(),
        is_dir=st.booleans(),
    )
)
def test_resource(resource):
    assert isinstance(resource.name, str)
    assert isinstance(resource.url_s, str) or isinstance(resource.url_s, list)
    assert isinstance(resource.lifetime, int)


def test_downloader(downloader):
    assert isinstance(downloader.cache_dir, str)
    assert isinstance(downloader.cache_file, str)


def test_download_file(downloader):
    resource = Resource(
        "test_resource",
        "https://github.com/biocypher/biocypher/raw/main/biocypher/_config/test_config.yaml",
        lifetime=7,
    )
    paths = downloader.download(resource)
    assert len(paths) == 1
    assert os.path.exists(paths[0])

    # test caching
    paths = downloader.download(resource)
    # should not download again
    assert paths[0] is None

    # manipulate cache dict to test expiration (datetime format)
    downloader.cache_dict["test_resource"][
        "date_downloaded"
    ] = datetime.now() - timedelta(days=8)

    paths = downloader.download(resource)
    # should download again
    assert len(paths) == 1
    assert paths[0] is not None


def test_download_lists(downloader):
    resource1 = Resource(
        name="test_resource1",
        url_s=[
            "https://github.com/biocypher/biocypher/raw/main/biocypher/_config/test_config.yaml",
            "https://github.com/biocypher/biocypher/raw/main/biocypher/_config/test_schema_config_disconnected.yaml",
        ],
    )
    resource2 = Resource(
        "test_resource2",
        "https://github.com/biocypher/biocypher/raw/main/test/test_CSVs.zip",
    )
    paths = downloader.download(resource1, resource2)
    assert len(paths) == 4  # 2 files from resource1, 2 files from resource2 zip
    assert os.path.exists(paths[0])
    assert os.path.exists(paths[1])
    assert os.path.exists(paths[2])
    assert os.path.exists(paths[3])
    expected_paths = [
        os.path.realpath(
            os.path.join(
                downloader.cache_dir, "test_resource1", "test_config.yaml"
            )
        ),
        os.path.realpath(
            os.path.join(
                downloader.cache_dir,
                "test_resource1",
                "test_schema_config_disconnected.yaml",
            )
        ),
        os.path.realpath(
            os.path.join(
                downloader.cache_dir,
                "test_resource2",
                "test_CSVs.zip.unzip",
                "file1.csv",
            )
        ),
        os.path.realpath(
            os.path.join(
                downloader.cache_dir,
                "test_resource2",
                "test_CSVs.zip.unzip",
                "file2.csv",
            )
        ),
    ]
    for path in paths:
        assert os.path.realpath(path) in expected_paths
    assert isinstance(
        downloader.cache_dict["test_resource1"]["date_downloaded"], datetime
    )
    assert isinstance(downloader.cache_dict["test_resource1"]["url"], list)
    assert len(downloader.cache_dict["test_resource1"]["url"]) == 2
    assert downloader.cache_dict["test_resource1"]["lifetime"] == 0
    assert isinstance(downloader.cache_dict["test_resource2"]["url"], list)
    assert len(downloader.cache_dict["test_resource2"]["url"]) == 1
    assert downloader.cache_dict["test_resource2"]["lifetime"] == 0


def test_download_directory_and_caching():
    # use temp dir, no cache file present
    downloader = Downloader(cache_dir=None)
    assert os.path.exists(downloader.cache_dir)
    assert os.path.exists(downloader.cache_file)
    resource = Resource(
        "ot_indication",
        "ftp://ftp.ebi.ac.uk/pub/databases/opentargets/platform/23.06/output/etl/parquet/go",
        lifetime=7,
        is_dir=True,
    )
    paths = downloader.download(resource)
    assert len(paths) == 17
    for path in paths:
        assert os.path.exists(path)

    # test caching
    paths = downloader.download(resource)
    # should not download again
    assert len(paths) == 1
    assert paths[0] is None


def test_download_zip_and_expiration():
    # use temp dir, no cache file present
    downloader = Downloader(cache_dir=None)
    assert os.path.exists(downloader.cache_dir)
    assert os.path.exists(downloader.cache_file)
    resource = Resource(
        "test_resource",
        "https://github.com/biocypher/biocypher/raw/main/test/test_CSVs.zip",
        lifetime=7,
    )
    paths = downloader.download(resource)
    with open(downloader.cache_file, "r") as f:
        cache = json.load(f)
    assert (
        cache["test_resource"]["url"][0]
        == "https://github.com/biocypher/biocypher/raw/main/test/test_CSVs.zip"
    )
    assert cache["test_resource"]["lifetime"] == 7
    assert cache["test_resource"]["date_downloaded"]
    for path in paths:
        assert os.path.exists(path)

    # use files downloaded here and manipulate cache file to test expiration
    downloader.cache_dict["test_resource"][
        "date_downloaded"
    ] = datetime.now() - timedelta(days=4)

    paths = downloader.download(resource)
    # should not download again
    assert paths[0] is None

    # minus 8 days from date_downloaded
    downloader.cache_dict["test_resource"][
        "date_downloaded"
    ] = datetime.now() - timedelta(days=8)

    paths = downloader.download(resource)
    # should download again
    assert paths[0] is not None
