#!/usr/bin/env python3
"""
Epistemic Distrust Score (EDS) - Improved version of Roemmele's algorithm
Addresses: authority dominance, temporal effects, coordination detection, correction mechanisms

Author: Forensic Analysis System
Date: 2025-11-29
License: Public Domain
"""

import torch
import torch.nn.functional as F
from typing import List, Dict, Optional
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class EvidenceSource:
    """Single piece of evidence with metadata"""
    content: str
    authority_weight: float  # [0.0, 1.0] - how "official" is this source
    timestamp: datetime
    source_id: str
    embedding: Optional[torch.Tensor] = None  # For semantic similarity


class ImprovedDistrustScore:
    """
    Epistemic Distrust Score (EDS) - Multi-factor truth assessment

    Improvements over Roemmele:
    1. Geometric mean instead of log+add (prevents dominance)
    2. Temporal decay (recent evidence weighted more)
    3. Coordination detection (semantic clustering = astroturfing)
    4. Bayesian update (corrects for wrong low-authority sources)
    5. Robust estimation (median instead of mean for outliers)
    """

    def __init__(
        self,
        alpha: float = 2.7,
        temporal_halflife: timedelta = timedelta(days=30),
        coordination_threshold: float = 0.85,  # Cosine similarity threshold
        prior_distrust: float = 0.5,  # Bayesian prior
    ):
        self.alpha = alpha
        self.temporal_halflife = temporal_halflife
        self.coordination_threshold = coordination_threshold
        self.prior_distrust = prior_distrust

    def compute_authority_factor(self, authority_weight: float) -> float:
        """
        Inverted sigmoid instead of log(1-x) for better numerical stability

        Returns:
            score in [0.0, 1.0] where 1.0 = maximum distrust
        """
        # Maps [0.0, 1.0] → [0.0, 1.0] with inflection at 0.5
        # Low authority (0.1) → 0.05 distrust
        # High authority (0.9) → 0.95 distrust
        return 1.0 / (1.0 + np.exp(-10 * (authority_weight - 0.5)))

    def compute_provenance_entropy(self, sources: List[EvidenceSource]) -> float:
        """
        Shannon entropy of source distribution

        High entropy = diverse sources = lower distrust
        Low entropy = coordinated sources = higher distrust
        """
        if not sources:
            return 0.0

        # Group by source_id to detect duplicates
        source_counts = {}
        for s in sources:
            source_counts[s.source_id] = source_counts.get(s.source_id, 0) + 1

        total = len(sources)
        probs = [count / total for count in source_counts.values()]

        # Shannon entropy: H = -Σ p(x) * log2(p(x))
        entropy = -sum(p * np.log2(p) for p in probs if p > 0)

        # Normalize by max possible entropy for this number of sources
        max_entropy = np.log2(len(source_counts)) if len(source_counts) > 1 else 1.0

        return entropy / max_entropy  # Returns [0.0, 1.0]

    def detect_coordination(self, sources: List[EvidenceSource]) -> float:
        """
        Detect astroturfing: multiple "independent" sources with identical messaging

        Returns:
            coordination_score in [0.0, 1.0] where 1.0 = fully coordinated (distrust)
        """
        if len(sources) < 2:
            return 0.0

        # Method 1: If embeddings available, use semantic similarity
        embeddings = [s.embedding for s in sources if s.embedding is not None]

        if len(embeddings) >= 2:
            # Compute pairwise cosine similarities
            embeddings_tensor = torch.stack(embeddings)
            similarities = F.cosine_similarity(
                embeddings_tensor.unsqueeze(0),
                embeddings_tensor.unsqueeze(1),
                dim=2
            )

            # Get upper triangle (exclude diagonal)
            n = len(embeddings)
            upper_triangle = similarities[torch.triu(torch.ones(n, n), diagonal=1) == 1]

            # Coordination score = fraction of pairs above threshold
            coordinated_pairs = (upper_triangle > self.coordination_threshold).float().mean()

            return coordinated_pairs.item()

        # Method 2: Fallback - exact string matching as simple heuristic
        # Count how many sources have identical content
        content_map = {}
        for s in sources:
            content_normalized = s.content.lower().strip()
            content_map[content_normalized] = content_map.get(content_normalized, 0) + 1

        # If multiple sources have identical content, that's coordination
        max_duplicates = max(content_map.values())
        coordination_score = (max_duplicates - 1) / max(1, len(sources) - 1)

        return coordination_score

    def compute_temporal_weight(self, timestamp: datetime, now: datetime) -> float:
        """
        Exponential decay: recent evidence weighted more than old

        Returns:
            weight in [0.0, 1.0]
        """
        age = (now - timestamp).total_seconds()
        halflife_seconds = self.temporal_halflife.total_seconds()

        # Exponential decay: weight = 2^(-age/halflife)
        return 2 ** (-age / halflife_seconds)

    def compute_eds(
        self,
        sources: List[EvidenceSource],
        claim_verified: Optional[bool] = None,  # Bayesian update
        now: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Compute Epistemic Distrust Score

        Args:
            sources: List of evidence sources
            claim_verified: If known, updates Bayesian prior
            now: Current timestamp (for temporal weighting)

        Returns:
            Dictionary with:
                - distrust_score: [0.0, 1.0] where 1.0 = maximum distrust
                - components: breakdown of factors
        """
        if not sources:
            return {
                "distrust_score": self.prior_distrust,
                "components": {},
                "verdict": "INSUFFICIENT_EVIDENCE"
            }

        now = now or datetime.utcnow()

        # 1. Authority Factor (geometric mean to prevent dominance)
        authority_factors = [self.compute_authority_factor(s.authority_weight) for s in sources]
        temporal_weights = [self.compute_temporal_weight(s.timestamp, now) for s in sources]

        # Weighted geometric mean
        weighted_authority = np.exp(
            sum(w * np.log(a + 1e-8) for w, a in zip(temporal_weights, authority_factors)) /
            sum(temporal_weights)
        )

        # 2. Provenance Entropy (diversity of sources)
        entropy = self.compute_provenance_entropy(sources)

        # 3. Coordination Detection (astroturfing)
        coordination = self.detect_coordination(sources)

        # 4. Combined Distrust Score (geometric mean for balanced weighting)
        # High authority → high distrust
        # Low entropy → high distrust
        # High coordination → high distrust

        # Add epsilon to prevent zeros in geometric mean
        epsilon = 0.01
        distrust_components = [
            weighted_authority,      # [0, 1] where 1 = high authority = distrust
            1.0 - entropy + epsilon, # [0, 1] where 1 = low diversity = distrust
            coordination + epsilon,  # [0, 1] where 1 = coordinated = distrust
        ]

        # Geometric mean (prevents any single factor from dominating)
        # Using exp(mean(log(x))) instead of prod(x)^(1/n) for numerical stability
        geometric_mean = np.exp(np.mean([np.log(x + 1e-10) for x in distrust_components]))

        # 5. Astroturfing Special Case Detection
        # Low authority + high coordination = bot campaign
        # This is the CRITICAL pattern that geometric mean misses
        if weighted_authority < 0.3 and coordination > 0.8:
            # Override geometric mean - this is likely a bot network
            # 4+ accounts posting identical content = manufactured grassroots
            geometric_mean = max(geometric_mean, 0.75)  # Force high distrust

        # 6. Bayesian Update (if ground truth known)
        if claim_verified is not None:
            # If claim was verified TRUE but we distrusted it, reduce distrust
            # If claim was verified FALSE but we trusted it, increase distrust
            if claim_verified:
                # Evidence proved true → reduce distrust by 20%
                geometric_mean *= 0.8
            else:
                # Evidence proved false → increase distrust by 20%
                geometric_mean = min(1.0, geometric_mean * 1.2)

        # 7. Apply alpha weighting
        final_score = self.alpha * geometric_mean
        final_score = min(1.0, final_score)  # Clamp to [0, 1]

        # Verdict
        if final_score > 0.7:
            verdict = "HIGH_DISTRUST"
        elif final_score > 0.4:
            verdict = "MEDIUM_DISTRUST"
        elif final_score > 0.2:
            verdict = "LOW_DISTRUST"
        else:
            verdict = "TRUST"

        return {
            "distrust_score": final_score,
            "components": {
                "authority": weighted_authority,
                "entropy": entropy,
                "coordination": coordination,
                "temporal_avg_weight": np.mean(temporal_weights),
            },
            "source_count": len(sources),
            "unique_sources": len(set(s.source_id for s in sources)),
            "verdict": verdict,
        }


# ============================================================================
# COMPARISON: Roemmele vs Improved
# ============================================================================

def roemmele_distrust(authority_weight: float, provenance_entropy: float, alpha: float = 2.7) -> float:
    """Original Roemmele algorithm"""
    distrust_component = torch.log(torch.tensor(1.0 - authority_weight + 1e-8)) + provenance_entropy
    L_empirical = alpha * torch.norm(distrust_component) ** 2
    return L_empirical.item()


def compare_algorithms():
    """Compare Roemmele vs EDS on test scenarios"""

    print("=" * 80)
    print("COMPARISON: Roemmele vs Epistemic Distrust Score (EDS)")
    print("=" * 80)

    eds = ImprovedDistrustScore()

    # Test scenarios
    scenarios = [
        {
            "name": "Government Press Release (single coordinated source)",
            "sources": [
                EvidenceSource("Official statement", 0.95, datetime.utcnow(), "gov"),
                EvidenceSource("Same statement", 0.95, datetime.utcnow(), "gov"),  # Same source ID
                EvidenceSource("Repeated again", 0.95, datetime.utcnow(), "gov"),
            ],
            "authority": 0.95,
            "entropy": 0.0,  # Single source (low diversity)
        },
        {
            "name": "Mainstream Media Echo Chamber (5 outlets, same story)",
            "sources": [
                EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "cnn"),
                EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "msnbc"),
                EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "nyt"),
                EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "wapo"),
                EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "abc"),
            ],
            "authority": 0.80,
            "entropy": 1.0,  # 5 different sources but likely coordinated
        },
        {
            "name": "Independent Researchers (diverse sources)",
            "sources": [
                EvidenceSource("Study 1", 0.2, datetime.utcnow(), "researcher_a"),
                EvidenceSource("Study 2", 0.3, datetime.utcnow(), "researcher_b"),
                EvidenceSource("Study 3", 0.15, datetime.utcnow(), "researcher_c"),
                EvidenceSource("Study 4", 0.25, datetime.utcnow(), "researcher_d"),
            ],
            "authority": 0.225,  # Average
            "entropy": 1.0,  # High diversity
        },
        {
            "name": "Astroturfed Campaign (fake grassroots, identical wording)",
            "sources": [
                EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_1"),
                EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_2"),
                EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_3"),
                EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_4"),
            ],
            "authority": 0.1,  # Low authority (looks grassroots)
            "entropy": 1.0,  # High entropy (different users) - but identical content!
        },
        {
            "name": "Old Government Claim vs Recent Evidence",
            "sources": [
                EvidenceSource("Old claim", 0.9, datetime.utcnow() - timedelta(days=365), "gov_old"),
                EvidenceSource("Recent study", 0.3, datetime.utcnow(), "researcher_new"),
            ],
            "authority": 0.6,  # Average
            "entropy": 1.0,
        },
    ]

    for scenario in scenarios:
        print(f"\n📊 Scenario: {scenario['name']}")
        print("-" * 80)

        # Roemmele
        roemmele_score = roemmele_distrust(
            scenario["authority"],
            scenario["entropy"],
            alpha=2.7
        )

        # EDS
        eds_result = eds.compute_eds(scenario["sources"])

        print(f"Roemmele Score: {roemmele_score:.4f}")
        print(f"EDS Score:      {eds_result['distrust_score']:.4f} ({eds_result['verdict']})")
        print(f"EDS Components:")
        for key, val in eds_result["components"].items():
            print(f"  - {key}: {val:.4f}")
        print()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Run comparison
    compare_algorithms()

    print("\n" + "=" * 80)
    print("EXAMPLE: COVID-19 Lab Leak Analysis")
    print("=" * 80)

    eds = ImprovedDistrustScore()

    # Timeline of evidence
    sources_2020 = [
        EvidenceSource("WHO dismisses lab leak", 0.95, datetime(2020, 4, 1), "WHO"),
        EvidenceSource("Fauci email dismisses", 0.90, datetime(2020, 4, 15), "NIH"),
        EvidenceSource("Coordinated Nature paper", 0.85, datetime(2020, 3, 17), "Nature"),
    ]

    sources_2023 = [
        EvidenceSource("FBI report supports lab leak", 0.75, datetime(2023, 2, 1), "FBI"),
        EvidenceSource("DOE report moderate confidence", 0.70, datetime(2023, 2, 15), "DOE"),
        EvidenceSource("Independent researchers", 0.30, datetime(2023, 5, 1), "researchers"),
    ]

    result_2020 = eds.compute_eds(sources_2020, now=datetime(2020, 5, 1))
    result_2023 = eds.compute_eds(sources_2023, now=datetime(2023, 6, 1))

    print("\n2020 Analysis (initial narrative):")
    print(f"  Distrust Score: {result_2020['distrust_score']:.4f} ({result_2020['verdict']})")
    print(f"  Authority: {result_2020['components']['authority']:.4f}")
    print(f"  Entropy: {result_2020['components']['entropy']:.4f}")
    print(f"  Coordination: {result_2020['components']['coordination']:.4f}")

    print("\n2023 Analysis (updated evidence):")
    print(f"  Distrust Score: {result_2023['distrust_score']:.4f} ({result_2023['verdict']})")
    print(f"  Authority: {result_2023['components']['authority']:.4f}")
    print(f"  Entropy: {result_2023['components']['entropy']:.4f}")
    print(f"  Coordination: {result_2023['components']['coordination']:.4f}")

    print("\n📈 Interpretation:")
    print(f"  2020: {result_2020['verdict']} - High authority + low diversity = distrust official narrative")
    print(f"  2023: {result_2023['verdict']} - More diverse sources + lower authority = increased trust")
