"""
Tests for the smart AI routing and RAG services.

Run: pytest tests/test_smart_services.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.complexity_analyzer import ComplexityAnalyzer, ComplexityScore


class TestComplexityAnalyzer:
    """Test complexity scoring and routing decisions."""

    def setup_method(self):
        self.analyzer = ComplexityAnalyzer()

    def test_simple_text_routes_to_qwen(self):
        """Simple text should score low and route to Qwen."""
        simple = "We licensed catalyst technology from XYZ Corp for 3% royalty."
        score = self.analyzer.analyze_text(simple)
        assert score.total_score <= 3, f"Expected <=3, got {score.total_score}"
        assert score.get_routing_decision() == "qwen_only"

    def test_complex_text_routes_to_claude(self):
        """Complex legal text should score high and route to Claude."""
        complex_text = """
        Pursuant to Section 4.2 of the Master License Agreement dated January 15, 2024,
        subject to FDA approval and notwithstanding any force majeure events as defined
        in Article 12, royalty payments shall range from 2.5% to 4.5% of Net Sales,
        as defined in Exhibit A, contingent upon achievement of commercially reasonable
        milestones not to exceed $10,000,000 in aggregate. The licensee shall have
        exclusive rights in the territory of North America, subject to the licensor's
        retained right to sublicense to third parties for research purposes only.
        Indemnification obligations shall survive termination for a period of 5 years.
        In the event of a material breach, the non-breaching party may terminate upon
        60 days written notice, provided that such breach remains uncured during the
        cure period. Governing law shall be the State of Delaware. Arbitration shall
        be conducted pursuant to the rules of the American Arbitration Association.
        Intellectual property rights in any improvements shall be jointly owned.
        """
        score = self.analyzer.analyze_text(complex_text)
        assert score.total_score >= 7, f"Expected >=7, got {score.total_score}"
        assert score.get_routing_decision() == "claude_direct"

    def test_medium_text_routes_to_fallback(self):
        """Medium complexity text should route to qwen_with_fallback."""
        medium = """
        The Company entered into a license agreement with ABC Corp in 2023 for
        the use of proprietary semiconductor manufacturing technology. Under the
        terms of the agreement, the Company will pay a royalty of 3.5% of net sales
        and an upfront payment of $5 million. The license is exclusive in the
        United States for a term of 10 years, subject to certain performance milestones.
        Pursuant to Section 3.1, the licensee shall indemnify the licensor against
        any claims of patent infringement. The territory covers North America and
        Europe, notwithstanding certain restricted regions. In the event of a material
        breach, the agreement may be terminated with 90 days notice. The royalty
        rate shall be adjusted annually based on the Consumer Price Index, with a
        minimum annual payment of $500,000 and a maximum of $2,000,000 per year.
        """
        score = self.analyzer.analyze_text(medium)
        assert 4 <= score.total_score <= 6, f"Expected 4-6, got {score.total_score}"
        assert score.get_routing_decision() == "qwen_with_fallback"

    def test_empty_text(self):
        """Empty text should score 0."""
        score = self.analyzer.analyze_text("")
        assert score.total_score == 0
        assert score.get_routing_decision() == "qwen_only"

    def test_score_components(self):
        """Verify individual score components are within expected ranges."""
        text = "Sample contract text with royalty of 5% and $1 million upfront."
        score = self.analyzer.analyze_text(text)
        assert 0 <= score.length_factor <= 2
        assert 0 <= score.legal_density <= 3
        assert 0 <= score.numeric_complexity <= 3
        assert 0 <= score.ambiguity_factor <= 2
        assert score.total_score <= 10

    def test_complexity_score_dataclass(self):
        """Test ComplexityScore routing thresholds."""
        low = ComplexityScore(total_score=2, length_factor=0, legal_density=1, numeric_complexity=1, ambiguity_factor=0)
        assert low.get_routing_decision() == "qwen_only"

        mid = ComplexityScore(total_score=5, length_factor=1, legal_density=2, numeric_complexity=1, ambiguity_factor=1)
        assert mid.get_routing_decision() == "qwen_with_fallback"

        high = ComplexityScore(total_score=8, length_factor=2, legal_density=3, numeric_complexity=2, ambiguity_factor=1)
        assert high.get_routing_decision() == "claude_direct"


class TestAIRouterUnit:
    """Unit tests for AIRouter (no external dependencies required)."""

    def test_router_import(self):
        """AI Router should be importable."""
        from services.ai_router import AIRouter, QwenProcessor, ClaudeProcessor, CostTracker
        assert AIRouter is not None

    def test_cost_tracker_init(self):
        """CostTracker should initialize without errors."""
        from services.ai_router import CostTracker
        tracker = CostTracker(db_path=":memory:")
        # Should not raise


class TestRAGEngineUnit:
    """Unit tests for RAG Engine (import and structure only)."""

    def test_rag_import(self):
        """RAG Engine should be importable."""
        from services.rag_engine import RAGEngine
        assert RAGEngine is not None

    def test_build_agreement_text(self):
        """Test the helper that builds searchable text from agreement rows."""
        from services.rag_engine import RAGEngine
        row = {
            "company": "Acme Refining",
            "licensor_name": "Generic Catalyst Inc.",
            "licensee_name": "Example Petrochem",
            "tech_name": "Platforming",
            "tech_category": "Energy",
            "royalty_rate": 3.5,
            "royalty_unit": "%",
            "upfront_amount": 5000000,
            "territory": "Global",
            "reasoning": "Catalyst technology license for refinery operations",
        }
        text = RAGEngine._build_agreement_text(row)
        assert "Acme Refining" in text
        assert "UOP LLC" in text
        assert "3.5%" in text
        assert "5,000,000" in text


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
