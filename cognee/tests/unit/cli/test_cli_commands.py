"""
Unit tests for CLI commands (T801-T805).

Tests cover all five CLI commands: add, cognify, search, config, and delete.
All tests use mocks to avoid real DB/LLM/network connections.

The CLI uses argparse for command parsing. Commands are implemented as classes
following the SupportsCliCommand protocol. Each command class has:
  - command_string: the subcommand name
  - configure_parser(): sets up argparse arguments
  - execute(): runs the command logic (typically calling async cognee.* functions)
"""

import argparse
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from cognee.cli._cognee import _create_parser, _discover_commands, main
from cognee.cli.exceptions import CliCommandException, CliCommandInnerException


# ============================================================================
# Helper fixtures
# ============================================================================


@pytest.fixture
def parser_and_commands():
    """Create the CLI parser and return (parser, installed_commands)."""
    with patch("cognee.cli._cognee.fmt"):
        parser, commands = _create_parser()
    return parser, commands


@pytest.fixture
def parse_args(parser_and_commands):
    """Return a helper that parses CLI argument strings."""
    parser, commands = parser_and_commands

    def _parse(argv: list[str]):
        return parser.parse_args(argv), commands

    return _parse


# ============================================================================
# T801: Test `cognee add` command
# ============================================================================


class TestAddCommand:
    """T801: Tests for the 'add' CLI command."""

    def test_add_command_is_discovered(self):
        """AddCommand is found by the discovery mechanism."""
        with patch("cognee.cli._cognee.fmt"):
            commands = _discover_commands()
        class_names = [cls.__name__ for cls in commands]
        assert "AddCommand" in class_names

    def test_add_command_registered_in_parser(self, parser_and_commands):
        """The 'add' subcommand is registered in the argparse parser."""
        parser, commands = parser_and_commands
        assert "add" in commands
        assert commands["add"].command_string == "add"

    def test_add_command_has_help_string(self, parser_and_commands):
        """The add command has a non-empty help string."""
        _, commands = parser_and_commands
        assert commands["add"].help_string
        assert len(commands["add"].help_string) > 0

    def test_add_command_has_description(self, parser_and_commands):
        """The add command has a detailed description."""
        _, commands = parser_and_commands
        assert commands["add"].description
        assert "knowledge graph" in commands["add"].description.lower()

    def test_add_accepts_single_text_input(self, parse_args):
        """Add command accepts a single text argument."""
        args, _ = parse_args(["add", "hello world"])
        assert args.command == "add"
        assert args.data == ["hello world"]

    def test_add_accepts_multiple_text_inputs(self, parse_args):
        """Add command accepts multiple text arguments via nargs='+'."""
        args, _ = parse_args(["add", "text1", "text2", "text3"])
        assert args.data == ["text1", "text2", "text3"]

    def test_add_accepts_file_path(self, parse_args):
        """Add command accepts file path-like strings."""
        args, _ = parse_args(["add", "/path/to/document.pdf"])
        assert args.data == ["/path/to/document.pdf"]

    def test_add_default_dataset_name(self, parse_args):
        """Add command defaults dataset name to 'main_dataset'."""
        args, _ = parse_args(["add", "some text"])
        assert args.dataset_name == "main_dataset"

    def test_add_custom_dataset_name_long_flag(self, parse_args):
        """Add command accepts --dataset-name flag."""
        args, _ = parse_args(["add", "--dataset-name", "my_ds", "data"])
        assert args.dataset_name == "my_ds"

    def test_add_custom_dataset_name_short_flag(self, parse_args):
        """Add command accepts -d shorthand for dataset name."""
        args, _ = parse_args(["add", "-d", "custom_ds", "data"])
        assert args.dataset_name == "custom_ds"

    def test_add_requires_data_argument(self, parser_and_commands):
        """Add command requires at least one data argument."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit):
            parser.parse_args(["add"])

    @patch("cognee.cli.commands.add_command.asyncio.run")
    @patch("cognee.cli.commands.add_command.fmt")
    def test_add_execute_calls_cognee_add_single(self, mock_fmt, mock_run):
        """Execute with single data item passes string (not list) to cognee.add."""
        from cognee.cli.commands.add_command import AddCommand

        cmd = AddCommand()
        args = argparse.Namespace(data=["hello world"], dataset_name="main_dataset")

        # mock asyncio.run to capture the coroutine
        mock_run.return_value = None

        cmd.execute(args)

        # asyncio.run should have been called once
        mock_run.assert_called_once()
        mock_fmt.echo.assert_any_call("Adding 1 item(s) to dataset 'main_dataset'...")

    @patch("cognee.cli.commands.add_command.asyncio.run")
    @patch("cognee.cli.commands.add_command.fmt")
    def test_add_execute_calls_cognee_add_multiple(self, mock_fmt, mock_run):
        """Execute with multiple data items passes list to cognee.add."""
        from cognee.cli.commands.add_command import AddCommand

        cmd = AddCommand()
        args = argparse.Namespace(data=["text1", "text2"], dataset_name="test_ds")

        mock_run.return_value = None
        cmd.execute(args)

        mock_run.assert_called_once()
        mock_fmt.echo.assert_any_call("Adding 2 item(s) to dataset 'test_ds'...")

    @patch("cognee.cli.commands.add_command.asyncio.run")
    @patch("cognee.cli.commands.add_command.fmt")
    def test_add_execute_raises_cli_exception_on_failure(self, mock_fmt, mock_run):
        """Execute raises CliCommandException when asyncio.run fails."""
        from cognee.cli.commands.add_command import AddCommand

        cmd = AddCommand()
        args = argparse.Namespace(data=["test"], dataset_name="ds")

        mock_run.side_effect = CliCommandInnerException("mock failure")

        with pytest.raises(CliCommandException):
            cmd.execute(args)

    @patch("cognee.cli.commands.add_command.asyncio.run")
    @patch("cognee.cli.commands.add_command.fmt")
    def test_add_execute_handles_generic_exception(self, mock_fmt, mock_run):
        """Execute wraps generic exceptions in CliCommandException."""
        from cognee.cli.commands.add_command import AddCommand

        cmd = AddCommand()
        args = argparse.Namespace(data=["test"], dataset_name="ds")

        mock_run.side_effect = RuntimeError("unexpected")

        with pytest.raises(CliCommandException, match="Failed to add data"):
            cmd.execute(args)


# ============================================================================
# T802: Test `cognee cognify` command
# ============================================================================


class TestCognifyCommand:
    """T802: Tests for the 'cognify' CLI command."""

    def test_cognify_command_is_discovered(self):
        """CognifyCommand is found by the discovery mechanism."""
        with patch("cognee.cli._cognee.fmt"):
            commands = _discover_commands()
        class_names = [cls.__name__ for cls in commands]
        assert "CognifyCommand" in class_names

    def test_cognify_command_registered_in_parser(self, parser_and_commands):
        """The 'cognify' subcommand is registered."""
        _, commands = parser_and_commands
        assert "cognify" in commands
        assert commands["cognify"].command_string == "cognify"

    def test_cognify_no_required_args(self, parse_args):
        """Cognify can run with no arguments (processes all data)."""
        args, _ = parse_args(["cognify"])
        assert args.command == "cognify"

    def test_cognify_accepts_datasets(self, parse_args):
        """Cognify accepts --datasets with multiple values."""
        args, _ = parse_args(["cognify", "--datasets", "ds1", "ds2"])
        assert args.datasets == ["ds1", "ds2"]

    def test_cognify_accepts_datasets_short_flag(self, parse_args):
        """Cognify accepts -d shorthand for datasets."""
        args, _ = parse_args(["cognify", "-d", "myds"])
        assert args.datasets == ["myds"]

    def test_cognify_accepts_chunk_size(self, parse_args):
        """Cognify accepts --chunk-size as integer."""
        args, _ = parse_args(["cognify", "--chunk-size", "1024"])
        assert args.chunk_size == 1024

    def test_cognify_accepts_ontology_file(self, parse_args):
        """Cognify accepts --ontology-file path."""
        args, _ = parse_args(["cognify", "--ontology-file", "/path/to/ontology.owl"])
        assert args.ontology_file == "/path/to/ontology.owl"

    def test_cognify_accepts_chunker_choice(self, parse_args):
        """Cognify accepts --chunker with valid choices."""
        args, _ = parse_args(["cognify", "--chunker", "TextChunker"])
        assert args.chunker == "TextChunker"

    def test_cognify_rejects_invalid_chunker(self, parser_and_commands):
        """Cognify rejects invalid chunker choices."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit):
            parser.parse_args(["cognify", "--chunker", "InvalidChunker"])

    def test_cognify_default_chunker_is_text_chunker(self, parse_args):
        """Cognify defaults to TextChunker."""
        args, _ = parse_args(["cognify"])
        assert args.chunker == "TextChunker"

    def test_cognify_accepts_background_flag(self, parse_args):
        """Cognify accepts --background / -b flag."""
        args, _ = parse_args(["cognify", "--background"])
        assert args.background is True

    def test_cognify_accepts_verbose_flag(self, parse_args):
        """Cognify accepts --verbose / -v flag."""
        args, _ = parse_args(["cognify", "-v"])
        assert args.verbose is True

    @patch("cognee.cli.commands.cognify_command.asyncio.run")
    @patch("cognee.cli.commands.cognify_command.fmt")
    def test_cognify_execute_calls_cognee_cognify(self, mock_fmt, mock_run):
        """Execute triggers the cognify pipeline via asyncio.run."""
        from cognee.cli.commands.cognify_command import CognifyCommand

        cmd = CognifyCommand()
        args = argparse.Namespace(
            datasets=None,
            chunk_size=None,
            ontology_file=None,
            chunker="TextChunker",
            background=False,
            verbose=False,
        )
        mock_run.return_value = None

        cmd.execute(args)

        mock_run.assert_called_once()
        mock_fmt.success.assert_called_once_with("Cognification completed successfully!")

    @patch("cognee.cli.commands.cognify_command.asyncio.run")
    @patch("cognee.cli.commands.cognify_command.fmt")
    def test_cognify_execute_background_mode(self, mock_fmt, mock_run):
        """Execute in background mode shows different success message."""
        from cognee.cli.commands.cognify_command import CognifyCommand

        cmd = CognifyCommand()
        args = argparse.Namespace(
            datasets=None,
            chunk_size=None,
            ontology_file=None,
            chunker="TextChunker",
            background=True,
            verbose=False,
        )
        mock_run.return_value = None

        cmd.execute(args)

        mock_fmt.success.assert_called_once_with("Cognification started in background!")

    @patch("cognee.cli.commands.cognify_command.asyncio.run")
    @patch("cognee.cli.commands.cognify_command.fmt")
    def test_cognify_execute_with_datasets(self, mock_fmt, mock_run):
        """Execute with specific datasets mentions them in output."""
        from cognee.cli.commands.cognify_command import CognifyCommand

        cmd = CognifyCommand()
        args = argparse.Namespace(
            datasets=["ds1", "ds2"],
            chunk_size=512,
            ontology_file=None,
            chunker="TextChunker",
            background=False,
            verbose=True,
        )
        mock_run.return_value = "result"

        cmd.execute(args)

        # Verify dataset names appear in the echo output
        echo_calls = [str(c) for c in mock_fmt.echo.call_args_list]
        assert any("ds1" in c and "ds2" in c for c in echo_calls)

    @patch("cognee.cli.commands.cognify_command.asyncio.run")
    @patch("cognee.cli.commands.cognify_command.fmt")
    def test_cognify_execute_raises_on_failure(self, mock_fmt, mock_run):
        """Execute raises CliCommandException on pipeline failure."""
        from cognee.cli.commands.cognify_command import CognifyCommand

        cmd = CognifyCommand()
        args = argparse.Namespace(
            datasets=None,
            chunk_size=None,
            ontology_file=None,
            chunker="TextChunker",
            background=False,
            verbose=False,
        )
        mock_run.side_effect = CliCommandInnerException("pipeline crashed")

        with pytest.raises(CliCommandException):
            cmd.execute(args)


# ============================================================================
# T803: Test `cognee search` command
# ============================================================================


class TestSearchCommand:
    """T803: Tests for the 'search' CLI command."""

    def test_search_command_is_discovered(self):
        """SearchCommand is found by discovery."""
        with patch("cognee.cli._cognee.fmt"):
            commands = _discover_commands()
        class_names = [cls.__name__ for cls in commands]
        assert "SearchCommand" in class_names

    def test_search_command_registered_in_parser(self, parser_and_commands):
        """The 'search' subcommand is registered."""
        _, commands = parser_and_commands
        assert "search" in commands
        assert commands["search"].command_string == "search"

    def test_search_requires_query_text(self, parser_and_commands):
        """Search requires a query_text positional argument."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit):
            parser.parse_args(["search"])

    def test_search_accepts_query_text(self, parse_args):
        """Search accepts query text as positional argument."""
        args, _ = parse_args(["search", "what is cognee?"])
        assert args.query_text == "what is cognee?"

    def test_search_default_query_type(self, parse_args):
        """Search defaults to GRAPH_COMPLETION query type."""
        args, _ = parse_args(["search", "test query"])
        assert args.query_type == "GRAPH_COMPLETION"

    def test_search_accepts_query_type(self, parse_args):
        """Search accepts --query-type with valid choices."""
        for qtype in ["GRAPH_COMPLETION", "RAG_COMPLETION", "CHUNKS", "SUMMARIES", "CODE", "CYPHER"]:
            args, _ = parse_args(["search", "--query-type", qtype, "query"])
            assert args.query_type == qtype

    def test_search_rejects_invalid_query_type(self, parser_and_commands):
        """Search rejects invalid query type."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit):
            parser.parse_args(["search", "--query-type", "INVALID", "query"])

    def test_search_accepts_query_type_short_flag(self, parse_args):
        """Search accepts -t shorthand for query type."""
        args, _ = parse_args(["search", "-t", "CHUNKS", "my query"])
        assert args.query_type == "CHUNKS"

    def test_search_accepts_datasets(self, parse_args):
        """Search accepts --datasets filter.

        Note: --datasets uses nargs='*', so the query_text positional arg
        must come BEFORE --datasets to avoid ambiguity.
        """
        args, _ = parse_args(["search", "query text", "--datasets", "ds1", "ds2"])
        assert args.datasets == ["ds1", "ds2"]
        assert args.query_text == "query text"

    def test_search_default_top_k(self, parse_args):
        """Search defaults top_k to 10."""
        args, _ = parse_args(["search", "query"])
        assert args.top_k == 10

    def test_search_accepts_top_k(self, parse_args):
        """Search accepts custom --top-k value."""
        args, _ = parse_args(["search", "--top-k", "25", "query"])
        assert args.top_k == 25

    def test_search_accepts_system_prompt(self, parse_args):
        """Search accepts --system-prompt option."""
        args, _ = parse_args(["search", "--system-prompt", "my_prompt.txt", "query"])
        assert args.system_prompt == "my_prompt.txt"

    def test_search_accepts_output_format(self, parse_args):
        """Search accepts --output-format with valid choices."""
        for fmt_choice in ["json", "pretty", "simple"]:
            args, _ = parse_args(["search", "-f", fmt_choice, "query"])
            assert args.output_format == fmt_choice

    def test_search_default_output_format(self, parse_args):
        """Search defaults output format to 'pretty'."""
        args, _ = parse_args(["search", "query"])
        assert args.output_format == "pretty"

    @patch("cognee.cli.commands.search_command.asyncio.run")
    @patch("cognee.cli.commands.search_command.fmt")
    def test_search_execute_calls_cognee_search(self, mock_fmt, mock_run):
        """Execute calls cognee.search with correct parameters."""
        from cognee.cli.commands.search_command import SearchCommand

        cmd = SearchCommand()
        args = argparse.Namespace(
            query_text="what is AI?",
            query_type="GRAPH_COMPLETION",
            datasets=None,
            top_k=10,
            system_prompt=None,
            output_format="pretty",
        )
        mock_run.return_value = ["Answer: AI is artificial intelligence"]

        cmd.execute(args)

        mock_run.assert_called_once()
        mock_fmt.echo.assert_any_call(
            "Searching for: 'what is AI?' (type: GRAPH_COMPLETION) across all datasets"
        )

    @patch("cognee.cli.commands.search_command.asyncio.run")
    @patch("cognee.cli.commands.search_command.fmt")
    def test_search_execute_json_output(self, mock_fmt, mock_run):
        """Execute with json output format outputs JSON."""
        from cognee.cli.commands.search_command import SearchCommand

        cmd = SearchCommand()
        args = argparse.Namespace(
            query_text="test",
            query_type="CHUNKS",
            datasets=None,
            top_k=5,
            system_prompt=None,
            output_format="json",
        )
        results = ["chunk1", "chunk2"]
        mock_run.return_value = results

        cmd.execute(args)

        # Verify json output was echoed
        expected_json = json.dumps(results, indent=2, default=str)
        mock_fmt.echo.assert_any_call(expected_json)

    @patch("cognee.cli.commands.search_command.asyncio.run")
    @patch("cognee.cli.commands.search_command.fmt")
    def test_search_execute_no_results(self, mock_fmt, mock_run):
        """Execute with no results shows warning."""
        from cognee.cli.commands.search_command import SearchCommand

        cmd = SearchCommand()
        args = argparse.Namespace(
            query_text="nonexistent",
            query_type="GRAPH_COMPLETION",
            datasets=None,
            top_k=10,
            system_prompt=None,
            output_format="pretty",
        )
        mock_run.return_value = []

        cmd.execute(args)

        mock_fmt.warning.assert_called_once_with("No results found for your query.")

    @patch("cognee.cli.commands.search_command.asyncio.run")
    @patch("cognee.cli.commands.search_command.fmt")
    def test_search_execute_raises_on_failure(self, mock_fmt, mock_run):
        """Execute raises CliCommandException on search failure."""
        from cognee.cli.commands.search_command import SearchCommand

        cmd = SearchCommand()
        args = argparse.Namespace(
            query_text="test",
            query_type="GRAPH_COMPLETION",
            datasets=None,
            top_k=10,
            system_prompt=None,
            output_format="pretty",
        )
        mock_run.side_effect = CliCommandInnerException("search failed")

        with pytest.raises(CliCommandException):
            cmd.execute(args)

    @patch("cognee.cli.commands.search_command.asyncio.run")
    @patch("cognee.cli.commands.search_command.fmt")
    def test_search_execute_with_datasets_filter(self, mock_fmt, mock_run):
        """Execute with datasets filter mentions them in output."""
        from cognee.cli.commands.search_command import SearchCommand

        cmd = SearchCommand()
        args = argparse.Namespace(
            query_text="question",
            query_type="GRAPH_COMPLETION",
            datasets=["ds1"],
            top_k=10,
            system_prompt=None,
            output_format="pretty",
        )
        mock_run.return_value = ["answer"]

        cmd.execute(args)

        mock_fmt.echo.assert_any_call(
            "Searching for: 'question' (type: GRAPH_COMPLETION) in datasets ['ds1']"
        )


# ============================================================================
# T804: Test `cognee config` command
# ============================================================================


class TestConfigCommand:
    """T804: Tests for the 'config' CLI command."""

    def test_config_command_is_discovered(self):
        """ConfigCommand is found by discovery."""
        with patch("cognee.cli._cognee.fmt"):
            commands = _discover_commands()
        class_names = [cls.__name__ for cls in commands]
        assert "ConfigCommand" in class_names

    def test_config_command_registered_in_parser(self, parser_and_commands):
        """The 'config' subcommand is registered."""
        _, commands = parser_and_commands
        assert "config" in commands
        assert commands["config"].command_string == "config"

    def test_config_get_subcommand(self, parse_args):
        """Config 'get' subcommand is parsed correctly."""
        args, _ = parse_args(["config", "get"])
        assert args.command == "config"
        assert args.config_action == "get"

    def test_config_get_with_key(self, parse_args):
        """Config 'get' accepts an optional key."""
        args, _ = parse_args(["config", "get", "llm_provider"])
        assert args.config_action == "get"
        assert args.key == "llm_provider"

    def test_config_set_subcommand(self, parse_args):
        """Config 'set' subcommand requires key and value."""
        args, _ = parse_args(["config", "set", "llm_model", "gpt-5"])
        assert args.config_action == "set"
        assert args.key == "llm_model"
        assert args.value == "gpt-5"

    def test_config_set_missing_args(self, parser_and_commands):
        """Config 'set' without key+value should error."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit):
            parser.parse_args(["config", "set"])

    def test_config_list_subcommand(self, parse_args):
        """Config 'list' subcommand is parsed correctly."""
        args, _ = parse_args(["config", "list"])
        assert args.config_action == "list"

    def test_config_unset_subcommand(self, parse_args):
        """Config 'unset' subcommand requires a key."""
        args, _ = parse_args(["config", "unset", "llm_api_key"])
        assert args.config_action == "unset"
        assert args.key == "llm_api_key"

    def test_config_unset_with_force(self, parse_args):
        """Config 'unset' accepts --force/-f flag."""
        args, _ = parse_args(["config", "unset", "--force", "llm_api_key"])
        assert args.force is True

    def test_config_reset_subcommand(self, parse_args):
        """Config 'reset' subcommand is parsed correctly."""
        args, _ = parse_args(["config", "reset"])
        assert args.config_action == "reset"

    def test_config_reset_with_force(self, parse_args):
        """Config 'reset' accepts --force flag."""
        args, _ = parse_args(["config", "reset", "--force"])
        assert args.force is True

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_no_action_shows_error(self, mock_fmt):
        """Execute with no config_action shows error message."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action=None)

        cmd.execute(args)

        mock_fmt.error.assert_called_once_with(
            "Please specify a config action: get, set, unset, list, or reset"
        )

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_list_action(self, mock_fmt):
        """Execute 'list' shows available config keys."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="list")

        cmd.execute(args)

        mock_fmt.note.assert_called_with("Available configuration keys:")
        # Verify some config keys are listed
        echo_calls = [str(c) for c in mock_fmt.echo.call_args_list]
        assert any("llm_provider" in c for c in echo_calls)

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_get_all(self, mock_fmt):
        """Execute 'get' without key tries to get all config."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="get", key=None)

        # Mock cognee module to avoid real imports
        mock_cognee = MagicMock()
        mock_cognee.config.get_all.return_value = {"llm_provider": "openai", "llm_model": "gpt-5"}
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_get_specific_key(self, mock_fmt):
        """Execute 'get' with key retrieves that specific value."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="get", key="llm_model")

        mock_cognee = MagicMock()
        mock_cognee.config.get.return_value = "gpt-5"
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_set_string_value(self, mock_fmt):
        """Execute 'set' with string value calls config.set correctly."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="set", key="llm_model", value="gpt-5")

        mock_cognee = MagicMock()
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

        mock_cognee.config.set.assert_called_once_with("llm_model", "gpt-5")

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_set_json_value(self, mock_fmt):
        """Execute 'set' with JSON-parseable value parses it correctly."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="set", key="chunk_size", value="1024")

        mock_cognee = MagicMock()
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

        # 1024 should be parsed as integer via json.loads
        mock_cognee.config.set.assert_called_once_with("chunk_size", 1024)

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_unset_known_key_with_force(self, mock_fmt):
        """Execute 'unset' with known key and force resets to default."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="unset", key="llm_provider", force=True)

        mock_cognee = MagicMock()
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

        mock_cognee.config.set_llm_provider.assert_called_once_with("openai")

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_unset_unknown_key(self, mock_fmt):
        """Execute 'unset' with unknown key shows error."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="unset", key="nonexistent_key", force=True)

        mock_cognee = MagicMock()
        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            cmd.execute(args)

        mock_fmt.error.assert_called_once_with("Unknown configuration key 'nonexistent_key'")

    @patch("cognee.cli.commands.config_command.fmt")
    def test_config_execute_reset_with_force(self, mock_fmt):
        """Execute 'reset' with force shows reset message."""
        from cognee.cli.commands.config_command import ConfigCommand

        cmd = ConfigCommand()
        args = argparse.Namespace(config_action="reset", force=True)

        cmd.execute(args)

        mock_fmt.note.assert_called_with("Configuration reset not fully implemented yet")


# ============================================================================
# T805: Test `cognee delete` command (project uses 'delete' not 'prune')
# ============================================================================


class TestDeleteCommand:
    """T805: Tests for the 'delete' CLI command.

    Note: The task spec mentions 'prune' but the actual codebase uses 'delete'.
    This tests the real 'delete' command which serves the same purpose.
    """

    def test_delete_command_is_discovered(self):
        """DeleteCommand is found by discovery."""
        with patch("cognee.cli._cognee.fmt"):
            commands = _discover_commands()
        class_names = [cls.__name__ for cls in commands]
        assert "DeleteCommand" in class_names

    def test_delete_command_registered_in_parser(self, parser_and_commands):
        """The 'delete' subcommand is registered."""
        _, commands = parser_and_commands
        assert "delete" in commands
        assert commands["delete"].command_string == "delete"

    def test_delete_accepts_dataset_name(self, parse_args):
        """Delete accepts --dataset-name."""
        args, _ = parse_args(["delete", "--dataset-name", "old_data"])
        assert args.dataset_name == "old_data"

    def test_delete_accepts_dataset_name_short_flag(self, parse_args):
        """Delete accepts -d shorthand."""
        args, _ = parse_args(["delete", "-d", "old_data"])
        assert args.dataset_name == "old_data"

    def test_delete_accepts_user_id(self, parse_args):
        """Delete accepts --user-id."""
        args, _ = parse_args(["delete", "--user-id", "user123"])
        assert args.user_id == "user123"

    def test_delete_accepts_all_flag(self, parse_args):
        """Delete accepts --all flag."""
        args, _ = parse_args(["delete", "--all"])
        assert getattr(args, "all") is True

    def test_delete_accepts_force_flag(self, parse_args):
        """Delete accepts --force / -f flag."""
        args, _ = parse_args(["delete", "--all", "--force"])
        assert args.force is True

    def test_delete_no_options_valid_parse(self, parse_args):
        """Delete with no options parses without error (validation in execute)."""
        args, _ = parse_args(["delete"])
        assert args.command == "delete"
        assert args.dataset_name is None
        assert args.user_id is None
        assert getattr(args, "all") is False

    @patch("cognee.cli.commands.delete_command.asyncio.run")
    @patch("cognee.cli.commands.delete_command.get_deletion_counts")
    @patch("cognee.cli.commands.delete_command.fmt")
    def test_delete_execute_no_target_shows_error(self, mock_fmt, mock_counts, mock_run):
        """Execute without any target shows error message."""
        from cognee.cli.commands.delete_command import DeleteCommand

        cmd = DeleteCommand()
        args = argparse.Namespace(
            dataset_name=None,
            user_id=None,
            force=False,
        )
        # Manually set 'all' attribute (argparse uses it as attribute name)
        setattr(args, "all", False)

        cmd.execute(args)

        mock_fmt.error.assert_called_once_with(
            "Please specify what to delete: --dataset-name, --user-id, or --all"
        )

    @patch("cognee.cli.commands.delete_command.asyncio.run")
    @patch("cognee.cli.commands.delete_command.get_deletion_counts")
    @patch("cognee.cli.commands.delete_command.fmt")
    def test_delete_execute_all_with_force(self, mock_fmt, mock_counts, mock_run):
        """Execute with --all --force skips confirmation and deletes."""
        from cognee.cli.commands.delete_command import DeleteCommand

        cmd = DeleteCommand()
        args = argparse.Namespace(
            dataset_name=None,
            user_id=None,
            force=True,
        )
        setattr(args, "all", True)

        mock_run.return_value = None

        cmd.execute(args)

        mock_fmt.success.assert_called_once_with("Successfully deleted all data")

    @patch("cognee.cli.commands.delete_command.asyncio.run")
    @patch("cognee.cli.commands.delete_command.get_deletion_counts")
    @patch("cognee.cli.commands.delete_command.fmt")
    def test_delete_execute_dataset_with_force(self, mock_fmt, mock_counts, mock_run):
        """Execute with --dataset-name --force deletes the dataset."""
        from cognee.cli.commands.delete_command import DeleteCommand

        cmd = DeleteCommand()
        args = argparse.Namespace(
            dataset_name="test_ds",
            user_id=None,
            force=True,
        )
        setattr(args, "all", False)

        mock_run.return_value = None

        cmd.execute(args)

        mock_fmt.success.assert_called_once_with("Successfully deleted dataset 'test_ds'")

    @patch("cognee.cli.commands.delete_command.asyncio.run")
    @patch("cognee.cli.commands.delete_command.get_deletion_counts")
    @patch("cognee.cli.commands.delete_command.fmt")
    def test_delete_execute_user_with_force(self, mock_fmt, mock_counts, mock_run):
        """Execute with --user-id --force deletes user data."""
        from cognee.cli.commands.delete_command import DeleteCommand

        cmd = DeleteCommand()
        args = argparse.Namespace(
            dataset_name=None,
            user_id="user42",
            force=True,
        )
        setattr(args, "all", False)

        mock_run.return_value = None

        cmd.execute(args)

        mock_fmt.success.assert_called_once_with("Successfully deleted data for user 'user42'")

    @patch("cognee.cli.commands.delete_command.asyncio.run")
    @patch("cognee.cli.commands.delete_command.get_deletion_counts")
    @patch("cognee.cli.commands.delete_command.fmt")
    def test_delete_execute_raises_on_failure(self, mock_fmt, mock_counts, mock_run):
        """Execute raises CliCommandException on deletion failure."""
        from cognee.cli.commands.delete_command import DeleteCommand

        cmd = DeleteCommand()
        args = argparse.Namespace(
            dataset_name="ds",
            user_id=None,
            force=True,
        )
        setattr(args, "all", False)

        mock_run.side_effect = CliCommandInnerException("deletion failed")

        with pytest.raises(CliCommandException):
            cmd.execute(args)

    def test_prune_command_not_implemented(self, parser_and_commands):
        """Verify that 'prune' is NOT a registered command (it's 'delete' instead).

        Note: The task spec mentions T805 as 'prune', but the actual codebase
        implements 'delete' instead. This test documents that distinction.
        """
        _, commands = parser_and_commands
        assert "prune" not in commands
        assert "delete" in commands


# ============================================================================
# Integration-level CLI tests (still using mocks)
# ============================================================================


class TestCLIParserIntegration:
    """Tests for the overall CLI parser structure and command discovery."""

    def test_all_five_commands_are_registered(self, parser_and_commands):
        """All five expected commands are registered."""
        _, commands = parser_and_commands
        expected = {"add", "cognify", "search", "config", "delete"}
        assert set(commands.keys()) == expected

    def test_parser_has_version_flag(self, parser_and_commands):
        """The CLI parser supports --version flag."""
        parser, _ = parser_and_commands
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_parser_has_debug_flag(self, parser_and_commands):
        """The CLI parser supports --debug flag."""
        parser, _ = parser_and_commands
        # --debug uses a custom action, parse should not fail
        args = parser.parse_args(["--debug", "add", "test"])
        assert args.command == "add"

    def test_parser_has_ui_flag(self, parser_and_commands):
        """The CLI parser supports -ui flag."""
        parser, _ = parser_and_commands
        args = parser.parse_args(["-ui"])
        assert hasattr(args, "start_ui")
        assert args.start_ui is True

    def test_unknown_command_does_not_parse(self, parser_and_commands):
        """An unknown command name leaves args.command as the unknown string."""
        parser, _ = parser_and_commands
        # argparse with subparsers: unknown subcommand causes error
        with pytest.raises(SystemExit):
            parser.parse_args(["unknown_cmd"])

    def test_each_command_has_docs_url(self, parser_and_commands):
        """Each registered command has a docs_url."""
        _, commands = parser_and_commands
        for name, cmd in commands.items():
            assert hasattr(cmd, "docs_url"), f"Command '{name}' is missing docs_url"
            assert cmd.docs_url is not None

    def test_command_classes_implement_protocol(self, parser_and_commands):
        """Each command implements the SupportsCliCommand protocol."""
        _, commands = parser_and_commands
        for name, cmd in commands.items():
            assert hasattr(cmd, "command_string"), f"{name} missing command_string"
            assert hasattr(cmd, "help_string"), f"{name} missing help_string"
            assert hasattr(cmd, "configure_parser"), f"{name} missing configure_parser"
            assert hasattr(cmd, "execute"), f"{name} missing execute"
            assert callable(cmd.configure_parser), f"{name}.configure_parser not callable"
            assert callable(cmd.execute), f"{name}.execute not callable"

    @patch("cognee.cli._cognee.fmt")
    def test_main_no_args_returns_negative(self, mock_fmt):
        """main() with no arguments returns -1 (shows help)."""
        with patch("sys.argv", ["cognee"]):
            result = main()
        assert result == -1

    @patch("cognee.cli._cognee.fmt")
    def test_discover_commands_handles_import_error(self, mock_fmt):
        """_discover_commands gracefully handles missing modules."""
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            commands = _discover_commands()
        # Should return empty list, not crash
        assert commands == []
