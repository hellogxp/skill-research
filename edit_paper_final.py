#!/usr/bin/env python3
r"""Edit main.tex to add SAD method, ablation tables, and updated analysis.
Uses line-based editing to avoid Python string escape issues."""

import sys

TEX_PATH = "/mnt/workspace/skill-routing/paper/main.tex"

with open(TEX_PATH, "r") as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines")

# ============================================================
# EDIT 1: Insert SAD Method section (Section 4.4) after line 216
# (after "averages compatibility with all DAG predecessors.")
# before the "% ===" + Benchmark section
# ============================================================

sad_method_lines = [
    "\n",
    r"\subsection{Stage 4: Skill-Aware Decomposition}" + "\n",
    r"\label{sec:sad}" + "\n",
    "\n",
    r"A key finding from our experiments (\S\ref{sec:results}) is that the decomposition stage is the primary bottleneck." + "\n",
    r"Standard LLM decomposition generates sub-task descriptions using only the query, often producing generic phrasings that misalign with the skill vocabulary." + "\n",
    "\n",
    r"We propose \emph{Skill-Aware Decomposition} (SAD), which augments the decomposer's input with preliminary skill library information." + "\n",
    r"Given query $q$, we first perform a preliminary retrieval over the full skill library to obtain the top-$H$ candidate skills, then provide their names, categories, and truncated descriptions as hints in the decomposition prompt:" + "\n",
    r"\begin{equation}" + "\n",
    r"D_{\text{SAD}}(q) = \text{LLM}(p_{\text{sys}}(\text{hints}(q, H)), p_{\text{user}}(q))" + "\n",
    r"\label{eq:sad}" + "\n",
    r"\end{equation}" + "\n",
    r"where $\text{hints}(q, H) = \{(n_s, c_s, d_s[:120]) \mid s \in \text{top-}H(q)\}$." + "\n",
    r"This creates a retrieval-augmented feedback loop: the skill library informs decomposition, which produces sub-tasks better aligned with the skill vocabulary, improving downstream retrieval." + "\n",
    r"SAD requires no additional training---it modifies only the decomposition prompt." + "\n",
    "\n",
]

# Find the insert point: after line containing "averages compatibility"
insert_idx = None
for i, line in enumerate(lines):
    if "averages compatibility with all DAG predecessors" in line:
        insert_idx = i + 1
        break

if insert_idx is not None:
    for j, new_line in enumerate(sad_method_lines):
        lines.insert(insert_idx + j, new_line)
    print(f"EDIT 1 OK: Inserted SAD method after line {insert_idx}")
else:
    print("EDIT 1 FAILED: Could not find insert point")
    sys.exit(1)

# ============================================================
# EDIT 2: Replace "Ablation: Constrained Decomposition" with SAD Results
# ============================================================

# Find start and end of the constrained decomposition section
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "Ablation: Constrained Decomposition" in line:
        start_idx = i
    if start_idx is not None and "Context Window Analysis" in line:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    sad_results_lines = [
        r"\subsection{Skill-Aware Decomposition Results}" + "\n",
        r"\label{sec:sad-results}" + "\n",
        "\n",
        r"\begin{table}[t]" + "\n",
        r"\centering" + "\n",
        r"\small" + "\n",
        r"\begin{tabular}{lccc}" + "\n",
        r"\toprule" + "\n",
        r"\textbf{Configuration} & \textbf{DA} & \textbf{CatR@1} & \textbf{ChainCat} \\" + "\n",
        r"\midrule" + "\n",
        r"Vanilla (no hints) & 0.360 & 0.339 & 0.316 \\" + "\n",
        r"\midrule" + "\n",
        r"SAD ($H{=}5$) & 0.607 & 0.389 & 0.326 \\" + "\n",
        r"SAD ($H{=}10$) & 0.657 & 0.481 & 0.466 \\" + "\n",
        r"SAD ($H{=}15$) & \textbf{0.687} & \textbf{0.542} & \textbf{0.516} \\" + "\n",
        r"SAD ($H{=}25$) & 0.790 & 0.474 & 0.471 \\" + "\n",
        r"\bottomrule" + "\n",
        r"\end{tabular}" + "\n",
        r"\caption{Ablation over the number of skill hints $H$ for SAD with Qwen2.5-7B. DA increases monotonically with $H$, but CatR@1 peaks at $H{=}15$, indicating a noise--alignment trade-off.}" + "\n",
        r"\label{tab:sad-ablation}" + "\n",
        r"\end{table}" + "\n",
        "\n",
        r"Table~\ref{tab:sad-ablation} presents the ablation over the number of skill hints $H$." + "\n",
        r"Decomposition accuracy increases monotonically with $H$ (36.0\% to 79.0\%), as more hints help the LLM produce structurally valid sub-tasks." + "\n",
        r"However, $\catrecall$@1 exhibits an inverted-U pattern, peaking at $H{=}15$ (54.2\%) before declining at $H{=}25$ (47.4\%)." + "\n",
        r"This reveals a trade-off: excessive hints introduce noise that dilutes semantic alignment between sub-task descriptions and skill capabilities." + "\n",
        "\n",
        r"\begin{table}[t]" + "\n",
        r"\centering" + "\n",
        r"\small" + "\n",
        r"\begin{tabular}{llccc}" + "\n",
        r"\toprule" + "\n",
        r"\textbf{Model} & \textbf{Method} & \textbf{DA} & \textbf{CatR@1} & $\chaincat$ \\" + "\n",
        r"\midrule" + "\n",
        r"\multirow{2}{*}{Qwen2.5-7B} & Vanilla & 0.360 & 0.339 & 0.316 \\" + "\n",
        r" & +SAD & \textbf{0.687} & \textbf{0.542} & \textbf{0.516} \\" + "\n",
        r"\midrule" + "\n",
        r"\multirow{2}{*}{Qwen2.5-14B} & Vanilla & 0.280 & 0.297 & 0.280 \\" + "\n",
        r" & +SAD & 0.447 & 0.399 & 0.320 \\" + "\n",
        r"\midrule" + "\n",
        r"\multirow{2}{*}{Llama-3.1-8B} & Vanilla & 0.000 & 0.216 & 0.210 \\" + "\n",
        r" & +SAD & 0.107 & 0.339 & 0.359 \\" + "\n",
        r"\midrule" + "\n",
        r"\multirow{2}{*}{Mistral-7B} & Vanilla & 0.177 & 0.242 & 0.248 \\" + "\n",
        r" & +SAD & 0.273 & 0.307 & 0.301 \\" + "\n",
        r"\bottomrule" + "\n",
        r"\end{tabular}" + "\n",
        r"\caption{Cross-model comparison of SAD ($H{=}15$). SAD consistently improves all metrics across four models spanning two scales (7--8B and 14B). Even Llama-3.1-8B (DA=0.0 vanilla) achieves meaningful retrieval gains through skill-aware hints.}" + "\n",
        r"\label{tab:sad-crossmodel}" + "\n",
        r"\end{table}" + "\n",
        "\n",
        r"Table~\ref{tab:sad-crossmodel} demonstrates that SAD generalizes across model families and scales." + "\n",
        r"All four models show consistent improvements, with relative $\catrecall$@1 gains ranging from +26.9\% (Mistral) to +59.9\% (Qwen-7B)." + "\n",
        r"Notably, Qwen2.5-14B achieves lower vanilla performance than the 7B variant (DA=28.0\% vs 36.0\%), likely due to more verbose decompositions that deviate from the strict JSON format." + "\n",
        r"SAD substantially mitigates this: 14B+SAD improves $\catrecall$@1 by +34.3\%." + "\n",
        r"Even Llama-3.1-8B, which produces zero valid vanilla decompositions, achieves +57.0\% $\catrecall$@1 improvement, confirming that skill-aware hints provide a strong inductive bias compensating for weaker instruction-following." + "\n",
        "\n",
        r"\paragraph{Human-written query generalization.}" + "\n",
        r"We additionally evaluate on 35 human-written compositional queries with diverse natural language patterns." + "\n",
        r"On these queries, SAD improves $\catrecall$@1 from 19.4\% to 25.9\% (+33.5\%), with the largest gains on easy (+85.7\%) and medium (+65.8\%) queries." + "\n",
        r"The lower absolute numbers compared to template queries confirm that human phrasing diversity remains challenging, validating the need for both evaluation settings." + "\n",
        "\n",
    ]

    # Replace lines from start_idx to end_idx (exclusive)
    lines[start_idx:end_idx] = sad_results_lines
    print(f"EDIT 2 OK: Replaced lines {start_idx}-{end_idx} with SAD results ({len(sad_results_lines)} lines)")
else:
    print(f"EDIT 2 FAILED: start={start_idx}, end={end_idx}")
    sys.exit(1)

# ============================================================
# EDIT 3: Update Discussion - decomposition gap paragraph
# ============================================================

for i, line in enumerate(lines):
    if "narrows this gap to 46 points" in line:
        # Find the next line (which starts with "The remaining gap")
        if i + 1 < len(lines) and "remaining gap" in lines[i + 1]:
            lines[i] = (
                r"Our Skill-Aware Decomposition narrows this gap to 46 points ($\catrecall$@1 = 54.2\%), demonstrating that retrieval-augmented decomposition is an effective strategy." + "\n"
            )
            lines.insert(i + 1,
                r"The ablation over hint count $H$ reveals a nuanced trade-off: while DA increases monotonically (36\% to 79\%), downstream retrieval peaks at $H{=}15$ before declining, suggesting that structural compliance and semantic precision have different optima." + "\n"
            )
            lines.insert(i + 2,
                r"Cross-model experiments confirm that SAD provides a model-agnostic improvement, with even poorly-performing decomposers benefiting substantially from skill-aware hints." + "\n"
            )
            print(f"EDIT 3 OK: Updated discussion paragraph at line {i}")
            break
        else:
            # The paragraph might be structured differently
            lines[i] = (
                r"Our Skill-Aware Decomposition narrows this gap to 46 points ($\catrecall$@1 = 54.2\%), demonstrating that retrieval-augmented decomposition is an effective strategy." + "\n"
            )
            print(f"EDIT 3 PARTIAL: Updated first line at {i}")
            break

# ============================================================
# EDIT 4: Add E2E pilot paragraph in Discussion
# ============================================================

for i, line in enumerate(lines):
    if "suggests that future work on skill routing should jointly optimize" in line:
        e2e_lines = [
            "\n",
            r"\paragraph{End-to-end pipeline analysis.}" + "\n",
            r"A pilot study on 20 stratified queries with SAD reveals that the full pipeline achieves 70.0\% step count accuracy, 80.0\% edge detection rate, and a functional coherence of 53.7\%." + "\n",
            r"Median end-to-end latency is 568ms (p95: 1.26s) per query on a single A100, demonstrating practical feasibility for interactive agent deployment." + "\n",
        ]
        for j, new_line in enumerate(e2e_lines):
            lines.insert(i + 1 + j, new_line)
        print(f"EDIT 4 OK: Added E2E pilot paragraph after line {i}")
        break

# ============================================================
# EDIT 5: Update Conclusion
# ============================================================

for i, line in enumerate(lines):
    if "Our key contributions include Skill-Aware Decomposition" in line:
        lines[i] = (
            r"Our key contributions include Skill-Aware Decomposition (SAD), a retrieval-augmented method that improves decomposition accuracy from 36\% to 69\% and category-level routing by 60\%, with consistent gains across four models (7--14B) and on both template and human-written queries; a dependency-aware DAG planner with multi-dimensional compatibility scoring; and a context window analysis showing 99\%+ token reduction with sub-second routing latency." + "\n"
        )
        print(f"EDIT 5 OK: Updated conclusion at line {i}")
        break

# ============================================================
# EDIT 6: Update Limitations
# ============================================================

for i, line in enumerate(lines):
    if "Our benchmark uses template-based query generation" in line:
        lines[i] = (
            r"Our benchmark primarily uses template-based query generation; while we supplement with 35 human-written queries showing consistent SAD improvements, the human evaluation subset remains small." + "\n"
        )
        print(f"EDIT 6a OK: Updated limitations line {i}")
        break

for i, line in enumerate(lines):
    if "We evaluate with 7--8B parameter LLMs" in line:
        lines[i] = (
            r"We evaluate with 7--14B parameter LLMs; while SAD shows consistent improvements across model scales, larger models (70B+) may exhibit different decomposition behaviors." + "\n"
        )
        print(f"EDIT 6b OK: Updated model limitation at line {i}")
        break

for i, line in enumerate(lines):
    if "Our evaluation is retrieval-focused and does not measure end-to-end" in line:
        lines[i] = (
            r"Our evaluation is retrieval-focused: while a 20-query pilot study demonstrates practical feasibility (568ms median latency, 53.7\% functional coherence), full end-to-end evaluation with actual skill execution remains future work." + "\n"
        )
        print(f"EDIT 6c OK: Updated e2e limitation at line {i}")
        break

# Write the result
with open(TEX_PATH, "w") as f:
    f.writelines(lines)

print(f"\nDone. Total lines: {len(lines)}")
