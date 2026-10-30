print("=== PYTHON SCRIPT INITIALIZED (CHEM & LIFE SCIENCES HYBRID BOT) ===", flush=True)

import os
import json
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from jobspy import scrape_jobs
import pandas as pd

CACHE_FILE = "seen_chem_jobs.json"

CHEM_GREENHOUSE_COMPANIES = [
    "abcellera"
]

CHEM_DIRECT_BOARDS = [
    {"name": "STEMCELL Technologies", "url": "https://www.stemcell.com/careers.html", "type": "html"},
    {"name": "Aspect Biosystems", "url": "https://aspectbiosystems.com/careers/", "type": "html"},
    {"name": "StarFish Medical", "url": "https://starfishmedical.com/careers/", "type": "html"},
    {"name": "Zymeworks", "url": "https://www.zymeworks.com/careers", "type": "html"},
    {"name": "fusion-pharmaceuticals", "url": "https://www.fusionpharma.com/careers", "type": "html"},
    {"name": "Microbiome Insights", "url": "https://microbiomeinsights.com/", "type": "html"}
]

CHEM_BASELINE_LOCATIONS = [
    "canada", "vancouver", "bc", "b.c.", "british columbia", "remote",
    "burnaby", "richmond", "surrey", "delta", "langley",
    "victoria", "kelowna", "calgary", "alberta", "ab", 
    "toronto", "ontario", "on", "gta", "waterloo", "ottawa",
    "montreal", "longueuil", "quebec", "qc"
]

CHEM_INTERN_KEYWORDS = ["intern", "internship", "coop", "co-op", "student", "placement", "fellow", "fellowship"]

CHEM_TARGET_FIELDS = [
    "bio", "chem", "lab", "laboratory", "research", "clinical", 
    "pharma", "genom", "molecular", "cell", "micro", "path", 
    "immun", "toxic", "scientific", "health", "environ", "assay", 
    "formulation", "medical", "neuro", "oncology", "drug", "medicine", 
    "therapeut", "epidemiol", "pharmacokinet", "pharmacodynam", "biostatist"
]

CHEM_EXCLUDED = [
    "software", "hardware", "mechanical", "electrical", "civil", "structural", 
    "wireless", "rf", "antenna", "aerospace", "drone", "robotics", "full stack", 
    "frontend", "backend", "devops", "nursing", "registered nurse", "physician", 
    "accountant", "sales", "senior", "manager", "director", "lead",
    "ai", "ml", "machine learning", "artificial intelligence", "computer science",
    "developer", "data engineer", "data scientist"
]

def is_chem_location_allowed(location_str):
    if not location_str:
        return True
    loc_lower = str(location_str).lower()
    return any(loc in loc_lower for loc in CHEM_BASELINE_LOCATIONS) or "ca" in loc_lower or "canada" in loc_lower

def is_chem_matching_role(title_str):
    if not title_str:
        return False
    title_lower = str(title_str).lower()
    
    if any(ex in title_lower for ex in CHEM_EXCLUDED):
        return False
        
    has_intern = any(kw in title_lower for kw in CHEM_INTERN_KEYWORDS)
    has_field = any(field in title_lower for field in CHEM_TARGET_FIELDS)
    
    return has_intern and has_field

def load_seen_jobs():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_jobs):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_jobs), f)

def send_discord_message(webhook_url, full_text):
    chunks = []
    if len(full_text) > 1900:
        chunks = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
    else:
        chunks = [full_text]

    for chunk in chunks:
        while True:
            res = requests.post(webhook_url, json={"content": chunk})
            if res.status_code == 429:
                retry_after = res.json().get("retry_after", 5)
                print(f"Discord rate-limited. Retrying after {retry_after} seconds...", flush=True)
                time.sleep(retry_after)
            else:
                res.raise_for_status()
                time.sleep(1)
                break

def fetch_direct_chem_employers():
    employer_jobs = []
    print("Checking direct Canadian life science employer boards...", flush=True)

    for company in CHEM_GREENHOUSE_COMPANIES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    location = job.get("location", {}).get("name", "")
                    if is_chem_matching_role(title) and is_chem_location_allowed(location):
                        employer_jobs.append({
                            "id": f"chem-gh-{company}-{job.get('id')}",
                            "title": title,
                            "company": company.capitalize(),
                            "location": location if location else "Canada",
                            "job_url": job.get("absolute_url"),
                            "source_type": "direct"
                        })
        except Exception as e:
            print(f"Error fetching Greenhouse board for {company}: {e}", flush=True)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for board in CHEM_DIRECT_BOARDS:
        name = board["name"]
        url = board["url"]
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    title = a_tag.get_text(strip=True)
                    job_url = a_tag['href']
                    if not job_url.startswith("http"):
                        job_url = urljoin(url, job_url)

                    if is_chem_matching_role(title):
                        employer_jobs.append({
                            "id": f"chem-dir-{name.lower().replace(' ', '-')}-{abs(hash(job_url))}",
                            "title": title,
                            "company": name,
                            "location": "Canada / Remote",
                            "job_url": job_url,
                            "source_type": "direct"
                        })
        except Exception as e:
            print(f"Error scraping direct board for {name}: {e}", flush=True)

    return employer_jobs

def main():
    print("=== HYBRID CANADIAN LIFE & PHARMA SCIENCES BOT INITIALIZED ===")
    
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK_URL environment variable is MISSING or EMPTY!", flush=True)
        return

    seen_ids = load_seen_jobs()
    all_new_jobs = []

    # 1. Pull from direct Canadian life science employer boards
    direct_jobs = fetch_direct_chem_employers()
    print(f"Found {len(direct_jobs)} role(s) from direct life science employer boards.", flush=True)
    for job in direct_jobs:
        if job["id"] not in seen_ids and job["job_url"]:
            all_new_jobs.append(job)
            seen_ids.add(job["id"])

    # 2. Pull from aggregators (LinkedIn, Indeed, etc.)
    print("Scraping LinkedIn and Indeed for Canadian life science co-ops...", flush=True)
    base_topics = [
        "Biochemistry", "Biologist", "Biotechnology", "Biomedical", "Bioinformatics",
        "Molecular Biology", "Genomics", "Immunology", "Microbiology", "Pharmacology",
        "Clinical Research", "Clinical Trials", "Analytical Chemistry", "Drug Discovery",
        "Oncology Research", "Medical Science", "Epidemiology", "Biochemist"
    ]
    modifiers = ["intern", "internship", "co-op", "coop"]

    search_queries = [f"{top} {mod}" for top in base_topics for mod in modifiers]
    
    search_targets = [
        {"location": "Canada", "country": "Canada"},
        {"location": "Vancouver, BC", "country": "Canada", "distance": 75},
        {"location": "Victoria, BC", "country": "Canada", "distance": 75},
        {"location": "Kelowna, BC", "country": "Canada", "distance": 75},
        {"location": "Calgary, AB", "country": "Canada", "distance": 75},
        {"location": "Toronto, ON", "country": "Canada", "distance": 75},
        {"location": "Ottawa, ON", "country": "Canada", "distance": 75},
        {"location": "Montreal, QC", "country": "Canada", "distance": 75}
    ]

    for target in search_targets:
        loc_str = target["location"]
        country_str = target["country"]

        for query in search_queries:
            try:
                scrape_args = {
                    "site_name": ["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                    "search_term": query,
                    "location": loc_str,
                    "country_indeed": country_str,
                    "hours_old": 72,
                    "results_wanted": 15
                }
                if "distance" in target:
                    scrape_args["distance"] = target["distance"]

                jobs = scrape_jobs(**scrape_args)
                if jobs is not None and not jobs.empty:
                    for _, row in jobs.iterrows():
                        job_id = str(row.get('id', row.get('job_url')))
                        title = str(row.get('title', ''))
                        company = row.get('company', 'Unknown Company')
                        location = str(row.get('location', loc_str))
                        description = str(row.get('description', '')).lower()
                        job_url = row.get('job_url', '')

                        if job_id in seen_ids or not job_id or job_id == 'nan':
                            continue
                        if "reposted" in title.lower() or "reposted" in description:
                            continue
                        if not is_chem_location_allowed(location):
                            continue
                        if is_chem_matching_role(title):
                            all_new_jobs.append({
                                "id": job_id,
                                "title": title,
                                "company": company,
                                "location": location,
                                "job_url": job_url,
                                "source_type": "aggregator"
                            })
                            seen_ids.add(job_id)
            except Exception as e:
                print(f"Error scraping query '{query}' in '{loc_str}': {e}")

    print(f"Total un-cached new life science jobs ready to send: {len(all_new_jobs)}", flush=True)
    if not all_new_jobs:
        print("No new unseen life science internships found today.", flush=True)
        save_seen_jobs(seen_ids)
        return

    # Separate into Direct vs Aggregator pools
    direct_pool = [j for j in all_new_jobs if j.get("source_type") == "direct"]
    agg_pool = [j for j in all_new_jobs if j.get("source_type") == "aggregator"]

    # Group and sort alphabetically by company name
    def group_and_sort(jobs_list):
        grouped = {}
        for job in jobs_list:
            comp = job['company']
            if comp not in grouped:
                grouped[comp] = []
            grouped[comp].append(job)
        return sorted(grouped.items(), key=lambda x: x[0].lower())

    sorted_direct_groups = group_and_sort(direct_pool)
    sorted_agg_groups = group_and_sort(agg_pool)

    message_lines = [f"**🚨 Found {len(all_new_jobs)} New Life Sciences Posting(s)!**\n"]

    if sorted_direct_groups:
        message_lines.append("📌 **--- DIRECT COMPANY WEBSITE POSTINGS ---**")
        for company, jobs_list in sorted_direct_groups:
            message_lines.append(f"🏢 **{company}**")
            for job in jobs_list:
                message_lines.append(f"  • **{job['title']}** ({job['location']})\n    🔗 <{job['job_url']}>")
        message_lines.append("")

    if sorted_agg_groups:
        message_lines.append("🌐 **--- LINKEDIN & RELATED JOB BOARD POSTINGS ---**")
        for company, jobs_list in sorted_agg_groups:
            message_lines.append(f"🏢 **{company}**")
            for job in jobs_list:
                message_lines.append(f"  • **{job['title']}** ({job['location']})\n    🔗 <{job['job_url']}>")
        message_lines.append("")

    full_text = "\n".join(message_lines)
    send_discord_message(webhook_url, full_text)

    save_seen_jobs(seen_ids)
    print(f"=== SCRAPING COMPLETE. Posted {len(all_new_jobs)} alerts to Discord. ===")

if __name__ == "__main__":
    main()
