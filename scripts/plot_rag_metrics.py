"""
Regenerates the two-panel evaluation chart for Chapter 4:
Panel 1: Retrieval Quality (Semantic vs BM25 baseline, n = 15, k = 2, order-shuffled)
Panel 2: Generation Quality across 3 Distinct Organizations (Judge A vs Judge B, n = 14 clean)

Numbers are read from scripts/rag_eval_results.json when available (produced by
`evaluate_rag.py --output-json scripts/rag_eval_results.json`).
Hard-coded values are used as fallback so the script always works standalone.
"""
import os
import json
import matplotlib.pyplot as plt
import numpy as np

# Set consistent typography
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11

# ── Load retrieval numbers from JSON if available ────────────────────────────
_RESULTS_JSON = os.path.join(os.path.dirname(__file__), "rag_eval_results.json")

# Hard-coded fallback (matches published report Table 4.1 / Table 4.2)
sem_scores  = [60.0, 96.7, 72.2, 100.0, 93.3]  # P@2, R@2, F1@2, HR@2, MRR×100
bm25_scores = [56.7, 93.3, 68.9, 100.0, 93.3]
judge_a     = [100.0, 98.6]
judge_b     = [100.0, 98.6]
n_clean_str = "n = 14 clean"

if os.path.isfile(_RESULTS_JSON):
    try:
        with open(_RESULTS_JSON, encoding="utf-8") as fh:
            _data = json.load(fh)
        if "retrieval" in _data:
            _sem  = _data["retrieval"]["semantic"]
            _bm25 = _data["retrieval"]["bm25_ws"]
            sem_scores  = [_sem["p"],  _sem["r"],  _sem["f1"],  _sem["hr"],  _sem["mrr"] * 100]
            bm25_scores = [_bm25["p"], _bm25["r"], _bm25["f1"], _bm25["hr"], _bm25["mrr"] * 100]
            print(f"[plot] Loaded retrieval numbers from {_RESULTS_JSON}")
        
        # Generation summary loading
        if "generation" in _data and isinstance(_data["generation"], dict):
            _gen_summary = _data["generation"].get("summary", {})
            if _gen_summary and "ja_faith" in _gen_summary:
                judge_a = [_gen_summary["ja_faith"], _gen_summary["ja_relev"] * 20.0]
                judge_b = [_gen_summary["jb_faith"], _gen_summary["jb_relev"] * 20.0]
                n_clean_val = _gen_summary.get("n_clean", 14)
                n_clean_str = f"n = {n_clean_val} clean"
                print(f"[plot] Loaded generation numbers from {_RESULTS_JSON}: Judge A={judge_a}, Judge B={judge_b} ({n_clean_str})")
    except Exception as exc:
        print(f"[plot] Warning: could not read {_RESULTS_JSON}: {exc} — using fallback values")
else:
    print(f"[plot] {_RESULTS_JSON} not found — using hard-coded fallback values")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), dpi=300)

c_blue   = '#4672c4'
c_orange = '#c5703f'
c_green  = '#4a9968'
c_brown  = '#996345'

# ── Panel 1: Retrieval Quality ──────────────────────────
metrics_ret = ['Precision@2', 'Recall@2', 'F1@2', 'Hit Rate@2', 'MRR (x100)']

x1 = np.arange(len(metrics_ret))
width = 0.32

rects1 = ax1.bar(x1 - width/2, sem_scores,  width, label='Semantic (Embedding)', color=c_blue,   edgecolor='black', linewidth=0.8)
rects2 = ax1.bar(x1 + width/2, bm25_scores, width, label='BM25 Baseline',        color=c_orange, edgecolor='black', linewidth=0.8)

ax1.set_title('Retrieval Quality (n = 15, k = 2, order-shuffled)', fontsize=14, pad=12)
ax1.set_ylabel('Score (%) -- MRR shown x100', fontsize=12)
ax1.set_xticks(x1)
ax1.set_xticklabels(metrics_ret, rotation=15, fontsize=10)
ax1.set_ylim(0, 115)
ax1.set_yticks(np.arange(0, 101, 20))
ax1.grid(axis='y', linestyle='--', alpha=0.5)
ax1.set_axisbelow(True)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# Legend positioned below plot to avoid covering any labels
ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=True, framealpha=0.9, fontsize=10)

# Separate labels cleanly, especially on Hit Rate@2
for i, rect in enumerate(rects1):
    h = rect.get_height()
    offset_x = -3 if i == 3 else 0
    ax1.annotate(f'{h:.1f}',
                 xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(offset_x, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=8.8)

for i, rect in enumerate(rects2):
    h = rect.get_height()
    offset_x = 3 if i == 3 else 0
    ax1.annotate(f'{h:.1f}',
                 xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(offset_x, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=8.8)

# ── Panel 2: Generation Quality ──────────────────────────
metrics_gen = ['Faithfulness', 'Relevancy (x20)']

x2 = np.arange(len(metrics_gen))
width2 = 0.34

rects3 = ax2.bar(x2 - width2/2, judge_a, width2, label='Judge A (OpenAI gpt-oss-120b)',  color=c_green, edgecolor='black', linewidth=0.8)
rects4 = ax2.bar(x2 + width2/2, judge_b, width2, label='Judge B (SDAIA/IBM allam-2-7b)', color=c_brown, edgecolor='black', linewidth=0.8)

ax2.set_title(f'Generation Quality: 3 Distinct Organizations ({n_clean_str})', fontsize=14, pad=12)
ax2.set_ylabel('Score (%) -- Relevancy shown ×20 (out of 100)', fontsize=12)
ax2.set_xticks(x2)
ax2.set_xticklabels(metrics_gen, fontsize=11)
ax2.set_ylim(0, 115)
ax2.set_yticks(np.arange(0, 101, 20))
ax2.grid(axis='y', linestyle='--', alpha=0.5)
ax2.set_axisbelow(True)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

# Legend positioned below plot to avoid covering any labels
ax2.legend(loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=True, framealpha=0.9, fontsize=10)

for rect in rects3:
    h = rect.get_height()
    ax2.annotate(f'{h:.1f}',
                 xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(0, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=9.5)

for rect in rects4:
    h = rect.get_height()
    ax2.annotate(f'{h:.1f}',
                 xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(0, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=9.5)

plt.tight_layout()

# ── Save image ───────────────────────────────────────────────────────────────
# Output path given by argv with a repository-relative default (Item F)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
default_output = os.path.join(_SCRIPT_DIR, "rag_eval_metrics.png")
output_path = sys.argv[1] if len(sys.argv) > 1 else default_output

try:
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved chart to: {output_path}")
except Exception as e:
    print(f"Error saving to {output_path}: {e}")
