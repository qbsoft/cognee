import os
import pytest
import cognee
from cognee.infrastructure.files.utils.get_data_file_path import get_data_file_path
from cognee.infrastructure.loaders.LoaderEngine import LoaderEngine
from cognee.infrastructure.loaders.external.beautiful_soup_loader import BeautifulSoupLoader
from cognee.tasks.ingestion import save_data_item_to_storage
from pathlib import Path


@pytest.mark.asyncio
async def test_url_saves_as_html_file():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        file = Path(file_path)
        assert file.exists()
        assert file.stat().st_size > 0
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_saved_content_is_valid():
    """Test that saved content is valid based on the fetching method used.

    - With TAVILY_API_KEY: Tavily returns plain text, verify text content
    - Without TAVILY_API_KEY: Default crawler returns HTML, verify HTML structure
    """
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        content = Path(file_path).read_text(encoding="utf-8")

        assert len(content) > 0, "File should not be empty"

        if os.getenv("TAVILY_API_KEY"):
            # Tavily returns plain text, verify it has meaningful content
            assert len(content) > 100, "Tavily text content should have meaningful length"
            # Tavily extracts text, so it should contain readable content
            assert any(char.isalpha() for char in content), "Content should contain text"
        else:
            # Default crawler returns HTML, verify HTML structure
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                pytest.fail("Test case requires bs4 installed")

            soup = BeautifulSoup(content, "html.parser")
            assert soup.find() is not None, "File should contain parseable HTML"

            has_html_elements = any(
                [
                    soup.find("html"),
                    soup.find("head"),
                    soup.find("body"),
                    soup.find("div"),
                    soup.find("p"),
                ]
            )
            assert has_html_elements, "File should contain common HTML elements"
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_add_url():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    await cognee.add("https://www.sina.com.cn/")


skip_in_ci = pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Skipping in Github for now - before we get TAVILY_API_KEY",
)


@skip_in_ci
@pytest.mark.asyncio
async def test_add_url_with_tavily():
    assert os.getenv("TAVILY_API_KEY") is not None
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    await cognee.add("https://www.sina.com.cn/")


@pytest.mark.asyncio
async def test_add_url_without_incremental_loading():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        await cognee.add(
            "https://www.sina.com.cn/",
            incremental_loading=False,
        )
    except Exception as e:
        pytest.fail(f"Failed to add url: {e}")


@pytest.mark.asyncio
async def test_add_url_with_incremental_loading():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        await cognee.add(
            "https://www.sina.com.cn/",
            incremental_loading=True,
        )
    except Exception as e:
        pytest.fail(f"Failed to add url: {e}")


@pytest.mark.asyncio
async def test_add_url_can_define_preferred_loader_as_list_of_str():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    await cognee.add(
        "https://www.sina.com.cn/",
        preferred_loaders=["beautiful_soup_loader"],
    )


@pytest.mark.asyncio
async def test_add_url_with_extraction_rules():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    extraction_rules = {
        "title": {"selector": "title"},
        "headings": {"selector": "h1, h2, h3", "all": True},
        "links": {"selector": "a", "attr": "href", "all": True},
        "paragraphs": {"selector": "p", "all": True},
    }

    try:
        await cognee.add(
            "https://www.sina.com.cn/",
            preferred_loaders={"beautiful_soup_loader": {"extraction_rules": extraction_rules}},
        )
    except Exception as e:
        pytest.fail(f"Failed to add url: {e}")


@pytest.mark.asyncio
async def test_loader_is_none_by_default():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    extraction_rules = {
        "title": {"selector": "title"},
        "headings": {"selector": "h1, h2, h3", "all": True},
        "links": {"selector": "a", "attr": "href", "all": True},
        "paragraphs": {"selector": "p", "all": True},
    }

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        file = Path(file_path)
        assert file.exists()
        assert file.stat().st_size > 0

        loader_engine = LoaderEngine()
        preferred_loaders = {"beautiful_soup_loader": {"extraction_rules": extraction_rules}}
        loader = loader_engine.get_loader(
            file_path,
            preferred_loaders=preferred_loaders,
        )

        assert loader is None
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_beautiful_soup_loader_is_selected_loader_if_preferred_loader_provided():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    extraction_rules = {
        "title": {"selector": "title"},
        "headings": {"selector": "h1, h2, h3", "all": True},
        "links": {"selector": "a", "attr": "href", "all": True},
        "paragraphs": {"selector": "p", "all": True},
    }

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        file = Path(file_path)
        assert file.exists()
        assert file.stat().st_size > 0

        loader_engine = LoaderEngine()
        bs_loader = BeautifulSoupLoader()
        loader_engine.register_loader(bs_loader)
        preferred_loaders = {"beautiful_soup_loader": {"extraction_rules": extraction_rules}}
        loader = loader_engine.get_loader(
            file_path,
            preferred_loaders=preferred_loaders,
        )

        assert loader == bs_loader
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_beautiful_soup_loader_works_with_and_without_arguments():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        file = Path(file_path)
        assert file.exists()
        assert file.stat().st_size > 0

        loader_engine = LoaderEngine()
        bs_loader = BeautifulSoupLoader()
        loader_engine.register_loader(bs_loader)
        preferred_loaders = {"beautiful_soup_loader": {}}
        await loader_engine.load_file(
            file_path,
            preferred_loaders=preferred_loaders,
        )
        extraction_rules = {
            "title": {"selector": "title"},
            "headings": {"selector": "h1, h2, h3", "all": True},
            "links": {"selector": "a", "attr": "href", "all": True},
            "paragraphs": {"selector": "p", "all": True},
        }
        preferred_loaders = {"beautiful_soup_loader": {"extraction_rules": extraction_rules}}
        await loader_engine.load_file(
            file_path,
            preferred_loaders=preferred_loaders,
        )
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_beautiful_soup_loader_successfully_loads_file_if_required_args_present():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        file = Path(file_path)
        assert file.exists()
        assert file.stat().st_size > 0

        loader_engine = LoaderEngine()
        bs_loader = BeautifulSoupLoader()
        loader_engine.register_loader(bs_loader)
        extraction_rules = {
            "title": {"selector": "title"},
            "headings": {"selector": "h1, h2, h3", "all": True},
            "links": {"selector": "a", "attr": "href", "all": True},
            "paragraphs": {"selector": "p", "all": True},
        }
        preferred_loaders = {"beautiful_soup_loader": {"extraction_rules": extraction_rules}}
        await loader_engine.load_file(
            file_path,
            preferred_loaders=preferred_loaders,
        )
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")


@pytest.mark.asyncio
async def test_beautiful_soup_loads_file_successfully():
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    extraction_rules = {
        "title": {"selector": "title"},
        "headings": {"selector": "h1, h2, h3", "all": True},
        "links": {"selector": "a", "attr": "href", "all": True},
        "paragraphs": {"selector": "p", "all": True},
    }

    try:
        original_file_path = await save_data_item_to_storage("https://www.sina.com.cn/")
        file_path = get_data_file_path(original_file_path)
        assert file_path.endswith(".html")
        original_file = Path(file_path)
        assert original_file.exists()
        assert original_file.stat().st_size > 0

        loader_engine = LoaderEngine()
        bs_loader = BeautifulSoupLoader()
        loader_engine.register_loader(bs_loader)
        preferred_loaders = {"beautiful_soup_loader": {"extraction_rules": extraction_rules}}
        loader = loader_engine.get_loader(
            file_path,
            preferred_loaders=preferred_loaders,
        )

        assert loader == bs_loader

        cognee_loaded_txt_path = await loader_engine.load_file(
            file_path=file_path, preferred_loaders=preferred_loaders
        )

        cognee_loaded_txt_path = get_data_file_path(cognee_loaded_txt_path)

        assert cognee_loaded_txt_path.endswith(".txt")

        extracted_file = Path(cognee_loaded_txt_path)

        assert extracted_file.exists()
        assert extracted_file.stat().st_size > 0

        original_basename = original_file.stem
        extracted_basename = extracted_file.stem
        assert original_basename == extracted_basename, (
            f"Expected same base name: {original_basename} vs {extracted_basename}"
        )
    except Exception as e:
        pytest.fail(f"Failed to save data item to storage: {e}")
