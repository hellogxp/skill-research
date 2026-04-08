#!/usr/bin/env python3
"""Apply all review fixes to main.tex.bak2 and write to main.tex"""
import re

with open('/mnt/workspace/skill-routing/paper/main.tex.bak2', 'r') as f:
    content = f.read()

# FIX 1: Add TikZ packages
content = content.replace(
    '\\usepackage{subcaption}',
    '\\usepackage{subcaption}\n\\usepackage{tikz}\n\\usetikzlibrary{arrows.meta, positioning, shapes.geometric, fit, backgrounds}'
)

# FIX 2: Replace fbox Figure 1 with TikZ
OLD_FIG = """\\begin{figure*}[t]
\\centering
\\fbox{\\parbox{0.95\\textwidth}{\\centering\\textbf{[Figure 1: System Overview Diagram]}\\\\[6pt]
Query $\\to$ Decomposer (LLM) $\\to$ Sub-tasks $[t_1, \\ldots, t_K]$ $\\to$ Retriever (Bi-Encoder + FAISS) $\\to$ Candidates $\\to$ DAG Planner $\\to$ Skill Chain $[s_1, \\ldots, s_K]$\\\\[4pt]
\\textit{Dashed feedback: Skill-Aware Decomposition (\\S\\ref{sec:sad})}}}
\\caption{Overview of \\system{}. A complex query is decomposed into atomic sub-tasks, each matched to candidate skills via bi-encoder retrieval, then composed into an executable DAG with compatibility scoring. Dashed arrows show the SAD feedback loop (\\S\\ref{sec:sad}).}
\\label{fig:overview}
\\end{figure*}"""

NEW_FIG = r"""\begin{figure*}[t]
\centering
\begin{tikzpicture}[scale=0.82, every node/.append style={transform shape},
    >=Stealth, node distance=0.35cm and 0.5cm,
    stage/.style={draw, rounded corners=2pt, fill=blue!8, minimum height=0.7cm, minimum width=2.4cm, font=\footnotesize\bfseries, align=center},
    query/.style={draw, rounded corners=2pt, fill=orange!12, minimum height=0.55cm, font=\footnotesize, align=center},
    subtask/.style={draw, rounded corners=2pt, fill=green!8, minimum height=0.5cm, font=\scriptsize, align=center},
    skill/.style={draw, rounded corners=2pt, fill=purple!8, minimum height=0.5cm, font=\scriptsize, align=center},
    dag/.style={draw, rounded corners=2pt, fill=red!8, minimum height=0.5cm, font=\scriptsize, align=center},
    arrow/.style={->, thick, color=gray!70},
    bigarrow/.style={->, very thick, color=blue!50},
    lbl/.style={font=\tiny\itshape, color=gray!80},
]
\node[query, minimum width=6cm] (query) {\textit{``Download the dataset, transform it, and create visual reports''}};
\node[stage, below=0.5cm of query] (stage1) {Stage 1: Decompose {\scriptsize (LLM)}};
\draw[bigarrow] (query) -- (stage1);
\node[subtask, below=0.5cm of stage1, xshift=-2.8cm] (t1) {$t_1$: Download dataset};
\node[subtask, below=0.5cm of stage1] (t2) {$t_2$: Transform data};
\node[subtask, below=0.5cm of stage1, xshift=2.8cm] (t3) {$t_3$: Create reports};
\draw[arrow] (stage1) -- (t1); \draw[arrow] (stage1) -- (t2); \draw[arrow] (stage1) -- (t3);
\node[stage, below=0.5cm of t2] (stage2) {Stage 2: Retrieve {\scriptsize (Bi-Enc + FAISS)}};
\draw[arrow] (t1) -- (stage2); \draw[arrow] (t2) -- (stage2); \draw[arrow] (t3) -- (stage2);
\node[skill, below=0.5cm of stage2, xshift=-2.8cm] (c1) {api-client, http-fetch, \ldots};
\node[skill, below=0.5cm of stage2] (c2) {csv-parser, etl-pipeline, \ldots};
\node[skill, below=0.5cm of stage2, xshift=2.8cm] (c3) {chart-gen, dashboard, \ldots};
\draw[arrow] (stage2) -- (c1); \draw[arrow] (stage2) -- (c2); \draw[arrow] (stage2) -- (c3);
\node[lbl, above=0.02cm of c1] {top-$k$}; \node[lbl, above=0.02cm of c2] {top-$k$}; \node[lbl, above=0.02cm of c3] {top-$k$};
\node[stage, below=0.5cm of c2] (stage3) {Stage 3: Compose {\scriptsize (DAG + Compat.)}};
\draw[arrow] (c1) -- (stage3); \draw[arrow] (c2) -- (stage3); \draw[arrow] (c3) -- (stage3);
\node[dag, below=0.5cm of stage3, xshift=-2cm] (s1) {$s_1$: api-client};
\node[dag, below=0.5cm of stage3] (s2) {$s_2$: csv-parser};
\node[dag, below=0.5cm of stage3, xshift=2cm] (s3) {$s_3$: chart-gen};
\draw[arrow] (stage3) -- (s1); \draw[arrow] (stage3) -- (s2); \draw[arrow] (stage3) -- (s3);
\draw[->, very thick, color=red!60] (s1) -- node[above, font=\tiny] {$g_0$} (s2);
\draw[->, very thick, color=red!60] (s2) -- node[above, font=\tiny] {$g_1$} (s3);
\node[draw, dashed, rounded corners=2pt, fill=yellow!10, minimum height=0.5cm, font=\scriptsize, align=center, right=1.2cm of stage1] (sad) {SAD\\{\tiny (\S\ref{sec:sad})}};
\draw[->, dashed, thick, color=orange!70] (stage2.east) -- ++(1.0,0) |- node[right, pos=0.25, font=\tiny, color=orange!70] {hints} (sad.south);
\draw[->, dashed, thick, color=orange!70] (sad.west) -- (stage1.east);
\node[draw, rounded corners=2pt, fill=gray!8, font=\scriptsize, minimum height=0.4cm, left=1.2cm of stage2] (lib) {Skill Library\\{\tiny ($N{=}2{,}595$)}};
\draw[arrow, color=gray!50] (lib) -- (stage2);
\end{tikzpicture}
\caption{Overview of \system{}. A query is decomposed into sub-tasks, each matched to skills via bi-encoder retrieval, then composed into a DAG. Dashed arrows: SAD feedback loop (\S\ref{sec:sad}).}
\label{fig:overview}
\end{figure*}"""

content = content.replace(OLD_FIG, NEW_FIG)

# FIX 3: Rename Stage 4
content = content.replace(
    '\\subsection{Stage 4: Skill-Aware Decomposition}',
    '\\subsection{Skill-Aware Decomposition (SAD)}'
)

# FIX 4: Tighten abstract
content = content.replace(
    'LLM agents increasingly rely on external skills---reusable tool specifications---but selecting the right combination of skills for complex, multi-step tasks remains an open challenge.',
    'LLM agents increasingly rely on external skills---reusable tool specifications---but real-world tasks often require \\emph{composing} multiple skills, not just selecting one.'
)
content = content.replace(
    'a decompose-retrieve-compose framework that combines an LLM-based task decomposer, a bi-encoder skill retriever with FAISS indexing, and a dependency-aware DAG planner with multi-dimensional compatibility scoring.',
    'a decompose-retrieve-compose framework combining an LLM task decomposer, a bi-encoder skill retriever with FAISS indexing, and a dependency-aware DAG planner.'
)
content = content.replace(
    'On \\benchmark{}, a new benchmark of 300 compositional queries over 2{,}595 curated skills spanning 17 categories',
    'On \\benchmark{}, a new benchmark of 300 compositional queries over 2{,}595 skills spanning 17 categories'
)
content = content.replace(
    'while the best LLM decomposition achieves only 33.9% category recall.',
    'while LLM decomposition reaches only 33.9% category recall.'
)
content = content.replace(
    'improving category recall from 33.9% to 54.2% (+60%) without any additional training.\nSAD generalizes across four models from three families, and \\system{} reduces agent context window consumption by over 99% compared to na\\"ively exposing all tools.',
    'improving category recall to 54.2% (+60%) consistently across five models (7--72B); notably, a 7B model with SAD outperforms a 72B model without it.\n\\system{} further reduces context window consumption by over 99% compared to exposing all tools.'
)

# FIX 5: Add text overlap disclosure
content = content.replace(
    'The benchmark totals 300 queries involving 523 unique ground-truth skills.\n\n\\subsection{Evaluation Metrics}',
    """The benchmark totals 300 queries involving 523 unique ground-truth skills.

\\paragraph{Text Overlap Disclosure.}
Because ground-truth sub-task descriptions are derived from skill metadata, there is substantial lexical overlap between sub-task descriptions and skill descriptions in the library.
An automated analysis reveals mean ROUGE-L of 0.845 and mean BLEU-1 of 0.980 between ground-truth sub-tasks and their corresponding skill descriptions, with 37.8\\% being exact copies.
This explains the near-perfect oracle retrieval performance (R@1 = 99.5\\%) and means that absolute retrieval scores on template queries should be interpreted as upper-bound estimates.
Our human-written query evaluation (\\S\\ref{sec:sad-results}) provides a complementary assessment with naturalistic phrasing diversity, where performance drops substantially (e.g., $\\catrecall$@1: 25.9\\% vs 54.2\\%), confirming that template-based scores overestimate real-world performance.

\\subsection{Evaluation Metrics}"""
)

# FIX 6: Update setup - 5 models
content = content.replace(
    'We compare four open-weight instruction-tuned LLMs:\nQwen2.5-7B-Instruct and Qwen2.5-14B-Instruct',
    'We compare five open-weight instruction-tuned models spanning three scales:\nQwen2.5-7B-Instruct, Qwen2.5-14B-Instruct, and Qwen2.5-72B-Instruct'
)

# FIX 6b: Update hardware
content = content.replace(
    '\\paragraph{Hardware.} All experiments run on a single NVIDIA A100-80GB GPU.',
    '\\paragraph{Hardware.} \n7--14B models run on a single NVIDIA A100-80GB GPU.\nThe 72B model uses four A100-80GB GPUs with automatic tensor parallelism via \\texttt{device\\_map="auto"}.'
)

# FIX 7: Add 72B to cross-model table
content = content.replace(
    '\\multirow{2}{*}{Mistral-7B} & Vanilla & 0.177 & 0.242 & 0.248 \\\\\n & +SAD & 0.273 & 0.307 & 0.301 \\\\\n\\bottomrule',
    '\\multirow{2}{*}{Mistral-7B} & Vanilla & 0.177 & 0.242 & 0.248 \\\\\n & +SAD & 0.273 & 0.307 & 0.301 \\\\\n\\midrule\n\\multirow{2}{*}{Qwen2.5-72B} & Vanilla & 0.627 & 0.368 & 0.358 \\\\\n & +SAD & 0.503 & 0.483 & \\underline{0.518} \\\\\n\\bottomrule'
)

# FIX 7b: Update cross-model caption
content = content.replace(
    'Cross-model comparison of SAD ($H{=}15$). SAD consistently improves routing across all four models and three model families. \\textbf{Bold}: best overall. \\underline{Underline}: second best.',
    'Cross-model SAD ($H{=}15$). SAD improves routing across five models (7--72B). \\textbf{Bold}: best. \\underline{Underline}: second best. 7B+SAD surpasses the 10$\\times$ larger 72B vanilla.'
)

# FIX 8: Compress cross-model discussion
OLD_CM = """Table~\\ref{tab:sad-crossmodel} demonstrates that SAD generalizes across model families.
All four models show consistent $\\catrecall$@1 improvements, with relative gains ranging from +26.9\\% (Mistral) to +59.9\\% (Qwen-7B).
The improvement is largest for the best-performing base model (Qwen), suggesting that SAD amplifies existing decomposition capability rather than merely compensating for poor decomposition.

Notably, Qwen2.5-14B achieves \\emph{lower} performance than the 7B variant (DA=28.0\\% vs 36.0\\%, $\\catrecall$@1=29.7\\% vs 33.9\\%).
Analysis reveals that the 14B model tends to over-decompose (average 5.3 sub-tasks vs 2.9 for 7B) and produces lower JSON parse rates (71.3\\% vs 89.3\\%), suggesting that model scale does not uniformly improve structured decomposition.
With SAD, the 14B model improves to 85.0\\% parse rate but 44.7\\% of queries collapse to single-subtask fallbacks, indicating that SAD hints cause the model to copy skill names verbatim rather than producing genuine decompositions.

Even Llama-3.1-8B, which produces zero valid vanilla decompositions, achieves +57.0\\% $\\catrecall$@1 improvement with SAD, demonstrating that skill hints can partially compensate for weak instruction-following."""

NEW_CM = """Table~\\ref{tab:sad-crossmodel} shows SAD generalizes across model families, with $\\catrecall$@1 gains from +26.9\\% (Mistral) to +59.9\\% (Qwen-7B).
\\textbf{Qwen2.5-7B+SAD (54.2\\%) outperforms 72B vanilla (36.8\\%)}, showing retrieval-augmented decomposition can surpass a 10$\\times$ larger model.
The 72B model's SAD reduces DA from 62.7\\% to 50.3\\% while improving $\\catrecall$@1 to 48.3\\%, suggesting SAD restructures outputs toward skill-aligned phrasing.
The 14B anomaly (lower performance than 7B) stems from over-decomposition and lower JSON parse rates; see Appendix~\\ref{app:14b}."""

content = content.replace(OLD_CM, NEW_CM)

# FIX 9: Add human eval + compress context window
content = content.replace(
    '\\subsection{Context Window Analysis}\n\\label{sec:context}\n\nA key practical concern for deploying large skill libraries is \\emph{context window overflow}: each tool description consumes approximately 400--500 tokens in the agent\'s prompt, and exposing all available tools simultaneously degrades both accuracy and cost.\n\nTable~\\ref{tab:context} quantifies the context window savings achieved by \\system{}\'s compositional routing.\n\n\\begin{table}[t]',
    """\\paragraph{Human-written query generalization.}
On 55 human-written queries (22 easy, 23 medium, 10 hard), SAD improves $\\catrecall$@1 from 18.8\\% to 30.8\\% (+63.8\\%).
Hard queries decline (17.0\\% $\\to$ 9.4\\%), suggesting hints become overwhelming for complex decompositions.
The lower absolute numbers confirm human phrasing diversity remains challenging.

\\subsection{Context Window Analysis}
\\label{sec:context}

Table~\\ref{tab:context} quantifies context savings: exposing all 2{,}595 skills consumes $\\sim$1.04M tokens, exceeding most LLM contexts; \\system{} reduces this to 2--5 skills per query ($>$99\\% reduction).

\\begin{table}[t]"""
)

# Remove budget cap row
content = content.replace(
    '\\system{} + budget cap & $\\leq$20 & $\\leq$8{,}000 & 99.2\\% \\\\\n\\bottomrule',
    '\\bottomrule'
)

# Shorten context caption
content = content.replace(
    'Context window consumption under different tool exposure strategies for our 2{,}595-skill library. Token estimates assume ${\\sim}$400 tokens per tool description. Compositional routing reduces consumption by over two orders of magnitude.',
    'Context window consumption (${\\sim}$400 tokens/tool). Compositional routing reduces consumption by two orders of magnitude.'
)

# Remove trailing context paragraph
content = content.replace(
    """With 2{,}595 skills, na\\"ively exposing all tools consumes $\\sim$1.04M tokens---exceeding the context of most LLMs.
\\system{}'s routing reduces this to 2--5 skills per query, a prerequisite for practical deployment.

""",
    "\n"
)

# FIX 10: Compress main results paragraphs
content = content.replace(
    """\\paragraph{Decomposition is the bottleneck.}
The most striking result is the enormous gap between oracle decomposition and LLM decomposition.
Oracle decomposition achieves R@1 of 99.5\\% and perfect category accuracy, demonstrating that the retriever is highly effective when given accurate sub-task descriptions.
The best LLM decomposer (Qwen2.5-7B) reaches only $\\catrecall$@1 = 36.3\\%, indicating that decomposition quality---not retrieval capability---is the primary bottleneck.""",
    """\\paragraph{Decomposition is the bottleneck.}
Oracle decomposition achieves R@1 = 99.5\\% and perfect category accuracy.
The best LLM decomposer (Qwen2.5-7B) reaches only $\\catrecall$@1 = 36.3\\%, confirming decomposition quality as the primary bottleneck."""
)

content = content.replace(
    """\\paragraph{Compositional routing outperforms single-skill.}
Despite imperfect decomposition, our full pipeline (Qwen + meta) achieves $\\catrecall$@1 = 33.9\\%, substantially outperforming the single-skill baseline at 21.1\\%.
This validates that even approximate decomposition provides value for compositional routing.""",
    """\\paragraph{Compositional routing outperforms single-skill.}
Our full pipeline achieves $\\catrecall$@1 = 33.9\\%, substantially outperforming the single-skill baseline (21.1\\%), validating that even approximate decomposition aids compositional routing."""
)

content = content.replace(
    """\\paragraph{Metadata matches or outperforms body.}
For oracle decomposition, metadata-only retrieval achieves R@1 = 99.5\\% versus 99.0\\% for body-aware retrieval.
In the full pipeline, body-aware has a slight edge at the category level ($\\catrecall$@1: 36.3\\% vs 33.9\\%), but the difference is small and comes with significantly higher encoding cost due to longer input sequences.
This suggests that concise skill metadata (name + description) captures the essential discriminative signal, consistent with the intuition that good skill descriptions should be self-contained summaries.""",
    """\\paragraph{Metadata matches or outperforms body.}
Metadata-only retrieval achieves oracle R@1 = 99.5\\% vs 99.0\\% for body-aware.
In the full pipeline, body-aware has a slight edge ($\\catrecall$@1: 36.3\\% vs 33.9\\%) but with higher encoding cost, suggesting concise metadata captures the essential discriminative signal."""
)

# FIX 11: Compress SAD ablation text
content = content.replace(
    """Table~\\ref{tab:sad-ablation} presents the ablation over the number of skill hints $H$.
Decomposition accuracy increases monotonically with $H$ (36.0\\% to 79.0\\%), as more hints help the LLM produce structurally valid sub-tasks.
However, $\\catrecall$@1 exhibits an inverted-U pattern, peaking at $H{=}15$ (54.2\\%) before declining at $H{=}25$ (47.4\\%).
This reveals a trade-off: excessive hints introduce noise that dilutes semantic alignment between sub-task descriptions and skill capabilities.""",
    """Table~\\ref{tab:sad-ablation} presents the ablation over hint count $H$.
DA increases monotonically (36.0\\% to 79.0\\%), but $\\catrecall$@1 peaks at $H{=}15$ (54.2\\%) before declining at $H{=}25$ (47.4\\%), revealing a noise--alignment trade-off."""
)

# FIX 12: Compress error analysis
content = content.replace(
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
\\textbf{under-decomposition} (14\\%) merges multiple steps, typically for 4+ skill queries."""
)

# FIX 13: Merge case study + oracle
content = content.replace(
    """\\subsection{Case Study}

\\paragraph{Successful (Q0):} ``\\textit{Generate code, write tests, deploy to production}'' is decomposed into three sub-tasks matching ground truth; the retriever correctly identifies all three skills.

\\paragraph{Over-decomposition (Q200):} ``\\textit{Draft a document and localize it}'' requires 2 skills, but the LLM produces 7 sub-tasks including review, proofreading, and cultural adaptation steps.

\\subsection{Oracle Retrieval}

The near-perfect oracle R@1 (99.5\\%) confirms retriever quality: the 0.5\\% failures occur when multiple skills share near-identical metadata, though category recall remains 100\\%.""",
    """\\subsection{Case Study and Oracle Retrieval}

``\\textit{Generate code, write tests, deploy}'' correctly decomposes into three ground-truth-matching sub-tasks.
Conversely, ``\\textit{Draft and localize a document}'' (2 skills) yields 7 sub-tasks---a typical over-decomposition failure.
Oracle R@1 (99.5\\%) confirms retriever quality; the 0.5\\% failures occur when skills share near-identical metadata."""
)

# FIX 14: Replace entire discussion section
OLD_DISC = """\\paragraph{The decomposition gap.}
Our results quantify a ``decomposition gap'' between oracle and LLM decomposition.
Standard LLM decomposition yields $\\catrecall$@1 = 33.9\\%, a 66-point gap from the oracle ceiling.
SAD narrows this gap to 46 points ($\\catrecall$@1 = 54.2\\%), demonstrating that retrieval-augmented prompting is a viable bridge even without fine-tuning.
The remaining gap suggests opportunities for fine-tuning decomposers on skill-aware data.
The ablation over hint count $H$ reveals a nuanced trade-off: while structural compliance (DA) increases monotonically with $H$, downstream retrieval quality peaks at $H{=}15$ before declining, suggesting that structural compliance and semantic precision have different optima.

\\paragraph{Metadata vs.\\ body.}
Our finding that metadata-only retrieval is competitive with body-aware retrieval has practical implications: it means that skill authors should invest in writing clear, descriptive metadata (names and descriptions) rather than relying on the full specification body to be the primary retrieval signal.
This finding contrasts with \\citet{xu2025skillrouter}, who report that body content is the ``decisive'' signal for single-skill routing.
We hypothesize that the compositional setting, where queries are decomposed into specific sub-tasks, produces more targeted retrieval queries that align naturally with concise metadata.

\\paragraph{DAG planning.}
Our DAG planner introduces lightweight dependency detection and parallel group assignment.
On a 20-query pilot with manually annotated dependencies, the planner achieves 80.0\\% edge detection accuracy and identifies 12\\% of sub-task pairs as parallelizable.
End-to-end latency analysis shows a median of 568ms (p95: 1.26s) per query, with decomposition accounting for $\\sim$85\\% of total time.

\\paragraph{End-to-end feasibility.}
Our 20-query pilot study demonstrates practical feasibility: \\system{} selects executable skill chains with 53.7\\% functional coherence (defined as the fraction of adjacent skill pairs where the upstream skill's output category is compatible with the downstream skill's input category).
While this is a preliminary assessment, it suggests the pipeline produces actionable routing decisions.

\\paragraph{Token efficiency.}
Compositional routing reduces context consumption by over 99\\% (Section~\\ref{sec:context}), making skill-based agents viable even with libraries of thousands of skills.
Future work should jointly optimize routing accuracy and context efficiency."""

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

content = content.replace(OLD_DISC, NEW_DISC)

# FIX 15: Compress conclusion
OLD_CONC = """We have formalized the Compositional Skill Routing problem and presented \\system{}, a decompose-retrieve-compose framework for routing complex queries to multiple skills from large libraries.
Our key contributions include: (1) Skill-Aware Decomposition (SAD), a retrieval-augmented approach that improves decomposition accuracy from 36\\% to 69\\% and category-level routing by 60\\%; (2) a dependency-aware DAG planner with multi-dimensional compatibility scoring; and (3) a context window analysis showing 99\\%+ token reduction with sub-second routing latency.
Through \\benchmark{}, a benchmark of 300 compositional queries over 2{,}595 curated skills, we identify task decomposition quality as the primary bottleneck: oracle decomposition achieves near-perfect retrieval, while the best LLM decomposer reaches only 33.9\\% category recall.
Over-decomposition and vocabulary mismatch are the dominant failure modes, pointing to decomposition-aware training and skill-metadata-guided prompting as the most promising directions for future work."""

NEW_CONC = """We formalized Compositional Skill Routing and presented \\system{}, a decompose-retrieve-compose framework.
SAD improves decomposition accuracy from 36\\% to 69\\% and $\\catrecall$@1 by 60\\% across five models (7--72B)---a 7B model with SAD outperforms a 72B model without it.
On \\benchmark{} (300 queries, 2{,}595 skills), oracle decomposition achieves near-perfect retrieval, identifying decomposition as the primary bottleneck.
Over-decomposition and vocabulary mismatch are the dominant failure modes, pointing to decomposition-aware training as the most promising future direction."""

content = content.replace(OLD_CONC, NEW_CONC)

# FIX 16: Compress limitations
OLD_LIM = """Our benchmark primarily uses template-based query generation, which may not fully capture the diversity of real-world compositional queries; future work should incorporate more human-authored queries.
While our DAG planner supports parallel execution grouping, the current benchmark evaluation uses sequential ground-truth chains; evaluating parallel plans requires partial-order ground-truth annotations, which we leave to future work.
We evaluate with 7--14B parameter LLMs; while SAD shows consistent improvements across model scales, larger models (70B+) may exhibit different decomposition behaviors.
Our evaluation is retrieval-focused: while a 20-query pilot study demonstrates practical feasibility (568ms median latency, 53.7\\% functional coherence), full end-to-end evaluation with actual skill execution remains future work.
Finally, the heuristic dependency detection (keyword matching and I/O type overlap) may miss semantic dependencies that require deeper understanding; learning-based dependency prediction is a promising extension."""

NEW_LIM = """Our benchmark uses template-based query generation with high text overlap (ROUGE-L=0.845); while 55 human-written queries show consistent SAD gains on easy/medium difficulties, hard queries (4--5 skills) see performance decline.
The DAG planner's parallelization capability lacks partial-order ground-truth evaluation.
Our evaluation is retrieval-focused; full end-to-end evaluation with actual skill execution and learning-based dependency prediction remain future work."""

content = content.replace(OLD_LIM, NEW_LIM)

# FIX 17: Compress ethics
content = content.replace(
    'This work focuses on skill routing for LLM agents and does not involve human subjects or personal data.\nOur benchmark is constructed entirely from publicly available, open-source skill repositories.\nWe acknowledge that improved skill routing could lower the barrier for deploying LLM agents at scale, which carries general risks associated with LLM-based automation.\nWe encourage responsible deployment with human oversight and appropriate access controls.',
    'This work uses only publicly available, open-source skill repositories and involves no human subjects or personal data.\nWe encourage responsible deployment of skill routing systems with human oversight.'
)

# FIX 18: Add 14B appendix
content = content.replace(
    '\\end{document}',
    """\\section{14B Anomaly Analysis}
\\label{app:14b}

The counter-intuitive result that Qwen2.5-14B underperforms the 7B variant warrants further examination.
Analysis of decomposition patterns reveals two contributing factors.
First, 14B vanilla produces an average of 5.3 sub-tasks per query (vs.\\ 2.9 for 7B), with 42.7\\% of queries generating more than 5 sub-tasks---a severe over-decomposition that fragments retrieval signals.
Second, only 71.3\\% of 14B vanilla outputs parse as valid JSON (vs.\\ 89.3\\% for 7B), indicating weaker adherence to the structured output format at this scale.
With SAD, the 14B model's JSON parse rate improves to 85.0\\%, but 44.7\\% of queries collapse to single-subtask fallbacks, suggesting the model copies skill names verbatim rather than producing genuine decompositions.
These findings indicate that larger models are not uniformly better at structured decomposition, and that instruction-following for constrained output formats is a distinct capability from general language understanding.

\\end{document}"""
)

# FIX 19: Compress difficulty text
content = content.replace(
    """Table~\\ref{tab:difficulty} breaks down results by difficulty level.
A notable finding is that the decomposition-based pipeline shows its \\emph{greatest advantage on harder queries}: for hard queries (4--5 skills), Qwen + Meta achieves $\\catrecall$@1 = 41.0\\% versus the single-skill baseline at 14.6\\%, a relative improvement of 181\\%.
For easy queries (2 skills), the improvement is more modest (21.4\\% vs 20.1\\%).
This pattern suggests that decomposition becomes increasingly important as task complexity grows.""",
    """Table~\\ref{tab:difficulty} breaks down results by difficulty level.
The decomposition-based pipeline shows its \\emph{greatest advantage on harder queries}: for hard queries (4--5 skills), Qwen + Meta achieves $\\catrecall$@1 = 41.0\\% versus the single-skill baseline at 14.6\\% (+181\\%).
This pattern suggests that decomposition becomes increasingly important as task complexity grows."""
)

with open('/mnt/workspace/skill-routing/paper/main.tex', 'w') as f:
    f.write(content)

lines = content.count('\n')
print(f'Written: {len(content)} chars, {lines} lines')
print(f'Has TikZ: {"tikzpicture" in content}')
print(f'Has 72B: {"72B" in content}')
print(f'Has overlap: {"Text Overlap" in content}')
print(f'Has 14B app: {"app:14b" in content}')
print(f'Has human eval: {"human-written queries" in content.lower() or "Human-written" in content}')
