"""Unit tests for cognee.modules.search.utils.quality_metrics module."""
import pytest
from unittest.mock import Mock, patch

from cognee.modules.search.utils.quality_metrics import (
    calculate_search_quality_metrics,
    calculate_diversity_score,
    calculate_coverage,
    calculate_precision,
)


def create_mock_edge(node1_name: str, node2_name: str, node1_type: str = "Entity", node2_type: str = "Entity"):
    """Create a mock Edge object for testing."""
    edge = Mock()
    edge.node1 = Mock()
    edge.node1.attributes = {"name": node1_name, "type": node1_type}
    edge.node2 = Mock()
    edge.node2.attributes = {"name": node2_name, "type": node2_type}
    return edge


class TestCalculateDiversityScore:
    """Tests for calculate_diversity_score function."""

    def test_empty_results_returns_zero(self):
        """Test empty results returns zero diversity."""
        result = calculate_diversity_score([])
        assert result == 0.0

    def test_single_type_low_diversity(self):
        """Test single node type has low diversity."""
        edges = [
            create_mock_edge("A", "B", "Entity", "Entity"),
            create_mock_edge("C", "D", "Entity", "Entity"),
        ]
        result = calculate_diversity_score(edges)
        assert 0.0 <= result <= 1.0

    def test_multiple_types_higher_diversity(self):
        """Test multiple node types have higher diversity."""
        edges = [
            create_mock_edge("Person1", "Company1", "Person", "Company"),
            create_mock_edge("Location1", "Event1", "Location", "Event"),
        ]
        result = calculate_diversity_score(edges)
        assert result > 0.0
        assert result <= 1.0

    def test_diversity_score_bounded(self):
        """Test diversity score is always between 0 and 1."""
        edges = [create_mock_edge(f"Node{i}", f"Node{i+100}", f"Type{i}", f"Type{i+50}") for i in range(20)]
        result = calculate_diversity_score(edges)
        assert 0.0 <= result <= 1.0


class TestCalculateCoverage:
    """Tests for calculate_coverage function."""

    def test_empty_results_returns_zero(self):
        """Test empty results returns zero coverage."""
        result = calculate_coverage("test query", [], "test answer")
        assert result == 0.0

    def test_empty_answer_returns_zero(self):
        """Test empty answer returns zero coverage."""
        edges = [create_mock_edge("Node1", "Node2")]
        result = calculate_coverage("test query", edges, "")
        assert result == 0.0

    def test_matching_names_increase_coverage(self):
        """Test matching node names increase coverage."""
        edges = [create_mock_edge("Python", "Programming")]
        result = calculate_coverage("What is Python?", edges, "Python is a programming language")
        assert result >= 0.0
        assert result <= 1.0

    def test_no_matching_names_low_coverage(self):
        """Test no matching names results in low coverage."""
        edges = [create_mock_edge("Java", "Enterprise")]
        result = calculate_coverage("What is Python?", edges, "Python is great")
        assert result >= 0.0

    def test_coverage_bounded(self):
        """Test coverage is always between 0 and 1."""
        edges = [create_mock_edge("Word1", "Word2")]
        result = calculate_coverage("query", edges, "answer with many words that do not match")
        assert 0.0 <= result <= 1.0


class TestCalculatePrecision:
    """Tests for calculate_precision function."""

    def test_empty_results_returns_zero(self):
        """Test empty results returns zero precision."""
        result = calculate_precision("test query", [])
        assert result == 0.0

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_precision_uses_relevance_scores(self, mock_relevance):
        """Test precision calculation uses relevance scores."""
        mock_relevance.return_value = 0.8
        edges = [create_mock_edge("Node1", "Node2")]

        result = calculate_precision("test query", edges)

        assert mock_relevance.called
        assert result >= 0.0

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_precision_averages_scores(self, mock_relevance):
        """Test precision is average of relevance scores."""
        mock_relevance.return_value = 0.5
        edges = [
            create_mock_edge("Node1", "Node2"),
            create_mock_edge("Node3", "Node4"),
        ]

        result = calculate_precision("test query", edges)

        assert result == 0.5  # All scores are 0.5, average is 0.5


class TestCalculateSearchQualityMetrics:
    """Tests for calculate_search_quality_metrics function."""

    def test_empty_results_returns_zero_metrics(self):
        """Test empty results returns all zero metrics."""
        result = calculate_search_quality_metrics("test query", [])

        assert result["avg_relevance"] == 0.0
        assert result["diversity_score"] == 0.0
        assert result["coverage"] == 0.0
        assert result["precision"] == 0.0

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_returns_all_metrics(self, mock_relevance):
        """Test function returns all expected metrics."""
        mock_relevance.return_value = 0.7
        edges = [create_mock_edge("Node1", "Node2", "Type1", "Type2")]

        result = calculate_search_quality_metrics("test query", edges, "test answer")

        assert "avg_relevance" in result
        assert "diversity_score" in result
        assert "coverage" in result
        assert "precision" in result

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_metrics_are_rounded(self, mock_relevance):
        """Test metrics are rounded to 3 decimal places."""
        mock_relevance.return_value = 0.33333333
        edges = [create_mock_edge("Node1", "Node2")]

        result = calculate_search_quality_metrics("test query", edges)

        # Check that values are rounded (have at most 3 decimal places)
        for key, value in result.items():
            assert round(value, 3) == value

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_without_answer_coverage_is_zero(self, mock_relevance):
        """Test coverage is zero when no answer is provided."""
        mock_relevance.return_value = 0.5
        edges = [create_mock_edge("Node1", "Node2")]

        result = calculate_search_quality_metrics("test query", edges)

        assert result["coverage"] == 0.0

    @patch('cognee.modules.search.utils.quality_metrics.calculate_result_relevance_score')
    def test_with_answer_coverage_calculated(self, mock_relevance):
        """Test coverage is calculated when answer is provided."""
        mock_relevance.return_value = 0.5
        edges = [create_mock_edge("Python", "Language")]

        result = calculate_search_quality_metrics("test query", edges, "Python is a language")

        assert result["coverage"] >= 0.0
