"""
Phase 9 T905-T908: Docker/CI-CD/Spec/YAML 部署与配置验证测试。

全部使用 mock，不依赖真实 Docker/DB/LLM/网络连接。
验证项目部署文件、CI/CD 配置、规范文档和 YAML 配置系统的完整性。
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helper: locate project root (the directory containing pyproject.toml)
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """向上搜索直到找到 pyproject.toml 所在的项目根目录。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Cannot locate project root (pyproject.toml not found)")


PROJECT_ROOT = _project_root()


# ===========================================================================
# T905: Docker Compose 一键部署验证
# ===========================================================================

class TestT905DockerCompose:
    """T905: Docker Compose 一键部署验证。"""

    def test_docker_compose_exists(self):
        """docker-compose.yml 必须存在于项目根目录。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"

    def test_docker_compose_is_valid_yaml(self):
        """docker-compose.yml 必须是合法的 YAML。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), "docker-compose.yml should parse to a dict"

    def test_docker_compose_defines_services(self):
        """docker-compose.yml 必须定义 services 顶级键。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "services" in data, "docker-compose.yml must define 'services'"
        assert isinstance(data["services"], dict), "'services' should be a dict"

    def test_docker_compose_has_app_service(self):
        """docker-compose.yml 必须包含主应用服务 (cognee)。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        # The main app service is named 'cognee'
        assert "cognee" in services, "docker-compose.yml must define 'cognee' service"

    def test_docker_compose_has_database_service(self):
        """docker-compose.yml 必须包含数据库服务 (postgres)。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        assert "postgres" in services, "docker-compose.yml must define 'postgres' service"

    def test_docker_compose_has_vector_db_service(self):
        """docker-compose.yml 必须包含向量数据库服务 (qdrant)。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        assert "qdrant" in services, "docker-compose.yml must define 'qdrant' service"

    def test_docker_compose_postgres_has_env_defaults(self):
        """Postgres 服务必须定义环境变量默认值。"""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        pg = data["services"]["postgres"]
        env = pg.get("environment", {})
        assert "POSTGRES_DB" in env, "postgres service must define POSTGRES_DB"
        assert "POSTGRES_USER" in env, "postgres service must define POSTGRES_USER"
        assert "POSTGRES_PASSWORD" in env, "postgres service must define POSTGRES_PASSWORD"

    def test_dockerfile_exists(self):
        """Dockerfile 必须存在于项目根目录。"""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        assert dockerfile.exists(), f"Dockerfile not found at {dockerfile}"

    def test_dockerfile_has_proper_base_image(self):
        """Dockerfile 必须使用 Python 基础镜像。"""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        # Check for FROM with python image
        assert "FROM" in content, "Dockerfile must have a FROM instruction"
        # The project uses python3.12 based images
        assert "python" in content.lower(), "Dockerfile must reference a Python base image"

    def test_dockerignore_exists(self):
        """.dockerignore 必须存在。"""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        assert dockerignore.exists(), f".dockerignore not found at {dockerignore}"

    @pytest.mark.parametrize("pattern", [
        ".venv",
        ".github",
    ])
    def test_dockerignore_excludes_common_dirs(self, pattern):
        """.dockerignore 必须排除常见不需要的目录。"""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        content = dockerignore.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
        assert any(pattern in line for line in lines), (
            f".dockerignore should exclude '{pattern}'"
        )


# ===========================================================================
# T906: CI/CD 流程验证
# ===========================================================================

class TestT906CICD:
    """T906: CI/CD 流程验证。"""

    def test_ci_config_directory_exists(self):
        """.github/workflows/ 目录必须存在。"""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"
        assert workflows_dir.exists(), ".github/workflows/ directory not found"
        assert workflows_dir.is_dir(), ".github/workflows/ should be a directory"

    def test_ci_has_workflow_files(self):
        """CI 目录下必须包含至少一个工作流文件。"""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"
        yml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        assert len(yml_files) > 0, "No workflow files found in .github/workflows/"

    def test_ci_has_basic_tests_workflow(self):
        """CI 必须包含基础测试工作流。"""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"
        basic_tests = workflows_dir / "basic_tests.yml"
        assert basic_tests.exists(), "basic_tests.yml workflow not found"

    def test_ci_basic_tests_includes_test_step(self):
        """基础测试工作流必须包含运行测试的步骤。"""
        basic_tests = PROJECT_ROOT / ".github" / "workflows" / "basic_tests.yml"
        with open(basic_tests, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        content = basic_tests.read_text(encoding="utf-8")
        # The workflow should contain pytest or test-related commands
        assert "pytest" in content or "test" in content.lower(), (
            "basic_tests.yml must include a test running step"
        )

    def test_ci_basic_tests_includes_lint_step(self):
        """基础测试工作流必须包含 linting 步骤。"""
        basic_tests = PROJECT_ROOT / ".github" / "workflows" / "basic_tests.yml"
        with open(basic_tests, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # Check jobs for a lint-related job
        jobs = data.get("jobs", {})
        job_names = [k.lower() for k in jobs.keys()]
        assert any("lint" in name for name in job_names), (
            "basic_tests.yml should include a linting job"
        )

    def test_ci_workflows_are_valid_yaml(self):
        """所有 CI 工作流文件必须是合法的 YAML。"""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"
        yml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        for yml_file in yml_files:
            with open(yml_file, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f)
                    assert data is not None, f"{yml_file.name} parsed to None"
                except yaml.YAMLError as e:
                    pytest.fail(f"{yml_file.name} is not valid YAML: {e}")

    def test_pyproject_has_project_name(self):
        """pyproject.toml 必须定义 project.name。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert 'name = "cognee"' in content, "pyproject.toml must define project name 'cognee'"

    def test_pyproject_has_version(self):
        """pyproject.toml 必须定义 project.version。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "version" in content, "pyproject.toml must define a version"

    def test_pyproject_has_description(self):
        """pyproject.toml 必须定义 project.description。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "description" in content, "pyproject.toml must define a description"

    def test_pyproject_has_test_dependencies(self):
        """pyproject.toml 必须配置测试依赖 (dev extras)。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "pytest" in content, "pyproject.toml must include pytest in dependencies"

    def test_pyproject_has_python_version_requirement(self):
        """pyproject.toml 必须指定 Python 版本要求。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "requires-python" in content, "pyproject.toml must define requires-python"

    def test_pyproject_has_build_system(self):
        """pyproject.toml 必须定义构建系统。"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "[build-system]" in content, "pyproject.toml must define [build-system]"


# ===========================================================================
# T907: Spec 文档完整性验证
# ===========================================================================

class TestT907SpecDocumentation:
    """T907: 规范文档完整性验证。"""

    def test_spec_md_exists(self):
        """spec.md 必须存在于 specs/cognee-platform/。"""
        spec_file = PROJECT_ROOT / "specs" / "cognee-platform" / "spec.md"
        assert spec_file.exists(), f"spec.md not found at {spec_file}"

    def test_constitution_md_exists(self):
        """constitution.md 必须存在于 specs/cognee-platform/。"""
        constitution = PROJECT_ROOT / "specs" / "cognee-platform" / "constitution.md"
        assert constitution.exists(), f"constitution.md not found at {constitution}"

    def test_tasks_md_exists(self):
        """tasks.md 必须存在于 specs/cognee-platform/。"""
        tasks = PROJECT_ROOT / "specs" / "cognee-platform" / "tasks.md"
        assert tasks.exists(), f"tasks.md not found at {tasks}"

    def test_implementation_plan_exists(self):
        """至少一个实现计划文件必须存在于 docs/plans/。"""
        plans_dir = PROJECT_ROOT / "docs" / "plans"
        assert plans_dir.exists(), f"docs/plans/ directory not found at {plans_dir}"
        plan_files = list(plans_dir.glob("*plan*")) + list(plans_dir.glob("*implementation*"))
        assert len(plan_files) > 0, "No implementation plan file found in docs/plans/"

    @pytest.mark.parametrize("config_file", [
        "parsers.yaml",
        "chunking.yaml",
        "search.yaml",
        "graph_builder.yaml",
        "multimodal.yaml",
        "ontology.yaml",
    ])
    def test_config_yaml_files_exist(self, config_file):
        """所有必需的 config/*.yaml 文件必须存在。"""
        config_path = PROJECT_ROOT / "config" / config_file
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_specs_directory_structure(self):
        """specs/cognee-platform/ 目录必须存在。"""
        specs_dir = PROJECT_ROOT / "specs" / "cognee-platform"
        assert specs_dir.exists(), f"specs/cognee-platform/ not found at {specs_dir}"
        assert specs_dir.is_dir(), "specs/cognee-platform/ should be a directory"

    def test_spec_files_are_non_empty(self):
        """规范文件不能为空。"""
        spec_files = [
            PROJECT_ROOT / "specs" / "cognee-platform" / "spec.md",
            PROJECT_ROOT / "specs" / "cognee-platform" / "constitution.md",
            PROJECT_ROOT / "specs" / "cognee-platform" / "tasks.md",
        ]
        for spec_file in spec_files:
            if spec_file.exists():
                size = spec_file.stat().st_size
                assert size > 0, f"{spec_file.name} is empty"


# ===========================================================================
# T908: YAML 配置系统完整性验证
# ===========================================================================

class TestT908YAMLConfigIntegrity:
    """T908: YAML 配置系统完整性验证。"""

    @pytest.mark.parametrize("config_file", [
        "parsers.yaml",
        "chunking.yaml",
        "search.yaml",
        "graph_builder.yaml",
        "multimodal.yaml",
        "ontology.yaml",
    ])
    def test_config_files_are_valid_yaml(self, config_file):
        """每个配置文件必须是合法的 YAML。"""
        config_path = PROJECT_ROOT / "config" / config_file
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{config_file} should parse to a dict"

    @pytest.mark.parametrize("config_file,expected_keys", [
        ("parsers.yaml", ["parsers"]),
        ("chunking.yaml", ["chunking"]),
        ("search.yaml", ["search"]),
        ("graph_builder.yaml", ["graph_builder"]),
        ("multimodal.yaml", ["image"]),
        ("ontology.yaml", ["enabled"]),
    ])
    def test_config_files_have_expected_top_level_keys(self, config_file, expected_keys):
        """每个配置文件必须包含预期的顶层键。"""
        config_path = PROJECT_ROOT / "config" / config_file
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for key in expected_keys:
            assert key in data, f"{config_file} missing top-level key '{key}'"

    def test_parsers_yaml_has_pdf_section(self):
        """parsers.yaml 必须有 pdf 配置区域，含 default parser。"""
        config_path = PROJECT_ROOT / "config" / "parsers.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "parsers" in data
        assert "pdf" in data["parsers"], "parsers.yaml must have 'pdf' section"
        assert "default" in data["parsers"]["pdf"], "parsers.yaml pdf must have 'default' parser"

    def test_chunking_yaml_has_strategy_and_parameters(self):
        """chunking.yaml 必须包含 strategy 和参数配置。"""
        config_path = PROJECT_ROOT / "config" / "chunking.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        chunking = data.get("chunking", {})
        assert "default_strategy" in chunking, "chunking.yaml must define default_strategy"
        assert "chunk_size" in chunking, "chunking.yaml must define chunk_size"
        assert "chunk_overlap" in chunking, "chunking.yaml must define chunk_overlap"

    def test_search_yaml_has_hybrid_search(self):
        """search.yaml 必须包含 hybrid search 配置。"""
        config_path = PROJECT_ROOT / "config" / "search.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        search = data.get("search", {})
        assert "hybrid" in search, "search.yaml must define 'hybrid' section"
        hybrid = search["hybrid"]
        assert "strategies" in hybrid, "hybrid search must define strategies"
        assert "fusion" in hybrid, "hybrid search must define fusion method"

    def test_graph_builder_yaml_has_extraction_and_entity_resolution(self):
        """graph_builder.yaml 必须包含 extraction 和 entity_resolution 区域。"""
        config_path = PROJECT_ROOT / "config" / "graph_builder.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        gb = data.get("graph_builder", {})
        assert "extraction" in gb, "graph_builder.yaml must define 'extraction'"
        assert "entity_resolution" in gb, "graph_builder.yaml must define 'entity_resolution'"

    def test_get_module_config_loads_parsers(self):
        """get_module_config 必须能正确加载 parsers 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("parsers")
        assert isinstance(config, dict)
        assert "parsers" in config

    def test_get_module_config_loads_chunking(self):
        """get_module_config 必须能正确加载 chunking 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("chunking")
        assert isinstance(config, dict)
        assert "chunking" in config

    def test_get_module_config_loads_search(self):
        """get_module_config 必须能正确加载 search 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("search")
        assert isinstance(config, dict)
        assert "search" in config

    def test_get_module_config_loads_graph_builder(self):
        """get_module_config 必须能正确加载 graph_builder 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("graph_builder")
        assert isinstance(config, dict)
        assert "graph_builder" in config

    def test_get_module_config_loads_multimodal(self):
        """get_module_config 必须能正确加载 multimodal 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("multimodal")
        assert isinstance(config, dict)
        assert "image" in config

    def test_get_module_config_loads_ontology(self):
        """get_module_config 必须能正确加载 ontology 配置。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("ontology")
        assert isinstance(config, dict)
        assert "enabled" in config

    def test_reload_config_clears_cache(self):
        """reload_config 必须清除缓存，使下次加载重新读取文件。"""
        from cognee.infrastructure.config.yaml_config import (
            get_module_config,
            reload_config,
            _config_cache,
        )
        reload_config()
        # Load to populate cache
        get_module_config("parsers")
        assert "parsers" in _config_cache

        # Reload should clear cache
        reload_config()
        assert "parsers" not in _config_cache

    def test_config_changes_picked_up_after_reload(self):
        """配置变更必须在 reload_config 后被感知。"""
        from cognee.infrastructure.config.yaml_config import (
            get_module_config,
            reload_config,
            _config_cache,
        )
        reload_config()
        # Load original config
        original = get_module_config("parsers")
        assert "parsers" in original

        # Simulate config change by injecting a modified value into cache,
        # then verify reload clears it and reloads from disk
        _config_cache["parsers"] = {"parsers": {"pdf": {"default": "MODIFIED"}}}
        cached = get_module_config("parsers")
        assert cached["parsers"]["pdf"]["default"] == "MODIFIED"

        # After reload, should get the original value from disk
        reload_config()
        refreshed = get_module_config("parsers")
        assert refreshed["parsers"]["pdf"]["default"] == "docling"

    def test_invalid_yaml_handled_gracefully(self):
        """无效的 YAML 文件不能导致崩溃，应返回空字典。"""
        from cognee.infrastructure.config.yaml_config import load_yaml_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: [broken: {unclosed\n")
            temp_path = f.name

        try:
            result = load_yaml_config(temp_path)
            assert result == {}, "Invalid YAML should return empty dict"
        finally:
            os.unlink(temp_path)

    def test_missing_config_file_returns_empty_dict(self):
        """不存在的配置文件应返回空字典。"""
        from cognee.infrastructure.config.yaml_config import load_yaml_config
        result = load_yaml_config("/nonexistent/path/config.yaml")
        assert result == {}, "Missing config file should return empty dict"

    def test_get_module_config_nonexistent_module(self):
        """加载不存在模块的配置应返回空字典。"""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("this_module_does_not_exist_xyz")
        assert config == {}, "Nonexistent module config should return empty dict"

    def test_empty_yaml_file_returns_empty_dict(self):
        """空的 YAML 文件应返回空字典。"""
        from cognee.infrastructure.config.yaml_config import load_yaml_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = load_yaml_config(temp_path)
            assert result == {}, "Empty YAML file should return empty dict"
        finally:
            os.unlink(temp_path)

    def test_yaml_with_only_scalar_returns_empty_dict(self):
        """仅含标量值的 YAML 文件应返回空字典（非 dict）。"""
        from cognee.infrastructure.config.yaml_config import load_yaml_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("just a string value\n")
            temp_path = f.name

        try:
            result = load_yaml_config(temp_path)
            assert result == {}, "Scalar-only YAML should return empty dict"
        finally:
            os.unlink(temp_path)

    def test_search_yaml_has_reranking_config(self):
        """search.yaml 必须包含 reranking 配置。"""
        config_path = PROJECT_ROOT / "config" / "search.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        search = data.get("search", {})
        assert "reranking" in search, "search.yaml must define 'reranking' section"
        reranking = search["reranking"]
        assert "enabled" in reranking, "reranking must have 'enabled' field"
        assert "model" in reranking, "reranking must have 'model' field"

    def test_graph_builder_extraction_has_validation_config(self):
        """graph_builder.yaml extraction 必须包含多轮验证配置。"""
        config_path = PROJECT_ROOT / "config" / "graph_builder.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        extraction = data["graph_builder"]["extraction"]
        assert "multi_round_validation" in extraction, (
            "extraction must have multi_round_validation"
        )
        assert "confidence_threshold" in extraction, (
            "extraction must have confidence_threshold"
        )

    def test_ontology_yaml_has_entity_types(self):
        """ontology.yaml 必须定义 entity_types。"""
        config_path = PROJECT_ROOT / "config" / "ontology.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "entity_types" in data, "ontology.yaml must define 'entity_types'"
        assert isinstance(data["entity_types"], list), "entity_types must be a list"
        assert len(data["entity_types"]) > 0, "entity_types must not be empty"

    def test_ontology_yaml_has_relation_types(self):
        """ontology.yaml 必须定义 relation_types。"""
        config_path = PROJECT_ROOT / "config" / "ontology.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "relation_types" in data, "ontology.yaml must define 'relation_types'"
        assert isinstance(data["relation_types"], list), "relation_types must be a list"
        assert len(data["relation_types"]) > 0, "relation_types must not be empty"

    def test_multimodal_yaml_has_ocr_config(self):
        """multimodal.yaml 必须定义 OCR 引擎配置。"""
        config_path = PROJECT_ROOT / "config" / "multimodal.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "image" in data, "multimodal.yaml must define 'image' section"
        image = data["image"]
        assert "ocr_engine" in image, "image section must define ocr_engine"
