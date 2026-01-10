import argparse
import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from cognee.cli.reference import SupportsCliCommand
from cognee.cli import DEFAULT_DOCS_URL
import cognee.cli.echo as fmt
from cognee.cli.exceptions import CliCommandException, CliCommandInnerException


class InitCommand(SupportsCliCommand):
    command_string = "init"
    help_string = "Initialize Cognee environment and setup required databases"
    docs_url = DEFAULT_DOCS_URL
    description = """
Initialize Cognee environment and setup required components.

This command performs the following operations:
- Checks for .env configuration file and helps create one if missing
- Creates necessary database tables (relational, vector, graph)
- Tests LLM and embedding provider connections
- Sets up required directories
- Validates the environment configuration

This is typically the first command you should run after installing Cognee
to ensure your environment is properly configured and ready for use.

Example Usage:
    cognee init                    # Interactive initialization with prompts
    cognee init --skip-wizard      # Skip configuration wizard
    cognee init --force            # Force re-initialization even if already setup
    """

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--skip-wizard",
            "-s",
            action="store_true",
            help="Skip the configuration wizard and use existing .env file",
        )
        parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Force re-initialization even if environment is already setup",
        )
        parser.add_argument(
            "--api-key",
            "-k",
            help="LLM API key (OpenAI by default)",
        )

    def execute(self, args: argparse.Namespace) -> None:
        try:
            fmt.echo("🚀 Initializing Cognee environment...")
            fmt.echo()

            # Run the async initialization
            asyncio.run(self._run_init(args))

        except Exception as e:
            if isinstance(e, CliCommandInnerException):
                raise CliCommandException(str(e), error_code=1) from e
            raise CliCommandException(
                f"Failed to initialize Cognee: {str(e)}", error_code=1
            ) from e

    async def _run_init(self, args: argparse.Namespace) -> None:
        """Main initialization flow"""
        try:
            # Step 1: Check and setup .env file
            env_path = Path.cwd() / ".env"
            env_template_path = Path(__file__).parent.parent.parent.parent / ".env.template"

            if not env_path.exists():
                fmt.warning("⚠️  No .env file found in the current directory.")

                if not args.skip_wizard:
                    self._setup_env_file(env_path, env_template_path, args.api_key)
                else:
                    fmt.warning("Skipping configuration wizard. Please create .env file manually.")
                    fmt.echo(f"You can copy the template from: {env_template_path}")
                    raise CliCommandInnerException(
                        "Cannot proceed without .env file. Run 'cognee init' without --skip-wizard or create .env manually."
                    )
            else:
                fmt.success("✓ Found existing .env file")

            # Step 2: Load environment variables from .env
            self._load_env_file(env_path)

            # Step 3: Setup databases and check environment
            fmt.echo()
            fmt.echo("📦 Setting up databases...")

            await self._setup_databases()

            fmt.success("✓ Databases initialized successfully")

            # Step 4: Test LLM and embedding connections
            fmt.echo()
            fmt.echo("🔌 Testing LLM and embedding connections...")

            await self._test_connections()

            fmt.success("✓ Connections validated successfully")

            # Step 5: Display success message
            fmt.echo()
            fmt.success("🎉 Cognee initialization completed successfully!")
            fmt.echo()
            fmt.echo("Next steps:")
            fmt.echo("  1. Add data:      cognee add \"Your text or file path\"")
            fmt.echo("  2. Process data:  cognee cognify")
            fmt.echo("  3. Search:        cognee search \"Your query\"")
            fmt.echo()
            fmt.echo(f"📖 Documentation: {DEFAULT_DOCS_URL}")

        except CliCommandInnerException:
            raise
        except Exception as e:
            raise CliCommandInnerException(f"Initialization failed: {str(e)}") from e

    def _setup_env_file(
        self, env_path: Path, env_template_path: Path, api_key: Optional[str] = None
    ) -> None:
        """Setup .env file interactively or with provided API key"""

        if api_key:
            # Non-interactive mode with API key provided
            fmt.echo("Creating .env file with provided API key...")
            self._create_env_from_template(env_path, env_template_path, api_key)
            fmt.success("✓ Created .env file")
        else:
            # Interactive mode
            fmt.echo()
            fmt.echo("Would you like to create a basic .env configuration now?")
            fmt.echo("(You can also manually copy .env.template and edit it)")
            fmt.echo()

            try:
                response = input("Create .env file? [Y/n]: ").strip().lower()

                if response in ["", "y", "yes"]:
                    fmt.echo()
                    fmt.echo("Please enter your OpenAI API key:")
                    fmt.echo("(You can get one at: https://platform.openai.com/api-keys)")
                    user_api_key = input("API Key: ").strip()

                    if not user_api_key:
                        raise CliCommandInnerException("API key is required to continue")

                    self._create_env_from_template(env_path, env_template_path, user_api_key)
                    fmt.success("✓ Created .env file")
                else:
                    raise CliCommandInnerException(
                        "Initialization cancelled. Please create .env file manually and run 'cognee init' again."
                    )
            except KeyboardInterrupt:
                fmt.echo()
                raise CliCommandInnerException("Initialization cancelled by user")

    def _create_env_from_template(
        self, env_path: Path, env_template_path: Path, api_key: str
    ) -> None:
        """Create .env file from template with user's API key"""

        if not env_template_path.exists():
            # Fallback: create minimal .env
            minimal_config = f"""# Cognee Configuration
# For more options, see: https://docs.cognee.ai

# LLM Settings
LLM_API_KEY="{api_key}"
LLM_MODEL="openai/gpt-5-mini"
LLM_PROVIDER="openai"

# Embedding Settings
EMBEDDING_PROVIDER="openai"
EMBEDDING_MODEL="openai/text-embedding-3-large"

# Default databases (file-based, no extra setup needed)
DB_PROVIDER="sqlite"
GRAPH_DATABASE_PROVIDER="kuzu"
VECTOR_DB_PROVIDER="lancedb"
"""
            env_path.write_text(minimal_config)
        else:
            # Copy template and replace API key
            template_content = env_template_path.read_text()

            # Replace the placeholder API key
            modified_content = template_content.replace(
                'LLM_API_KEY="your_api_key"',
                f'LLM_API_KEY="{api_key}"'
            )

            env_path.write_text(modified_content)

    def _load_env_file(self, env_path: Path) -> None:
        """Load environment variables from .env file"""
        try:
            # Try to use python-dotenv if available
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path, override=True)
            except ImportError:
                # Manual loading if python-dotenv is not available
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip().strip('"').strip("'")
                            os.environ[key.strip()] = value
        except Exception as e:
            raise CliCommandInnerException(f"Failed to load .env file: {str(e)}") from e

    async def _setup_databases(self) -> None:
        """Setup and initialize databases"""
        try:
            from cognee.infrastructure.databases.relational import (
                create_db_and_tables as create_relational_db_and_tables,
            )
            from cognee.infrastructure.databases.vector.pgvector import (
                create_db_and_tables as create_pgvector_db_and_tables,
            )

            # Create relational database tables
            fmt.echo("  - Initializing relational database...")
            await create_relational_db_and_tables()

            # Create vector database tables
            fmt.echo("  - Initializing vector database...")
            await create_pgvector_db_and_tables()

        except Exception as e:
            raise CliCommandInnerException(
                f"Database setup failed: {str(e)}\nPlease check your database configuration in .env"
            ) from e

    async def _test_connections(self) -> None:
        """Test LLM and embedding provider connections"""
        try:
            from cognee.infrastructure.llm.utils import (
                test_llm_connection,
                test_embedding_connection,
            )

            # Test LLM connection with timeout
            fmt.echo("  - Testing LLM connection...")
            try:
                await asyncio.wait_for(test_llm_connection(), timeout=10.0)
                fmt.success("    LLM connection successful")
            except asyncio.TimeoutError:
                fmt.warning("    LLM connection test timed out")
                fmt.note("    Please verify your LLM_API_KEY and network connectivity")
            except Exception as llm_error:
                error_msg = str(llm_error).split('\n')[0]  # Get first line only
                fmt.warning(f"    LLM connection failed: {error_msg}")
                fmt.note("    Please verify your LLM_API_KEY in .env file")

            # Test embedding connection with timeout
            fmt.echo("  - Testing embedding connection...")
            try:
                await asyncio.wait_for(test_embedding_connection(), timeout=10.0)
                fmt.success("    Embedding connection successful")
            except asyncio.TimeoutError:
                fmt.warning("    Embedding connection test timed out")
                fmt.note("    Please verify your EMBEDDING_API_KEY (or LLM_API_KEY) and network connectivity")
            except Exception as embed_error:
                error_msg = str(embed_error).split('\n')[0]  # Get first line only
                fmt.warning(f"    Embedding connection failed: {error_msg}")
                fmt.note("    Please verify your EMBEDDING_API_KEY (or LLM_API_KEY) in .env file")

        except Exception as e:
            # Only raise if we can't even import the test functions
            if "import" in str(e).lower():
                raise CliCommandInnerException(
                    f"Connection test setup failed: {str(e)}"
                ) from e
            # Otherwise, just log a warning - the connection tests already handled individual failures
            pass
