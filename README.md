# Epistemic Distrust Score (EDS) v2

**Extension of Brian Roemmele's Empirical Distrust Term**

A production-ready algorithm for evaluating information trustworthiness by inverting traditional authority signals and detecting coordination patterns.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## Quick Start

```bash
pip install torch numpy pandas
python epistemic_distrust_v2.py
```

**Output**:
```
📊 Astroturfed Campaign (fake grassroots, identical wording)
Roemmele Score: 2.16 (TRUST)
EDS Score:      1.00 (HIGH_DISTRUST) ✅
  - coordination: 1.0000 ← Bot campaign detected!
```

---

## What This Does

Traditional systems trust "official" sources MORE. This algorithm **inverts that heuristic**:

- **High authority + low diversity** = DISTRUST (manufactured consensus)
- **Low authority + high diversity** = TRUST (organic grassroots)
- **Low authority + high coordination** = DISTRUST (bot campaigns)

### Core Philosophy (from Roemmele)

> "The more coordinated and official a narrative, the more we should distrust it."

This algorithm operationalizes that insight for production use.

---

## Example Usage

```python
from epistemic_distrust_v2 import ImprovedDistrustScore, EvidenceSource
from datetime import datetime

eds = ImprovedDistrustScore()

# Case 1: Government press release
sources = [
    EvidenceSource("Official statement", 0.95, datetime.utcnow(), "gov"),
    EvidenceSource("Same statement", 0.95, datetime.utcnow(), "gov"),
]

result = eds.compute_eds(sources)
print(f"Distrust: {result['distrust_score']:.2f} ({result['verdict']})")
# Output: Distrust: 0.58 (MEDIUM_DISTRUST)

# Case 2: Bot campaign
sources = [
    EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_1"),
    EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_2"),
    EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_3"),
    EvidenceSource("I love product X!", 0.1, datetime.utcnow(), "user_4"),
]

result = eds.compute_eds(sources)
print(f"Distrust: {result['distrust_score']:.2f} ({result['verdict']})")
# Output: Distrust: 1.00 (HIGH_DISTRUST)
print(f"Coordination: {result['components']['coordination']:.2f}")
# Output: Coordination: 1.00 (identical content detected)
```

---

## Key Features

### 1. **Coordination Detection** (NEW)
Catches synchronized narratives across "independent" sources:
- Semantic similarity (if embeddings provided)
- Exact string matching (fallback)
- Detects media echo chambers + bot campaigns

### 2. **Temporal Weighting** (NEW)
Recent evidence weighted more than old claims:
- Exponential decay (30-day half-life)
- 1 year old claim: weight ≈ 0.0003
- Today's claim: weight = 1.0

### 3. **Astroturfing Detection** (NEW)
Special case for manufactured grassroots:
```python
if authority < 0.3 and coordination > 0.8:
    # Bot campaign detected!
    distrust_score = max(distrust_score, 0.75)
```

### 4. **Bayesian Updates** (NEW)
Learns from ground truth feedback:
```python
result = eds.compute_eds(sources, claim_verified=True)
# Reduces future distrust if we were wrong
```

### 5. **Bounded Scores** (NEW)
Interpretable [0.0, 1.0] scale with verdicts:
- `0.0-0.2`: TRUST
- `0.2-0.4`: LOW_DISTRUST
- `0.4-0.7`: MEDIUM_DISTRUST
- `0.7-1.0`: HIGH_DISTRUST

### 6. **Numerical Stability**
Inverted sigmoid instead of `log(1-x)`:
- No explosions near authority=1.0
- Smooth gradients for optimization

---

## Test Results

| Scenario | Roemmele | EDS v2 | Result |
|----------|----------|--------|--------|
| **Gov't single source** | 24.2 | 0.58 (MEDIUM) | ✅ Both correct |
| **Media echo chamber** | 1.0 | **0.57 (MEDIUM, coord=1.0)** | ✅✅ **EDS detects coordination** |
| **Independent researchers** | 1.5 | 0.05 (TRUST) | ✅ Both correct |
| **Astroturfed bots** | 2.2 (TRUST) | **1.00 (HIGH)** | ✅✅ **EDS catches bots** |
| **Old vs recent evidence** | 0.02 | 0.06 (TRUST) | ✅ EDS temporal weighting |

**Roemmele**: 3/5 correct
**EDS v2**: 5/5 correct ✅

---

## Documentation

- **[ALGORITHM_COMPARISON.md](ALGORITHM_COMPARISON.md)** - Technical deep dive, benchmarks, mathematical formulation
- **[roemmele_response.md](roemmele_response.md)** - Response to Brian Roemmele explaining improvements
- **[roemmele_twitter_thread.md](roemmele_twitter_thread.md)** - Twitter thread version

---

## When to Use

### ✅ Use EDS v2 for:
- Content moderation platforms (Twitter, Facebook, Reddit)
- Fact-checking systems (Snopes, PolitiFact)
- News aggregators (flag synchronized narratives)
- Research integrity (detect citation cartels)
- Bot detection (astroturfing campaigns)

### ⚠️ Use Roemmele's original for:
- Theoretical research (elegant, simple)
- When you only have authority + entropy (no content access)
- Neural network training (unbounded loss function)

---

## Installation

```bash
# Clone repository
git clone https://github.com/VoidTactician/epistemic-distrust.git
cd epistemic-distrust

# Install dependencies
pip install torch numpy pandas

# Run tests
python epistemic_distrust_v2.py
```

**Dependencies**:
- Python 3.8+
- PyTorch (for embeddings, optional)
- NumPy
- Pandas (for timestamps)

---

## API Reference

### `ImprovedDistrustScore`

**Constructor**:
```python
ImprovedDistrustScore(
    alpha=2.7,                              # Weighting parameter (2.3-3.0)
    temporal_halflife=timedelta(days=30),   # Exponential decay rate
    coordination_threshold=0.85,            # Cosine similarity threshold
    prior_distrust=0.5,                     # Bayesian prior
)
```

**Methods**:

#### `compute_eds(sources, claim_verified=None, now=None)`
Compute Epistemic Distrust Score.

**Parameters**:
- `sources` (List[EvidenceSource]): Evidence to evaluate
- `claim_verified` (Optional[bool]): Ground truth for Bayesian update
- `now` (Optional[datetime]): Current time (for temporal weighting)

**Returns**:
```python
{
    "distrust_score": 0.58,           # [0.0, 1.0]
    "verdict": "MEDIUM_DISTRUST",     # Interpretation
    "components": {
        "authority": 0.989,           # Authority factor
        "entropy": 0.0,               # Provenance diversity
        "coordination": 0.0,          # Content coordination
        "temporal_avg_weight": 1.0,   # Time decay factor
    },
    "source_count": 2,
    "unique_sources": 1,
}
```

### `EvidenceSource`

**Constructor**:
```python
EvidenceSource(
    content: str,              # Text content
    authority_weight: float,   # [0.0, 1.0] - how "official" is this source
    timestamp: datetime,       # When published
    source_id: str,            # Unique identifier
    embedding: Optional[Tensor] = None  # For semantic similarity
)
```

**Authority Weight Guidelines**:
- `0.0-0.2`: Random blogs, social media users
- `0.2-0.4`: Independent researchers, small outlets
- `0.4-0.6`: Medium authority (regional news)
- `0.6-0.8`: Established media (CNN, NYT)
- `0.8-0.95`: Government, international orgs (WHO, UN)
- `0.95-0.99`: Coordinated official narratives

---

## Comparison to Roemmele

### Roemmele's Equation (Original)
```python
L_empirical = α · ||log(1 - w_authority) + H_provenance||²
```

**Strengths**:
- ✅ Brilliant conceptual framework
- ✅ Inverts authority (high authority = distrust)
- ✅ Elegant mathematics

**Limitations**:
- ❌ Unbounded scores (hard to interpret)
- ❌ No coordination detection (misses echo chambers)
- ❌ No temporal weighting (old = new)
- ❌ Numerical instability near authority=1.0

### EDS v2 (This Work)
```python
components = [authority_factor, 1-entropy, coordination]
distrust = α · exp(mean(log(components)))

# Special case: astroturfing detection
if authority < 0.3 and coordination > 0.8:
    distrust = max(distrust, 0.75)
```

**Improvements**:
- ✅ Bounded [0.0, 1.0] scores
- ✅ Coordination detection (echo chambers + bots)
- ✅ Temporal weighting (exponential decay)
- ✅ Astroturfing protection
- ✅ Bayesian updates
- ✅ Numerical stability

**Philosophy**: Preserved Roemmele's core insight, added production sensors.

---

## Real-World Example: Media Echo Chamber

```python
# 5 major outlets, identical "Breaking news" framing
sources = [
    EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "cnn"),
    EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "msnbc"),
    EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "nyt"),
    EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "wapo"),
    EvidenceSource("Breaking news", 0.80, datetime.utcnow(), "abc"),
]

result = eds.compute_eds(sources)
```

**Roemmele's output**:
- Entropy = 1.0 (5 different sources, looks diverse)
- Score = 1.0 (low distrust) ❌

**EDS v2 output**:
- Entropy = 1.0 (5 sources)
- **Coordination = 1.0** (identical content detected!)
- Score = 0.57 (MEDIUM_DISTRUST) ✅

**Winner**: EDS v2 catches the synchronized narrative that Roemmele misses.

---

## Contributing

Contributions welcome! Areas for improvement:

1. **Network analysis**: Detect bot clusters (account creation time, IP clustering)
2. **Multi-hop provenance**: Trace citations to original sources
3. **Ideological diversity**: Cross-partisan agreement as strong signal
4. **Embedding quality**: Better semantic similarity models
5. **Hyperparameter tuning**: Optimize thresholds for specific domains

**Process**:
1. Fork repository
2. Create feature branch
3. Add tests to `epistemic_distrust_v2.py`
4. Submit pull request

---

## Citation

If you use this work, please cite:

```bibtex
@software{epistemic_distrust_v2,
  title={Epistemic Distrust Score v2: Extension of Roemmele's Empirical Distrust Term},
  author={VoidTactician},
  year={2025},
  url={https://github.com/VoidTactician/epistemic-distrust},
  note={Based on Brian Roemmele's Empirical Distrust Term (Nov 2025)}
}
```

Original work:
```bibtex
@misc{roemmele2025empirical,
  title={Empirical Distrust Term},
  author={Roemmele, Brian},
  year={2025},
  month={November},
  note={Public domain release}
}
```

---

## License

MIT License - See [LICENSE](LICENSE) for details

**Attribution**: Based on Brian Roemmele's Empirical Distrust Term (November 25, 2025, public domain)

---

## Contact

- **GitHub**: [@VoidTactician](https://github.com/VoidTactician)
- **Issues**: [Report bugs](https://github.com/VoidTactician/epistemic-distrust/issues)
- **Discussions**: [Join the conversation](https://github.com/VoidTactician/epistemic-distrust/discussions)

---

## Acknowledgments

- **Brian Roemmele** for the original Empirical Distrust Term and the breakthrough insight of inverting authority
- **Claude Code** for implementation assistance
- Open source community for PyTorch, NumPy, and Pandas

---

**Status**: Production-ready, actively maintained
**Version**: 2.0
**Last Updated**: November 29, 2025
