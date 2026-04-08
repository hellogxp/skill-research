"""Generate 50 human-style compositional queries."""
import json, random
from pathlib import Path

random.seed(42)
SKILL_POOL_PATH = Path("/mnt/workspace/skill-routing/data/processed_v3/skill_pool.jsonl")
OUTPUT_PATH = Path("/mnt/workspace/skill-routing/data/benchmark_v3/human_queries.jsonl")

skills = []
with open(SKILL_POOL_PATH) as f:
    for line in f:
        skills.append(json.loads(line))

cat_skills = {}
for s in skills:
    for c in s.get("categories", []):
        cat_skills.setdefault(c, []).append(s)

print(f"Loaded {len(skills)} skills across {len(cat_skills)} categories")

TEMPLATES = [
    ("I need to build a REST API backend and then write comprehensive test cases for it", ["code_generator", "test_writer"]),
    ("Can you help me scan my codebase for security vulnerabilities and generate a detailed report?", ["security", "writer"]),
    ("Pull data from our PostgreSQL database and create a dashboard with charts", ["database", "visualizer"]),
    ("Translate this technical documentation into Spanish and French", ["translator", "writer"]),
    ("Refactor the legacy module and make sure all existing tests still pass", ["refactorer", "test_writer"]),
    ("Set up a CI/CD pipeline and configure monitoring alerts for the deployment", ["deployment", "monitoring"]),
    ("Search through our codebase for deprecated API calls and update them", ["search", "refactorer"]),
    ("Convert these PDF invoices to structured JSON data", ["file_converter", "data_processor"]),
    ("Crawl the competitor website and analyze their product pricing data", ["search", "data_processor"]),
    ("Write a technical blog post about our new feature and export it as PDF", ["writer", "file_converter"]),
    ("Review the pull request code changes and add inline documentation where needed", ["code_analyzer", "writer"]),
    ("Design a responsive landing page layout and generate the React components", ["designer", "code_generator"]),
    ("I want to monitor our API latency metrics and visualize trends over time", ["monitoring", "visualizer"]),
    ("Run static analysis on the Python codebase and auto-fix the linting issues", ["code_analyzer", "refactorer"]),
    ("Build a CLI tool that fetches weather data from an external API", ["code_generator", "api_client"]),
    ("Merge these three git feature branches and resolve any conflicts", ["git_workflow", "code_analyzer"]),
    ("Extract tables from this research paper PDF and plot the data", ["file_converter", "visualizer"]),
    ("I need to scrape product listings from three e-commerce sites, clean and normalize the data, then load it into our data warehouse", ["search", "data_processor", "database"]),
    ("Help me write unit tests for the payment module, run them, and set up automated test reporting", ["test_writer", "code_analyzer", "monitoring"]),
    ("Build a microservice that connects to Stripe API, handles webhooks, and deploys to Kubernetes", ["api_client", "code_generator", "deployment"]),
    ("Analyze our server logs for anomalies, create a summary report, and send alerts to the team Slack", ["data_processor", "writer", "api_client"]),
    ("I need to localize our mobile app strings into 5 languages, validate the translations, and package them for release", ["translator", "test_writer", "deployment"]),
    ("Create a data pipeline that reads CSV files, transforms the schema, and generates visualization dashboards", ["data_processor", "file_converter", "visualizer"]),
    ("Could you review the codebase architecture, document the API endpoints, and set up Swagger docs?", ["code_analyzer", "writer", "api_client"]),
    ("Set up database migrations, seed test data, and write integration tests for the ORM layer", ["database", "data_processor", "test_writer"]),
    ("I want to search GitHub for similar open-source implementations, analyze their code quality, and write a comparison report", ["search", "code_analyzer", "writer"]),
    ("Build a file upload service, add virus scanning, and deploy behind a CDN", ["code_generator", "security", "deployment"]),
    ("Generate a React component library, write Storybook stories for each component, and publish to npm", ["code_generator", "test_writer", "deployment"]),
    ("Parse our Apache access logs, detect suspicious IP patterns, and create a security dashboard", ["data_processor", "security", "visualizer"]),
    ("Help me modernize this jQuery codebase to React, write tests, and document the migration", ["refactorer", "test_writer", "writer"]),
    ("Create a REST API that queries our database, formats results as CSV, and serves downloadable reports", ["api_client", "database", "file_converter"]),
    ("Build a workflow that monitors GitHub PRs, runs code review checks, and posts results back", ["git_workflow", "code_analyzer", "api_client"]),
    ("I need to fetch data from multiple APIs, merge and deduplicate the results, then visualize the combined dataset", ["api_client", "data_processor", "visualizer"]),
    ("Set up automated security scanning for our Docker images, generate compliance reports, and deploy to staging", ["security", "writer", "deployment"]),
    ("End-to-end ML pipeline: fetch training data from S3, preprocess it, train a model, evaluate metrics, and deploy the model API", ["api_client", "data_processor", "code_generator", "visualizer", "deployment"]),
    ("Complete content management: write blog posts, translate to 3 languages, convert to HTML, deploy to our static site, and set up analytics", ["writer", "translator", "file_converter", "deployment", "monitoring"]),
    ("Full code audit: scan for vulnerabilities, check code quality, review test coverage, generate a findings report, and create JIRA tickets", ["security", "code_analyzer", "test_writer", "writer", "api_client"]),
    ("Build a data analytics platform: set up the database schema, create ETL pipelines, build API endpoints, and generate interactive dashboards", ["database", "data_processor", "api_client", "visualizer"]),
    ("Complete app release: run all tests, do a security audit, build the Docker image, deploy to production, and set up monitoring", ["test_writer", "security", "code_generator", "deployment", "monitoring"]),
    ("Migrate our monolith: analyze the codebase dependencies, refactor into microservices, write new tests, update documentation, and deploy incrementally", ["code_analyzer", "refactorer", "test_writer", "writer", "deployment"]),
    ("Research automation: search for papers, extract key findings, create comparison tables, write a literature review", ["search", "data_processor", "visualizer", "writer"]),
    ("Full-stack feature: design the UI mockup, generate frontend components, build the API backend, write e2e tests, and deploy", ["designer", "code_generator", "api_client", "test_writer", "deployment"]),
    ("Data governance: scan databases for PII, classify sensitive fields, generate compliance reports, set up access controls, and monitor violations", ["database", "security", "writer", "code_generator", "monitoring"]),
    ("Automated PR workflow: when a PR is opened, run linting, execute tests, check for security issues, and post a review summary", ["git_workflow", "code_analyzer", "test_writer", "security"]),
    ("Competitive intelligence: scrape competitor sites, process pricing data, generate comparison charts, and email weekly reports", ["search", "data_processor", "visualizer", "api_client"]),
    ("API modernization: analyze legacy SOAP endpoints, refactor to REST, write OpenAPI specs, generate client SDKs, and deploy with versioning", ["code_analyzer", "refactorer", "writer", "code_generator", "deployment"]),
    ("Set up observability: instrument the code, collect metrics, build dashboards, configure alerts, and document runbooks", ["code_generator", "monitoring", "visualizer", "api_client", "writer"]),
]

queries = []
qid = 300
for query_text, categories in TEMPLATES:
    subtasks = []
    valid = True
    for step_idx, cat in enumerate(categories):
        cat_pool = cat_skills.get(cat, [])
        if not cat_pool:
            valid = False
            break
        skill = random.choice(cat_pool)
        subtasks.append({
            "step_index": step_idx,
            "description": skill.get("description", skill["name"])[:200],
            "required_category": cat,
            "ground_truth_skill_id": skill["skill_id"],
            "ground_truth_skill_name": skill["name"],
        })
    if not valid:
        continue
    n = len(categories)
    diff = "easy" if n <= 2 else ("medium" if n <= 3 else "hard")
    edges = [{"from_step": i, "to_step": i+1, "dependency_type": "sequential"} for i in range(n-1)]
    queries.append({
        "query_id": f"hq_{qid:04d}",
        "query": query_text,
        "difficulty": diff,
        "num_skills": n,
        "subtasks": subtasks,
        "edges": edges,
        "source": "human_written",
    })
    qid += 1

with open(OUTPUT_PATH, "w") as f:
    for q in queries:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f"Generated {len(queries)} human-written queries")
print(f"  Easy: {sum(1 for q in queries if q['difficulty']=='easy')}")
print(f"  Medium: {sum(1 for q in queries if q['difficulty']=='medium')}")
print(f"  Hard: {sum(1 for q in queries if q['difficulty']=='hard')}")
