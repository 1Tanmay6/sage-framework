import os
import re
import time
import yaml
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote
from datetime import datetime
from ddgs import DDGS
from urllib.parse import urlparse


BASE_DIR = "scraped_data"
METADATA_FILE = "./data/metadata/metadata.yaml"
TRUSTED_DOMAINS = [
    # Academic & Research
    "arxiv.org",
    "paperswithcode.com",
    "scholar.google.com",
    "aclweb.org",
    "neurips.cc",
    "icml.cc",
    "openreview.net",
    "jmlr.org",
    "ieee.org",
    "dl.acm.org",

    # Big Tech Research
    "research.google",
    "ai.googleblog.com",
    "openai.com",
    "deepmind.com",
    "anthropic.com",
    "microsoft.com",
    "meta.com",
    "aws.amazon.com",
    "nvidia.com",
    "ibm.com",

    # Engineering Blogs
    "engineering.fb.com",
    "netflixtechblog.com",
    "uber.com",
    "stripe.com",
    "airbnb.io",
    "linkedin.com",
    "dropbox.tech",
    "slack.engineering",
    "pinterest.engineering",
    "cloudflare.com",

    # AI/ML Platforms
    "towardsdatascience.com",
    "machinelearningmastery.com",
    "kaggle.com",
    "huggingface.co",
    "fast.ai",
    "distill.pub",
    "thegradient.pub",
    "deeplearning.ai",

    # Developer / CS Knowledge
    "stackoverflow.com",
    "github.com",
    "geeksforgeeks.org",
    "freecodecamp.org",
    "w3schools.com",
    "developer.mozilla.org",
    "cppreference.com",
    "python.org",

    # Tech News
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "arstechnica.com",
    "venturebeat.com",
    "zdnet.com",
    "infoq.com",

    # Finance
    "bloomberg.com",
    "reuters.com",
    "wsj.com",
    "ft.com",
    "investopedia.com",
    "morningstar.com",
    "sec.gov",
    "federalreserve.gov",
    "imf.org",
    "worldbank.org",

    # Data Sources
    "uci.edu",
    "data.gov",
    "registry.opendata.aws",

    # Universities
    "mit.edu",
    "stanford.edu",
    "cs.cmu.edu",
    "berkeley.edu",
    "ox.ac.uk",
    "cam.ac.uk",
    "harvard.edu",

    # AI Safety / Policy
    "alignmentforum.org",
    "futureoflife.org",
    "partnershiponai.org",

    # High-quality individual blogs
    "karpathy.ai",
    "colah.github.io",
    "jalammar.github.io",
    "ruder.io",
    "lilianweng.github.io",
    "sebastianraschka.com",
    "eugeneyan.com",
    "leimao.github.io",
    "timdettmers.com",
    "danluu.com",
    "jvns.ca",
    "paulgraham.com",
    "martinfowler.com",

    # Org-backed / curated blogs
    "blog.google",
    "ai.facebook.com",
    "deepmind.google",
    "engineering.atspotify.com",
    "doordash.engineering",
    "engineering.snap.com",
    "roblox.github.io",
    "discord.com",
    "highscalability.com",

    # Quant / finance blogs
    "quantocracy.com",
    "alphaarchitect.com",
    "quantstart.com"
]


# -----------------------------
# Utils
# -----------------------------
def sanitize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    return name.strip('_')


def is_trusted(url: str) -> bool:
    domain = urlparse(url).netloc
    return any(domain.endswith(td) for td in TRUSTED_DOMAINS)


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DataCollector/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


def create_storage_path(topic: str, url: str) -> str:
    domain = sanitize_name(urlparse(url).netloc)
    topic_clean = sanitize_name(topic)

    folder_path = os.path.join(BASE_DIR, topic_clean, domain)
    os.makedirs(folder_path, exist_ok=True)

    return folder_path


def generate_file_name(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12] + ".txt"


# -----------------------------
# YAML Metadata
# -----------------------------
def update_metadata(entry: dict):
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            data = yaml.safe_load(f) or []
    else:
        data = []

    data.append(entry)

    with open(METADATA_FILE, "w") as f:
        yaml.dump(data, f, sort_keys=False)


# -----------------------------
# Scraper
# -----------------------------
def scrape_and_store(url: str, query: str, topic: str, uid: str, difficulty: str, objective: str):
    if not is_trusted(url):
        print(f"[SKIP] Untrusted: {url}")
        return None

    try:
        html = fetch_page(url)
        text = extract_text(html)

        if len(text) < 300:  # basic quality filter
            print(f"[SKIP] Too short: {url}")
            return None

        folder_path = create_storage_path(topic, url)
        file_name = generate_file_name(url)
        file_path = os.path.join(folder_path, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        metadata_entry = {
            "id": uid,
            "query": query,
            "objective": objective,
            "topic": topic,
            "difficulty": difficulty,
            "url": url,
            "file_path": file_path,
            "domain": urlparse(url).netloc,
            "timestamp": datetime.utcnow().isoformat()
        }

        update_metadata(metadata_entry)

        print(f"[OK] {file_path}")
        return file_path

    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
        return None


# -----------------------------
# Google Search + Filter
# -----------------------------
def get_trusted_urls(query: str, num_results: int = 20):
    urls = set()

    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=num_results)

            for r in results:
                url = r.get("href")
                if not url:
                    continue

                domain = urlparse(url).netloc

                if any(domain.endswith(td) for td in TRUSTED_DOMAINS):
                    if "pdf" in url:
                        continue
                    if any(x in url for x in ["login", "signup", "careers"]):
                        continue

                    urls.add(url)

    except Exception as e:
        print(f"[SEARCH ERROR] {e}")

    return list(urls)

# -----------------------------
# Full Pipeline
# -----------------------------
def search_and_scrape(query: str, topic: str, uid_prefix: str, difficulty: str, objective: str, num_results: int = 20):
    urls = get_trusted_urls(query, num_results=num_results)

    print(f"[INFO] Trusted URLs found: {len(urls)}")

    stored_files = []

    for i, url in enumerate(urls):
        uid = f"{uid_prefix}_{i}"

        path = scrape_and_store(
            url=url,
            query=query,
            topic=topic,
            objective=objective,
            uid=uid,
            difficulty=difficulty
        )

        if path:
            stored_files.append(path)

    return stored_files


# -----------------------------
# Example Run
# -----------------------------
if __name__ == "__main__":
    AI_QUESTIONS = [
    {
        "Q": "Under what conditions does RAG fail even when relevant documents are retrieved?",
        "O": "Diagnose failure conditions in RAG despite relevant retrieval and identify detection signals"
    },
    {
        "Q": "How does increasing retrieval depth (k) impact hallucination versus noise trade-off?",
        "O": "Analyze trade-off between retrieval depth and hallucination/noise in RAG systems"
    },
    {
        "Q": "When does adding more context degrade LLM answer quality despite containing correct information?",
        "O": "Identify conditions where excessive context negatively impacts answer accuracy"
    },
    {
        "Q": "How can we formally define and detect context insufficiency in retrieval pipelines?",
        "O": "Define and detect insufficient context for answering queries"
    },
    {
        "Q": "How can a system select a minimal subset of context that is sufficient to answer a query?",
        "O": "Determine minimal sufficient context while eliminating redundancy"
    },
    {
        "Q": "What are systematic approaches to detect and resolve contradictions in retrieved documents?",
        "O": "Identify and handle conflicting information within retrieved context"
    },
    {
        "Q": "How does redundancy in retrieved chunks affect generation quality?",
        "O": "Analyze impact of redundant context on LLM output quality"
    },
    {
        "Q": "What are failure cases of dense retrieval models in technical domains?",
        "O": "Identify limitations of dense retrieval in domain-specific queries"
    },
    {
        "Q": "How does query reformulation improve retrieval performance?",
        "O": "Evaluate impact of query rewriting on retrieval accuracy"
    },
    {
        "Q": "How do LLMs combine information across multiple context chunks?",
        "O": "Analyze multi-hop reasoning behavior in LLMs"
    },
    {
        "Q": "What are common failure patterns in multi-hop question answering systems?",
        "O": "Identify recurring failure modes in multi-hop reasoning tasks"
    },
    {
        "Q": "How can we detect whether a query requires multi-hop reasoning?",
        "O": "Classify queries based on reasoning complexity"
    },
    {
        "Q": "What measurable signals indicate hallucination in LLM outputs?",
        "O": "Identify observable indicators of hallucinated responses"
    },
    {
        "Q": "How can grounding be enforced during answer generation?",
        "O": "Ensure all generated claims are supported by provided context"
    },
    {
        "Q": "How can we verify that every claim in an answer is supported by context?",
        "O": "Design methods to validate grounding of generated answers"
    },
    {
        "Q": "How do smaller models behave differently from large models under noisy context?",
        "O": "Compare robustness of small vs large models to noisy inputs"
    },
    {
        "Q": "When do LLMs ignore relevant context during generation?",
        "O": "Identify conditions where models fail to utilize useful context"
    },
    {
        "Q": "How does prompt structure influence context utilization?",
        "O": "Analyze effect of prompt design on context usage"
    },
    {
        "Q": "How can retrieval pipelines be optimized under token constraints?",
        "O": "Optimize context selection within limited token budgets"
    },
    {
        "Q": "What are practical methods to evaluate retriever performance objectively?",
        "O": "Define measurable metrics for retrieval quality"
    }
    ]

    ML_QUESTIONS =[
    {
        "Q": "How do bias and variance trade-offs manifest in modern deep learning models?",
        "O": "Analyze bias-variance behavior in deep neural networks and its practical implications"
    },
    {
        "Q": "What are failure modes of gradient descent in non-convex optimization?",
        "O": "Identify optimization challenges and convergence failures in non-convex settings"
    },
    {
        "Q": "How does overparameterization affect generalization in neural networks?",
        "O": "Examine relationship between model size and generalization performance"
    },
    {
        "Q": "What causes vanishing and exploding gradients, and how are they mitigated?",
        "O": "Diagnose gradient instability issues and evaluate mitigation techniques"
    },
    {
        "Q": "How do different regularization techniques impact model generalization?",
        "O": "Compare effectiveness of regularization methods in reducing overfitting"
    },
    {
        "Q": "What are limitations of cross-validation in large-scale ML systems?",
        "O": "Identify scalability and reliability issues in validation techniques"
    },
    {
        "Q": "How does data distribution shift impact model performance?",
        "O": "Analyze effects of distribution drift on model accuracy and robustness"
    },
    {
        "Q": "What are common sources of bias in training datasets?",
        "O": "Identify dataset biases and their impact on model outcomes"
    },
    {
        "Q": "How can we detect and handle label noise in supervised learning?",
        "O": "Design methods to identify and mitigate noisy labels"
    },
    {
        "Q": "What are failure cases of transfer learning in domain adaptation?",
        "O": "Analyze limitations of transfer learning across domains"
    },
    {
        "Q": "How does feature scaling impact optimization convergence?",
        "O": "Evaluate role of feature normalization in training stability"
    },
    {
        "Q": "What are limitations of tree-based models in high-dimensional spaces?",
        "O": "Identify scalability and performance issues in tree models"
    },
    {
        "Q": "How does class imbalance affect model training and evaluation?",
        "O": "Analyze impact of imbalanced datasets and mitigation strategies"
    },
    {
        "Q": "What are trade-offs between interpretability and performance in ML models?",
        "O": "Compare explainability versus accuracy in model selection"
    },
    {
        "Q": "How can uncertainty be quantified in machine learning predictions?",
        "O": "Evaluate methods for estimating predictive uncertainty"
    }
    ]
    
    CS_QUESTIONS = [
    {
        "Q": "How do different data structures impact algorithmic performance in real systems?",
        "O": "Analyze trade-offs between data structures in practical applications"
    },
    {
        "Q": "What are limitations of Big-O notation in real-world performance analysis?",
        "O": "Evaluate gaps between theoretical and practical complexity"
    },
    {
        "Q": "How does caching improve system performance and what are its trade-offs?",
        "O": "Examine benefits and drawbacks of caching strategies"
    },
    {
        "Q": "What are common causes of deadlocks in concurrent systems?",
        "O": "Identify conditions leading to deadlocks and prevention techniques"
    },
    {
        "Q": "How do different scheduling algorithms affect system throughput and latency?",
        "O": "Compare scheduling strategies in operating systems"
    },
    {
        "Q": "What are trade-offs between consistency, availability, and partition tolerance?",
        "O": "Analyze CAP theorem implications in distributed systems"
    },
    {
        "Q": "How do indexing strategies impact database query performance?",
        "O": "Evaluate effectiveness of indexing in optimizing queries"
    },
    {
        "Q": "What are failure modes in distributed systems and how are they handled?",
        "O": "Identify common distributed system failures and mitigation strategies"
    },
    {
        "Q": "How does memory management impact program performance?",
        "O": "Analyze role of memory allocation and garbage collection"
    },
    {
        "Q": "What are trade-offs between relational and NoSQL databases?",
        "O": "Compare database paradigms based on use cases"
    },
    {
        "Q": "How does network latency affect distributed application performance?",
        "O": "Evaluate impact of latency on system design"
    },
    {
        "Q": "What are limitations of multithreading in CPU-bound tasks?",
        "O": "Analyze scalability challenges in parallel execution"
    },
    {
        "Q": "How do load balancing strategies affect system reliability?",
        "O": "Examine effectiveness of load distribution techniques"
    },
    {
        "Q": "What are trade-offs between synchronous and asynchronous communication?",
        "O": "Compare communication models in system design"
    },
    {
        "Q": "How does fault tolerance improve system reliability?",
        "O": "Evaluate techniques for building resilient systems"
    }
    ]
    
    FIN_QUESTIONS = [
    {
        "Q": "How do interest rate changes impact equity valuations across different sectors?",
        "O": "Analyze relationship between interest rates and sector-wise stock valuation changes"
    },
    {
        "Q": "What are the limitations of traditional valuation models like DCF in volatile markets?",
        "O": "Evaluate weaknesses of discounted cash flow models under uncertainty"
    },
    {
        "Q": "How does market sentiment influence asset pricing beyond fundamentals?",
        "O": "Examine role of behavioral factors in financial markets"
    },
    {
        "Q": "What are the risks of overfitting in quantitative trading strategies?",
        "O": "Identify pitfalls in designing and validating trading models"
    },
    {
        "Q": "How do macroeconomic indicators affect portfolio allocation decisions?",
        "O": "Analyze impact of economic signals on investment strategies"
    },
    {
        "Q": "What are failure modes of risk management systems during financial crises?",
        "O": "Identify breakdown points in risk models under extreme conditions"
    },
    {
        "Q": "How does liquidity risk manifest in financial markets and how is it measured?",
        "O": "Evaluate methods to detect and quantify liquidity risk"
    },
    {
        "Q": "What are trade-offs between passive and active investment strategies?",
        "O": "Compare performance, cost, and risk between passive and active investing"
    }
    ]
    
    scrape_now = True
    questions = AI_QUESTIONS + ML_QUESTIONS + CS_QUESTIONS + FIN_QUESTIONS
    length = len()
    while True:

        files = search_and_scrape(
            query="what is a transformer?",
            topic="transformers",
            uid_prefix="run001",
            difficulty="medium",
            objective="asd",
            num_results=50
        )

        print(f"\nStored {len(files)} files.")