#!/usr/bin/env python3
"""Apply all review fixes to main.tex.bak2 (v2 - corrected patterns matching actual bak2)"""

with open('/mnt/workspace/skill-routing/paper/main.tex.bak2', 'r') as f:
    content = f.read()

applied = []
failed = []

def safe_replace(content, old, new, label):
    if old in content:
        content = content.replace(old, new)
        applied.append(label)
    else:
        failed.append(label)
        print(f'[FAIL] {label}')
        print(f'  Pattern starts: {repr(old[:100])}')
    return content

# ============================================================
# FIX 1: Add TikZ packages
# ============================================================
content = safe_replace(content,
    '\\usepackage{subcaption}',
    '\\usepackage{subcaption}\n\\usepackage{tikz}\n\\usetikzlibrary{arrows.meta, positioning, shapes.geometric, fit, backgrounds}',
    'FIX1: TikZ packages')

# ============================================================
# FIX 2: Replace fbox Figure 1 with TikZ
# ============================================================
OLD_FIG = """\\begin{figure*}[t]
\\centering
\\fbox{\\parbox{0.95\\textwidth}{\\centering\\vspace{1.5em}
\\small
\\textbf{Query:} ``Download the dataset, transform it, and create visual reports'' \\\\[0.8em]
$\\downarrow$ \\textbf{Stage 1: Decompose} (LLM) $\\downarrow$ \\\\[0.4em]
$[t_1]$ Download dataset $\\;\\to\\;$ $[t_2]$ Transform data $\\;\\to\\;$ $[t_3]$ Create visual reports \\\\[0.8em]
$\\downarrow$ \\textbf{Stage 2: Retrieve} (Bi-Encoder + FAISS) $\\downarrow$ \\\\[0.4em]
$t_1 \\to$ \\{api-client, http-fetch, ...\\} \\quad $t_2 \\to$ \\{csv-parser, etl-pipeline, ...\\} \\quad $t_3 \\to$ \\{chart-gen, dashboard, ...\\} \\\\[0.8em]
$\\downarrow$ \\textbf{Stage 3: Compose} (Compatibility-Aware Planning) $\\downarrow$ \\\\[0.4em]
$s_1$: api-client $\\;\\xrightarrow{g_0}\\;$ $s_2$: csv-parser $\\;\\xrightarrow{g_1}\\;$ $s_3$: chart-gen \\quad {\\footnotesize (DAG: $g_0 \\to g_1 \\to g_2$)}
\\vspace{1.5em}}}
\\caption{Overview of \\system{}. A complex query is decomposed into atomic sub-tasks, each matched to candidate skills via bi-encoder retrieval, then composed into an executable DAG using dependency-aware planning with multi-dimensional compatibility scoring.}
\\label{fig:overview}
\\end{figure*}"""

NEW_FIG = """\\begin{figure*}[t]
\\centering
\\begin{tikzpicture}[scale=0.82, every node/.append style={transform shape},
    >=Stealth, node distance=0.35cm and 0.5cm,
    stage/.style={draw, rounded corners=2pt, fill=blue!8, minimum height=0.7cm, minimum width=2.4cm, font=\\footnotesize\\bfseries, align=center},
    query/.style={draw, rounded corners=2pt, fill=orange!12, minimum height=0.55cm, font=\\footnotesize, align=center},
    subtask/.style={draw, rounded corners=2pt, fill=green!8, minimum height=0.5cm, font=\\scriptsize, align=center},
    skill/.style={draw, rounded corners=2pt, fill=purple!8, minimum height=0.5cm, font=\\scriptsize, align=center},
    dag/.style={draw, rounded corners=2pt, fill=red!8, minimum height=0.5cm, font=\\scriptsize, align=center},
    arrow/.style={->, thick, color=gray!70},
    bigarrow/.style={->, very thick, color=blue!50},
    lbl/.style={font=\\tiny\\itshape, color=gray!80},
]
\\node[query, minimum width=6cm] (query) {\\textit{``Download the dataset, transform it, and create visual reports''}};
\\node[stage, below=0.5cm of query] (stage1) {Stage 1: Decompose {\\scriptsize (LLM)}};
\\draw[bigarrow] (query) -- (stage1);
\\node[subtask, below=0.5cm of stage1, xshift=-2.8cm] (t1) {$t_1$: Download dataset};
\\node[subtask, below=0.5cm of stage1] (t2) {$t_2$: Transform data};
\\node[subtask, below=0.5cm of stage1, xshift=2.8cm] (t3) {$t_3$: Create reports};
\\draw[arrow] (stage1) -- (t1); \\draw[arrow] (stage1) -- (t2); \\draw[arrow] (stage1) -- (t3);
\\node[stage, below=0.5cm of t2] (stage2) {Stage 2: Retrieve {\\scriptsize (Bi-Enc + FAISS)}};
\\draw[arrow] (t1) -- (stage2); \\draw[arrow] (t2) -- (stage2); \\draw[arrow] (t3) -- (stage2);
\\node[skill, below=0.5cm of stage2, xshift=-2.8cm] (c1) {api-client, http-fetch, \\ldots};
\\node[skill, below=0.5cm of stage2] (c2) {csv-parser, etl-pipeline, \\ldots};
\\node[skill, below=0.5cm of stage2, xshift=2.8cm] (c3) {chart-gen, dashboard, \\ldots};
\\draw[arrow] (stage2) -- (c1); \\draw[arrow] (stage2) -- (c2); \\draw[arrow] (stage2) -- (c3);
\\node[lbl, above=0.02cm of c1] {top-$k$}; \\node[lbl, above=0.02cm of c2] {top-$k$}; \\node[lbl, above=0.02cm of c3] {top-$k$};
\\node[stage, below=0.5cm of c2] (stage3) {Stage 3: Compose {\\scriptsize (DAG + Compat.)}};
\\draw[arrow] (c1) -- (stage3); \\draw[arrow] (c2) -- (stage3); \\draw[arrow] (c3) -- (stage3);
\\node[dag, below=0.5cm of stage3, xshift=-2cm] (s1) {$s_1$: api-client};
\\node[dag, below=0.5cm of stage3] (s2) {$s_2$: csv-parser};
\\node[dag, below=0.5cm of stage3, xshift=2cm] (s3) {$s_3$: chart-gen};
\\draw[arrow] (stage3) -- (s1); \\draw[arrow] (stage3) -- (s2); \\draw[arrow] (stage3) -- (s3);
\\draw[->, very thick, color=red!60] (s1) -- node[above, font=\\tiny] {$g_0$} (s2);
\\draw[->, very thick, color=red!60] (s2) -- node[above, font=\\tiny] {$g_1$} (s3);
\\node[draw, dashed, rounded corners=2pt, fill=yellow!10, minimum height=0.5cm, font=\\scriptsize, align=center, right=1.2cm of stage1] (sad) {SAD\\\\{\\tiny (\\S\\ref{sec:sad})}};
\\draw[->, dashed, thick, color=orange!70] (stage2.east) -- ++(1.0,0) |- node[right, pos=0.25, font=\\tiny, color=orange!70] {hints} (sad.south);
\\draw[->, dashed, thick, color=orange!70] (sad.west) -- (stage1.east);
\\node[draw, rounded corners=2pt, fill=gray!8, font=\\scriptsize, minimum height=0.4cm, left=1.2cm of stage2] (lib) {Skill Library\\\\{\\tiny ($N{=}2{,}595$)}};
\\draw[arrow, color=gray!50] (lib) -- (stage2);
\\end{tikzpicture}
\\caption{Overview of \\system{}. A query is decomposed into sub-tasks, each matched to skills via bi-encoder retrieval, then composed into a DAG. Dashed arrows: SAD feedback loop (\\S\\ref{sec:sad}).}
\\label{fig:overview}
\\end{figure*}"""

content = safe_replace(content, OLD_FIG, NEW_FIG, 'FIX2: TikZ figure')

# ============================================================
# FIX 3: Add SAD subsection in Method (insert after Stage 3)
# ============================================================
content = safe_replace(content,
    """averages compatibility with all DAG predecessors.

% ============================================================
\\section{Benchmark: \\benchmark{}}""",
    """averages compatibility with all DAG predecessors.

\\subsection{Skill-Aware Decomposition (SAD)}
\\label{sec:sad}

A key insight from our experiments is that LLM decomposers produce generic sub-task descriptions that poorly align with skill metadata.
We propose \\emph{Skill-Aware Decomposition} (SAD), a retrieval-augmented feedback loop that informs the decomposer about available skills.
Given an initial decomposition $D^{(0)}(q)$ and the retrieval results $\\text{cand}(t_k)$ from Stage~2, SAD constructs a hint set $\\mathcal{H}$ containing the top-$H$ skill names from the union of all candidate lists.
The decomposer is re-prompted with both the original query and $\\mathcal{H}$:
\\begin{equation}
D^{(1)}(q) = \\text{LLM}(p_{\\text{sys}}, p_{\\text{SAD}}(q, \\mathcal{H}))
\\end{equation}
where $p_{\\text{SAD}}$ appends \\emph{``Available skills that may be relevant: $\\mathcal{H}$''} to the decomposition prompt, allowing the decomposer to produce sub-task descriptions better aligned with actual skill names.

% ============================================================
\\section{Benchmark: \\benchmark{}}""",
    'FIX3: SAD section in Method')

# ============================================================
# FIX 4: Tighten abstract
# ============================================================
content = safe_replace(content,
    'Large language model (LLM) agents increasingly rely on external skills---reusable tool specifications that define capabilities such as code generation, data analysis, or API interaction.\nWhile recent work addresses routing queries to a single best-matching skill, real-world tasks often require \\emph{composing} multiple skills into coordinated execution plans.',
    'LLM agents increasingly rely on external skills---reusable tool specifications---but real-world tasks often require \\emph{composing} multiple skills, not just selecting one.',
    'FIX4a: Abstract opening')

content = safe_replace(content,
    'We present \\system{}, a three-stage framework consisting of (1)~an LLM-based task decomposer, (2)~a bi-encoder skill retriever with FAISS indexing, and (3)~a compatibility-aware DAG planner.',
    'We present \\system{}, a decompose-retrieve-compose framework combining an LLM task decomposer, a bi-encoder skill retriever with FAISS indexing, and a dependency-aware DAG planner.',
    'FIX4b: Abstract framework')

content = safe_replace(content,
    'a benchmark of 300 compositional queries over 2{,}595 curated skills spanning 17 categories, with ground-truth skill chains and difficulty stratification.',
    'a benchmark of 300 compositional queries over 2{,}595 skills spanning 17 categories.',
    'FIX4c: Abstract benchmark')

content = safe_replace(content,
    'improving category recall to 54.2\\% (+60\\%).\nWe further find that metadata-only retrieval matches or outperforms body-aware retrieval, and that the proposed DAG planner with multi-dimensional compatibility scoring reduces context window consumption by over 99\\%.',
    'improving category recall to 54.2\\% (+60\\%) consistently across five models (7--72B); notably, a 7B model with SAD outperforms a 72B model without it.\n\\system{} further reduces context window consumption by over 99\\% compared to exposing all tools.',
    'FIX4d: Abstract conclusion')

# ============================================================
# FIX 5: Add text overlap disclosure
# ============================================================
content = safe_replace(content,
    'The benchmark totals 300 queries involving 523 unique ground-truth skills.\n\n\\subsection{Evaluation Metrics}',
    """The benchmark totals 300 queries involving 523 unique ground-truth skills.

\\paragraph{Text Overlap Disclosure.}
Because ground-truth sub-task descriptions are derived from skill metadata, there is substantial lexical overlap between sub-task descriptions and skill descriptions in the library.
An automated analysis reveals mean ROUGE-L of 0.845 and mean BLEU-1 of 0.980 between ground-truth sub-tasks and their corresponding skill descriptions, with 37.8\\% being exact copies.
This explains the near-perfect oracle retrieval performance (R@1 = 99.5\\%) and means that absolute retrieval scores on template queries should be interpreted as upper-bound estimates.
Our human-written query evaluation (\\S\\ref{sec:sad-results}) provides a complementary assessment with naturalistic phrasing diversity, where performance drops substantially (e.g., $\\catrecall$@1: 25.9\\% vs 54.2\\%), confirming that template-based scores overestimate real-world performance.

\\subsection{Evaluation Metrics}""",
    'FIX5: Text overlap disclosure')

# ============================================================
# FIX 6: Update experimental setup - 3 models -> 5 models
# ============================================================
content = safe_replace(content,
    'We compare three open-weight 7--8B instruction-tuned models:\nQwen2.5-7B-Instruct \\cite{qwen2.5}, \nLlama-3.1-8B-Instruct \\cite{dubey2024llama3}, and \nMistral-7B-Instruct-v0.3 \\cite{jiang2023mistral}.',
    'We compare five open-weight instruction-tuned models spanning three scales:\nQwen2.5-7B-Instruct, Qwen2.5-14B-Instruct, and Qwen2.5-72B-Instruct \\cite{qwen2.5}, \nLlama-3.1-8B-Instruct \\cite{dubey2024llama3}, and \nMistral-7B-Instruct-v0.3 \\cite{jiang2023mistral}.',
    'FIX6a: 5 models')

content = safe_replace(content,
    'All experiments run on a single NVIDIA A100-80GB GPU with 491GB system RAM.',
    '7--14B models run on a single NVIDIA A100-80GB GPU.\nThe 72B model uses four A100-80GB GPUs with automatic tensor parallelism via \\texttt{device\\_map="auto"}.',
    'FIX6b: Hardware')

# ============================================================
# FIX 7: Add SAD results section (before Ablation: Constrained)
# ============================================================
content = safe_replace(content,
    '\\subsection{Ablation: Constrained Decomposition}',
    """\\subsection{Skill-Aware Decomposition Results}
\\label{sec:sad-results}

\\paragraph{SAD ablation.}

\\begin{table}[t]
\\centering
\\small
\\begin{tabular}{lccc}
\\toprule
\\textbf{Hints $H$} & \\textbf{DA} & $\\catrecall$\\textbf{@1} & $\\chaincat$ \\\\
\\midrule
0 (Vanilla) & 0.360 & 0.339 & 0.316 \\\\
5 & 0.457 & 0.468 & 0.445 \\\\
10 & 0.537 & 0.519 & 0.498 \\\\
15 & 0.690 & \\textbf{0.542} & \\textbf{0.521} \\\\
25 & \\textbf{0.790} & 0.474 & 0.451 \\\\
\\bottomrule
\\end{tabular}
\\caption{SAD ablation (Qwen2.5-7B). DA increases monotonically but $\\catrecall$@1 peaks at $H{=}15$, revealing a noise--alignment trade-off.}
\\label{tab:sad-ablation}
\\end{table}

Table~\\ref{tab:sad-ablation} presents the ablation over hint count $H$.
DA increases monotonically (36.0\\% to 79.0\\%), but $\\catrecall$@1 peaks at $H{=}15$ (54.2\\%) before declining at $H{=}25$ (47.4\\%), revealing a noise--alignment trade-off.

\\paragraph{Cross-model generalization.}

\\begin{table}[t]
\\centering
\\small
\\begin{tabular}{llccc}
\\toprule
\\textbf{Model} & \\textbf{Mode} & \\textbf{DA} & $\\catrecall$\\textbf{@1} & $\\chaincat$ \\\\
\\midrule
\\multirow{2}{*}{Qwen2.5-7B} & Vanilla & 0.360 & 0.339 & 0.316 \\\\
 & +SAD & 0.690 & \\textbf{0.542} & \\textbf{0.521} \\\\
\\midrule
\\multirow{2}{*}{Qwen2.5-14B} & Vanilla & 0.280 & 0.297 & 0.280 \\\\
 & +SAD & 0.443 & 0.385 & 0.377 \\\\
\\midrule
\\multirow{2}{*}{Llama-3.1-8B} & Vanilla & 0.000 & 0.216 & 0.210 \\\\
 & +SAD & 0.217 & 0.339 & 0.323 \\\\
\\midrule
\\multirow{2}{*}{Mistral-7B} & Vanilla & 0.177 & 0.242 & 0.248 \\\\
 & +SAD & 0.273 & 0.307 & 0.301 \\\\
\\midrule
\\multirow{2}{*}{Qwen2.5-72B} & Vanilla & 0.627 & 0.368 & 0.358 \\\\
 & +SAD & 0.503 & 0.483 & \\underline{0.518} \\\\
\\bottomrule
\\end{tabular}
\\caption{Cross-model SAD ($H{=}15$). SAD improves routing across five models (7--72B). \\textbf{Bold}: best. \\underline{Underline}: second best. 7B+SAD surpasses the 10$\\times$ larger 72B vanilla.}
\\label{tab:sad-crossmodel}
\\end{table}

Table~\\ref{tab:sad-crossmodel} shows SAD generalizes across model families, with $\\catrecall$@1 gains from +26.9\\% (Mistral) to +59.9\\% (Qwen-7B).
\\textbf{Qwen2.5-7B+SAD (54.2\\%) outperforms 72B vanilla (36.8\\%)}, showing retrieval-augmented decomposition can surpass a 10$\\times$ larger model.
The 72B model's SAD reduces DA from 62.7\\% to 50.3\\% while improving $\\catrecall$@1 to 48.3\\%, suggesting SAD restructures outputs toward skill-aligned phrasing.
The 14B anomaly (lower performance than 7B) stems from over-decomposition and lower JSON parse rates; see Appendix~\\ref{app:14b}.

\\paragraph{Human-written query generalization.}
On 55 human-written queries (22 easy, 23 medium, 10 hard), SAD improves $\\catrecall$@1 from 18.8\\% to 30.8\\% (+63.8\\%).
Hard queries decline (17.0\\% $\\to$ 9.4\\%), suggesting hints become overwhelming for complex decompositions.
The lower absolute numbers confirm human phrasing diversity remains challenging.

\\subsection{Ablation: Constrained Decomposition}""",
    'FIX7: SAD results section')

# ============================================================
# FIX 8: Compress context window section
# ============================================================
content = safe_replace(content,
    """A key practical concern for deploying large skill libraries is \\emph{context window overflow}: each tool description consumes approximately 400--500 tokens in the agent's prompt, and exposing all available tools simultaneously degrades both accuracy and cost.

Table~\\ref{tab:context} quantifies the context window savings achieved by \\system{}'s compositional routing.""",
    "Table~\\ref{tab:context} quantifies context savings: exposing all 2{,}595 skills consumes $\\sim$1.04M tokens, exceeding most LLM contexts; \\system{} reduces this to 2--5 skills per query ($>$99\\% reduction).",
    'FIX8a: Context window intro')

content = safe_replace(content,
    '\\system{} + budget cap & $\\leq$20 & $\\leq$8{,}000 & 99.2\\% \\\\\n\\bottomrule',
    '\\bottomrule',
    'FIX8b: Remove budget cap row')

content = safe_replace(content,
    'Context window consumption under different tool exposure strategies for our 2{,}595-skill library. Token estimates assume $\\sim$400 tokens per tool description. Compositional routing reduces consumption by over two orders of magnitude.',
    'Context window consumption ($\\sim$400 tokens/tool). Compositional routing reduces consumption by two orders of magnitude.',
    'FIX8c: Context caption')

content = safe_replace(content,
    """With 2{,}595 skills, na\\"ively exposing all tools consumes $\\sim$1.04M tokens---exceeding the context window of most current LLMs.
Even 128K-token models would dedicate over 8$\\times$ their full capacity to tool descriptions alone.
\\system{}'s routing reduces this to only the 2--5 skills needed per query, freeing context for instructions, conversation history, and chain-of-thought reasoning.
This token efficiency is a prerequisite for practical agent deployment over large skill libraries.""",
    "",
    'FIX8d: Remove trailing context para')

# ============================================================
# FIX 9: Compress main results paragraphs
# ============================================================
content = safe_replace(content,
    """\\paragraph{Decomposition is the bottleneck.}
The most striking result is the enormous gap between oracle decomposition and LLM decomposition.
Oracle decomposition achieves R@1 of 99.5\\% and perfect category accuracy, demonstrating that the retriever is highly effective when given accurate sub-task descriptions.
The best LLM decomposer (Qwen2.5-7B) reaches only $\\catrecall$@1 = 36.3\\%, indicating that decomposition quality---not retrieval capability---is the primary bottleneck.""",
    """\\paragraph{Decomposition is the bottleneck.}
Oracle decomposition achieves R@1 = 99.5\\% and perfect category accuracy.
The best LLM decomposer (Qwen2.5-7B) reaches only $\\catrecall$@1 = 36.3\\%, confirming decomposition quality as the primary bottleneck.""",
    'FIX9a: Bottleneck para')

content = safe_replace(content,
    """\\paragraph{Compositional routing outperforms single-skill.}
Despite imperfect decomposition, our full pipeline (Qwen + meta) achieves $\\catrecall$@1 = 33.9\\%, substantially outperforming the single-skill baseline at 21.1\\%.
This validates that even approximate decomposition provides value for compositional routing.""",
    """\\paragraph{Compositional routing outperforms single-skill.}
Our full pipeline achieves $\\catrecall$@1 = 33.9\\%, substantially outperforming the single-skill baseline (21.1\\%), validating that even approximate decomposition aids compositional routing.""",
    'FIX9b: Compositional routing para')

content = safe_replace(content,
    """\\paragraph{Metadata matches or outperforms body.}
For oracle decomposition, metadata-only retrieval achieves R@1 = 99.5\\% versus 99.0\\% for body-aware retrieval.
In the full pipeline, body-aware has a slight edge at the category level ($\\catrecall$@1: 36.3\\% vs 33.9\\%), but the difference is small and comes with significantly higher encoding cost due to longer input sequences.
This suggests that concise skill metadata (name + description) captures the essential discriminative signal, consistent with the intuition that good skill descriptions should be self-contained summaries.""",
    """\\paragraph{Metadata matches or outperforms body.}
Metadata-only retrieval achieves oracle R@1 = 99.5\\% vs 99.0\\% for body-aware.
In the full pipeline, body-aware has a slight edge ($\\catrecall$@1: 36.3\\% vs 33.9\\%) but with higher encoding cost, suggesting concise metadata captures the essential discriminative signal.""",
    'FIX9c: Metadata para')

# ============================================================
# FIX 10: Compress difficulty text
# ============================================================
content = safe_replace(content,
    """Table~\\ref{tab:difficulty} breaks down results by difficulty level.
A notable finding is that the decomposition-based pipeline shows its \\emph{greatest advantage on harder queries}: for hard queries (4--5 skills), Qwen + Meta achieves $\\catrecall$@1 = 41.0\\% versus the single-skill baseline at 14.6\\%, a relative improvement of 181\\%.
For easy queries (2 skills), the improvement is more modest (21.4\\% vs 20.1\\%).
This pattern suggests that decomposition becomes increasingly important as task complexity grows.""",
    """Table~\\ref{tab:difficulty} breaks down results by difficulty level.
The decomposition-based pipeline shows its \\emph{greatest advantage on harder queries}: for hard queries (4--5 skills), Qwen + Meta achieves $\\catrecall$@1 = 41.0\\% versus the single-skill baseline at 14.6\\% (+181\\%).
This pattern suggests that decomposition becomes increasingly important as task complexity grows.""",
    'FIX10: Difficulty text')

# ============================================================
# FIX 11: Compress error analysis
# ============================================================
content = safe_replace(content,
    """We manually examine 50 randomly selected failure cases from the Qwen + Meta pipeline to categorize error types:

\\begin{itemize}[nosep,leftmargin=*]
  \\item \\textbf{Over-decomposition} (36\\%): The LLM splits a query into more steps than necessary, inserting intermediate steps not in the ground truth (e.g., ``identify necessary patches'' inserted between ``run security audit'' and ``apply patches'').
  \\item \\textbf{Generic sub-task descriptions} (28\\%): The LLM produces descriptions that are too broad (e.g., ``process the data'' instead of ``transform CSV data using pandas''), leading to retrieval of tangentially related skills.
  \\item \\textbf{Vocabulary mismatch} (22\\%): The sub-task description uses different terminology than the skill metadata (e.g., ``create visual reports'' vs. skill named ``matplotlib-chart-generator'').
  \\item \\textbf{Under-decomposition} (14\\%): The LLM merges multiple steps into one, typically for hard queries with 4+ required skills.
\\end{itemize}""",
    """We examine 50 failure cases from the Qwen + Meta pipeline.
\\textbf{Over-decomposition} (36\\%) inserts unnecessary intermediate steps;
\\textbf{generic descriptions} (28\\%) produce overly broad phrasings that misalign with skills;
\\textbf{vocabulary mismatch} (22\\%) uses different terminology than skill metadata;
\\textbf{under-decomposition} (14\\%) merges multiple steps, typically for 4+ skill queries.""",
    'FIX11: Error analysis')

# ============================================================
# FIX 12: Merge case study + oracle retrieval
# ============================================================
content = safe_replace(content,
    """\\subsection{Case Study}

\\paragraph{Successful routing (Q0):} 
``\\textit{Generate the application code, write tests, and deploy to production}'' is decomposed into three sub-tasks matching the ground truth exactly. The retriever correctly identifies a code generator, a QA tool, and a deployment orchestrator.

\\paragraph{Partial success (Q100):}
``\\textit{Search for sources, process findings, visualize trends, write report, and export document}'' is correctly decomposed into 5 steps. The retriever correctly identifies skills for search, data processing, and report writing (3/5 categories correct), but selects an exploratory data analysis skill instead of a dedicated visualizer.

\\paragraph{Over-decomposition failure (Q200):}
``\\textit{Draft a document and localize it for international readers}'' requires 2 skills (writer + translator), but the LLM produces 7 sub-tasks including review, translation, proofreading, and cultural adaptation steps. The first step correctly selects a document writing skill, but subsequent steps diverge from the ground truth.

\\subsection{Retrieval Quality with Oracle Decomposition}

The near-perfect oracle performance (R@1 = 99.5\\%) deserves further examination.
The 0.5\\% of oracle failures occur when multiple skills in the library have very similar metadata, making exact ID matching ambiguous even though the correct \\emph{category} of skill is retrieved (category recall remains 100\\%).
This validates our design choice of including category-level metrics, which better reflect practical routing quality.""",
    """\\subsection{Case Study and Oracle Retrieval}

``\\textit{Generate code, write tests, deploy}'' correctly decomposes into three ground-truth-matching sub-tasks.
Conversely, ``\\textit{Draft and localize a document}'' (2 skills) yields 7 sub-tasks---a typical over-decomposition failure.
Oracle R@1 (99.5\\%) confirms retriever quality; the 0.5\\% failures occur when skills share near-identical metadata.""",
    'FIX12: Case study + oracle')

# ============================================================
# FIX 13: Replace discussion section
# ============================================================
OLD_DISC = """\\paragraph{The decomposition gap.}
Our results quantify a ``decomposition gap'' between oracle and LLM decomposition.
Standard decomposition yields $\\catrecall$@1 = 33.9\\%, a 66-point gap from the oracle ceiling.
Our Skill-Aware Decomposition narrows this gap to 46 points ($\\catrecall$@1 = 54.2\\%), demonstrating that retrieval-augmented decomposition is an effective strategy.
The remaining gap suggests further improvements from fine-tuning decomposers on skill-aware data or iterative refinement with retrieval feedback.

\\paragraph{Metadata vs.\\ body.}
Our finding that metadata-only retrieval is competitive with body-aware retrieval has practical implications: it means that skill authors should invest in writing clear, descriptive metadata (names and descriptions) rather than relying on the full specification body to be the primary retrieval signal.
This finding contrasts with \\citet{xu2025skillrouter}, who report that body content is the ``decisive'' signal for single-skill routing.
We hypothesize that the compositional setting, where queries are decomposed into specific sub-tasks, produces more targeted retrieval queries that align naturally with concise metadata.

\\paragraph{Scalability.}
Our FAISS-based retrieval scales to thousands of skills with sub-second latency per query.
The primary computational cost is LLM-based decomposition, which at approximately 0.8 seconds per query (sequential generation on A100) is practical for interactive use.
Batch processing reduces amortized cost further.

\\paragraph{From sequential to parallel planning.}
Our DAG planner (Section~\\ref{sec:compose}) demonstrates that the Compose stage can move beyond simple sequential chaining.
The dependency detection and parallel group assignment algorithms are lightweight---linear in the number of sub-task pairs and edges, respectively---and produce execution plans that reduce critical-path latency without requiring additional training data.
This opens the door to more efficient agent execution, where independent sub-tasks (e.g., writing documentation and running tests after code generation) proceed concurrently.

\\paragraph{Token efficiency as a routing metric.}
Our context window analysis (Section~\\ref{sec:context}) reveals that compositional routing provides a secondary benefit beyond accuracy: by exposing only the relevant skills per query, token consumption drops by over 99\\%.
This suggests that future work on skill routing should jointly optimize for both routing accuracy and context efficiency."""

NEW_DISC = """\\paragraph{The decomposition gap.}
Standard 7B decomposition yields $\\catrecall$@1 = 33.9\\%, a 66-point gap from oracle.
Scaling to 72B improves this to only 36.8\\%, confirming that model size alone is insufficient.
SAD narrows the gap to 46 points ($\\catrecall$@1 = 54.2\\% with 7B+SAD): \\textbf{7B+SAD surpasses 72B vanilla by 7.4 points} while using $10\\times$ fewer parameters.
The hint count ablation reveals a noise--alignment trade-off (DA increases monotonically, but retrieval peaks at $H{=}15$).
Cross-model results across five models (7B--72B) confirm SAD as a model-agnostic improvement.

\\paragraph{Metadata vs.\\ body.}
Metadata-only retrieval matches body-aware encoding, contrasting with \\citet{xu2025skillrouter}'s finding that body content is ``decisive'' for single-skill routing.
We hypothesize that compositional decomposition produces targeted sub-task queries that align naturally with concise metadata.

\\paragraph{Scalability and planning.}
FAISS retrieval scales to thousands of skills; end-to-end median latency is 568ms (p95: 1.26s).
Our DAG planner achieves 80.0\\% edge detection on a 20-query pilot.
We define \\emph{functional coherence} as the fraction of adjacent skill pairs with compatible I/O categories (53.7\\% on pilot).
Compositional routing reduces context consumption by over 99\\% (\\S\\ref{sec:context})."""

content = safe_replace(content, OLD_DISC, NEW_DISC, 'FIX13: Discussion')

# ============================================================
# FIX 14: Compress conclusion
# ============================================================
OLD_CONC = """We have formalized the Compositional Skill Routing problem and presented \\system{}, a decompose-retrieve-compose framework for routing complex queries to multiple skills.
Our key contributions include Skill-Aware Decomposition (SAD), a retrieval-augmented method that improves decomposition accuracy from 36\\% to 69\\% and category-level routing by 60\\%; a dependency-aware DAG planner with multi-dimensional compatibility scoring; and a context window analysis showing 99\\%+ token reduction.
Through \\benchmark{}, a benchmark of 300 compositional queries over 2{,}595 curated skills, we identify task decomposition quality as the primary bottleneck: oracle decomposition achieves near-perfect retrieval, while the best 7B LLM decomposer reaches 33.9\\% category recall.
Over-decomposition and vocabulary mismatch are the dominant failure modes, pointing to decomposition-aware training and skill-metadata-guided prompting as the most promising directions for future work."""

NEW_CONC = """We formalized Compositional Skill Routing and presented \\system{}, a decompose-retrieve-compose framework.
SAD improves decomposition accuracy from 36\\% to 69\\% and $\\catrecall$@1 by 60\\% across five models (7--72B)---a 7B model with SAD outperforms a 72B model without it.
On \\benchmark{} (300 queries, 2{,}595 skills), oracle decomposition achieves near-perfect retrieval, identifying decomposition as the primary bottleneck.
Over-decomposition and vocabulary mismatch are the dominant failure modes, pointing to decomposition-aware training as the most promising future direction."""

content = safe_replace(content, OLD_CONC, NEW_CONC, 'FIX14: Conclusion')

# ============================================================
# FIX 15: Compress limitations
# ============================================================
OLD_LIM = """Our benchmark uses template-based query generation, which may not fully capture the diversity of real-world compositional queries.
While our DAG planner supports parallel execution grouping, the current benchmark evaluation uses sequential ground-truth chains; evaluating parallel plans requires partial-order ground-truth annotations, which we leave to future work.
We evaluate with 7--8B parameter LLMs; larger models may achieve better decomposition quality but at higher computational cost.
Our evaluation is retrieval-focused and does not measure end-to-end task completion with actual skill execution.
Finally, the heuristic dependency detection (keyword matching and I/O type overlap) may miss some semantic dependencies; learning-based dependency prediction is a promising extension."""

NEW_LIM = """Our benchmark uses template-based query generation with high text overlap (ROUGE-L=0.845); while 55 human-written queries show consistent SAD gains on easy/medium difficulties, hard queries (4--5 skills) see performance decline.
The DAG planner's parallelization capability lacks partial-order ground-truth evaluation.
Our evaluation is retrieval-focused; full end-to-end evaluation with actual skill execution and learning-based dependency prediction remain future work."""

content = safe_replace(content, OLD_LIM, NEW_LIM, 'FIX15: Limitations')

# ============================================================
# FIX 16: Compress ethics
# ============================================================
content = safe_replace(content,
    'This work focuses on skill routing for LLM agents and does not involve human subjects or personal data.\nOur benchmark is constructed entirely from publicly available, open-source skill repositories.\nWe acknowledge that improved skill routing could lower the barrier for deploying LLM agents at scale, which carries general risks associated with LLM-based automation.\nWe encourage responsible deployment with human oversight and appropriate access controls.',
    'This work uses only publicly available, open-source skill repositories and involves no human subjects or personal data.\nWe encourage responsible deployment of skill routing systems with human oversight.',
    'FIX16: Ethics')

# ============================================================
# FIX 17: Add 14B appendix
# ============================================================
content = safe_replace(content,
    '\\end{document}',
    """\\section{14B Anomaly Analysis}
\\label{app:14b}

The counter-intuitive result that Qwen2.5-14B underperforms the 7B variant warrants further examination.
Analysis of decomposition patterns reveals two contributing factors.
First, 14B vanilla produces an average of 5.3 sub-tasks per query (vs.\\ 2.9 for 7B), with 42.7\\% of queries generating more than 5 sub-tasks---a severe over-decomposition that fragments retrieval signals.
Second, only 71.3\\% of 14B vanilla outputs parse as valid JSON (vs.\\ 89.3\\% for 7B), indicating weaker adherence to the structured output format at this scale.
With SAD, the 14B model's JSON parse rate improves to 85.0\\%, but 44.7\\% of queries collapse to single-subtask fallbacks, suggesting the model copies skill names verbatim rather than producing genuine decompositions.
These findings indicate that larger models are not uniformly better at structured decomposition.

\\end{document}""",
    'FIX17: 14B appendix')

# ============================================================
# Write output
# ============================================================
with open('/mnt/workspace/skill-routing/paper/main.tex', 'w') as f:
    f.write(content)

lines = content.count('\n')
print(f'\n=== Summary ===')
print(f'Written: {len(content)} chars, {lines} lines')
print(f'Applied: {len(applied)}/{len(applied)+len(failed)}')
for a in applied:
    print(f'  [OK] {a}')
if failed:
    print(f'Failed: {len(failed)}')
    for f_ in failed:
        print(f'  [FAIL] {f_}')

# Verification
print(f'\n=== Verification ===')
print(f'Has TikZ figure: {"tikzpicture" in content}')
print(f'Has 72B: {"72B" in content}')
print(f'Has overlap: {"Text Overlap" in content}')
print(f'Has 14B app: {"app:14b" in content}')
print(f'Has SAD section: {"label{{sec:sad}}" in content}')
print(f'Has SAD results: {"sad-crossmodel" in content}')
print(f'Has human eval: {"Human-written" in content}')
